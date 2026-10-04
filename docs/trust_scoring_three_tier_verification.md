# Three-Tier Verification Model

How the platform handles trust for history that comes from outside our own system —
written so whoever presents this can explain it without notes.

## The problem

Most outside platforms don't have an API for us to pull verified worker history
automatically. The realistic fallback is a worker uploading their own exported file,
which they could edit before handing it over. We can't solve that tampering risk with
code in the time we have. So instead of pretending we've solved verification, we
structured trust into three explicit levels.

## Tier 1 — Unverified (built for the demo)

A worker uploads a CSV or similar file from another platform. We take it at face value,
but treat it as low-trust: it only produces a `starting_rating` (capped, never reaching
the top tier), never a real `trust_score`. Clearly labeled "Building History (imported)"
on the worker's profile. This is the tier that's fully built and demoable.

## Tier 2 — Manually verified (short-term, not scalable)

For cases where it's worth the effort — e.g. a driver with real history on both Uber and
Bolt wanting to move into higher-paying work — a person on our team can review the
imported data by hand and upgrade it from unverified to verified. This works, but only
at small volume. It's a plausible short-term answer, not a scaling strategy.

## Tier 2a — Customer-confirmed sample (a lighter alternative to full manual review)

Raised by the team as an option for when a full platform partnership isn't possible, but
manual review by our own staff doesn't scale either. The idea: let the *customer* who
actually hired the worker do the confirming, instead of a person on our team reviewing
every imported job by hand.

**How it would work:**

1. From a worker's imported history, pick a small sample of jobs — around 5 — to send
   for confirmation. Deliberately mix in jobs the import marked as something other than
   completed (cancelled, no-show, etc.), not only the clean ones.
2. Give the worker a link covering that sample. The worker shares it with the relevant
   customers.
3. For each job in the sample, the customer is shown what the import already said — the
   date and the status — and confirms whether that's accurate. They also select which
   platform the job was actually done on.
4. The customer isn't asked to rate the worker or supply new information. They're only
   confirming facts we already have from the import, using the exact same minimal
   fields the import schema already expects (`date`, `status`) — no new data collected.

**Why mixing in non-completed jobs matters:** if every job sent for confirmation is
already marked "completed," a customer (or a worker colluding with a fake "customer")
could just approve everything without really checking. By deliberately including a few
jobs that weren't marked completed, the check becomes meaningful: does the customer's
answer **match what the import already said**, not just "did they say yes." A mismatch —
e.g. a job imported as cancelled that a "customer" confirms as completed — is a concrete
signal that something's wrong, either carelessness or an attempt to game the system.

**Status:** this is a promising idea raised in team discussion, not yet a committed
plan. Before building it, we'd need to decide: does this apply to every imported job a
worker has, or only a sample (recommended, since confirming hundreds of jobs one by one
isn't realistic)? Does it apply retroactively to old imported history, or only to new
jobs going forward? These aren't resolved yet.

## Tier 3 — Partner-verified (long-term, the real fix)

We partner directly with source platforms so their data arrives with a verifiable
signature — no human review needed. Precedent exists (e.g. Bolt has done this kind of
integration with other services). This is the actual long-term solution, but it depends
on outside companies' cooperation and isn't something we can build this week.

## What we're actually building vs. presenting

We're building Tier 1 fully. We are **not** building Tier 2's manual review workflow,
Tier 2a's customer-confirmation flow, or Tier 3's partner integration — but we document
a stub API endpoint representing where Tier 3 would plug in, so the pitch has something
concrete to point at. Tier 2a is included here as a documented idea worth mentioning if
asked how we'd scale verification, even though it isn't built or fully specified yet.

**The reason this matters for the pitch specifically:** if a judge asks "how do you plan
to scale past manual verification," the answer is this document, not something worked
out on the spot.
