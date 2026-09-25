import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from visit_semantic_metrics import evaluate_semantics, summarize_semantics  # noqa: E402


def row(name, quote, **changes):
    return {
        "name": name,
        "sourceText": quote,
        "kind": "CONDITION",
        "subject": "PATIENT",
        "assertion": "CONFIRMED",
        "medicationState": "NOT_APPLICABLE",
        "temporality": "CURRENT",
        **changes,
    }


def test_semantics_does_not_penalize_shorter_real_evidence_as_wrong_status():
    text = "У пациента диабет подтверждён. Нужна сверка."
    g = row("диабет", text)
    a = {**g, "sourceText": "У пациента диабет подтверждён."}
    score = evaluate_semantics([g], [a], text)
    assert score["tp"] == 1 and score["exactQuotes"] == 0
    assert score["differences"] == [{"goldIndex": 0, "fields": ["sourceText"]}]


def test_same_name_other_subject_or_event_cannot_mask_a_promotion():
    g = [
        row("диабет", "У отца диабет подтверждён.", subject="FAMILY"),
        row("диабет", "У пациента диабет не подтверждён.", assertion="NOT_CONFIRMED"),
    ]
    text = " ".join(r["sourceText"] for r in g)
    wrong = {**g[1], "assertion": "CONFIRMED"}
    score = evaluate_semantics(g, [wrong], text)
    assert score["tp"] == 0 and score["criticalPromotions"] == 1
    # A whole paragraph covering both mentions is ambiguous, never matched by convenient status.
    ambiguous = {**g[0], "sourceText": text}
    assert evaluate_semantics(g, [ambiguous], text)["ambiguousActual"] == 1


def test_unmatched_and_withheld_records_stay_in_denominator():
    g = row("болезнь", "болезнь не исключена.", assertion="SUSPECTED")
    score = evaluate_semantics([g], [], g["sourceText"])
    assert score["fn"] == 1
    summary = summarize_semantics([{"repeat": 1, "semantic": score}])[0]
    assert summary["macroF1"]["assertion"] == 0


def test_fake_quote_or_wrong_utf8_span_cannot_get_semantic_credit():
    g = row("болезнь", "У пациента болезнь.")
    a = {**g, "source": {"pageIndex": 0, "startByte": 1, "endByte": len(g["sourceText"].encode())}}
    assert evaluate_semantics([g], [a], g["sourceText"])["tp"] == 0
    a = {**g, "sourceText": "болезнь установлена"}
    assert evaluate_semantics([g], [a], g["sourceText"])["tp"] == 0


def test_new_fixture_manifest_is_frozen_and_gold_requires_human_review():
    path = ROOT / "evaluation/ingestion-visits-v2"
    m = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    assert len(m["cases"]) == 10 and sum(len(c["statements"]) for c in m["cases"]) == 60
    assert sum(c["split"] == "held-out" for c in m["cases"]) == 4
    assert "pending" in m["goldReview"]
    for c in m["cases"]:
        raw = (path / c["originalFile"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == c["sha256"]
        assert all(
            r["name"] in r["sourceText"] and raw.decode().count(r["sourceText"]) == 1 for r in c["statements"]
        )


def test_wrong_page_and_incomplete_span_do_not_fall_back_to_quote():
    g = row("disease", "disease confirmed")
    for span in ({"pageIndex": 1, "startByte": 0, "endByte": 17}, {}):
        assert evaluate_semantics([g], [{**g, "source": span}], g["sourceText"])["tp"] == 0
