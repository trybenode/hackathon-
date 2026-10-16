"""Gateway contract regressions with instrumented pipelines; these are not live model benchmarks."""
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

spec = importlib.util.spec_from_file_location("natlas_gateway", Path(__file__).resolve().parents[2] / "scripts/history_model_gateway.py")
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)
KEY = "test-key-" * 8


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("HISTORY_GATEWAY_KEY", KEY)
    gateway.loaded_models.clear()
    with TestClient(gateway.app) as client:
        client.headers["Authorization"] = f"Bearer {KEY}"
        yield client


def pipeline():
    return SimpleNamespace(model=SimpleNamespace(config=SimpleNamespace(_commit_hash="test-revision")))


def test_auth_and_readiness(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 503
    assert client.post("/translate", headers={"Authorization": "Bearer wrong"}, json={"text": "hello", "model": gateway.LLM, "source": "en", "target": "yo"}).status_code == 401
    gateway.loaded_models.update({gateway.LLM: "rev", gateway.MODELS["yo"]: "rev"})
    assert client.get("/health/ready?language=yo").json()["status"] == "ready"
    assert client.get("/health/ready?language=en").status_code == 503


def test_short_key_never_authenticates(client, monkeypatch):
    monkeypatch.setenv("HISTORY_GATEWAY_KEY", "short")
    assert client.get("/health/ready", headers={"Authorization": "Bearer short"}).status_code == 503


@pytest.mark.parametrize("output", ['{"text":"Bawo"}', [{"role": "assistant", "content": '```json\n{"text":"Bawo"}\n```'}]])
def test_inference_parses_generated_content_only(monkeypatch, output):
    seen = {}
    def fake(messages, **kwargs):
        seen.update(kwargs)
        return [{"generated_text": output}]
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            assert kwargs["date_string"]
            return "formatted prompt"
        def __call__(self, prompt, **kwargs):
            return {"input_ids": [1, 2, 3]}
    fake.tokenizer = Tokenizer()
    monkeypatch.setattr(gateway, "llm_pipeline", lambda: fake)
    assert gateway.infer_json("translate", "private input") == {"text": "Bawo"}
    assert seen["return_full_text"] is False


def test_invalid_extraction_does_not_invent_completion(client, monkeypatch):
    monkeypatch.setattr(gateway, "infer_json", lambda *args: {"work_type": "Plumbing", "description": "Fixed tap", "language": "en"})
    result = client.post("/extract", json={"text": "Fixed tap", "model": gateway.LLM, "language": "en"})
    assert result.status_code == 422


def test_valid_draft_and_translation_keep_metadata(client, monkeypatch):
    monkeypatch.setattr(gateway, "llm_pipeline", pipeline)
    monkeypatch.setattr(gateway, "infer_json", lambda *args: {"work_type": "Plumbing", "description": "Fixed tap", "claimed_completed": False, "language": "en"})
    result = client.post("/extract", json={"text": "Fixed tap", "model": gateway.LLM, "language": "en"})
    assert result.status_code == 200
    assert result.json()["details"]["claimed_completed"] is False
    assert result.json()["revision"] == "test-revision"
    monkeypatch.setattr(gateway, "infer_json", lambda *args: {"text": "Owo 2500"})
    result = client.post("/translate", json={"text": "Price 2500", "model": gateway.LLM, "source": "en", "target": "yo"})
    assert result.json()["text"] == "Owo 2500"


def test_provider_failure_is_private(client, monkeypatch, caplog):
    def fail(*args):
        raise RuntimeError("SECRET and private user text")
    monkeypatch.setattr(gateway, "infer_json", fail)
    result = client.post("/translate", json={"text": "private user text", "model": gateway.LLM, "source": "en", "target": "yo"})
    assert result.status_code == 503
    assert "SECRET" not in result.text + caplog.text
    assert "private user text" not in result.text + caplog.text


def test_audio_format_validation_and_sixty_second_chunking(client, monkeypatch):
    import numpy as np
    import soundfile as sf
    class FakeASR:
        model = pipeline().model
        def __call__(self, audio, **kwargs):
            assert len(audio["array"]) == 16000 * 40
            assert kwargs["chunk_length_s"] == 30
            return {"text": "real pipeline contract"}
    monkeypatch.setattr(gateway, "asr_pipeline", lambda model: FakeASR())
    result = client.post("/asr", data={"language": "en", "model": gateway.MODELS["en"]}, files={"audio": ("audio.wav", b"invalid", "audio/wav")})
    assert result.status_code == 422
    stream = io.BytesIO(); sf.write(stream, np.zeros(16000 * 40), 16000, format="WAV")
    result = client.post("/asr", data={"language": "en", "model": gateway.MODELS["en"]}, files={"audio": ("audio.wav", stream.getvalue(), "audio/wav")})
    assert result.status_code == 200
    assert result.json()["revision"] == "test-revision"


def test_warmup_reports_only_loaded_models(client, monkeypatch):
    def load_llm():
        gateway.loaded_models[gateway.LLM] = "llm-test"
        return pipeline()
    def load_asr(model):
        gateway.loaded_models[model] = "asr-test"
        return pipeline()
    monkeypatch.setattr(gateway, "llm_pipeline", load_llm)
    monkeypatch.setattr(gateway, "asr_pipeline", load_asr)
    response = client.post("/warmup", json={"language": "yo"})
    assert response.status_code == 200
    assert set(response.json()["models"]) == {gateway.LLM, gateway.MODELS["yo"]}
