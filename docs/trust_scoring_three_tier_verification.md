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
the top tier), never a real trust band. Clearly labeled "Building History (imported)"
on the worker's profile. This is the tier that's fully built and demoable.

## Tier 2 — Manually verified (short-term, not scalable)

For cases where it's worth the effort — e.g. a driver with real history on both Uber and
Bolt wanting to move into higher-paying work — a person on our team can review the
imported data by hand and upgrade it from unverified to verified. This works, but only
at small volume. It's a plausible short-term answer, not a scaling strategy.

## Tier 3 — Partner-verified (long-term, the real fix)

We partner directly with source platforms so their data arrives with a verifiable
signature — no human review needed. Precedent exists (e.g. Bolt has done this kind of
integration with other services). This is the actual long-term solution, but it depends
on outside companies' cooperation and isn't something we can build this week.

## What we're actually building vs. presenting

We're building Tier 1 fully. We are NOT building Tier 2's review workflow or Tier
3's partner integration — but we document a stub API endpoint representing where Tier 3
would plug in, so the pitch has something concrete to point at.

**The reason this matters for the pitch specifically:** if a judge asks "how do you plan
to scale past manual verification," the answer is this document, not something worked
out on the spot.
