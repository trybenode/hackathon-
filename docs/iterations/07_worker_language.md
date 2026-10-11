# Stage 1 — worker page language

Workers select English, Yoruba, Hausa or Igbo across dashboard, navigation, jobs, profile, records, notifications and dialogs. Switching language must retain form state, selected records and operation IDs. Shared sign-in localizes only when returning to a worker URL.

Reuse the root language provider and cookie, client dictionaries and existing components. Add a worker-copy dictionary with English fallback and candidate translations. Localize presentation only: keep enum values, API payloads, authorization and state transitions unchanged. Dates and currency use locale-aware formatting. No migration or account changes.

Sequence: inventory visible strings; dictionary and preference updates; worker components and sign-in; checks and coverage audit. Dependencies: native reviewers and Figma/mobile comparison. Rollout retains the visible pilot notice; untranslated/provider content remains English or its original language. Verify type/lint, state-preserving switching and existing flows. English remains the rollback/default.
