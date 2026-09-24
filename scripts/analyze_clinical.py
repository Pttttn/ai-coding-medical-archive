"""Publish content-free clinical benchmark aggregates; retain raw answers only locally."""
import argparse
import hashlib
import json
from pathlib import Path


def aggregate(profile):
    runs = []
    by_case = {}
    for run in profile['runs']:
        rows = []
        for result in run['results']:
            response = result.get('response', {})
            row = {'id': result['id'], 'passed': bool(result.get('passed')),
                   'evidencePass': bool(result.get('evidencePass', result.get('passed'))),
                   'coverageComplete': response.get('coverage', {}).get('complete', False),
                   'seconds': result['seconds'], 'sourceCount': len(response.get('sources', [])),
                   'missingEvidenceCount': result.get('missingEvidenceCount', 0),
                   'failedBatches': response.get('coverage', {}).get('failedBatches'),
                   'toolCalls': len(result.get('tools', [])), 'generationCalls': result.get('generationCalls'),
                   'answerSha256': hashlib.sha256(response.get('answer', '').encode()).hexdigest()}
            if 'error' in result:
                row['error'] = result['error']
            rows.append(row)
            by_case.setdefault(row['id'], []).append(row)
        runs.append({'run': run['run'], 'total': len(rows), 'passed': sum(r['passed'] for r in rows),
                     'evidencePass': sum(r['evidencePass'] for r in rows),
                     'seconds': round(sum(r['seconds'] for r in rows), 2), 'results': rows})
    return {'model': profile.get('model'), 'strategy': profile.get('strategy'), 'runs': runs,
            'stableEvidenceResults': sum(len({r['evidencePass'] for r in rows}) == 1 and len(rows) == len(runs) for rows in by_case.values()),
            'stableAnswers': sum(len({r['answerSha256'] for r in rows}) == 1 and len(rows) == len(runs) and all('error' not in r for r in rows) for rows in by_case.values()),
            'allRunsEvidencePass': sum(all(r['evidencePass'] for r in rows) and len(rows) == len(runs) for rows in by_case.values()),
            'caseCount': len(by_case)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('inputs', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    experiments = []
    for path in args.inputs:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        allowed = ['kind', 'createdAt', 'seedSha256', 'questionsSha256', 'modelDigests', 'referenceDate', 'parameters', 'engineSha256', 'environment', 'index', 'indexMode', 'plannedRuns', 'plannedProfiles', 'selectedCases', 'providerMetadata']
        entry = {k: data[k] for k in allowed if k in data}
        profiles = data.get('profiles', [data])
        expected_cases = len(data.get('selectedCases', [])) or max(len(r['results']) for p in profiles for r in p['runs'])
        complete = (len(profiles) == len(data.get('plannedProfiles', profiles)) and
                    all(len(p['runs']) == data.get('plannedRuns', len(p['runs'])) and
                        all(len(r['results']) == expected_cases for r in p['runs']) for p in profiles))
        entry['complete'] = complete
        entry['expectedCaseCount'] = expected_cases
        entry['profiles'] = [aggregate(p) for p in profiles]
        experiments.append(entry)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'description': 'Aggregate metrics only; one-run stability counts are not evidence of repeatability.', 'experiments': experiments}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    for experiment in experiments:
        for profile in experiment['profiles']:
            print(profile['model'], profile['strategy'], [(r['evidencePass'], r['total']) for r in profile['runs']])


if __name__ == '__main__':
    main()
