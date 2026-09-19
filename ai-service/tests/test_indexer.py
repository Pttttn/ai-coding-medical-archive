import os

import pytest

from medical_ai.errors import ServiceError
from medical_ai.indexer import Corpus, source_of
from medical_ai.schemas import Page


@pytest.mark.parametrize("extension", ["md", "txt"])
def test_medical_text_formats_are_data(services, settings, provider, extension):
    (settings.sample_docs_dir / ("fixture." + extension)).write_text("SYN-CASE-7F29 4.1 mmol/L", encoding="utf-8")
    result = services.demo.index_folder()
    assert result["files"] == 1 and result["chunks"] == 1
    assert all(call[0] == "embed" for call in provider.calls)
    assert services.archive.status()["files"] == 0


def test_idempotency_update_remove_and_restart(services, settings, provider):
    corpus = services.demo
    assert corpus.status()["lastIndexedAt"] is None
    corpus.index_document("a", "a.md", 1, "first LDL 4.1")
    assert corpus.index_document("a", "a.md", 1, "first LDL 4.1")["unchanged"]
    corpus.index_document("a", "a.md", 2, "updated LDL 2.7")
    assert corpus.status()["chunks"] == 1
    restarted = Corpus("mcp_demo", settings, provider)
    assert restarted.retrieve("LDL")[0].page_content == "updated LDL 2.7"
    restarted.remove("a")
    assert restarted.retrieve("LDL") == []


def test_folder_deletion_removes_stale_document(services, settings):
    path = settings.sample_docs_dir / "a.md"
    path.write_text("first document", encoding="utf-8")
    services.demo.index_folder()
    path.unlink()
    assert services.demo.index_folder()["removed"] == 1
    assert services.demo.status()["files"] == 0


def test_page_metadata_and_corrections_are_separate(services):
    services.archive.index_document("a", "lab.pdf", 2, "LDL 4.1", [Page(pageNumber=2, text="LDL 4.1")],
        [{"id": "f", "name": "LDL", "valueNumber": 2.7, "unit": "mmol/L", "reviewStatus": "CORRECTED"}])
    found = services.archive.retrieve("LDL")
    assert any(d.metadata["pageNumber"] == 2 and d.metadata["version"] == 2 for d in found)
    assert any(d.metadata["userCorrection"] and "не цитата" in d.page_content for d in found)
    assert source_of(found[0])["documentId"] == "a"


def test_document_filter_and_hybrid_rrf(services):
    services.archive.index_document("a", "A", 1, "rareXYZ target")
    services.archive.index_document("b", "B", 1, "unrelated OTHER")
    docs = services.archive.retrieve("rareXYZ", document_ids=["b"])
    assert len(docs) == 1 and docs[0].metadata["documentId"] == "b"
    assert services.archive.retrieve("rareXYZ")[0].metadata["documentId"] == "a"
    assert services.archive.retrieve("rareXYZ", document_ids=[]) == []


@pytest.mark.parametrize("path,glob", [("../", "**/*"), ("/etc", "**/*"), ("./sample_docs", "../*"),
                                       ("./sample_docs", "**/../../*"), ("./sample_docs", "C:/*")])
def test_path_traversal_is_rejected(services, path, glob):
    with pytest.raises(ServiceError) as error:
        services.demo.index_folder(path, glob)
    assert error.value.code == "PATH_NOT_ALLOWED"


def test_symlink_escape_is_rejected(services, settings, tmp_path):
    external = tmp_path / "secret.txt"
    external.write_text("PRIVATE", encoding="utf-8")
    link = settings.sample_docs_dir / "escape.txt"
    try:
        os.symlink(external, link)
    except OSError:
        pytest.skip("Host does not permit symlink creation; Linux CI runs this check")
    result = services.demo.index_folder()
    assert result["errors"][0]["code"] == "PATH_NOT_ALLOWED"
    assert result["files"] == 0


@pytest.mark.parametrize("extension", ["py", "js", "ts", "json", "yaml", "yml"])
def test_legacy_code_formats_are_skipped(services, settings, provider, extension):
    (settings.sample_docs_dir / ("legacy." + extension)).write_text("SYNTHETIC", encoding="utf-8")
    result = services.demo.index_folder()
    assert result["files"] == 0
    assert result["skipped"] == [{"source": "legacy." + extension, "reason": "UNSUPPORTED_FORMAT"}]
    assert provider.calls == []


def test_format_policy_removes_existing_legacy_index_even_with_narrow_glob(services, settings):
    (settings.sample_docs_dir / "legacy.py").write_text("SYNTHETIC legacy content", encoding="utf-8")
    (settings.sample_docs_dir / "medical.md").write_text("SYNTHETIC retained content", encoding="utf-8")
    services.demo.index_document("demo:legacy.py", "legacy.py", 1, "SYNTHETIC legacy content")
    result = services.demo.index_folder(glob="*.md")
    assert result["removed"] == 1 and result["files"] == 1
    found = services.demo.retrieve("content")
    assert found and all(doc.metadata["source"] == "medical.md" for doc in found)
    assert services.demo.collection.count() == len(services.demo.rows) == 1


def test_cleanup_removes_persisted_path_escape_without_reading_external_file(services, settings, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("PRIVATE", encoding="utf-8")
    services.demo.index_document("demo:unsafe", "../outside.md", 1, "old content")
    result = services.demo.index_folder()
    assert result["removed"] == 1 and result["files"] == 0
    assert services.demo.retrieve("old") == []
    assert outside.read_text(encoding="utf-8") == "PRIVATE"


def test_splitter_version_changes_content_hash_and_reindexes(services, provider, monkeypatch):
    corpus = services.archive
    corpus.index_document("a", "lab.txt", 1, "LDL 4.73 mmol/L.")
    old_ids = {row["id"] for row in corpus.rows}
    count = len(provider.calls)
    assert corpus.index_document("a", "lab.txt", 1, "LDL 4.73 mmol/L.")["unchanged"]
    assert len(provider.calls) == count
    monkeypatch.setattr("medical_ai.indexer.SPLITTER_VERSION", "next-structural-version")
    assert not corpus.index_document("a", "lab.txt", 1, "LDL 4.73 mmol/L.")["unchanged"]
    assert len(provider.calls) == count + 1
    assert not old_ids.intersection(row["id"] for row in corpus.rows)
    assert corpus.collection.count() == 1


def test_long_correction_chunks_are_bounded_and_each_remains_marked(services, settings):
    services.archive.index_document("a", "lab.txt", 1, "LDL 4.1 mmol/L", corrections=[
        {"id": "f", "name": "LDL", "valueText": "Synthetic correction statement. " * 40,
         "unit": "mmol/L", "reviewStatus": "CORRECTED"}
    ])
    corrections = [doc for doc in services.archive.documents if doc.metadata["userCorrection"]]
    assert len(corrections) > 1
    assert all(doc.page_content.startswith("[Пользовательское исправление; не цитата оригинала]")
               and len(doc.page_content) <= settings.chunk_size for doc in corrections)
