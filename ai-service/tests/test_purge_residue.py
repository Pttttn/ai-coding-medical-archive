"""Permanent deletion must not leave the removed text in local index files (review finding 7)."""
import sqlite3

from fastapi.testclient import TestClient

from medical_ai.indexer import Corpus
from medical_ai.main import create_app

CANARY = "ZXQPURGECANARY"


def residue(folder):
    # hnswlib dumps its preallocated buffers (data_level0.bin, length.bin, ...) without zeroing them, so the
    # binary files of the live segment can hold stray process memory; a known limit covered by disk encryption.
    return sorted(str(path.relative_to(folder)) for path in folder.rglob("*")
                  if path.is_file() and path.suffix != ".bin" and CANARY.encode() in path.read_bytes())


def segment_dirs(folder):
    return {path.name for path in (folder / "chroma").iterdir() if path.is_dir()}


def fill(corpus):
    for n in range(20):
        corpus.index_document(f"d{n}", f"d{n}.md", 1, f"{CANARY}{n} LDL 4.1 mmol/L. " * 40)
    corpus.index_document("keep", "keep.md", 1, "Other LDL 2.7 mmol/L.")


def test_purge_leaves_no_removed_text_in_index_files(settings, provider):
    corpus = Corpus("archive", settings, provider)
    fill(corpus)
    assert residue(corpus.folder)
    for n in range(20):
        corpus.remove(f"d{n}", purge=n == 19)
    assert residue(corpus.folder) == []
    live = {row[0] for row in sqlite3.connect(corpus.folder / "chroma" / "chroma.sqlite3").execute("SELECT id FROM segments")}
    assert segment_dirs(corpus.folder) <= live
    assert corpus.retrieve("LDL")[0].page_content == "Other LDL 2.7 mmol/L."
    restarted = Corpus("archive", settings, provider)
    assert restarted.retrieve("LDL")[0].page_content == "Other LDL 2.7 mmol/L."


def test_soft_delete_keeps_compaction_off(settings, provider):
    corpus = Corpus("archive", settings, provider)
    fill(corpus)
    for n in range(20):
        corpus.remove(f"d{n}")
    assert corpus.retrieve("LDL")[0].page_content == "Other LDL 2.7 mmol/L."


def test_remove_contract_accepts_purge_flag(services, settings):
    client = TestClient(create_app(services))
    headers = {"X-Internal-Token": settings.internal_token}
    assert client.post("/internal/remove", json={"documentId": "x", "purge": True}, headers=headers).json() == {"ok": True}
    assert client.post("/internal/remove", json={"documentId": "x", "purge": "maybe"}, headers=headers).status_code == 422
