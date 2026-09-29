"""P0 set integrity, gold isolation and exact-tuple scoring. Mechanism tests, not an LLM evaluation."""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SET = ROOT / "evaluation/ingestion-p0-v1"
sys.path.insert(0, str(ROOT / "scripts"))
import p0_metrics as metrics  # noqa: E402


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


MANIFEST = json.loads((SET / "gold/manifest.json").read_text(encoding="utf-8"))


def test_set_meets_the_p0_size_and_split_gate():
    cases = MANIFEST["cases"]
    labs = [c for c in cases if c["type"] == "LAB_REPORT"]
    visits = [c for c in cases if c["type"] == "VISIT"]
    assert len(labs) == 12 and len(visits) == 12
    assert sum(len(c["rows"]) for c in labs) >= 120
    assert sum(len(c["statements"]) for c in visits) >= 80
    assert sum(c["split"] == "held-out" for c in cases) >= 8
    assert {c["format"] for c in cases} == {"txt", "md", "pdf"}
    for case in cases:
        original = SET / "originals" / case["originalFile"]
        assert hashlib.sha256(original.read_bytes()).hexdigest() == case["sha256"]


def test_gold_names_and_printed_values_are_in_the_originals():
    for case in MANIFEST["cases"]:
        if case["format"] == "pdf":
            continue  # PDF bytes are checked by hash; the text layer is what the pipeline must recover.
        text = (SET / "originals" / case["originalFile"]).read_text(encoding="utf-8")
        flat = " ".join(text.split())
        for row in case.get("rows", []):
            assert row["test"].split()[0] in text and row["result"] in text
        for statement in case.get("statements", []):
            assert statement["name"] in statement["sourceText"]
            assert " ".join(statement["sourceText"].split()) in flat


def test_gold_is_out_of_reach_of_extraction_and_indexing():
    # Application images copy only their own sources; app services do not mount evaluation/.
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "./evaluation" not in compose
    assert re.findall(r"(?m)^COPY (?!--from)(\S+)", (ROOT / "ai-service/Dockerfile").read_text()) == [
        "pyproject.toml", "medical_ai"]
    for directory in (ROOT / "ai-service/medical_ai", ROOT / "backend/src"):
        for path in directory.rglob("*.*"):
            if path.suffix in {".py", ".ts"}:
                assert "ingestion-p0" not in path.read_text(encoding="utf-8")


def test_generator_reproduces_the_text_originals_and_gold(tmp_path, monkeypatch):
    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not font.is_file():
        pytest.skip("Cyrillic font for synthetic PDF rendering is not installed")
    generator = module("p0_generator", "generate_ingestion_p0.py")
    monkeypatch.setattr(generator, "ROOT", tmp_path / "set")
    monkeypatch.setattr(sys, "argv", ["generate", "--font", str(font)])
    generator.main()
    with pytest.raises(SystemExit):
        generator.main()  # The frozen set is never overwritten.
    fresh = json.loads((tmp_path / "set/gold/manifest.json").read_text(encoding="utf-8"))
    for new, old in zip(fresh["cases"], MANIFEST["cases"], strict=True):
        assert {k: v for k, v in new.items() if k != "sha256"} == {k: v for k, v in old.items() if k != "sha256"}
        if new["format"] != "pdf":  # PDF bytes depend on the local font build.
            assert new["sha256"] == old["sha256"]


def lab(**changes):
    row = dict(test="Ферритин", result="<5,0", kind="NUMERIC", comparator="<", value="5.0", unit="мкг/л",
               reference="15–150", dates={"SPECIMEN": "2026-02-01"}, subject="PATIENT", page=1)
    return {**row, **changes}


def found(gold, **changes):
    return {**{k: v for k, v in gold.items() if k != "result"},
            "sourceText": f"| {gold['test']} | {gold['result']} | мкг/л | 15–150 |", **changes}


def test_lab_tuple_requires_every_field_and_counts_dangerous_values():
    gold = lab()
    assert metrics.score_lab([gold], [found(gold)])["tp"] == 1
    for change in [dict(comparator="="), dict(unit="нг/мл"), dict(reference=None), dict(subject="UNKNOWN"),
                   dict(dates={}), dict(page=2), dict(sourceText="| Железо | 6,1 |")]:
        assert metrics.score_lab([gold], [found(gold, **change)])["tp"] == 0, change
    wrong = metrics.score_lab([gold], [found(gold, comparator="=")])
    assert wrong["criticalValueErrors"] == 1 and wrong["fields"]["comparator"]["tp"] == 0
    assert wrong["fields"]["value"]["tp"] == 1
    duplicate = metrics.score_lab([gold], [found(gold), found(gold)])
    assert (duplicate["tp"], duplicate["fp"], duplicate["fn"]) == (1, 1, 0)
    missing = metrics.score_lab([gold], [])
    assert (missing["tp"], missing["fn"], missing["criticalValueErrors"]) == (0, 1, 0)


def visit(**changes):
    row = dict(name="диабет", kind="CONDITION", subject="FAMILY", assertion="CONFIRMED",
               medicationState="NOT_APPLICABLE", temporality="CURRENT",
               sourceText="У отца пациента диабет подтверждён.", page=1)
    return {**row, **changes}


def test_visit_tuple_source_and_promotions():
    gold = visit()
    assert metrics.score_visit([gold], [visit(sourceText="- У отца пациента  диабет подтверждён.")])["tp"] == 1
    assert metrics.score_visit([gold], [visit(sourceText="пациента диабет")])["tp"] == 1
    paragraph = visit(sourceText="У отца пациента диабет подтверждён. Сам пациент здоров.")
    assert metrics.score_visit([gold], [paragraph])["tp"] == 0
    promoted = metrics.score_visit([gold], [visit(subject="PATIENT")])
    assert promoted["tp"] == 0 and promoted["criticalPromotions"] == 1
    assert promoted["fields"]["subject"]["tp"] == 0 and promoted["fields"]["assertion"]["tp"] == 1
    assert promoted["classes"]["subject"]["FAMILY"] == {"tp": 0, "fp": 0, "fn": 1}
    medication = visit(name="Метформин", kind="MEDICATION", subject="PATIENT", assertion="UNKNOWN",
                       medicationState="NOT_STARTED", sourceText="Метформин назначен, не начат.")
    taking = metrics.score_visit([medication], [{**medication, "medicationState": "TAKING"}])
    assert taking["criticalPromotions"] == 1


def test_legacy_facts_are_scored_as_the_patients_without_missing_fields():
    fact = dict(type="LAB_RESULT", name="Ферритин", valueNumber=5.0, unit="мкг/л", eventDate="2026-02-01",
                assertionStatus="CONFIRMED", provenance=dict(pageNumber=None, sourceText="| Ферритин | <5,0 |"))
    rows = metrics.legacy_lab_rows([fact])
    assert rows[0]["subject"] == "PATIENT" and rows[0]["reference"] is None and rows[0]["value"] == "5"
    score = metrics.score_lab([lab()], rows)
    assert score["tp"] == 0 and score["fields"]["value"]["tp"] == 1 and score["criticalValueErrors"] == 0
    statements = metrics.legacy_statements([dict(fact, type="MEDICATION", name="Метформин",
                                                 assertionStatus="PRESCRIBED")])
    assert statements[0]["medicationState"] == "PRESCRIBED" and statements[0]["temporality"] is None


def test_summary_keeps_failures_and_separates_unmeasured_documents():
    rows = [dict(split="held-out", type="LAB_REPORT", expected=1, measured=True, reason="LAB_TABLE_PARSE_FAILED",
                 score=metrics.score_lab([lab()], []), seconds=1.0),
            dict(split="held-out", type="VISIT", expected=1, measured=False, reason="MODEL_REQUIRED",
                 score=metrics.score_visit([visit()], []), seconds=0.1)]
    summary = {(s["split"], s["type"]): s for s in metrics.summarize(rows)}
    held_lab = summary[("held-out", "LAB_REPORT")]
    assert (held_lab["fn"], held_lab["recall"], held_lab["reasons"]) == (1, 0.0, {"LAB_TABLE_PARSE_FAILED": 1})
    assert summary[("held-out", "VISIT")] == {"split": "held-out", "type": "VISIT", "repeat": 1,
                                             "documents": 1, "measured": 0, "notMeasured": 1}


def test_end_to_end_adapter_uses_stored_artifacts_and_keeps_failed_documents(monkeypatch):
    runner = module("p0_runner", "evaluate_ingestion_p0.py")
    case = next(c for c in MANIFEST["cases"] if c["id"] == "lab-03")
    gold = case["rows"][0]
    artifact = {"dates": [{"role": role, "iso": iso} for role, iso in gold["dates"].items()],
                "rows": [{"name": gold["test"], "result": {"kind": "NUMERIC", "comparator": gold["comparator"],
                                                           "numericValue": gold["value"]},
                          "unit": gold["unit"], "referenceRaw": gold["reference"], "subject": "PATIENT",
                          "source": {"pageIndex": 0}, "sourceText": f"{gold['test']} | {gold['result']}"}]}
    responses = {"/documents/upload": {"id": "d1", "jobId": "j1"}, "/jobs/j1": {"status": "READY"},
                 "/documents/d1": {"status": "READY", "extraction": {"id": "e1"}, "pages": [{"pageNumber": 1}],
                                   "laboratory": artifact, "visit": None, "facts": []}}
    monkeypatch.setattr(runner, "request", lambda base, route, *a, **k: responses[route])
    row = {"score": metrics.empty_score(case)}
    runner.api_case(type("Args", (), {"base": "http://x", "timeout": 5})(), case, row, {}, {})
    assert row["method"] == "lab" and row["score"]["tp"] == 1 and row["score"]["fn"] == len(case["rows"]) - 1
    responses["/jobs/j1"] = {"status": "FAILED"}
    responses["/documents/d1"] = {"status": "FAILED", "errorCode": "LAB_TABLE_PARSE_FAILED"}
    failed = {"score": metrics.empty_score(case)}
    runner.api_case(type("Args", (), {"base": "http://x", "timeout": 5})(), case, failed, {}, {})
    assert failed["reason"] == "LAB_TABLE_PARSE_FAILED" and failed["score"]["fn"] == len(case["rows"])
