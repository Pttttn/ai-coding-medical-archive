"""P0 original-upload baseline on the frozen ingestion-p0-v1 set.

Two separate modes, never mixed in one report:

* ``--base URL`` (end to end): uploads originals into a dedicated EMPTY archive through the
  normal API (PDF multipart upload, TXT/MD as a text note), waits for processing, scores what
  the archive stored. No seed, no precomputed facts; gold is read only by this scorer.
* ``--parser-only``: runs the deterministic stages in process (parse, source IR, the lab-row
  annotator shared by lab-rows-v1/clinical-v1). No model is called, so VISIT extraction and the
  legacy extractor are not measured; VISIT documents are reported as MODEL_REQUIRED.

Reports hold only aggregates, hashes and counts, never document text. Output is never overwritten.
"""
import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p0_metrics as metrics  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SET = ROOT / 'evaluation/ingestion-p0-v1'
CODE = ['scripts/evaluate_ingestion_p0.py', 'scripts/p0_metrics.py', 'ai-service/medical_ai/laboratory.py',
        'ai-service/medical_ai/visit.py', 'ai-service/medical_ai/extraction.py', 'ai-service/medical_ai/parsing.py',
        'ai-service/medical_ai/source_ir.py', 'backend/src/processing.service.ts']


def load(split):
    raw = (SET / 'gold/manifest.json').read_bytes()
    manifest = json.loads(raw)
    cases = [c for c in manifest['cases'] if split == 'all' or c['split'] == split]
    # Validate every selected original before any upload or parse.
    for case in cases:
        if hashlib.sha256((SET / 'originals' / case['originalFile']).read_bytes()).hexdigest() != case['sha256']:
            raise SystemExit('Frozen original differs from the gold manifest.')
    return manifest, hashlib.sha256(raw).hexdigest(), cases


def request(base, route, payload=None, data=None, content_type=None):
    import urllib.request
    if payload is not None:
        data, content_type = json.dumps(payload).encode(), 'application/json'
    req = urllib.request.Request(base.rstrip('/') + '/api' + route, data=data,
                                 headers={'Content-Type': content_type} if content_type else {})
    with urllib.request.urlopen(req, timeout=600) as response:
        return json.load(response)


def upload(base, case):
    raw = (SET / 'originals' / case['originalFile']).read_bytes()
    title = 'SYNTHETIC P0 ' + case['id']
    if case['format'] == 'pdf':
        boundary = uuid4().hex
        data = f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\n{title}\r\n'.encode()
        data += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{case["id"]}.pdf"\r\n'
                 'Content-Type: application/pdf\r\n\r\n').encode() + raw + f'\r\n--{boundary}--\r\n'.encode()
        return request(base, '/documents/upload', data=data, content_type='multipart/form-data; boundary=' + boundary)
    # The upload endpoint accepts PDF only; TXT/MD originals enter through the text-note API unchanged.
    return request(base, '/documents/note', {'title': title, 'text': raw.decode('utf-8')})


def api_case(args, case, row, ids, runs):
    if case['id'] in ids:
        queued = request(args.base, '/documents/' + ids[case['id']] + '/reprocess', {'mode': 'ORIGINAL'}
                         if case['format'] == 'pdf' else {})
    else:
        queued = upload(args.base, case)
        ids[case['id']] = queued['id']
    job, deadline = None, time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        job = request(args.base, '/jobs/' + queued['jobId'])
        if job['status'] in {'READY', 'FAILED', 'SUPERSEDED'}:
            break
        time.sleep(0.5)
    doc = request(args.base, '/documents/' + ids[case['id']])
    row['status'] = doc['status']
    if not job or job['status'] != 'READY' or doc['status'] != 'READY':
        row['reason'] = doc.get('errorCode') or (job or {}).get('errorCode') or 'PROCESSING_TIMEOUT'
        return
    extraction = doc.get('extraction') or {}
    if not extraction.get('id') or extraction['id'] == runs.get(case['id']):
        row['reason'] = 'NO_NEW_EXTRACTION_RUN'
        return
    runs[case['id']] = extraction['id']
    row['profile'] = doc.get('extractionProfile')
    row['recipe'] = {k: extraction.get(k) for k in ('model', 'modelDigest', 'promptVersion', 'schemaVersion',
                                                     'parserVersion')}
    pages = doc.get('pages') or []
    lab, visit, facts = doc.get('laboratory'), doc.get('visit'), doc.get('facts') or []
    if case['type'] == 'LAB_REPORT':
        row['method'] = 'lab' if lab else 'visit' if visit else 'legacy'
        actual = (metrics.lab_rows(lab, pages) if lab else [] if visit else metrics.legacy_lab_rows(facts))
        row['score'] = metrics.score_lab(case['rows'], actual)
        if visit:
            row['score']['fp'] += len(visit.get('statements', []))
            row['reason'] = 'CLASSIFIED_AS_VISIT'
        elif not lab:
            row['legacyFactTypes'] = sorted({f['type'] for f in facts})
        elif not actual:
            row['reason'] = 'NO_SUPPORTED_ROWS'
    else:
        row['method'] = 'visit' if visit else 'lab' if lab else 'legacy'
        actual = (metrics.visit_statements(visit, pages) if visit else [] if lab else metrics.legacy_statements(facts))
        row['score'] = metrics.score_visit(case['statements'], actual)
        if lab:
            row['score']['fp'] += len(lab.get('rows', []))
            row['reason'] = 'CLASSIFIED_AS_LAB'
    row['actual'] = len(actual)
    row['scored'] = True


def parser_case(case, row):
    """Same code as /internal/parse and the LAB branch of /internal/process in a LAB-enabled profile."""
    ai = str(ROOT / 'ai-service')
    if ai not in sys.path:
        sys.path.insert(0, ai)
    from medical_ai.config import Settings
    from medical_ai.laboratory import annotate_laboratory
    from medical_ai.parsing import parse_original
    from medical_ai.source_ir import SourceIR, build_source_ir
    from medical_ai.visit import supports_visit

    path = SET / 'originals' / case['originalFile']
    # TXT/MD originals reach the service as note text, exactly as the end-to-end runner sends them.
    file_path, text = (path, None) if case['format'] == 'pdf' else (None, path.read_text(encoding='utf-8'))
    _, pages, _, parser_version = parse_original(file_path, text, Settings().max_file_bytes, lab_tables=True)
    ir = SourceIR.model_validate(build_source_ir('p0-' + case['id'], pages, parser_version))
    row['status'] = 'PARSED'
    row['parserVersion'] = parser_version
    lab = annotate_laboratory(ir)
    page_dicts = [p.model_dump() for p in ir.pages]
    row['visitClassifier'] = supports_visit(ir)
    if case['type'] == 'LAB_REPORT':
        row['method'] = 'lab' if lab else 'none'
        actual = metrics.lab_rows(lab.model_dump(mode='json'), page_dicts) if lab else []
        row['score'] = metrics.score_lab(case['rows'], actual)
        row['actual'], row['scored'] = len(actual), True
        if lab is None:
            row['reason'] = 'NOT_RECOGNISED_AS_LAB'
        else:
            row['candidateRows'] = lab.candidateRows
            row['issues'] = {code: sum(i.code == code for i in lab.issues) for code in sorted({i.code for i in lab.issues})}
            if not actual:
                row['reason'] = 'NO_SUPPORTED_ROWS'
    else:
        # Statements need the model; only the deterministic routing is observable here.
        row['method'] = 'lab' if lab else 'visit-model' if row['visitClassifier'] else 'legacy-model'
        row['reason'] = 'CLASSIFIED_AS_LAB' if lab else 'MODEL_REQUIRED'
        row['measured'] = bool(lab)  # A LAB misroute is a measured failure; a model stage is not measured.


def run(args):
    if args.output.exists():
        raise SystemExit('Refusing to overwrite a previous attempt.')
    manifest, gold_sha, cases = load(args.split)
    if args.base and request(args.base, '/documents?pageSize=1&deleted=all')['total']:
        raise SystemExit('Requires an EMPTY dedicated SEED_ENABLED=false archive, including trash.')
    report = {
        'kind': 'p0-parser-only' if args.parser_only else 'p0-original-upload',
        'createdAt': datetime.now(timezone.utc).isoformat(), 'dataset': manifest['version'],
        'goldSha256': gold_sha, 'goldReview': manifest['goldReview'], 'split': args.split,
        'plannedRepeats': args.repeats, 'plannedCasesPerRepeat': len(cases), 'complete': False,
        'codeHashes': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in CODE},
        'runtime': {'python': platform.python_version(), 'system': platform.system()},
        'limitations': [
            manifest['scope'],
            'Exact tuple; unsupported/failed documents keep all gold items as FN. Not a clinical validation.',
            'Parser-only measures deterministic stages without a model; it is not an end-to-end or LLM result.'
            if args.parser_only else
            'Repeats after the first reprocess the same documents in one installation; not independent deployments.'],
        'results': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        report['summary'] = metrics.summarize(report['results'])
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

    save()
    ids, runs = {}, {}
    for repeat in range(1, args.repeats + 1):
        for case in cases:
            expected = len(case['rows'] if case['type'] == 'LAB_REPORT' else case['statements'])
            row = {'case': case['id'], 'type': case['type'], 'split': case['split'], 'format': case['format'],
                   'repeat': repeat, 'expected': expected, 'score': metrics.empty_score(case), 'scored': False,
                   'measured': True}
            started = time.monotonic()
            try:
                parser_case(case, row) if args.parser_only else api_case(args, case, row, ids, runs)
            except Exception as exc:  # Failures stay in the denominator with their type only.
                code = getattr(exc, 'code', None)
                row['reason'] = row.get('reason') or (code if isinstance(code, str) else type(exc).__name__)
            row['seconds'] = round(time.monotonic() - started, 3)
            report['results'].append(row)
            save()
            print(f"repeat={repeat} case={case['id']} method={row.get('method')} "
                  f"tp={row['score']['tp']}/{expected} fp={row['score']['fp']} reason={row.get('reason')}", flush=True)
    report['complete'] = True
    save()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--base', help='API of a dedicated empty SEED_ENABLED=false installation')
    mode.add_argument('--parser-only', action='store_true', help='Deterministic stages in process, no model')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--split', choices=['development', 'held-out', 'all'], required=True)
    parser.add_argument('--repeats', type=int, choices=range(1, 11), default=1)
    parser.add_argument('--timeout', type=int, default=900, help='Seconds per document')
    run(parser.parse_args())
