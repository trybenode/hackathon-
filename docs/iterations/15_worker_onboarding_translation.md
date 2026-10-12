# Worker onboarding translation

Scope confirmed by user: worker onboarding only, excluding developer pages.

User journey: English/Yoruba/Hausa/Igbo selection remains available through
introduction, signup, identity, liveness and guarantor/link preview screens.
Language changes must preserve names, codes, uploaded files, form values, camera
stage and navigation. Candidate translations require native review; unknown
provider errors fall back to English.

Reuse: existing LanguageProvider/cookie, useWorkerCopy, worker dictionaries and
shared verification components. Add onboarding dictionary rows and widen the
worker-only presentation boundary to /join and /join/*; other shared consumers
remain in English. Translate relationship labels without changing option values.
No API, authentication, scoring, consent state or migration changes.

Sequence: inspect incoming screens; translate fixed copy, labels and displayed
errors; add selectors; extend dictionary and regression coverage; typecheck/lint.
Dependencies: native review and Figma/device/browser checks remain outstanding.
Rollback: revert presentation files and dictionary extension, with no data changes.
Acceptance: locale copy/fallback, stable JSX keys/wire values, camera logic and
form handlers unchanged; manual mobile/browser language-switch testing required.

Validation: frontend typecheck, targeted ESLint and expanded test:language passed.
The language regression includes onboarding phrases, English fallback and JSX
identity/domain-attribute boundaries. Scoped whitespace checks passed.
No browser/device or native-language acceptance claimed. No commit/push performed.
