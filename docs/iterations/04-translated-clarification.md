# Iteration 4 — private job clarification and derivative translation

## Stories and acceptance
Only the owner and attributed recipient discuss a particular immutable request snapshot. Both parties see original messages and may request a machine-labelled translation in their chosen language. Messages cannot confirm work, change terms, open formal disputes or alter scores. Revocation, expiry, archive, claim edits and changes of hiring account block recipient access on every operation.

## Data/contracts and implementation
Add immutable HistoryMessage(request, role, optional user actor, operation UUID, source language, text) and MessageTranslation(message, target, status, derivative text, model/version, error). Unique request/role/operation keys reject changed retries. Lists use standard 20/max100 pagination. Worker routes are under /me/history-claims/{id}/messages; recipient routes under /history-confirmations/{token}/messages. Translations are separate POST resources and never replace originals. Preserve contact/date/amount/UUID/URL tokens; remaining semantic accuracy, especially negation and code-switching, needs real language review. Failed processing returns failed metadata and keeps the original; no other-model fallback. Preview translation of the request description uses the same model adapter and authorization.

## Dependencies, tests and rollout
N-ATLAS gateway access and representative language-pair evaluation are ML/Software dependencies. UI provides a paginated asynchronous thread and explicit source/translation labels, preserved inputs and stable retry keys. Add a LiveChat protocol with a test-only stub and no runtime live-chat integration. Test cross-request/worker leakage, contact/account auth, revoked guest sessions, duplicate writes, translation-value preservation, failed gateway behavior and score isolation. Feature disable/English fallback does not remove originals. No live presence/delivery claim or native-language signoff without evidence.
