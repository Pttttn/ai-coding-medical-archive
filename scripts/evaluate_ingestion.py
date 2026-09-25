"""Development ingestion baseline: original uploads, never seed-imported predictions.

Existing hand-authored seed facts are a partial development gold only. Extra
extractions are not automatically false positives; this is not a held-out score.
"""
import argparse
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def request(base, route, payload=None, data=None, content_type=None):
    if payload is not None:
        data, content_type = json.dumps(payload).encode(), 'application/json'
    req = urllib.request.Request(base.rstrip('/') + '/api' + route, data=data,
                                 headers={'Content-Type': content_type} if content_type else {})
    with urllib.request.urlopen(req, timeout=600) as response:
        return json.load(response)


def norm(text):
    return ' '.join((text or '').casefold().split())


def compare(expected, actual):
    """One-to-one partial-gold coverage; does not pretend to measure precision."""
    unused = set(range(len(actual)))
    matched = 0
    for gold in expected:
        quote = norm(gold['provenance']['sourceText'])
        for index in sorted(unused):
            found = actual[index]
            source = norm(found.get('sourceText'))
            if (source and quote and (source in quote or quote in source)
                and found['type'] == gold['type']
                and found['assertionStatus'] == gold.get('assertionStatus', 'UNKNOWN')
                and (gold.get('valueNumber') is None or found.get('valueNumber') == gold['valueNumber'])
                and (gold.get('unit') is None or norm(found.get('unit')) == norm(gold['unit']))):
                unused.remove(index)
                matched += 1
                break
    return {'expected': len(expected), 'matched': matched, 'actual': len(actual), 'unmatchedActual': len(unused)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, help='Dedicated empty SEED_ENABLED=false installation only')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Refusing to overwrite an earlier attempt.')
    existing = request(args.base, '/documents?pageSize=1&deleted=all')
    if existing['total']:
        parser.error('Requires an empty dedicated archive, including trash. Never runs against an existing personal archive.')
    manifest = ROOT / 'seed/clinical/records.json'
    records = json.loads(manifest.read_text(encoding='utf-8'))
    report = {'kind': 'original-ingestion-development-baseline', 'createdAt': datetime.now(timezone.utc).isoformat(),
              'goldKind': 'partial development seed annotations, used only by scorer; not held-out',
              'goldSha256': hashlib.sha256(manifest.read_text(encoding='utf-8').encode()).hexdigest(),
              'plannedCases': len(records), 'complete': False, 'results': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    for case in records:
        row = {'fixture': case['originalFile'], 'expected': len(case['facts'])}
        started = time.monotonic()
        try:
            path = manifest.parent / case['originalFile']
            raw = path.read_bytes()
            row['originalSha256'] = hashlib.sha256(raw).hexdigest()
            title = 'SYNTHETIC ingestion ' + path.stem
            if path.suffix == '.pdf':
                boundary = uuid4().hex
                data = f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\n{title}\r\n'.encode()
                data += f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="synthetic.pdf"\r\nContent-Type: application/pdf\r\n\r\n'.encode()
                data += raw + f'\r\n--{boundary}--\r\n'.encode()
                created = request(args.base, '/documents/upload', data=data, content_type='multipart/form-data; boundary='+boundary)
            else:
                created = request(args.base, '/documents/note', {'title': title, 'text': raw.decode('utf-8-sig')})
            document_id = created['id']
            deadline = time.monotonic() + 600
            while True:
                doc = request(args.base, '/documents/' + document_id)
                if doc['status'] in ['READY', 'FAILED', 'UNSUPPORTED_OCR_REQUIRED'] or time.monotonic() > deadline:
                    break
                time.sleep(1)
            row['status'] = doc['status']
            extraction = doc.get('extraction') or {}
            row['recipe'] = {k: extraction.get(k) for k in ['model', 'modelDigest', 'promptVersion', 'schemaVersion', 'parserVersion']}
            if doc['status'] != 'READY':
                row.update(matched=0, error=doc.get('errorCode') or 'PROCESSING_TIMEOUT')
            else:
                actual, valid_sources = [], 0
                for fact in doc['facts']:
                    source = request(args.base, '/facts/' + fact['id'] + '/source')
                    quote = source.get('sourceText', '')
                    valid_sources += bool(quote and norm(quote) in norm(doc['text']))
                    actual.append({**fact, 'sourceText': quote})
                row.update(compare(case['facts'], actual))
                row['sourceQuotesValid'] = valid_sources
                row['warningCount'] = len(doc.get('processingWarnings', []))
                ir = request(args.base, '/documents/' + document_id + '/source-ir')['content']
                row['sourceIR'] = {'schemaVersion': ir['schemaVersion'], 'pages': len(ir['pages']),
                                   'blocks': len(ir['blocks']), 'sourceHash': ir['sourceHash']}
        except Exception as exc:
            row.update(error=type(exc).__name__, matched=0)
        row['seconds'] = round(time.monotonic() - started, 2)
        report['results'].append(row)
        report['complete'] = len(report['results']) == len(records)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
        print(f"case={len(report['results'])}/{len(records)} status={row.get('status')} matched={row.get('matched')}/{row['expected']} error={row.get('error')} seconds={row['seconds']}", flush=True)


if __name__ == '__main__':
    main()
