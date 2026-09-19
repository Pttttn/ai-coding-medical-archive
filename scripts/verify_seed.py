"""Check synthetic originals, provenance, required variety and correction history."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
records = json.loads((root / "seed/records.json").read_text(encoding="utf-8"))
assert len(records) >= 30
assert len({tag for record in records for tag in record["tags"]}) >= 15
assert len({record["documentDate"][:4] for record in records}) >= 2
assert {"PDF", "TEXT"} <= {record["sourceType"] for record in records}
assert {"LAB_REPORT", "NOTE", "VISIT_TRANSCRIPT"} <= {record["documentType"] for record in records}
assert sum(any("correction" in fact for fact in record["facts"]) for record in records) >= 5
for record in records:
    assert (root / "seed" / record["originalFile"]).is_file()
    for fact in record["facts"]:
        assert fact["provenance"]["sourceText"] in record["text"]
print(f"Seed verified: {len(records)} records; originals, provenance and corrections present")
