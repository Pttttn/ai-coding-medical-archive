#!/usr/bin/env python3
"""Explicit opt-in Ollama adapter for an operator-configured llama.cpp endpoint.

No prompts, generated content, credentials, URLs or provider errors are logged.
Readiness checks both local embeddings and an authenticated synthetic generation.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REMOTE_CHAT = os.environ["REMOTE_CHAT_URL"]
REMOTE_MODEL = os.environ.get("REMOTE_MODEL", "qwen3.8-27b-q8-100k-cuda")
LOCAL_OLLAMA = os.environ.get("LOCAL_OLLAMA_URL", "http://host.docker.internal:11434")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")
PORT = int(os.environ.get("SHIM_PORT", "11435"))
try:
    with open(os.environ.get("API_KEY_FILE", "/keys/llama-cpp.keys")) as key_file:
        API_KEY = key_file.read().strip().splitlines()[0]
except (OSError, IndexError):
    raise SystemExit("SHIM_KEY_UNAVAILABLE") from None

_ready_lock = threading.Lock()
_ready_until = 0.0
_ready_tags = None


def remote_call(payload, timeout=180):
    request = urllib.request.Request(
        REMOTE_CHAT, data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def invalidate_readiness():
    global _ready_until, _ready_tags
    with _ready_lock:
        _ready_until, _ready_tags = 0.0, None


def ready_tags():
    """Cache a successful synthetic probe for at most five seconds; never invent availability."""
    global _ready_until, _ready_tags
    with _ready_lock:
        if _ready_tags is not None and time.monotonic() < _ready_until:
            return _ready_tags
        _ready_until, _ready_tags = 0.0, None
        with urllib.request.urlopen(LOCAL_OLLAMA + "/api/tags", timeout=3) as response:
            local = json.loads(response.read())
        embedding = next(model for model in local["models"]
                         if model.get("name") in {EMBEDDING_MODEL, EMBEDDING_MODEL + ":latest"})
        result = remote_call({"model": REMOTE_MODEL, "messages": [
            {"role": "user", "content": "Synthetic readiness check. Reply OK."}],
            "stream": False, "temperature": 0, "max_tokens": 1}, timeout=5)
        # An API/version page, auth error, or error envelope is not working generation.
        choice = result["choices"][0]
        if not isinstance(choice.get("message"), dict) or choice.get("finish_reason") not in {"stop", "length"}:
            raise ValueError("Invalid readiness response")
        _ready_tags = {"models": [embedding, {"name": REMOTE_MODEL, "model": REMOTE_MODEL,
                                              "size": 0, "digest": "remote-llama-cpp"}]}
        _ready_until = time.monotonic() + 5
        return _ready_tags


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            if self.close_connection:
                self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_error(self, code, message=None, explain=None):
        self.close_connection = True
        self._error(code, "INVALID_HTTP_REQUEST")

    def _error(self, code, name):
        self._send(code, {"error": {"code": name, "message": name}})

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/api/tags", "/health"):
            try:
                tags = ready_tags()
            except Exception:
                self._error(503, "PROVIDER_NOT_READY")
                return
            self._send(200, tags if path == "/api/tags" else {"ready": True})
        elif path == "/api/version":
            self._send(200, {"version": "shim-1.1"})
        elif path == "/api/ps":
            self._send(200, {"models": []})
        else:
            self._error(403, "PATH_NOT_ALLOWED")

    def do_POST(self):
        path = self.path.split("?")[0]
        if path not in ("/api/chat", "/api/embed", "/api/embeddings"):
            self.close_connection = True
            self._error(403, "PATH_NOT_ALLOWED")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 20 * 1024 * 1024:
                raise ValueError("Invalid request length")
            raw = self.rfile.read(length)
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError("Expected object")
        except (ValueError, UnicodeError):
            self.close_connection = True
            self._error(400, "INVALID_REQUEST")
            return
        if path == "/api/chat":
            self._chat(body)
            return
        try:
            request = urllib.request.Request(LOCAL_OLLAMA + path, data=raw,
                                             headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=180) as response:
                self._send(200, json.loads(response.read()))
        except Exception:
            invalidate_readiness()
            self._error(503, "EMBEDDING_UNAVAILABLE")

    def _remote_call(self, payload):
        return remote_call(payload)

    CATEGORY_ALIASES = {
        "clinic_name": "CLINIC", "clinic": "CLINIC", "facility": "CLINIC",
        "hospital": "CLINIC", "institution": "CLINIC",
        "person": "PERSON", "patient": "PERSON", "person_name": "PERSON",
        "personal_name": "PERSON", "patient_name": "PERSON", "full_name": "PERSON",
        "name": "PERSON", "patient_name_full": "PERSON",
        "doctor": "DOCTOR", "doctor_name": "DOCTOR", "physician": "DOCTOR",
        "clinician": "DOCTOR", "provider": "DOCTOR",
        "address": "ADDRESS", "location": "ADDRESS", "street": "ADDRESS",
        "dob": "DOB", "birth_date": "DOB", "birthdate": "DOB", "date_of_birth": "DOB",
        "contact": "CONTACT", "phone": "CONTACT", "email": "CONTACT",
        "telephone": "CONTACT", "phone_number": "CONTACT", "email_address": "CONTACT",
        "identifier": "IDENTIFIER", "id": "IDENTIFIER", "record_id": "IDENTIFIER",
        "card_number": "IDENTIFIER", "id_number": "IDENTIFIER", "number": "IDENTIFIER",
    }
    CATEGORY_SUBSTRINGS = (
        ("CLINIC", ("clinic", "hospital", "facility")),
        ("DOCTOR", ("doctor", "physician", "clinician")),
        ("PERSON", ("person", "patient", "name")),
        ("ADDRESS", ("address", "location", "street")),
        ("DOB", ("birth", "dob")),
        ("CONTACT", ("contact", "phone", "email", "mail", "tel")),
    )

    def _constrain(self, value, schema):
        """Recursively align model output with the caller's JSON schema.

        Drops keys not declared by additionalProperties:false schemas, descends
        into array items, and normalizes enum values (case/aliases). Category
        normalization only changes the placeholder label, never the redaction
        itself; anything unmappable stays and fails closed at the caller.
        """
        if not isinstance(schema, dict):
            return value
        if isinstance(value, dict):
            props = schema.get("properties")
            if props and schema.get("additionalProperties") is False:
                value = {k: self._constrain(v, props[k]) for k, v in value.items() if k in props}
            required = schema.get("required")
            if isinstance(value, dict) and required and not all(r in value for r in required):
                return value  # missing required keys: let the caller fail closed
            return value
        if isinstance(value, list):
            items = schema.get("items")
            if isinstance(items, dict):
                return [self._constrain(v, items) for v in value]
            return value
        enum = schema.get("enum")
        if enum and isinstance(value, str) and value not in enum:
            for member in enum:
                if value.upper() == member:
                    return member
            mapped = self.CATEGORY_ALIASES.get(value.lower())
            if mapped in enum:
                return mapped
            low = value.lower()
            for member, needles in self.CATEGORY_SUBSTRINGS:
                if member in enum and any(n in low for n in needles):
                    return member
            if "IDENTIFIER" in enum:
                # Generic redaction label: redaction itself never depends on the category.
                return "IDENTIFIER"
        return value

    def _chat(self, body):
        fmt = body.get("format")
        options = body.get("options", {})
        if not isinstance(options, dict) or not isinstance(body.get("messages"), list):
            self._error(400, "INVALID_REQUEST")
            return
        payload = {
            "model": REMOTE_MODEL, "messages": body["messages"],
            "temperature": options.get("temperature", 0),
            "max_tokens": options.get("num_predict", 1024), "stream": False,
        }
        if isinstance(fmt, dict):
            payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "schema": fmt}}
        elif fmt == "json":
            payload["response_format"] = {"type": "json_object"}
        try:
            try:
                data = self._remote_call(payload)
            except urllib.error.HTTPError as error:
                if error.code != 400 or not isinstance(fmt, dict):
                    raise
                # Some builds reject json_schema; the caller still validates the result.
                payload["response_format"] = {"type": "json_object"}
                data = self._remote_call(payload)
            choice = data["choices"][0]
            content = choice["message"].get("content") or ""
            if not isinstance(content, str) or choice.get("finish_reason") not in {"stop", "length"}:
                raise ValueError("Invalid generation response")
            if "<think>" in content:
                start, end = content.find("<think>"), content.find("</think>")
                content = content[:start] + (content[end + 8:] if end != -1 else "")
            if isinstance(fmt, dict):
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        content = json.dumps(self._constrain(parsed, fmt), ensure_ascii=False)
                except json.JSONDecodeError:
                    pass  # The caller rejects invalid JSON without a raw public fallback.
        except Exception:
            invalidate_readiness()
            self._error(503, "REMOTE_UNAVAILABLE")
            return
        self._send(200, {"message": {"role": "assistant", "content": content},
                         "done_reason": choice["finish_reason"], "done": True})


class SafeHTTPServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        # BaseServer prints tracebacks for otherwise unhandled request errors.
        print("SHIM_REQUEST_FAILED", flush=True)


if __name__ == "__main__":
    server = SafeHTTPServer(("0.0.0.0", PORT), Handler)
    print("SHIM_STARTED", flush=True)
    server.serve_forever()
