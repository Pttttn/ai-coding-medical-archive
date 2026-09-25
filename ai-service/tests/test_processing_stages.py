import pytest
from fastapi.testclient import TestClient

from medical_ai.main import create_app
from medical_ai.ollama import Ollama
from medical_ai.parsing import LAB_TABLE_PARSER_VERSION
from medical_ai.recipe import RECIPE_VERSION, _hashed, parse_recipe, processing_recipe
from medical_ai.source_ir import canonical_hash
from test_pdf_lab_tables import synthetic_report

HEADERS = {"X-Internal-Token": "test-secret"}
NOTE = "Синтетический визит.\n\nLDL 4.1 mmol/L. Не принимает статины."


def without_hash(recipe):
    return {k: v for k, v in recipe.items() if k != "recipeHash"}


def test_parse_stage_is_deterministic_and_calls_no_model(services):
    with TestClient(create_app(services)) as client:
        first = client.post("/internal/parse", headers=HEADERS,
                            json={"documentId": "a", "version": 1, "title": "note", "text": NOTE}).json()
        second = client.post("/internal/parse", headers=HEADERS,
                             json={"documentId": "a", "version": 1, "title": "note", "text": NOTE}).json()
    assert first == second
    assert not services.provider.calls
    assert first["sourceIR"]["pages"] == [{"pageNumber": None, "text": NOTE}]
    assert first["text"] == NOTE
    recipe = first["parseRecipe"]
    assert recipe["recipeVersion"] == RECIPE_VERSION and recipe["parserVersion"] == "user-text-v1"
    assert recipe["recipeHash"] == canonical_hash(without_hash(recipe))


def test_extraction_from_stored_ir_matches_single_call_and_records_full_recipe(services):
    with TestClient(create_app(services)) as client:
        parsed = client.post("/internal/parse", headers=HEADERS,
                             json={"documentId": "a", "version": 1, "title": "note", "text": NOTE}).json()
        staged = client.post("/internal/process", headers=HEADERS,
                             json={"documentId": "a", "version": 1, "title": "note", "sourceIR": parsed["sourceIR"]}).json()
        direct = client.post("/internal/process", headers=HEADERS,
                             json={"documentId": "a", "version": 1, "title": "note", "text": NOTE}).json()
    assert staged == direct
    assert staged["sourceIR"] == parsed["sourceIR"] and staged["text"] == NOTE
    recipe = staged["processingRecipe"]
    assert recipe["recipeHash"] == canonical_hash(without_hash(recipe))
    assert recipe["parse"] == parsed["parseRecipe"]
    assert recipe["method"] == "legacy" and recipe["annotation"]["promptVersion"] == "medical-extract-v4"
    assert recipe["index"]["chunkerVersion"] and recipe["index"]["embeddingModel"] == services.settings.embedding_model


def test_stored_pdf_ir_is_extracted_without_the_original_file(services):
    services.settings.extraction_profile = "lab-rows-v1"
    services.settings.upload_dir.mkdir()
    path = services.settings.upload_dir / "synthetic.pdf"
    synthetic_report(path)
    with TestClient(create_app(services)) as client:
        parsed = client.post("/internal/parse", headers=HEADERS,
                             json={"documentId": "lab", "version": 1, "title": "lab", "filePath": str(path)}).json()
        path.unlink()
        result = client.post("/internal/process", headers=HEADERS,
                             json={"documentId": "lab", "version": 1, "title": "lab", "sourceIR": parsed["sourceIR"]})
    assert result.status_code == 200
    body = result.json()
    assert parsed["parseRecipe"]["parserVersion"] == LAB_TABLE_PARSER_VERSION
    assert body["processingRecipe"]["parse"] == parsed["parseRecipe"]
    assert body["processingRecipe"]["method"] == "lab" and body["processingRecipe"]["model"] is None
    assert body["laboratory"]["candidateRows"] == 3
    assert not services.provider.calls


@pytest.mark.parametrize("mutate", [
    lambda ir: ir["blocks"][0].update(normalizedText="invented"),
    lambda ir: ir["pages"][0].update(text=ir["pages"][0]["text"].replace("4.1", "1.4")),
    lambda ir: ir.update(documentId="other"),
    lambda ir: ir.update(irHash="0" * 64),
])
def test_tampered_or_foreign_ir_is_rejected_before_any_model_call(services, mutate):
    with TestClient(create_app(services)) as client:
        ir = client.post("/internal/parse", headers=HEADERS,
                         json={"documentId": "a", "version": 1, "title": "note", "text": NOTE}).json()["sourceIR"]
        mutate(ir)
        response = client.post("/internal/process", headers=HEADERS,
                               json={"documentId": "a", "version": 1, "title": "note", "sourceIR": ir})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SOURCE_IR_INVALID"
    assert not services.provider.calls


def test_ambiguous_stage_inputs_are_rejected(services):
    with TestClient(create_app(services)) as client:
        ir = client.post("/internal/parse", headers=HEADERS,
                         json={"documentId": "a", "version": 1, "title": "note", "text": NOTE}).json()["sourceIR"]
        both = client.post("/internal/process", headers=HEADERS,
                           json={"documentId": "a", "version": 1, "title": "note", "text": NOTE, "sourceIR": ir})
        parse_ir = client.post("/internal/parse", headers=HEADERS,
                               json={"documentId": "a", "version": 1, "title": "note", "sourceIR": ir})
    assert both.json()["detail"]["code"] == "INVALID_INPUT"
    assert parse_ir.json()["detail"]["code"] == "INVALID_INPUT"


class DecodingProvider:
    """Real generation options of the Ollama adapter without a network call."""
    def __init__(self, settings):
        self.settings = settings

    def health(self):
        return {"models": [{"name": self.settings.llm_model, "digest": "sha256:model"},
                           {"name": self.settings.embedding_model + ":latest", "digest": "sha256:embed"}]}

    def generation_options(self, task):
        return Ollama.generation_options(self, task)


def test_recipe_hash_changes_with_every_result_affecting_setting(settings):
    def recipe(parser, method, current=settings):
        return processing_recipe(current, DecodingProvider(current), parser, method)
    base = recipe("user-text-v1", "legacy")
    assert base["modelDigest"] == "sha256:model" and base["index"]["embeddingDigest"] == "sha256:embed"
    assert base["generationOptions"]["num_predict"] == settings.llm_extraction_max_tokens
    assert recipe("user-text-v1", "lab")["generationOptions"] is None
    assert recipe("user-text-v1", "legacy") == base
    variants = [recipe("pypdf-x/text-v1", "legacy"), recipe("user-text-v1", "visit")]
    for change in [{"llm_model": "other"}, {"llm_seed": 7}, {"llm_extraction_max_tokens": 1024},
                   {"extraction_max_facts_per_batch": 4}, {"chunk_size": 800}, {"embedding_model": "other-embed"}]:
        variants.append(recipe("user-text-v1", "legacy", settings.model_copy(update=change)))
    assert len({base["recipeHash"], *(v["recipeHash"] for v in variants)}) == len(variants) + 1
    assert parse_recipe("user-text-v1")["recipeHash"] != parse_recipe("pypdf-x/text-v1")["recipeHash"]


def test_recipe_rejects_values_without_a_cross_language_canonical_form():
    with pytest.raises(ValueError):
        _hashed({"temperature": 0.1})


def test_recipe_contract_fixture_hashes_match_python():
    import json
    from pathlib import Path
    contracts = Path(__file__).resolve().parents[2] / "contracts"
    fixture = json.loads((contracts / "processing-recipe-v1.synthetic.json").read_text())
    ir = json.loads((contracts / fixture["sourceIR"]).read_text())
    assert fixture["parseRecipe"] == parse_recipe(ir["parserVersion"])
    for recipe in (fixture["parseRecipe"], fixture["processingRecipe"], fixture["processingRecipe"]["parse"]):
        assert recipe["recipeHash"] == canonical_hash(without_hash(recipe))
