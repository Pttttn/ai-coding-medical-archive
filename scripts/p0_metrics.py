"""Exact-tuple scoring for the P0 original-upload set (ingestion-p0-v1).

Pure functions, no I/O. A tuple is correct only when every field matches: for LAB, test +
kind/comparator/value + unit + reference + date roles + subject + source; for VISIT, name +
kind + subject + assertion + medication state + temporality + source. Missing documents
keep all their gold items as FN; duplicates and extra items are FP. Field counts are
reported separately so that an error is never hidden by averaging over filled fields.
"""
import re
from decimal import Decimal, InvalidOperation

LAB_FIELDS = ('test', 'kind', 'comparator', 'value', 'unit', 'reference', 'dates', 'subject', 'source')
VISIT_FIELDS = ('name', 'kind', 'subject', 'assertion', 'medicationState', 'temporality', 'source')
VISIT_CLASSES = ('subject', 'assertion', 'medicationState', 'temporality')


def norm(text):
    return ' '.join(str(text or '').casefold().split())


def plain(text):
    """Visible words without markdown markers, table pipes or bullet dashes."""
    text = re.sub(r'[|*_#`]', ' ', str(text or ''))
    text = re.sub(r'(?m)^\s*[-•]\s+', ' ', text)
    return norm(text)


def decimal(value):
    try:
        return Decimal(str(value).replace(' ', '').replace(',', '.')) if value not in (None, '') else None
    except InvalidOperation:
        return None


def lab_field(field, gold, actual):
    if field == 'test':
        return norm(gold['test']) == norm(actual.get('test'))
    if field == 'value':
        return decimal(gold['value']) == decimal(actual.get('value'))
    if field in ('unit', 'reference'):
        return norm(gold[field]) == norm(actual.get(field))
    if field == 'dates':
        return gold['dates'] == (actual.get('dates') or {})
    if field == 'source':
        # Correct page, and the quoted row holds this test's printed result (parser-agnostic).
        quote = plain(actual.get('sourceText'))
        words = plain(gold['test']).split()
        return (actual.get('page') == gold['page'] and plain(gold['result']) in quote
                and bool(words) and words[0] in quote)
    return gold[field] == actual.get(field)


def visit_field(field, gold, actual):
    if field == 'name':
        return norm(gold['name']) == norm(actual.get('name'))
    if field == 'source':
        quote, sentence = plain(actual.get('sourceText')), plain(gold['sourceText'])
        # The exact sentence, or a shorter part of it that still names the item. A whole paragraph is not.
        return actual.get('page') == gold['page'] and bool(quote) and (
            quote == sentence or (quote in sentence and norm(gold['name']) in quote))
    return gold[field] == actual.get(field)


def overlaps(gold, actual, key):
    quote, sentence = plain(actual.get('sourceText')), plain(gold[key])
    return bool(quote) and (quote in sentence or sentence in quote)


def pair(gold, actual, same):
    """Greedy one-to-one alignment by identity, preferring more matching fields."""
    unused, pairs = set(range(len(actual))), []
    for g in gold:
        options = [i for i in sorted(unused) if same(g, actual[i])]
        if options:
            # max() keeps the first of equal candidates, so the alignment is deterministic.
            best = max(options, key=lambda i: sum(1 for f in actual[i] if f in g and g[f] == actual[i][f]))
            unused.remove(best)
            pairs.append((g, actual[best]))
        else:
            pairs.append((g, None))
    return pairs


def exact(gold, actual, fields, check):
    unused, tp = set(range(len(actual))), 0
    for g in gold:
        hit = next((i for i in sorted(unused) if all(check(f, g, actual[i]) for f in fields)), None)
        if hit is not None:
            unused.remove(hit)
            tp += 1
    return tp


def field_counts(pairs, gold, actual, fields, check):
    out = {}
    for field in fields:
        tp = sum(1 for g, a in pairs if a is not None and check(field, g, a))
        out[field] = {'tp': tp, 'fp': len(actual) - tp, 'fn': len(gold) - tp}
    return out


def score_lab(gold, actual):
    tp = exact(gold, actual, LAB_FIELDS, lab_field)
    pairs = pair(gold, actual, lambda g, a: norm(g['test']) == norm(a.get('test')))
    critical = 0
    for g, a in pairs:
        # A value that was accepted but differs from the printed one is the dangerous case.
        if a is None or decimal(a.get('value')) is None:
            continue
        if (decimal(a['value']) != decimal(g['value'])
                or (a.get('comparator') is not None and a['comparator'] != g['comparator'])
                or (a.get('unit') is not None and norm(a['unit']) != norm(g['unit']))):
            critical += 1
    return {'tp': tp, 'fp': len(actual) - tp, 'fn': len(gold) - tp,
            'fields': field_counts(pairs, gold, actual, LAB_FIELDS, lab_field), 'criticalValueErrors': critical}


def score_visit(gold, actual):
    tp = exact(gold, actual, VISIT_FIELDS, visit_field)
    pairs = pair(gold, actual, lambda g, a: norm(g['name']) == norm(a.get('name')) and overlaps(g, a, 'sourceText'))
    matched = {id(a) for _, a in pairs if a is not None}
    unmatched = [a for a in actual if id(a) not in matched]
    classes = {}
    for field in VISIT_CLASSES:
        labels = sorted({g[field] for g in gold} | {a.get(field) for a in actual if a.get(field)})
        classes[field] = {}
        for label in labels:
            ctp = sum(1 for g, a in pairs if a is not None and g[field] == label and a.get(field) == label)
            cfp = sum(1 for g, a in pairs if a is not None and g[field] != label and a.get(field) == label)
            cfp += sum(1 for a in unmatched if a.get(field) == label)
            cfn = sum(1 for g, a in pairs if g[field] == label) - ctp
            classes[field][label] = {'tp': ctp, 'fp': cfp, 'fn': cfn}
    critical = 0
    for g, a in pairs:
        if a is None:
            continue
        if a.get('subject') == 'PATIENT' and a.get('assertion') == 'CONFIRMED' and not (
                g['subject'] == 'PATIENT' and g['assertion'] == 'CONFIRMED'):
            critical += 1
        if a.get('medicationState') == 'TAKING' and g['medicationState'] != 'TAKING':
            critical += 1
    return {'tp': tp, 'fp': len(actual) - tp, 'fn': len(gold) - tp,
            'fields': field_counts(pairs, gold, actual, VISIT_FIELDS, visit_field),
            'classes': classes, 'criticalPromotions': critical}


def empty_score(case):
    return score_lab(case['rows'], []) if case['type'] == 'LAB_REPORT' else score_visit(case['statements'], [])


# ------------------------------------------------------------------ adapters from pipeline output
def page_number(pages, index):
    page = pages[index] if 0 <= index < len(pages) else {}
    return page.get('pageNumber') or index + 1


def lab_rows(artifact, pages):
    dates = {}
    for role in sorted({d['role'] for d in artifact.get('dates', [])}):
        values = {d['iso'] for d in artifact['dates'] if d['role'] == role}
        if len(values) == 1:
            dates[role] = values.pop()
    return [{'test': r['name'], 'kind': r['result']['kind'], 'comparator': r['result']['comparator'],
             'value': r['result']['numericValue'], 'unit': r['unit'], 'reference': r['referenceRaw'],
             'dates': dict(dates), 'subject': r['subject'], 'page': page_number(pages, r['source']['pageIndex']),
             'sourceText': r['sourceText']} for r in artifact.get('rows', [])]


def visit_statements(artifact, pages):
    return [{**{k: s[k] for k in ('name', 'kind', 'subject', 'assertion', 'medicationState', 'temporality')},
             'page': page_number(pages, s['source']['pageIndex']), 'sourceText': s['sourceText']}
            for s in artifact.get('statements', [])]


def legacy_lab_rows(facts):
    """Legacy facts are implicitly the patient's; they carry no comparator, reference or date role."""
    rows = []
    for f in facts:
        provenance = f.get('provenance') or {}
        number = f.get('valueNumber')
        rows.append({'test': f['name'], 'kind': 'NUMERIC' if number is not None else None, 'comparator': None,
                     'value': None if number is None else format(Decimal(str(number)).normalize(), 'f'),
                     'unit': f.get('unit'), 'reference': None,
                     'dates': {'UNSPECIFIED': f['eventDate']} if f.get('eventDate') else {},
                     'subject': 'PATIENT', 'page': provenance.get('pageNumber') or 1,
                     'sourceText': provenance.get('sourceText'), 'factType': f['type']})
    return rows


def legacy_statements(facts):
    out = []
    for f in facts:
        provenance = f.get('provenance') or {}
        status = f.get('assertionStatus') or 'UNKNOWN'
        medication = f['type'] == 'MEDICATION'
        out.append({'name': f['name'], 'kind': f['type'], 'subject': 'PATIENT',
                    'assertion': 'UNKNOWN' if medication or status == 'PRESCRIBED' else status,
                    'medicationState': ('PRESCRIBED' if status == 'PRESCRIBED' else 'UNKNOWN') if medication
                    else 'NOT_APPLICABLE', 'temporality': None,
                    'page': provenance.get('pageNumber') or 1, 'sourceText': provenance.get('sourceText')})
    return out


# ------------------------------------------------------------------ aggregation
def ratio(numerator, denominator):
    return round(numerator / denominator, 6) if denominator else None


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))]


def summarize(results):
    """Per split × document type. Every scheduled document stays in the denominator."""
    groups = {}
    for row in results:
        for split in (row['split'], 'all'):
            groups.setdefault((split, row['type'], row.get('repeat', 1)), []).append(row)
    summary = []
    for (split, kind, repeat), all_rows in sorted(groups.items()):
        # Not measured (a model stage in parser-only mode) is not the same as failed: failures stay as FN.
        rows = [r for r in all_rows if r.get('measured', True)]
        if not rows:
            summary.append({'split': split, 'type': kind, 'repeat': repeat, 'documents': len(all_rows),
                            'measured': 0, 'notMeasured': len(all_rows)})
            continue
        totals = {k: sum(r['score'][k] for r in rows) for k in ('tp', 'fp', 'fn')}
        fields = {}
        for field in rows[0]['score']['fields']:
            counts = {k: sum(r['score']['fields'][field][k] for r in rows) for k in ('tp', 'fp', 'fn')}
            fields[field] = {**counts, 'precision': ratio(counts['tp'], counts['tp'] + counts['fp']),
                             'recall': ratio(counts['tp'], counts['tp'] + counts['fn'])}
        out = {'split': split, 'type': kind, 'repeat': repeat, 'documents': len(all_rows),
               'measured': len(rows), 'notMeasured': len(all_rows) - len(rows),
               'scored': sum(1 for r in rows if r.get('scored')),
               'expected': sum(r['expected'] for r in rows), **totals,
               'precision': ratio(totals['tp'], totals['tp'] + totals['fp']),
               'recall': ratio(totals['tp'], totals['tp'] + totals['fn']), 'fields': fields,
               'reasons': {}}
        for r in rows:
            if r.get('reason'):
                out['reasons'][r['reason']] = out['reasons'].get(r['reason'], 0) + 1
        seconds = [r['seconds'] for r in rows if r.get('seconds') is not None]
        out['seconds'] = {'total': round(sum(seconds), 2), 'p50': percentile(seconds, 0.5),
                          'p95': percentile(seconds, 0.95)}
        if kind == 'LAB_REPORT':
            out['criticalValueErrors'] = sum(r['score']['criticalValueErrors'] for r in rows)
        else:
            out['criticalPromotions'] = sum(r['score']['criticalPromotions'] for r in rows)
            out['macroF1'] = {}
            for field in VISIT_CLASSES:
                labels = {label for r in rows for label in r['score']['classes'][field]}
                f1 = []
                for label in sorted(labels):
                    c = {k: sum(r['score']['classes'][field].get(label, {}).get(k, 0) for r in rows)
                         for k in ('tp', 'fp', 'fn')}
                    if 2 * c['tp'] + c['fp'] + c['fn']:
                        f1.append(2 * c['tp'] / (2 * c['tp'] + c['fp'] + c['fn']))
                out['macroF1'][field] = round(sum(f1) / len(f1), 6) if f1 else None
        summary.append(out)
    return summary
