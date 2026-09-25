import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from evaluate_ingestion import compare  # noqa: E402
from evaluate_lab_ingestion import score_rows  # noqa: E402


def test_partial_gold_matching_is_one_to_one_and_keeps_type_errors():
    gold={'type':'LAB_RESULT','valueNumber':4.1,'unit':'mmol/L','assertionStatus':'CONFIRMED','provenance':{'sourceText':'LDL 4.1 mmol/L'}}
    actual={'type':'LAB_RESULT','valueNumber':4.1,'unit':'mmol/L','assertionStatus':'CONFIRMED','sourceText':'LDL 4.1 mmol/L'}
    assert compare([gold,gold],[actual])['matched'] == 1
    assert compare([gold],[{**actual,'type':'OBSERVATION'}])['matched'] == 0
    assert compare([gold],[{**actual,'valueNumber':1.4}])['matched'] == 0
    assert compare([gold],[{**actual,'assertionStatus':'SUSPECTED'}])['matched'] == 0


def test_lab_tuple_missing_fields_and_duplicates_are_errors():
    gold = [{'name': 'MCV', 'resultRaw': '74,2', 'unit': 'фл', 'referenceRaw': '80–100',
             'resultDate': '2026-06-18', 'specimenDate': '2026-06-17', 'subject': 'PATIENT',
             'sourceText': 'MCV | 74,2 | фл | 80–100'}]
    assert score_rows(gold, gold)['tp'] == 1
    duplicate = score_rows(gold, gold * 2)
    assert (duplicate['tp'], duplicate['fp'], duplicate['fn']) == (1, 1, 0)
    assert score_rows(gold, [{**gold[0], 'specimenDate': None}])['fn'] == 1
    wrong = score_rows(gold, [{**gold[0], 'resultRaw': '80'}])
    assert wrong['tp'] == 0 and wrong['fields']['resultRaw']['fp'] == 1
    assert score_rows(gold, [])['fn'] == 1


def test_lab_series_reprocesses_and_requires_new_job_and_extraction(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    import evaluate_lab_ingestion as runner
    docs, calls = {}, []

    def fake_request(base, route, payload=None):
        calls.append((route, payload))
        if route.startswith('/documents?'):
            return {'total': 0}
        if route == '/documents/note':
            assert set(payload) == {'title', 'text'}
            identity = str(len(docs) + 1)
            docs[identity] = {'id': identity, 'runs': 1}
            return {'id': identity, 'jobId': identity + '-1'}
        if route.endswith('/reprocess'):
            identity = route.split('/')[2]
            docs[identity]['runs'] += 1
            return {'id': identity, 'jobId': identity + '-' + str(docs[identity]['runs'])}
        if route.startswith('/jobs/'):
            return {'status': 'READY'}
        if route.endswith('/source-ir'):
            return {'content': {'sourceHash': 'synthetic'}}
        identity = route.split('/')[2]
        run_id = identity + '-' + str(docs[identity]['runs'])
        return {'id': identity, 'status': 'READY', 'latestJob': {'id': run_id},
                'extraction': {'id': run_id}, 'facts': []}

    monkeypatch.setattr(runner, 'request', fake_request)
    output = tmp_path / 'series.json'
    runner.run(SimpleNamespace(base='synthetic', output=output, split='development', repeats=3))
    report = json.loads(output.read_text())
    assert report['complete'] and len(report['results']) == 24
    assert all(row.get('newExtractionRun') and not row.get('error') for row in report['results'])
    assert sum(route == '/documents/note' for route, _ in calls) == 8
    assert sum(route.endswith('/reprocess') for route, _ in calls) == 16
