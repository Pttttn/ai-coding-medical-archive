"""Real PDF upload/parse/status/provenance acceptance on synthetic fixtures."""
import argparse
import io
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader, PdfWriter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:3000")
    parser.add_argument("--output", default="docs/evaluation/pdf-smoke.json")
    args = parser.parse_args()
    outcomes = []

    def call(method, route, body=None):
        req = urllib.request.Request(args.base + route, data=json.dumps(body).encode() if body is not None else None,
                                     method=method, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as response:
            return json.loads(response.read())

    def upload(payload, title):
        boundary = uuid4().hex
        data = f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\n{title}\r\n'.encode()
        data += f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic-check.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode() + payload + f'\r\n--{boundary}--\r\n'.encode()
        req = urllib.request.Request(args.base + "/api/documents/upload", data=data,
                                     headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
        with urllib.request.urlopen(req, timeout=30) as response:
            doc = json.loads(response.read())
        return doc.get("id") or doc["documentId"]

    for kind in ("text", "scan", "malformed", "partial"):
        writer = PdfWriter()
        if kind in {"text", "partial"}:
            writer.append(PdfReader("seed/originals/lab-01.pdf"))
        if kind in {"scan", "partial"}:
            writer.add_blank_page(width=595, height=842)
        writer.add_metadata({"/Title": "Synthetic acceptance fixture " + uuid4().hex})
        buf = io.BytesIO()
        writer.write(buf)
        payload = buf.getvalue() if kind != "malformed" else b"%PDF-1.7\nnot a valid document " + uuid4().hex.encode()
        start = time.monotonic()
        document_id = upload(payload, "SYNTHETIC PDF acceptance " + kind)
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            doc = call("GET", f"/api/documents/{document_id}")
            if doc["status"] in {"READY", "FAILED", "UNSUPPORTED_OCR_REQUIRED"}:
                break
            time.sleep(2)
        expected = "UNSUPPORTED_OCR_REQUIRED" if kind == "scan" else "FAILED" if kind == "malformed" else "READY"
        assert doc["status"] == expected, (kind, doc["status"], doc.get("latestJob"))
        if kind in {"text", "partial"}:
            assert "LDL cholesterol" in doc["text"]
            assert doc["facts"], "PDF should yield source-backed facts"
            for fact in doc["facts"]:
                source = call("GET", f"/api/facts/{fact['id']}/source")
                assert source["pageNumber"] == 1 and source["sourceText"]
            if kind == "partial":
                assert doc.get("processingWarnings"), "Incomplete PDF extraction must be visible to the user"
        outcomes.append({"kind": kind, "status": doc["status"], "warnings": doc.get("processingWarnings", []), "seconds": round(time.monotonic() - start, 2)})
        print("PASS", kind, doc["status"], flush=True)
        call("DELETE", f"/api/documents/{document_id}")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "base": args.base, "results": outcomes}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
