"""Official-model gateway adapter; inference never supplies verification authority."""
import re
import asyncio
from pathlib import Path
from typing import Any
import httpx
from app.core.config import get_settings
from app.schemas.history import ClaimDetails, Language
from app.services.feature_common import FeatureError

ASR_MODELS = {"yo": "NCAIR1/Yoruba-ASR", "ha": "NCAIR1/Hausa-ASR", "ig": "NCAIR1/Igbo-ASR", "en": "NCAIR1/NigerianAccentedEnglish"}
LLM_MODEL = "NCAIR1/N-ATLaS"


class HistoryModelGateway:
    """Call only configured official-model services; no hidden alternate-model fallback."""
    def __init__(self) -> None:
        cfg = get_settings()
        if not cfg.history_ai_enabled or not cfg.history_ai_base_url:
            raise FeatureError(503, "MODEL_UNAVAILABLE", "Language processing is not configured. Use manual entry.")
        if cfg.environment != "development" and not cfg.history_ai_base_url.startswith("https://"):
            raise FeatureError(503, "MODEL_TRANSPORT_INVALID", "Secure language processing is required.")
        if cfg.environment != "development" and not cfg.history_ai_api_key:
            raise FeatureError(503, "MODEL_UNAVAILABLE", "Authenticated language processing is required.")
        self.translation_revision: str | None = None
        self.extraction_revision: str | None = None
        self.base = cfg.history_ai_base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {cfg.history_ai_api_key}"}

    async def _call(self, path: str, **kwargs: Any) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=90) as client:
            try:
                response = await client.post(f"{self.base}/{path}", headers=self.headers, **kwargs)
                if response.status_code != 200:
                    raise FeatureError(503, "MODEL_UNAVAILABLE", "Language processing failed. Original inputs are preserved.")
                body = response.json()
                if not isinstance(body, dict):
                    raise ValueError("Invalid gateway response")
                return body
            except (httpx.HTTPError, ValueError) as error:
                raise FeatureError(503, "MODEL_UNAVAILABLE", "Language processing failed. Original inputs are preserved.") from error

    async def transcribe(self, audio: Path, language: Language) -> tuple[str, dict]:
        """Transcribe temporary normalized audio with the selected official ASR."""
        data = await asyncio.to_thread(audio.read_bytes)
        body = await self._call("asr", data={"language": language, "model": ASR_MODELS[language]}, files={"audio": ("audio.wav", data, "audio/wav")})
        text = body.get("text")
        if body.get("model") != ASR_MODELS[language] or not isinstance(text, str) or not text.strip() or len(text) > 12000:
            raise FeatureError(422, "MODEL_OUTPUT_INVALID", "The transcript could not be validated.")
        return text, {"asr": body["model"], "revision": str(body.get("revision", "unspecified")), "prompt_version": "history-v1"}

    async def extract(self, transcript: str, language: Language) -> ClaimDetails:
        """Propose editable facts only; reject extra fields and unsupported model identities."""
        body = await self._call("extract", json={"text": transcript, "language": language, "model": LLM_MODEL})
        if body.get("model") != LLM_MODEL:
            raise FeatureError(422, "MODEL_OUTPUT_INVALID", "Unsupported extraction model.")
        try:
            proposed = body.get("details")
            if not isinstance(proposed, dict) or not isinstance(proposed.get("claimed_completed"), bool):
                raise ValueError("Explicit draft completion claim required")
            details = ClaimDetails.model_validate(proposed)
        except ValueError as error:
            raise FeatureError(422, "MODEL_OUTPUT_INVALID", "The proposed work details need manual entry.") from error
        self.extraction_revision = str(body["revision"])[:160] if body.get("revision") else None
        details.language = language
        return details

    async def translate(self, text: str, source: Language, target: Language) -> str:
        """Return a derivative translation, preserving numeric and identifier tokens."""
        if source == target:
            return text
        body = await self._call("translate", json={"text": text, "source": source, "target": target, "model": LLM_MODEL})
        self.translation_revision = str(body["revision"])[:160] if body.get("revision") else None
        translated = body.get("text")
        if body.get("model") != LLM_MODEL or not isinstance(translated, str) or not translated.strip() or len(translated) > 8000:
            raise FeatureError(422, "TRANSLATION_INVALID", "Translation could not be validated. Use the original.")
        # Numbers, phone/contact strings, URLs and UUIDs must not be changed or dropped.
        tokens = re.findall(r"https?://\S+|[\w.+-]+@[\w.-]+\.[a-zA-Z]+|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}|[₦$£€]?\+?\d[\d.,:/-]*", text)
        if any(translated.count(token) < text.count(token) for token in tokens):
            raise FeatureError(422, "TRANSLATION_VALUES_CHANGED", "Translation changed a factual value. Use the original.")
        return translated
