#!/usr/bin/env python3
"""Ollama-protocol shim for the remote llama.cpp (OpenAI-compatible) server.

POST /api/chat        -> translated to remote /v1/chat/completions (Bearer auth)
POST /api/embed       -> forwarded to the local host Ollama (nomic-embed-text)
GET  /api/tags        -> local models + the remote model (for the ai health check)
anything else         -> 403 (mirrors the repo's fixed egress proxy stance)
"""
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REMOTE_CHAT = os.environ.get("REMOTE_CHAT_URL", "http://10.44.0.67:11435/v1/chat/completions")
REMOTE_MODEL = os.environ.get("REMOTE_MODEL", "qwen3.8-27b-q8-100k-cuda")
LOCAL_OLLAMA = os.environ.get("LOCAL_OLLAMA_URL", "http://host.docker.internal:11434")
PORT = int(os.environ.get("SHIM_PORT", "11435"))
API_KEY = open(os.environ.get("API_KEY_FILE", "/keys/llama-mpc1.keys")).read().strip().splitlines()[0]


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        return self.rfile.read(length) if length else b"{}"

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/tags":
            try:
                with urllib.request.urlopen(LOCAL_OLLAMA + "/api/tags", timeout=10) as r:
                    tags = json.loads(r.read())
            except Exception:
                tags = {"models": []}
            names = {m.get("name", "") for m in tags.get("models", [])}
            if REMOTE_MODEL not in names and REMOTE_MODEL + ":latest" not in names:
                tags.setdefault("models", []).append(
                    {"name": REMOTE_MODEL, "model": REMOTE_MODEL, "size": 0, "digest": "remote-mpc1"})
            self._send(200, tags)
        elif path == "/api/version":
            self._send(200, {"version": "shim-1.0"})
        elif path == "/api/ps":
            self._send(200, {"models": []})
        else:
            self._send(403, {"error": {"code": "403", "message": "path not allowed by shim"}})

    def do_POST(self):
        path = self.path.split("?")[0]
        raw = self._read_body()
        if path == "/api/chat":
            self._chat(json.loads(raw))
            return
        if path in ("/api/embed", "/api/embeddings"):
            req = urllib.request.Request(LOCAL_OLLAMA + path, data=raw,
                                         headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=300) as r:
                    self._send(200, json.loads(r.read()))
            except urllib.error.HTTPError as e:
                self._send(e.code, json.loads(e.read() or b"{}"))
            return
        self._send(403, {"error": {"code": "403", "message": "path not allowed by shim"}})

    def _remote_call(self, payload):
        req = urllib.request.Request(
            REMOTE_CHAT, data=json.dumps(payload).encode(),
            headers={"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=900) as r:
            return json.loads(r.read())

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
        task = next((m.get("content", "")[:44] for m in body.get("messages", [])
                     if m.get("role") == "system"), "?")
        payload = {
            "model": REMOTE_MODEL,
            "messages": body.get("messages", []),
            "temperature": options.get("temperature", 0),
            "max_tokens": options.get("num_predict", 1024),
            "stream": False,
        }
        if isinstance(fmt, dict):
            payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "schema": fmt}}
        elif fmt == "json":
            payload["response_format"] = {"type": "json_object"}
        try:
            try:
                data = self._remote_call(payload)
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:300]
                # Some builds reject json_schema; retry unconstrained, the service validates itself.
                if e.code == 400 and isinstance(fmt, dict):
                    payload["response_format"] = {"type": "json_object"}
                    data = self._remote_call(payload)
                else:
                    print(f"CHAT remote {e.code}: {detail[:120]} | task={task}", flush=True)
                    self._send(503, {"error": {"code": str(e.code), "message": detail}})
                    return
        except Exception as exc:  # network / timeout -> provider-unavailable for the caller
            print(f"CHAT unavailable: {str(exc)[:120]} | task={task}", flush=True)
            self._send(503, {"error": {"code": "REMOTE_UNAVAILABLE", "message": str(exc)[:300]}})
            return
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        # Defense in depth: never let reasoning leak into the JSON contract.
        if "<think>" in content:
            start = content.find("<think>")
            end = content.find("</think>")
            content = content[:start] + (content[end + 8:] if end != -1 else "")
        dropped = ""
        if isinstance(fmt, dict):
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    constrained = self._constrain(parsed, fmt)
                    if constrained != parsed:
                        dropped = f" | dropped keys={sorted(set(parsed) - set(constrained))}"
                        content = json.dumps(constrained, ensure_ascii=False)
            except json.JSONDecodeError:
                pass
        done_reason = "length" if choice.get("finish_reason") == "length" else "stop"
        print(f"CHAT ok task={task!r} done={done_reason}{dropped} | {content[:70]!r}", flush=True)
        self._send(200, {"message": {"role": "assistant", "content": content},
                         "done_reason": done_reason, "done": True})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"shim listening on 0.0.0.0:{PORT} -> {REMOTE_CHAT} (model {REMOTE_MODEL})", flush=True)
    server.serve_forever()
