"""Operator live ASR/extraction/translation check; never submits claims or changes scores.

Uses HISTORY_AI_BASE_URL and HISTORY_AI_API_KEY from process environment.
Pass a consenting person's normalized mono 16-kHz WAV. No private text is printed.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import httpx

MODELS = {"yo": "NCAIR1/Yoruba-ASR", "ha": "NCAIR1/Hausa-ASR", "ig": "NCAIR1/Igbo-ASR", "en": "NCAIR1/NigerianAccentedEnglish"}
LLM = "NCAIR1/N-ATLaS"


async def main() -> int:
    """Warm real models and print only metadata needed to record acceptance evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--language", choices=MODELS, required=True)
    parser.add_argument("--target", choices=MODELS, required=True)
    args = parser.parse_args()
    base = os.environ.get("HISTORY_AI_BASE_URL", "").rstrip("/")
    key = os.environ.get("HISTORY_AI_API_KEY", "")
    if not base or len(key) < 32:
        parser.error("Set HISTORY_AI_BASE_URL and a 32+ character HISTORY_AI_API_KEY")
    if not base.startswith("https://") and not base.startswith(("http://127.0.0.1:", "http://localhost:")):
        parser.error("Use HTTPS except loopback development")
    if args.target == args.language:
        parser.error("Choose a different target to exercise actual translation")
    if not args.audio.is_file() or not 0 < args.audio.stat().st_size <= 5 * 1024 * 1024:
        parser.error("Use a WAV file up to 5 MB")
    started = time.monotonic()
    async with httpx.AsyncClient(base_url=base + "/", headers={"Authorization": f"Bearer {key}"}, timeout=900) as client:
        async def post(path: str, **kwargs: object) -> dict:
            response = await client.post(path, **kwargs)
            response.raise_for_status()
            return response.json()
        await post("warmup", json={"language": args.language})
        with args.audio.open("rb") as stream:
            asr = await post("asr", data={"language": args.language, "model": MODELS[args.language]}, files={"audio": ("audio.wav", stream, "audio/wav")})
        if asr.get("model") != MODELS[args.language] or not asr.get("text", "").strip():
            raise ValueError("Invalid live ASR response")
        draft = await post("extract", json={"model": LLM, "language": args.language, "text": asr["text"]})
        if draft.get("model") != LLM or not isinstance(draft.get("details", {}).get("claimed_completed"), bool):
            raise ValueError("Invalid live extraction response")
        translated = await post("translate", json={"model": LLM, "source": args.language, "target": args.target, "text": asr["text"]})
        if translated.get("model") != LLM or not translated.get("text", "").strip():
            raise ValueError("Invalid live translation response")
    print(json.dumps({"live_inference": True, "asr": asr["model"], "asr_revision": asr.get("revision"), "llm": LLM, "llm_revision": draft.get("revision"), "language": args.language, "target": args.target, "transcript_sha256": hashlib.sha256(asr["text"].encode()).hexdigest(), "transcript_characters": len(asr["text"]), "translation_characters": len(translated["text"]), "elapsed_seconds": round(time.monotonic()-started, 2), "claim_created": False, "quality_review": "pending"}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except (httpx.HTTPError, ValueError, OSError) as error:
        # Do not print provider errors, request bodies, audio paths or bearer headers.
        print(f"Live inference check failed ({type(error).__name__}); inspect sanitized gateway logs.", file=sys.stderr)
        raise SystemExit(1)
