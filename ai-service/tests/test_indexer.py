import os

import pytest

from medical_ai.errors import ServiceError
from medical_ai.indexer import Corpus, source_of
from medical_ai.schemas import Page


@pytest.mark.parametrize("extension", ["md", "txt", "py", "js", "ts", "json", "yaml"])
def test_seven_required_formats_are_data(services, settings, provider, extension):
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

