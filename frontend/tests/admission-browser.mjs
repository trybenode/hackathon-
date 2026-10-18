/** Browser contract checks with isolated API fixtures, never production accounts/providers. */
import { createRequire } from "node:module";
import assert from "node:assert/strict";
const { chromium } = createRequire(import.meta.url)("playwright");
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || undefined,
    headless: true,
  });
  const context = await browser.newContext({
    viewport: { width: 360, height: 800 },
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  let batch = null,
    prepared = 0,
    lost = true;
  let operation;
  const json = (route, data, status = 200) =>
    route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(data),
    });
  const empty = { items: [], total: 0, page: 1, size: 20, pages: 0 };
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    if (path.endsWith("/auth/me")) return json(route, { is_demo: false });
    if (path.endsWith("/me/verification-capabilities"))
      return json(route, {
        unsigned_imports_enabled: true,
        additional_verification_enabled: true,
        csv_max_bytes: 2097152,
        document_max_bytes: 3145728,
        max_rows: 1000,
      });
    if (path.endsWith("/me/additional-verification"))
      return json(route, {
        action: "manual_review",
        requirements: [],
        reason_codes: ["INSUFFICIENT_VERIFIED_HISTORY"],
        case_id: null,
        case_version: null,
        policy_version: 1,
        evidence_revision: "a".repeat(64),
        restrictions: null,
        expires_at: null,
        next_steps: ["submit_review"],
      });
    if (path.endsWith("/me/record"))
      return json(route, { starting_rating: null });
    if (path.includes("/platform-grants")) return json(route, empty);
    if (path.endsWith("/history-imports") && method === "POST") {
      prepared++;
      operation = request.headers()["idempotency-key"];
      batch = {
        id: "11111111-1111-4111-8111-111111111111",
        version: 1,
        source_name: "Customer invoices",
        state: "preparing",
        row_count: 1,
        document_present: false,
        expires_at: "2026-11-16T00:00:00Z",
        last_reason: null,
        rows: [{ job_id: "one", date: "2025-01-01", status: "completed" }],
        ownership_label: "History unverified",
      };
      if (lost) {
        lost = false;
        return route.abort("failed");
      }
      return json(route, batch, 201);
    }
    if (path.includes("/history-imports/operations/")) {
      assert.equal(path.split("/").at(-1), operation);
      return json(route, batch);
    }
    if (path.endsWith("/document") && method === "PUT") {
      batch = { ...batch, document_present: true, version: 2 };
      return json(route, batch);
    }
    if (path.endsWith("/submit")) {
      batch = { ...batch, state: "submitted", version: 3 };
      return json(route, batch);
    }
    if (path.endsWith("/history-imports"))
      return json(route, {
        ...empty,
        items: batch?.state === "submitted" ? [{ ...batch, rows: [] }] : [],
        total: batch?.state === "submitted" ? 1 : 0,
        pages: 1,
      });
    if (path.includes("/history-imports/")) return json(route, batch);
    return json(route, {});
  });
  await page.goto(
    `${process.env.BROWSER_BASE_URL || "http://localhost:3199"}/worker/profile/record/verification`,
  );
  await page.getByLabel("Source of this history").fill("Customer invoices");
  const uploads = page.locator("input[type=file]");
  await uploads.nth(0).setInputFiles({
    name: "jobs.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "worker_id,job_id,date,status\nworker,one,2025-01-01,completed\n",
    ),
  });
  await uploads.nth(1).setInputFiles({
    name: "evidence.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4\nfixture\n%%EOF"),
  });
  await page.getByRole("checkbox").check();
  const language = page.getByRole("combobox").first();
  for (const lang of ["yo", "ha", "ig", "en"]) {
    await language.selectOption(lang);
    assert.equal(
      await page
        .locator("input[type=text],input:not([type])")
        .first()
        .inputValue(),
      "Customer invoices",
    );
    assert.equal(
      await uploads.nth(0).evaluate((el) => el.files[0].name),
      "jobs.csv",
    );
    assert.equal(await page.getByRole("checkbox").isChecked(), true);
  }
  await page
    .getByRole("button", { name: "Prepare preview", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Check submission status", exact: true })
    .waitFor();
  assert.equal(
    await page
      .getByRole("button", { name: "Prepare preview", exact: true })
      .isDisabled(),
    true,
  );
  await language.selectOption("yo");
  await language.selectOption("en");
  await page
    .getByRole("button", { name: "Check submission status", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Submit for ownership review", exact: true })
    .waitFor();
  assert.equal(prepared, 1, "reconciliation must not repeat creation");
  await page
    .getByRole("button", { name: "Submit for ownership review", exact: true })
    .click();
  await page
    .getByRole("status")
    .filter({ hasText: "Submitted for ownership review" })
    .waitFor();
  assert.equal(batch.state, "submitted");
  if (process.env.BROWSER_SCREENSHOT)
    await page.screenshot({
      path: process.env.BROWSER_SCREENSHOT,
      fullPage: true,
    });
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
    "worker screen fits 360px",
  );
  assert.deepEqual(errors, []);
  console.log(
    "PASS: four languages preserve files, inputs and consent; uncertain creation reconciles without duplicate POST; preview + submit; 360px layout; no runtime errors.",
  );

  const review = await context.newPage();
  review.on("pageerror", (e) => errors.push(e.message));
  await review.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/review/access"))
      return json(route, {
        roles: [{ scope: "operations", environment: "production" }],
      });
    if (path.endsWith("/review/onboarding/first_party"))
      return json(route, empty);
    if (path.endsWith("/review/imports"))
      return json(route, {
        ...empty,
        items: [{ ...batch, rows: [] }],
        total: 1,
        pages: 1,
      });
    if (path.endsWith("/decision")) {
      batch = { ...batch, state: "approved", version: 4 };
      return json(route, batch);
    }
    if (path.includes("/review/imports/"))
      return json(route, {
        batch: {
          ...batch,
          state: batch.state === "approved" ? "approved" : "submitted",
        },
        worker: {
          id: "fixture-worker",
          name: "Fixture Worker",
          email: "fixture@example.com",
          profile_phone: "",
          identity: "verified",
          liveness: "verified",
        },
      });
    return json(route, {});
  });
  await review.goto(
    `${process.env.BROWSER_BASE_URL || "http://localhost:3199"}/review`,
  );
  await review
    .getByRole("button", { name: "Ownership evidence", exact: true })
    .click();
  await review
    .getByRole("button", {
      name: "Inspect identity association and rows",
      exact: true,
    })
    .click();
  await review
    .getByLabel("Reason shown to the worker")
    .fill("Reviewed the worker association with supplied references.");
  await review
    .getByLabel(
      "Private ownership association checked (name alone is insufficient)",
    )
    .fill("Profile and supporting account references match verified identity.");
  await review.getByRole("button", { name: "approve", exact: true }).click();
  await review.waitForFunction(() =>
    document.body.textContent.includes("approved"),
  );
  assert.equal(batch.state, "approved");
  assert.equal(
    await review.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
    "review screen fits 360px",
  );
  assert.deepEqual(errors, []);
  console.log(
    "PASS: explicit operations role, private identity association and ownership decision UI at 360px.",
  );
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
