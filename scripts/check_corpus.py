"""Verify only indexed source data count toward the required corpus size."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "evaluation/corpus-manifest.json").read_text())
supported = {".md", ".txt", ".py", ".js", ".ts", ".json", ".yaml"}
seen = set()
total = 0
for item in manifest["files"]:
    path = root / "sample_docs" / item["path"]
    assert path.suffix in supported
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert digest == item["sha256"] and len(data) == item["bytes"]
    assert digest not in seen, f"Duplicate content: {path}"
    seen.add(digest)
    total += len(data)
assert total == manifest["indexedBytes"] and total >= 512000
assert supported <= {p.suffix for p in (root / "sample_docs").rglob("*") if p.is_file()}
print(f"Corpus verified: {len(seen)} unique files, {total} bytes, all 7 formats")
