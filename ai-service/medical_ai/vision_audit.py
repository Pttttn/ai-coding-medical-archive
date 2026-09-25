"""Local, read-only visual audit of laboratory PDF tables.

The model sees cropped page pixels, never the parser's extracted cells. This
experimental evaluator reports discrepancies only; it never edits the archive.
Raw images, model output and document identifiers are kept in memory and are
not emitted to stdout or written to disk.
"""
import argparse
import base64
import io
import json
import time
from pathlib import Path

import httpx
import pdfplumber
from jsonschema import ValidationError, validate

from .lab_consensus import reconcile_lab_rows

FIELDS = ("test", "result", "unit", "reference")
PROMPT_VERSION = "lab-vision-audit-v2"
SCHEMA = {
    "type": "object",
    "properties": {"rows": {"type": "array", "maxItems": 200, "items": {
        "type": "object",
        "properties": {field: {"type": "string", "maxLength": 2000} for field in FIELDS},
        "required": list(FIELDS),
        "additionalProperties": False,
    }}},
    "required": ["rows"],
    "additionalProperties": False,
}
PROMPT = (
    "Read the visible laboratory table. For every data row, copy ONLY the text "
    "printed inside each of its four cells into the corresponding JSON field. "
    "Keep the original language, decimal comma or dot, comparison signs, units, "
    "and every line of a multi-line reference. Do not translate, interpret, "
    "normalize, add notes, or include text from another cell. Use an empty string "
    "for an empty cell. Do not include the header, footer, or section title."
)
OLLAMA_URL = "http://127.0.0.1:11434"  # Never send private pages to a configured remote endpoint.


def normalized(value: str | None) -> str:
    return " ".join((value or "").split())


def lab_header(row: list[str | None]) -> bool:
    if len(row) != 4:
        return False
    cells = [normalized(cell).casefold() for cell in row]
    return (cells[0] in {"тест", "показатель", "test"}
            and cells[1] in {"результат", "result"}
            and cells[2] in {"ед. измерения", "ед.измерения", "единица", "единицы", "unit"}
            and cells[3] in {"референсный интервал", "референс", "reference"})


def table_png(page, bbox: tuple[float, float, float, float], margin: int = 14) -> bytes:
    """Render only a detected table plus a narrow margin, in memory."""
    scale = 3  # 216 DPI; retain small decimal points and inequality signs.
    image = page.to_image(resolution=72 * scale).original
    x0, y0, x1, y1 = bbox
    crop = image.crop((max(0, int((x0 - margin) * scale)),
                       max(0, int((y0 - margin) * scale)),
                       min(image.width, int((x1 + margin) * scale)),
                       min(image.height, int((y1 + margin) * scale))))
    output = io.BytesIO()
    crop.save(output, format="PNG")
    return output.getvalue()


def compare_rows(expected: list[list[str]], observed: list[dict[str, str]]) -> list[dict]:
    """Return positions/field types only; never include private values."""
    if len(expected) != len(observed):
        return [{"row": None, "field": "row_count"}]
    return [{"row": index + 1, "field": field}
            for index, (source, read) in enumerate(zip(expected, observed))
            for field, value in zip(FIELDS, source)
            if normalized(read[field]) != value]


def read_image(client: httpx.Client, model: str, image: bytes) -> list[dict[str, str]]:
    response = client.post("/api/chat", json={
        "model": model,
        "messages": [{"role": "user", "content": PROMPT,
                      "images": [base64.b64encode(image).decode("ascii")]}],
        "format": SCHEMA,
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 2048},
    })
    response.raise_for_status()
    result = json.loads(response.json()["message"]["content"])
    validate(result, SCHEMA)
    return result["rows"]


def audit(paths: list[Path], model: str, runs: int = 1) -> dict:
    """Read-only evaluation. The returned report contains no PDF/model text."""
    if not 1 <= runs <= 10 or not paths or len(paths) > 20:
        raise ValueError("Expected 1-20 PDFs and 1-10 runs")
    report = {"schemaVersion": "vision-lab-audit-v2", "evidencePolicyVersion": "lab-consensus-v1",
              "promptVersion": PROMPT_VERSION,
              "model": model, "documents": len(paths), "runs": runs, "checks": []}
    with httpx.Client(base_url=OLLAMA_URL, timeout=240, trust_env=False) as client:
        model_info = client.post("/api/show", json={"model": model})
        model_info.raise_for_status()
        if "vision" not in model_info.json().get("capabilities", []):
            raise ValueError("Selected local model has no vision capability")
        tags = client.get("/api/tags")
        tags.raise_for_status()
        installed = next((entry for entry in tags.json().get("models", [])
                          if entry.get("name") == model and entry.get("digest")
                          and isinstance(entry.get("size"), int) and entry["size"] > 0), None)
        if installed is None:
            raise ValueError("Selected vision model is not installed locally")
        report["modelDigest"] = installed["digest"]
        for run in range(1, runs + 1):
            for document_index, path in enumerate(paths, 1):
                if path.suffix.lower() != ".pdf" or path.stat().st_size > 20_000_000:
                    raise ValueError("Expected a PDF of at most 20 MB")
                with pdfplumber.open(path) as pdf:
                    for page_index, page in enumerate(pdf.pages, 1):
                        for table_index, table in enumerate(page.find_tables(), 1):
                            rows = table.extract()
                            if not rows or not lab_header(rows[0]):
                                continue
                            expected = [[normalized(cell) for cell in row] for row in rows[1:]]
                            started = time.monotonic()
                            check = {"run": run, "document": document_index, "page": page_index,
                                     "table": table_index, "expectedRows": len(expected)}
                            try:
                                observed = read_image(client, model, table_png(page, table.bbox))
                                mismatches = compare_rows(expected, observed)
                                evidence = reconcile_lab_rows({
                                    "text_layer": [dict(zip(FIELDS, row)) for row in expected],
                                    "vision": observed,
                                })
                                check.update(status="REVIEW" if mismatches else "PASS",
                                             observedRows=len(observed), mismatches=mismatches,
                                             evidenceDecision=evidence["decision"])
                            except (httpx.HTTPError, ValueError, KeyError, TypeError, ValidationError):
                                check.update(status="ERROR", observedRows=None,
                                             mismatches=[{"row": None, "field": "model_error"}],
                                             evidenceDecision="REVIEW_UNAVAILABLE")
                            check["seconds"] = round(time.monotonic() - started, 2)
                            report["checks"].append(check)
    if not report["checks"]:
        raise ValueError("No supported laboratory tables")
    report["expectedRows"] = sum(c["expectedRows"] for c in report["checks"])
    report["passedTables"] = sum(c["status"] == "PASS" for c in report["checks"])
    report["reviewTables"] = sum(c["status"] == "REVIEW" for c in report["checks"])
    report["errorTables"] = sum(c["status"] == "ERROR" for c in report["checks"])
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Local visual audit; emits counts and mismatch positions only")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.paths, args.model, args.runs), ensure_ascii=False))
    except Exception:
        # Exceptions may contain source paths or upstream bodies; do not print them.
        print(json.dumps({"status": "ERROR", "code": "AUDIT_UNAVAILABLE"}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
