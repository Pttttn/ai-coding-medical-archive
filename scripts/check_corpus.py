"""Verify only indexed source data count toward the required corpus size."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "evaluation/corpus-manifest.json").read_text())
supported = {".md", ".txt", ".pdf"}
seen = set()
manifest_paths = {item["path"] for item in manifest["files"]}
actual_paths = {p.relative_to(root / "sample_docs").as_posix() for p in (root / "sample_docs").rglob("*") if p.is_file()}
assert manifest_paths == actual_paths, "Manifest must cover exactly the indexed corpus"
total = 0
plain_text_bytes = 0
for item in manifest["files"]:
    path = root / "sample_docs" / item["path"]
    assert path.suffix in supported
    data = path.read_bytes()
    if path.suffix != ".pdf":
        assert b"\r\n" not in data, "Generated corpus must use LF to match Git checkouts"
        plain_text_bytes += len(data)
    digest = hashlib.sha256(data).hexdigest()
    assert digest == item["sha256"] and len(data) == item["bytes"]
    assert digest not in seen, f"Duplicate content: {path}"
    seen.add(digest)
    total += len(data)
assert total == manifest["indexedBytes"]
assert plain_text_bytes >= 512000, "Plain indexed text alone must exceed 500 KiB; PDF container bytes do not count"
assert supported <= {p.suffix for p in (root / "sample_docs").rglob("*") if p.is_file()}
print(f"Corpus verified: {len(seen)} unique files, {total} file bytes ({plain_text_bytes} plain text bytes), medical formats MD/TXT/PDF")
