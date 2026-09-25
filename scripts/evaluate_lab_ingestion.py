"""Frozen original-upload lab evaluation. Reports every planned repeat, including failures.

Gold is read only by the scorer, never sent to the archive. Does not alter/delete existing data.
"""
import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError

from evaluate_ingestion import request

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('resultKind', 'comparator', 'numericValue', 'name', 'resultRaw', 'unit', 'referenceRaw', 'resultDate', 'specimenDate', 'subject', 'sourceText')


def gold_rows(rows):
    result = []
    for row in rows:
        raw = row['resultRaw']
        comparator = next((c for c in ['<=', '>=', '≤', '≥', '<', '>', '='] if raw.startswith(c)), '')
        try:
            numeric = str(Decimal(raw[len(comparator):].replace(',', '.').replace('−', '-')))
            kind = 'NUMERIC'
            comparator = {'≤': '<=', '≥': '>='}.get(comparator, comparator) or '='
        except InvalidOperation:
            numeric, kind, comparator = None, 'QUALITATIVE', None
        result.append({**row, 'resultKind': kind, 'comparator': comparator, 'numericValue': numeric})
    return result


def score_rows(gold, actual):
    """Multiset exact tuple; duplicates are FP. Every expected row remains in denominator."""
    def key(row, fields=FIELDS):
        return tuple(row.get(f) for f in fields)
    expected = Counter(key(row) for row in gold)
    found = Counter(key(row) for row in actual)
    tp = sum((expected & found).values())
    fields = {}
    # Field scores are keyed by name+source, so swapping values across tests cannot pass.
    for field in FIELDS:
        identity = tuple(dict.fromkeys(('name', 'sourceText', field)))
        count = sum((Counter(key(r, identity) for r in gold) & Counter(key(r, identity) for r in actual)).values())
        fields[field] = {'tp': count, 'fp': len(actual) - count, 'fn': len(gold) - count}
    return {'tp': tp, 'fp': len(actual) - tp, 'fn': len(gold) - tp, 'fields': fields}


def annotation_rows(artifact):
    dates = {}
    for role in ['RESULT', 'SPECIMEN']:
        values = {d['iso'] for d in artifact.get('dates', []) if d['role'] == role}
        dates[role] = next(iter(values)) if len(values) == 1 else None
    return [{'resultKind': r['result']['kind'], 'comparator': r['result']['comparator'],
             'numericValue': r['result']['numericValue'], 'name': r['name'], 'resultRaw': r['result']['raw'], 'unit': r['unit'],
             'referenceRaw': r['referenceRaw'], 'resultDate': dates['RESULT'],
             'specimenDate': dates['SPECIMEN'], 'subject': r['subject'], 'sourceText': r['sourceText']}
            for r in artifact.get('rows', [])]


def legacy_coverage(gold, facts):
    """Separate scalar metric. Never mistakes missing structured fields for correct tuples."""
    unused, matched = set(range(len(facts))), 0
    for row in gold:
        try:
            value = Decimal(row['resultRaw'].replace(',', '.'))
        except InvalidOperation:
            continue
        for index in sorted(unused):
            fact = facts[index]
            if (fact['type'] == 'LAB_RESULT' and fact['name'] == row['name'] and fact.get('unit') == row['unit']
                    and fact.get('valueNumber') is not None and Decimal(str(fact['valueNumber'])) == value):
                unused.remove(index)
                matched += 1
                break
    return matched


def run(args):
    if args.output.exists():
        raise SystemExit('Refusing to overwrite a previous attempt.')
    if request(args.base, '/documents?pageSize=1&deleted=all')['total']:
        raise SystemExit('Requires an EMPTY dedicated SEED_ENABLED=false installation, including trash.')
    manifest_path = ROOT / 'evaluation/ingestion-labs-v1/manifest.json'
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    cases = [c for c in manifest['cases'] if args.split == 'all' or c['split'] == args.split]
    for case in cases:
        case['rows'] = gold_rows(case['rows'])
    # Validate the entire selected fixture set before any upload.
    for case in cases:
        if hashlib.sha256((manifest_path.parent / case['originalFile']).read_bytes()).hexdigest() != case['sha256']:
            raise SystemExit('Frozen fixture bytes differ from the manifest.')
    report = {'kind': 'original-upload-laboratory-series', 'createdAt': datetime.now(timezone.utc).isoformat(),
              'goldSha256': hashlib.sha256(raw_manifest).hexdigest(),
              'codeHashes': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in [
                  'scripts/evaluate_lab_ingestion.py', 'ai-service/medical_ai/extraction.py',
                  'ai-service/medical_ai/laboratory.py', 'ai-service/medical_ai/source_ir.py',
                  'ai-service/medical_ai/ollama.py', 'backend/src/laboratory.ts']},
              'plannedRepeats': args.repeats,
              'plannedCasesPerRepeat': len(cases), 'split': args.split, 'complete': False, 'results': [],
              'limitations': [manifest['goldReview'], manifest['scope'],
                              'Exact source-row tuple, not medical validation or numeric reference interpretation.',
                              'First repeat uploads originals; subsequent repeats explicitly reprocess the same documents. '
                              'New jobs/extraction IDs are required; not three independent fresh indexes.']}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def save():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    save()
    document_ids, extraction_ids = {}, {}
    for repeat in range(1, args.repeats + 1):
        for case in cases:
            row = {'case': case['id'], 'split': case['split'], 'repeat': repeat, 'sha256': case['sha256'],
                   'expected': len(case['rows']), 'tuple': score_rows(case['rows'], [])}
            started = time.monotonic()
            try:
                raw = (manifest_path.parent / case['originalFile']).read_bytes()
                if case['id'] in document_ids:
                    queued = request(args.base, '/documents/' + document_ids[case['id']] + '/reprocess', {})
                else:
                    queued = request(args.base, '/documents/note', {'title': 'SYNTHETIC lab ingestion', 'text': raw.decode('utf-8')})
                    document_ids[case['id']] = queued['id']
                deadline = time.monotonic() + 600
                while True:
                    job = request(args.base, '/jobs/' + queued['jobId'])
                    if job['status'] in {'READY', 'FAILED', 'SUPERSEDED'} or time.monotonic() > deadline:
                        break
                    time.sleep(0.5)
                doc = request(args.base, '/documents/' + queued['id'])
                if job['status'] != 'READY' or doc['latestJob']['id'] != queued['jobId']:
                    row['status'] = job['status']
                    raise RuntimeError('ProcessingJobDidNotComplete')
                row['status'] = doc['status']
                extraction = doc.get('extraction') or {}
                if not extraction.get('id') or extraction['id'] == extraction_ids.get(case['id']):
                    raise RuntimeError('NewExtractionRunRequired')
                extraction_ids[case['id']] = extraction['id']
                row['newExtractionRun'] = True
                row['recipe'] = {k: extraction.get(k) for k in ['model', 'modelDigest', 'promptVersion', 'schemaVersion', 'parserVersion']}
                row['profile'] = doc.get('extractionProfile', 'legacy')
                if doc['status'] == 'READY':
                    ir = request(args.base, '/documents/' + doc['id'] + '/source-ir')['content']
                    row['sourceHash'] = ir['sourceHash']
                    artifact = doc.get('laboratory')
                    row['artifactPresent'] = artifact is not None
                    row['legacyScalarMatches'] = legacy_coverage(case['rows'], doc['facts'])
                    if artifact is not None:
                        if artifact['sourceIRHash'] != ir['irHash'] or artifact['sourceHash'] != ir['sourceHash']:
                            raise ValueError('ArtifactSourceMismatch')
                        for r in artifact['rows']:
                            span = r['source']
                            source = ir['pages'][span['pageIndex']]['text'].encode()[span['startByte']:span['endByte']].decode()
                            if source != r['sourceText']:
                                raise ValueError('RowSourceMismatch')
                        row['verifiedSourceRows'] = len(artifact['rows'])
                        row['tuple'] = score_rows(case['rows'], annotation_rows(artifact))
                        row['candidateRows'] = artifact['candidateRows']
                        row['issues'] = dict(Counter(i['code'] for i in artifact['issues']))
                        # Compare semantic rows across repeats without document-specific IDs/hash.
                        semantic = json.dumps(annotation_rows(artifact), sort_keys=True, ensure_ascii=False).encode()
                        row['semanticHash'] = hashlib.sha256(semantic).hexdigest()
                    row['actualFacts'] = len(doc['facts'])
                else:
                    row['error'] = doc.get('errorCode') or 'PROCESSING_TIMEOUT'
            except HTTPError as exc:
                row['error'], row['httpStatus'] = 'HTTPError', exc.code
            except Exception as exc:
                row['error'] = type(exc).__name__
            row['seconds'] = round(time.monotonic() - started, 2)
            report['results'].append(row)
            save()
            print(f"repeat={repeat} case={case['id']} status={row.get('status')} tp={row['tuple']['tp']}/{row['expected']} error={row.get('error')}", flush=True)
    report['complete'] = True
    save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--split', choices=['development', 'held-out', 'all'], default='development')
    parser.add_argument('--repeats', type=int, choices=range(1, 11), default=3)
    run(parser.parse_args())
