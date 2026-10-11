# Iteration 2 — core page localization

## Acceptance and repository impact
Workers and recipients independently choose en/yo/ha/ig without changing existing URLs or bearer links. Translate recording/history/confirmation/clarification controls, record/share summaries, consent, loading and error states. Use typed dictionaries and a server-selected dictionary delivered through a small client context. A non-sensitive cookie stores locale; the root HTML lang follows it. Existing unsupported pages are not claimed as translated.

## Interfaces and execution
Add Language/dictionary types and language switcher to shared layout; core features consume the same translator. Preserve originals of all backend/user text. Do not use AI for consent or verification labels. Numeric/date display uses explicit locale and Africa/Lagos. English remains the explicit fallback for untranslated dynamic evidence. Source-language reviewers must approve candidate Yoruba/Hausa/Igbo copies and future spoken assets before release. No invented reviewer signoff or generated voice prompts.

## Dependencies, tests and rollout
Read installed Next.js server/client and internationalization guides before editing. Check dictionary key coverage, glyphs/diacritics, language switching, no shared-link redirect, root lang, long-text layout, type/lint/build. Public token routes remain uncached/noindex. Figma 360px references and human comprehension testing are gates. Ship language support as pilot translations pending review; do not promise independent non-reader access without tested audio guidance. Failure falls back visibly, never silently mistranslates consent. Rollback selects English while preserving canonical content.
