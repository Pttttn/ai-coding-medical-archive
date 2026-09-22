"""Synthetic HTTP regression checks for the optional adapter; no real upstream calls."""
import importlib.util
import io
import json
import threading
import urllib.error
from pathlib import Path

import httpx
import pytest

SECRET = "SYNTHETIC_PRIVATE_CONTENT"


@pytest.fixture
def shim(tmp_path, monkeypatch):
    key = tmp_path / "key"
    key.write_text("synthetic-test-key", encoding="utf-8")
    monkeypatch.setenv("API_KEY_FILE", str(key))
    monkeypatch.setenv("REMOTE_CHAT_URL", "http://example.invalid/v1/chat/completions")
    monkeypatch.setenv("REMOTE_MODEL", "test-remote-model")
    monkeypatch.setenv("EMBEDDING_MODEL", "nomic-embed-text")
    path = Path(__file__).resolve().parents[2] / "infra" / "llama-shim.py"
    spec = importlib.util.spec_from_file_location("test_shim", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(
        json.dumps({"models": [{"name": "nomic-embed-text:latest"}]}).encode()))
    monkeypatch.setattr(module, "remote_call", lambda *a, **k: {
        "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}]})
    server = module.SafeHTTPServer(("127.0.0.1", 0), module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False) as client:
        yield module, client
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.mark.parametrize("failure", ["auth", "offline", "timeout", "invalid"])
def test_remote_failure_is_unready_and_never_echoes_provider_data(shim, monkeypatch, capsys, failure):
    module, client = shim

    def remote(*args, **kwargs):
        if failure == "invalid":
            return {"error": SECRET}
        if failure == "timeout":
            raise TimeoutError(SECRET)
        raise urllib.error.HTTPError("http://example.invalid/" + SECRET,
                                     401 if failure == "auth" else 503, SECRET, {}, io.BytesIO(SECRET.encode()))

    monkeypatch.setattr(module, "remote_call", remote)
    for route in ("/health", "/api/tags"):
        response = client.get(route)
        assert response.status_code == 503
        assert SECRET not in response.text
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": SECRET}]})
    assert response.status_code == 503
    assert SECRET not in response.text
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err


def test_ready_probes_selected_model_caches_and_recovers_after_outage(shim, monkeypatch):
    module, client = shim
    probes = []

    def remote(payload, **kwargs):
        probes.append(payload)
        return {"choices": [{"message": {"content": "OK"}, "finish_reason": "length"}]}

    monkeypatch.setattr(module, "remote_call", remote)
    assert client.get("/health").json() == {"ready": True}
    models = client.get("/api/tags").json()["models"]
    assert {m["name"] for m in models} == {"test-remote-model", "nomic-embed-text:latest"}
    assert len(probes) == 1
    assert probes[0]["model"] == "test-remote-model"
    assert probes[0]["max_tokens"] == 1
    module.invalidate_readiness()
    monkeypatch.setattr(module, "remote_call", lambda *a, **k: {})
    assert client.get("/health").status_code == 503
    monkeypatch.setattr(module, "remote_call", remote)
    assert client.get("/health").status_code == 200


def test_missing_embedding_is_not_ready_even_with_remote_available(shim, monkeypatch):
    module, client = shim
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b'{"models": []}'))
    assert client.get("/health").status_code == 503
    assert client.get("/api/tags").status_code == 503


def test_success_does_not_log_prompt_answer_or_unexpected_keys(shim, monkeypatch, capsys):
    module, client = shim
    monkeypatch.setattr(module, "remote_call", lambda *a, **k: {"choices": [{
        "message": {"content": json.dumps({"value": SECRET, SECRET: "extra"})}, "finish_reason": "stop"}]})
    response = client.post("/api/chat", json={"messages": [{"role": "system", "content": SECRET}],
        "format": {"type": "object", "additionalProperties": False, "properties": {"value": {"type": "string"}}}})
    assert response.status_code == 200
    assert json.loads(response.json()["message"]["content"]) == {"value": SECRET}
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err


def test_embedding_failure_is_safe_and_malformed_input_is_closed(shim, monkeypatch, capsys):
    module, client = shim

    def unavailable(*args, **kwargs):
        raise urllib.error.HTTPError("http://example.invalid", 500, SECRET, {}, io.BytesIO(SECRET.encode()))

    monkeypatch.setattr(module.urllib.request, "urlopen", unavailable)
    result = client.post("/api/embed", json={"input": SECRET})
    assert result.status_code == 503 and SECRET not in result.text
    result = client.post("/api/chat", content=SECRET)
    assert result.status_code == 400 and SECRET not in result.text
    assert result.headers["connection"] == "close"
    assert client.post("/api/pull", json={"model": SECRET}).status_code == 403
    output = capsys.readouterr()
    assert SECRET not in output.out + output.err


def test_schema_fallback_stays_validated_and_length_is_preserved(shim, monkeypatch):
    module, client = shim
    formats = []

    def remote(payload, **kwargs):
        formats.append(payload["response_format"]["type"])
        if len(formats) == 1:
            raise urllib.error.HTTPError("http://example.invalid", 400, SECRET, {}, io.BytesIO(SECRET.encode()))
        return {"choices": [{"message": {"content": '{"value":"partial"}'}, "finish_reason": "length"}]}

    monkeypatch.setattr(module, "remote_call", remote)
    response = client.post("/api/chat", json={"messages": [], "format": {"type": "object"}})
    assert response.json()["done_reason"] == "length"
    assert formats == ["json_schema", "json_object"]



def test_seed_is_forwarded_to_optional_provider(shim, monkeypatch):
    module, client = shim
    calls = []

    def remote(payload, **kwargs):
        calls.append(payload)
        return {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]}

    monkeypatch.setattr(module, "remote_call", remote)
    assert client.post("/api/chat", json={"messages": [], "options": {"seed": 42}}).status_code == 200
    assert calls[0]["seed"] == 42
