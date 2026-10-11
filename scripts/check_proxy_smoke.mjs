/** Exercise the actual built Next.js API bridge against a local fake upstream; no real accounts/providers. */
import assert from "node:assert/strict";
import http from "node:http";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { once } from "node:events";

const serverFile = new URL("../frontend/.next/standalone/server.js", import.meta.url);
assert(existsSync(serverFile), "Build the standalone frontend first.");
const secret = "proxy-smoke-key-".repeat(4);
let captured;
let calls = 0;
const api = http.createServer(async (request, response) => {
  calls++;
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  captured = { headers: request.headers, url: request.url, body: Buffer.concat(chunks).toString() };
  if (request.url === "/api/v1/health/ready") {
    response.setHeader("Content-Type", "application/json"); response.end('{"status":"ready"}'); return;
  }
  if (request.url === "/api/v1/audio") {
    response.setHeader("Content-Type", "audio/mpeg"); response.end(Buffer.from("ID3audio")); return;
  }
  response.setHeader("Set-Cookie", ["guarantor_session=sample; HttpOnly; Secure; SameSite=Lax; Path=/", "history_recipient=scoped; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/history-confirmations"]);
  response.setHeader("Content-Type", "application/json");
  response.statusCode = request.url === "/api/v1/reject" ? 409 : 200;
  response.end(JSON.stringify({ ok: true }));
});
await new Promise(resolve => api.listen(0, "127.0.0.1", resolve));
const apiPort = api.address().port;
// Reserve and release an unused frontend port before spawning Next.js.
const reservation = http.createServer();
await new Promise(resolve => reservation.listen(0, "127.0.0.1", resolve));
const webPort = reservation.address().port;
await new Promise(resolve => reservation.close(resolve));
let logs = "";
const child = spawn(process.execPath, [serverFile.pathname], { env: { ...process.env, HOSTNAME: "127.0.0.1", PORT: String(webPort), API_PROXY_ORIGIN: `http://127.0.0.1:${apiPort}`, INTERNAL_PROXY_SECRET: secret, PROXY_TRUSTED_HOPS: "1" }, stdio: ["ignore", "pipe", "pipe"] });
child.stdout.on("data", data => { logs += data.toString(); });
child.stderr.on("data", data => { logs += data.toString(); });
const origin = `http://127.0.0.1:${webPort}`;
try {
  let ready = false;
  for (let attempt = 0; attempt < 80; attempt++) {
    try { if ((await fetch(`${origin}/health`)).ok) { ready = true; break; } } catch { /* Startup retry. */ }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert(ready, "Standalone frontend did not become ready.");
  const result = await fetch(`${origin}/api/v1/probe?page=2`, { method: "POST", headers: { Cookie: "guarantor_session=existing", Origin: "https://app.example.com", "Content-Type": "application/json", "Idempotency-Key": "operation-123", "X-Forwarded-For": "203.0.113.9, 198.51.100.2", "X-Trust-Proxy-Key": "forged", "X-Trust-Client-IP": "203.0.113.9" }, body: '{"entered":"keep me"}' });
  assert.equal(result.status, 200);
  assert.equal(result.headers.getSetCookie().length, 2);
  assert.equal(result.headers.get("cache-control"), "no-store, private");
  assert.equal(captured.url, "/api/v1/probe?page=2");
  assert.equal(captured.body, '{"entered":"keep me"}');
  assert.equal(captured.headers.cookie, "guarantor_session=existing");
  assert.equal(captured.headers["idempotency-key"], "operation-123");
  assert.equal(captured.headers.origin, "https://app.example.com");
  assert.equal(captured.headers["x-trust-proxy-key"], secret);
  assert.equal(captured.headers["x-trust-client-ip"], "198.51.100.2");
  assert.equal((await fetch(`${origin}/api/v1/reject`)).status, 409);
  const audio = await fetch(`${origin}/api/v1/audio`);
  assert.equal(audio.headers.get("content-type"), "audio/mpeg");
  assert.equal(await audio.text(), "ID3audio");
  const before = calls;
  assert.equal((await fetch(`${origin}/api/v1/upload`, { method: "POST", body: Buffer.alloc(12*1024*1024+1) })).status, 413);
  assert.equal(calls, before);
  const token = "private-test-bearer-token-1234567890";
  await fetch(`${origin}/api/v1/history-confirmations/${token}`);
  assert(!logs.includes(token), "Bearer path appeared in frontend logs.");
  await new Promise(resolve => api.close(resolve));
  const unavailable = await fetch(`${origin}/api/v1/probe`);
  assert.equal(unavailable.status, 502);
  assert.equal((await unavailable.json()).code, "UPSTREAM_UNAVAILABLE");
  console.log("Production proxy smoke passed: cookies, idempotency, origin, authenticated IP, status/audio, upload limit, unavailable upstream and token-safe logs.");
} finally {
  const exited = once(child, "exit");
  child.kill("SIGTERM");
  await exited;
  if (api.listening) await new Promise(resolve => api.close(resolve));
}
