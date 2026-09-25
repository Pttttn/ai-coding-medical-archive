import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "visit_evaluation", ROOT / "scripts/evaluate_visit_ingestion.py"
)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def statement(**changes):
    return dict(
        name="diabetes",
        kind="CONDITION",
        subject="FAMILY",
        assertion="CONFIRMED",
        medicationState="NOT_APPLICABLE",
        temporality="HISTORICAL",
        sourceText="Mother had diabetes.",
        **changes,
    )


def test_scorer_missing_duplicate_and_subject_promotion():
    gold = statement()
    missing = evaluation.score([gold], [])
    assert (missing["tp"], missing["fn"]) == (0, 1)
    duplicate = evaluation.score([gold], [gold, gold])
    assert (duplicate["tp"], duplicate["fp"]) == (1, 1)
    changed = {**gold, "subject": "PATIENT"}
    assert evaluation.score([gold], [changed])["criticalPromotions"] == 1
    assert evaluation.score([gold], [changed])["tp"] == 0


def test_not_started_is_not_taking_and_quote_narrowing_does_not_pass():
    gold = {
        **statement(),
        "kind": "MEDICATION",
        "name": "drug",
        "subject": "PATIENT",
        "assertion": "UNKNOWN",
        "medicationState": "NOT_STARTED",
    }
    assert evaluation.score([gold], [{**gold, "medicationState": "TAKING"}])["criticalPromotions"] == 1
    assert evaluation.score([gold], [{**gold, "sourceText": "drug"}])["tp"] == 0


def test_failed_documents_stay_in_repeat_macro_f1_denominator():
    g = statement()
    rows = [
        {"repeat": 1, "status": "READY", "score": evaluation.score([g], [g])},
        {"repeat": 1, "status": "FAILED", "error": "Failure", "score": evaluation.score([g], [])},
    ]
    summary = evaluation.summarize(rows)[0]
    assert summary["fn"] == 1 and summary["ready"] == 1
    assert summary["macroF1"]["subject"] == 0.666667
