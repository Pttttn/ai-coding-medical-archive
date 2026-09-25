import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from evaluate_ingestion import compare  # noqa: E402


def test_partial_gold_matching_is_one_to_one_and_keeps_type_errors():
    gold={'type':'LAB_RESULT','valueNumber':4.1,'unit':'mmol/L','assertionStatus':'CONFIRMED','provenance':{'sourceText':'LDL 4.1 mmol/L'}}
    actual={'type':'LAB_RESULT','valueNumber':4.1,'unit':'mmol/L','assertionStatus':'CONFIRMED','sourceText':'LDL 4.1 mmol/L'}
    assert compare([gold,gold],[actual])['matched'] == 1
    assert compare([gold],[{**actual,'type':'OBSERVATION'}])['matched'] == 0
    assert compare([gold],[{**actual,'valueNumber':1.4}])['matched'] == 0
    assert compare([gold],[{**actual,'assertionStatus':'SUSPECTED'}])['matched'] == 0
