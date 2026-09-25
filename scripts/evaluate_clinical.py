"""Repeat actual user-facing API questions against the synthetic clinical seed only."""
import argparse
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def request(base, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base.rstrip('/') + path, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=600) as response:
        return json.load(response)


def assess(case, answer, seed_ids):
    normalized = ' '.join(answer.get('answer', '').casefold().split())
    missing = [s for s in case['required'] if s.casefold() not in normalized]
    sources = answer.get('sources', [])
    valid = all(s.get('documentId') in seed_ids for s in sources)
    source_ids = {s.get('documentId') for s in sources}
    missing_rows = [e for e in case.get('expectedEvidence', [])
                    if e['quote'].casefold() not in normalized or e['documentId'] not in source_ids]
    expected_abstain = case.get('abstain', False)
    evidence_pass = (not missing and not missing_rows and valid
                     and bool(answer.get('insufficientContext')) == expected_abstain
                     and (bool(sources) != expected_abstain))
    complete = answer.get('coverage', {}).get('complete') is True
    return {'id': case['id'], 'passed': bool(evidence_pass and complete),
            'evidencePass': bool(evidence_pass), 'coverageComplete': complete,
            'missing': missing, 'missingEvidenceCount': len(missing_rows), 'response': answer}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:3000/api')
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--cases', nargs='+', help='Optional IDs; report declares selected subset')
    parser.add_argument('--output', type=Path, default=ROOT / '.local-evaluation/clinical.json')
    args = parser.parse_args()
    if args.runs < 1:
        parser.error('--runs must be positive')
    if args.output.exists():
        parser.error('Use a new output path to retain every attempt.')
    seed_bytes = (ROOT / 'seed/clinical/records.json').read_text(encoding='utf-8').encode()
    seed_ids = {r['id'] for r in json.loads(seed_bytes)}
    docs = request(args.base, '/documents?pageSize=100')['items']
    if {d['id'] for d in docs} != seed_ids or any(not d.get('isSeed') or d['status'] != 'READY' for d in docs):
        raise SystemExit('Requires exactly the READY synthetic clinical seed; refusing to evaluate personal/mixed archive.')
    cases_bytes = (ROOT / 'evaluation/clinical_questions.json').read_text(encoding='utf-8').encode()
    cases = json.loads(cases_bytes)['cases']
    if args.cases:
        if set(args.cases) - {c['id'] for c in cases}:
            parser.error('Unknown case ID')
        cases = [c for c in cases if c['id'] in args.cases]
    report = {'createdAt': datetime.now(timezone.utc).isoformat(), 'seedSha256': hashlib.sha256(seed_bytes).hexdigest(),
              'questionsSha256': hashlib.sha256(cases_bytes).hexdigest(), 'health': request(args.base, '/health'),
              'plannedRuns': args.runs, 'kind': 'real-private-archive-api', 'selectedCases': [c['id'] for c in cases], 'runs': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for run in range(1, args.runs + 1):
        rows = []
        report['runs'].append({'run': run, 'results': rows})
        for case in cases:
            started = time.monotonic()
            try:
                payload = {k: case[k] for k in ('question', 'dateFrom', 'dateTo') if k in case}
                answer = request(args.base, '/ask', payload)
                row = assess(case, answer, seed_ids)
            except Exception as exc:
                # Only exception class: no URLs, tokens or unexpected server content in aggregate logs.
                row = {'id': case['id'], 'passed': False, 'error': type(exc).__name__}
            row['seconds'] = round(time.monotonic() - started, 2)
            rows.append(row)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print(f"run={run} case={case['id']} passed={row['passed']} seconds={row['seconds']}", flush=True)
    scores = [sum(row['passed'] for row in run['results']) for run in report['runs']]
    print(f'Per-run scores: {scores}/{len(cases)}; all attempts retained in local output.')
    return 0 if all(score == len(cases) for score in scores) else 1


if __name__ == '__main__':
    raise SystemExit(main())
