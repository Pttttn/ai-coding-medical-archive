"""Real local API acceptance flow on synthetic demo data only (never production)."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:3000")
    parser.add_argument("--output", default="docs/evaluation/application-smoke.json")
    args = parser.parse_args()
    assert urllib.parse.urlsplit(args.base).hostname in {"localhost", "127.0.0.1"}, "Local demo only"
    checks = []
    started = time.monotonic()

    def request(method, path, body=None, expected=None):
        req = urllib.request.Request(args.base + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json"}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=600) as response:
                raw, code, kind = response.read(), response.status, response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as error:
            raw, code, kind = error.read(), error.code, error.headers.get("Content-Type", "")
        if expected is not None:
            assert code == expected, (method, path, code, raw[:300])
        else:
            assert 200 <= code < 300, (method, path, code, raw[:300])
        return json.loads(raw) if "json" in kind and raw else raw.decode("utf-8", errors="replace")

    def check(name, condition=True):
        assert condition, name
        checks.append({"name": name, "passed": True, "elapsedSeconds": round(time.monotonic() - started, 2)})
        print(f"PASS {name}", flush=True)

    def ready(document_id):
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            doc = request("GET", f"/api/documents/{document_id}")
            if doc["status"] == "READY":
                return doc
            assert doc["status"] not in {"FAILED", "UNSUPPORTED_OCR_REQUIRED"}, doc.get("latestJob", doc["status"])
            time.sleep(2)
        raise AssertionError("Document processing exceeded 600 seconds")

    dashboard = request("GET", "/api/dashboard")
    check("dashboard seed", dashboard["totalDocuments"] >= 30)
    first = request("GET", "/api/documents?page=1&pageSize=5")
    second = request("GET", "/api/documents?page=2&pageSize=5")
    check("server pagination", len(first["items"]) == 5 and not ({d["id"] for d in first["items"]} & {d["id"] for d in second["items"]}))
    check("swagger local", "swagger" in request("GET", "/docs").lower())
    request("POST", "/api/documents/note", {"title": "", "text": ""}, expected=400)
    check("backend validation")
    title = "SYNTHETIC acceptance record " + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    note = request("POST", "/api/documents/note", {"title": title, "documentType": "NOTE", "documentDate": "2025-06-17", "tags": ["синтетика", "acceptance"], "text": "SYNTHETIC SOFTWARE TEST, not medical advice. Patient: Alex Example. Document date: 2025-06-17. The unique Copper Finch visit code is SYN-COPPER-931. Walking duration: 23 minutes. Dizziness is explicitly denied. Medication intake is unknown."})
    document_id = note.get("id") or note.get("document", {}).get("id") or note.get("documentId")
    assert document_id, note
    ready(document_id)
    check("real note extraction and indexing")
    found = request("GET", "/api/documents?q=" + urllib.parse.quote("SYN-COPPER-931"))
    check("full text search", any(d["id"] == document_id for d in found["items"]))
    answer = request("POST", "/api/ask", {"question": "What is the Copper Finch visit code?"})
    check("real archive RAG citations", "SYN-COPPER-931" in answer["answer"] and any(s.get("documentId") == document_id for s in answer["sources"]))
    request("PATCH", f"/api/documents/{document_id}", {"title": title + " edited"})
    check("metadata update", request("GET", f"/api/documents/{document_id}")["title"].endswith("edited"))
    preparation = request("POST", "/api/consultations/prepare", {"question": "Summarize the Copper Finch visit for patient Alex Example, email alex@example.test.", "documentIds": [document_id]})
    consultation_id = preparation["id"]
    content = preparation["content"]
    check("privacy pass", "alex@example.test" not in content.lower() and "Alex Example" not in content)
    request("GET", f"/api/consultations/{consultation_id}/export", expected=409)
    check("unreviewed export blocked")
    request("POST", f"/api/consultations/{consultation_id}/review", {"contentHash": preparation["contentHash"]})
    exported = request("GET", f"/api/consultations/{consultation_id}/export")
    check("reviewed exact export", exported == content and hashlib.sha256(exported.encode()).hexdigest() == preparation["contentHash"])
    changed = request("PATCH", f"/api/consultations/{consultation_id}", {"content": content + "\n\nReviewed synthetic note."})
    check("edit clears review", changed["status"] != "REVIEWED")
    request("GET", f"/api/consultations/{consultation_id}/export", expected=409)
    check("stale review cannot export")
    request("DELETE", f"/api/documents/{document_id}")
    found = request("GET", "/api/documents?q=" + urllib.parse.quote("SYN-COPPER-931"))
    check("soft delete excludes search", not any(d["id"] == document_id for d in found["items"]))
    answer = request("POST", "/api/ask", {"question": "What is the Copper Finch visit code?"})
    check("soft delete excludes RAG", not any(s.get("documentId") == document_id for s in answer["sources"]))
    request("POST", f"/api/documents/{document_id}/restore", {})
    ready(document_id)
    check("restore and reindex")
    history = request("GET", f"/api/documents/{document_id}/history?page=1&pageSize=50")
    check("persistent audit", len(history["items"]) >= 4)
    # Test-created record is soft-deleted; demo source documents remain untouched.
    request("DELETE", f"/api/documents/{document_id}")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "base": args.base, "mode": "real Ollama on synthetic demo", "checks": checks, "seconds": round(time.monotonic() - started, 2)}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
