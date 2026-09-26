import pytest
from fastapi.testclient import TestClient

from medical_ai.main import create_app
from test_archive_qa import evidence_provider

OLD, NEW = "LDL 4.7 mmol/L old revision.", "LDL 3.1 mmol/L new revision."


def texts(chunks):
    return sorted(d.page_content for d in chunks)


def test_staged_revision_is_invisible_until_its_snapshot_is_requested(services):
    archive = services.archive
    archive.index_document("d", "d.md", 1, OLD, revision_id="A")
    staged = archive.index_document("d", "d.md", 2, NEW, revision_id="B")
    assert staged["revisionId"] == "B" and staged["documentChunks"] == 1
    assert texts(archive.visible(["d"], {"d": "A"})) == [OLD]
    assert texts(archive.visible(["d"], {"d": "B"})) == [NEW]
    assert texts(archive.retrieve("LDL", 5, ["d"], revisions={"d": "A"})) == [OLD]
    assert texts(archive.retrieve("LDL", 5, ["d"], revisions={"d": "B"})) == [NEW]
    assert archive.prune("d", "B")["removedChunks"] == 1
    assert archive.visible(["d"], {"d": "A"}) == []
    assert texts(archive.visible(["d"], {"d": "B"})) == [NEW]


def test_legacy_and_revision_chunks_never_substitute_for_each_other(services):
    archive = services.archive
    archive.index_document("d", "d.md", 1, OLD)
    archive.index_document("d", "d.md", 2, NEW, revision_id="B")
    assert texts(archive.visible(["d"], {"d": None})) == [OLD]
    assert texts(archive.visible(["d"], {"d": "B"})) == [NEW]
    assert archive.visible(["d"], {"d": "missing"}) == []
    archive.prune("d", "B")
    assert archive.visible(["d"], {"d": None}) == []


def test_restaging_one_revision_is_idempotent_and_leaves_others(services):
    archive = services.archive
    archive.index_document("d", "d.md", 1, OLD, revision_id="A")
    first = archive.index_document("d", "d.md", 2, NEW, revision_id="B")
    again = archive.index_document("d", "d.md", 2, NEW, revision_id="B")
    assert again["unchanged"] and again["documentChunks"] == first["documentChunks"]
    corrected = archive.index_document("d", "d.md", 2, NEW, revision_id="B", corrections=[
        {"id": "f", "name": "LDL", "valueText": None, "valueNumber": 3.0, "unit": "mmol/L", "reviewStatus": "CORRECTED"}])
    assert not corrected["unchanged"] and corrected["documentChunks"] == 2
    assert texts(archive.visible(["d"], {"d": "A"})) == [OLD]
    assert archive.status()["files"] == 1
    archive.remove("d")
    assert archive.visible(["d"], {"d": "A"}) == archive.visible(["d"], {"d": "B"}) == []


def test_archive_answer_reads_only_the_active_revision_and_reports_missing_one(services, provider):
    evidence_provider(provider)
    archive = services.archive
    archive.index_document("d", "d.md", 1, OLD, revision_id="A")
    archive.index_document("d", "d.md", 2, NEW, revision_id="B")
    answer = services.archive_rag.ask("LDL", ["d"], [{"documentId": "d", "documentDate": None, "processingRevisionId": "A"}])
    assert answer["sources"] and all("old revision" in s["text"] for s in answer["sources"])
    missing = services.archive_rag.ask("LDL", ["d"], [{"documentId": "d", "documentDate": None, "processingRevisionId": "C"}])
    assert missing["sources"] == [] and missing["coverage"]["missingIndexedDocuments"] == 1


def test_internal_index_and_prune_contract(services):
    headers = {"X-Internal-Token": "test-secret"}
    with TestClient(create_app(services)) as client:
        assert client.post("/internal/prune", json={"documentId": "d", "keepRevisionId": "B"}).status_code == 401
        staged = client.post("/internal/index", headers=headers, json={
            "documentId": "d", "title": "d.md", "version": 1, "text": NEW, "revisionId": "B"}).json()
        assert staged["revisionId"] == "B" and staged["documentChunks"] == 1 and len(staged["contentHash"]) == 64
        assert client.post("/internal/prune", headers=headers,
                           json={"documentId": "d", "keepRevisionId": "B"}).json() == {"ok": True, "removedChunks": 0}


class DigestProvider:
    """Deterministic embeddings with an Ollama-like model list whose embedding digest can change."""
    def __init__(self, inner, settings):
        self.inner, self.settings, self.digest, self.up = inner, settings, "sha256:embed-a", True

    def embed(self, texts):
        return self.inner.embed(texts)

    def health(self):
        if not self.up:
            return {"ollama": False, "ready": False, "models": []}
        return {"ollama": True, "models": [{"name": self.settings.embedding_model + ":latest", "digest": self.digest}]}


def test_staged_revision_reports_the_index_settings_it_used(services):
    from medical_ai.errors import ServiceError
    from medical_ai.recipe import processing_recipe
    archive = services.archive
    provider = archive.provider = DigestProvider(archive.provider, services.settings)
    first = archive.index_document("d", "d.md", 1, NEW, revision_id="B")
    assert first["indexSettings"] == processing_recipe(services.settings, provider, "user-text-v1", "lab")["index"]
    assert first["indexSettings"]["embeddingDigest"] == "sha256:embed-a"
    provider.digest = "sha256:embed-b"
    changed = archive.index_document("d", "d.md", 1, NEW, revision_id="B")
    assert not changed.get("unchanged") and changed["indexSettings"]["embeddingDigest"] == "sha256:embed-b"
    assert changed["contentHash"] != first["contentHash"]
    provider.up = False
    with pytest.raises(ServiceError) as error:
        archive.index_document("d", "d.md", 1, NEW, revision_id="B")
    assert error.value.code == "EMBEDDING_UNAVAILABLE"
    assert texts(archive.visible(["d"], {"d": "B"})) == [NEW]
    assert archive.index_document("d", "d.md", 1, OLD)["indexSettings"] is None


def test_indexer_refuses_to_stage_a_revision_with_settings_other_than_its_recipe(services):
    from medical_ai.errors import ServiceError
    archive = services.archive
    provider = archive.provider = DigestProvider(archive.provider, services.settings)
    expected = archive.index_document("d", "d.md", 1, OLD, revision_id="A")["indexSettings"]
    provider.digest = "sha256:embed-b"
    with pytest.raises(ServiceError) as error:
        archive.index_document("d", "d.md", 2, NEW, revision_id="A", expected_settings=expected)
    assert error.value.code == "INDEX_RECIPE_MISMATCH"
    assert texts(archive.visible(["d"], {"d": "A"})) == [OLD]
    headers = {"X-Internal-Token": "test-secret"}
    with TestClient(create_app(services)) as client:
        body = {"documentId": "d", "title": "d.md", "version": 2, "text": NEW, "revisionId": "A"}
        refused = client.post("/internal/index", headers=headers, json={**body, "expectedIndexSettings": expected})
        assert refused.status_code == 409 and refused.json()["detail"]["code"] == "INDEX_RECIPE_MISMATCH"
        current = {**expected, "embeddingDigest": "sha256:embed-b"}
        staged = client.post("/internal/index", headers=headers, json={**body, "expectedIndexSettings": current}).json()
    assert staged["indexSettings"] == current
    assert texts(archive.visible(["d"], {"d": "A"})) == [NEW]
