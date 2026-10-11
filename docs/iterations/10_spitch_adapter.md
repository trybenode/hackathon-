# Spitch adapter — detailed implementation plan

1. User story and acceptance: an authorized thread participant requests Listen for a ready translation; the configured language voice reads the exact text. Missing configuration exposes unavailable audio; provider failures retain the translation and permit existing safe retries.
2. Repository impact: extend speech_provider and settings; reuse history_speech queue, scoped routes and private playback. No frontend workflow, authentication or scoring changes.
3. Contracts and persistence: select gateway or spitch through configuration. Spitch POST https://api.spitch.app/v1/speech uses bearer authentication and text/language/voice/format=mp3. Bound audio responses and validate MP3. Include provider, configured model/version and voice in fingerprints; version is a local configuration revision, not a claim of an upstream model version. No migration or public API changes.
4. Dependencies: Software supplies API credentials; ML and native-language reviewers validate the selected voice per language. No external calls using real credentials during automated checks. Existing UI/Figma gates remain.
5. Sequence: record plan; add provider selection and explicit voice mapping; adapt queue fingerprint; add mocked transport and regression tests; document setup and validation.
6. Verification: exact text and language, authentication, missing voice, disabled provider, invalid audio, bounded response, provider failure and voice-change invalidation; rerun speech and history API regressions.
7. Rollout: speech stays disabled by default; configure only reviewed languages. Development trials may evaluate candidate voices without production claims. Disable speech or restore gateway selection to roll back. No paid requests or secret changes performed by this implementation.

Sources: https://docs.spitch.app/features/speech and https://docs.spitch.app/concepts/voices (checked 2026-10-10).
