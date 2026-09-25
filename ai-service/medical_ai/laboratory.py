"""Opt-in, conservative lab-row annotation of the immutable source IR.

No model guesses, unit conversion, reference interpretation or diagnosis inference.
Unknown layouts remain explicit issues; the raw document is always retained.
"""
import math
import re
from datetime import date
from decimal import Decimal
from typing import Literal


from .schemas import Extraction, Fact, Provenance, StrictModel
from .source_ir import SourceIR, Span, canonical_hash, resolve_span

LAB_VERSION = 'lab-rows-v1'
LAB_PROJECTION_VERSION = 'lab-facts-v2'
NUMBER = r'[+−-]?\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?'
RESULT = re.compile(rf'(?P<comparator><=|>=|≤|≥|<|>|=)?\s*(?P<number>{NUMBER})')
QUALITATIVE = {'положительно', 'отрицательно', 'не обнаружено', 'обнаружено', 'positive', 'negative'}
TITLE = re.compile(r'^(?:лабораторные исследования|лабораторный отч[её]т|laboratory report)\s*$', re.I)
HEADERS = [{'показатель', 'test'}, {'результат', 'result'},
           {'единица', 'единицы', 'unit'}, {'референс', 'референсный интервал', 'reference'}]
DATE_LABELS = {'дата результата': 'RESULT', 'дата взятия материала': 'SPECIMEN',
               'дата исследования': 'STUDY', 'result date': 'RESULT', 'specimen date': 'SPECIMEN'}


class LabResult(StrictModel):
    raw: str
    kind: Literal['NUMERIC', 'QUALITATIVE']
    comparator: Literal['=', '<', '>', '<=', '>='] | None
    numericValue: str | None  # Decimal string preserves precision and cross-language hashes.


class LabDate(StrictModel):
    role: Literal['RESULT', 'SPECIMEN', 'STUDY']
    iso: str
    raw: str
    source: Span


class LabRow(StrictModel):
    name: str
    result: LabResult
    unit: str | None
    referenceRaw: str | None
    subject: Literal['PATIENT', 'UNKNOWN']
    source: Span
    sourceText: str


class LabIssue(StrictModel):
    code: Literal['UNSUPPORTED_ROW', 'DATE_CONFLICT', 'INVALID_DATE', 'ROW_LIMIT', 'UNSUPPORTED_CONTENT']
    source: Span | None = None


class Laboratory(StrictModel):
    schemaVersion: Literal['lab-rows-v1'] = LAB_VERSION
    sourceIRHash: str
    sourceHash: str
    rows: list[LabRow]
    dates: list[LabDate]
    subjectSources: list[Span]
    issues: list[LabIssue]
    candidateRows: int
    coverage: Literal['SUPPORTED_ROWS_ONLY'] = 'SUPPORTED_ROWS_ONLY'
    artifactHash: str


def parse_result(raw: str) -> LabResult | None:
    raw = raw.strip()
    match = RESULT.fullmatch(raw)
    if match:
        value = float(match['number'].replace(',', '.').replace('−', '-'))
        if math.isfinite(value):
            return LabResult(raw=raw, kind='NUMERIC',
                             comparator={'≤': '<=', '≥': '>='}.get(match['comparator'], match['comparator']) or '=',
                             numericValue=str(Decimal(match['number'].replace(',', '.').replace('−', '-'))))
    if raw.casefold() in QUALITATIVE:
        return LabResult(raw=raw, kind='QUALITATIVE', comparator=None, numericValue=None)
    return None


def cells(line: str) -> list[str] | None:
    if '|' in line:
        return [s.strip() for s in line.strip().strip('|').split('|')]
    if '\t' in line:
        return [s.strip() for s in line.split('\t')]
    return None


def source_lines(ir: SourceIR):
    for page_index, page in enumerate(ir.pages):
        offset = 0
        for line in page.text.splitlines(keepends=True):
            text = line.rstrip('\r\n')
            yield text, Span(pageIndex=page_index, startByte=offset, endByte=offset + len(text.encode()))
            offset += len(line.encode())


def annotate_laboratory(ir: SourceIR) -> Laboratory | None:
    lines = list(source_lines(ir))
    # A table embedded in a clinical visit must not reclassify the whole document.
    first = next((line.strip() for line, _ in lines if line.strip()), '')
    if not TITLE.fullmatch(first):
        return None
    rows, dates, issues, subjects = [], [], [], []
    candidate_rows = 0
    table = False
    table_page = None
    for line, span in lines:
        stripped = line.strip()
        if not stripped or (table_page is not None and span.pageIndex != table_page):
            table = False
        if not stripped or TITLE.fullmatch(stripped):
            continue
        parts = cells(line)
        if parts and len(parts) == 4 and all(p.casefold() in names for p, names in zip(parts, HEADERS)):
            table, table_page = True, span.pageIndex
            continue
        if parts and all(re.fullmatch(r':?-+:?', p) for p in parts):
            continue
        label, separator, value = stripped.partition(':')
        if separator and label.casefold() in DATE_LABELS:
            try:
                original = value.strip()
                # Only complete ISO/day-first dates; no fabricated first day of a month/year.
                if re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', original):
                    day, month, year = original.split('.')
                    normalized = f'{year}-{month}-{day}'
                elif re.fullmatch(r'\d{4}-\d{2}-\d{2}', original):
                    normalized = original
                else:
                    raise ValueError('Partial or unsupported date')
                dates.append(LabDate(role=DATE_LABELS[label.casefold()], iso=date.fromisoformat(normalized).isoformat(),
                                     raw=original, source=span))
            except ValueError:
                issues.append(LabIssue(code='INVALID_DATE', source=span))
            continue
        if stripped.casefold() in {'субъект: пациент', 'subject: patient'}:
            subjects.append(span)
            continue
        fields = None
        if table:
            candidate_rows += 1
            if parts and len(parts) == 4:
                fields = parts
        elif re.search(r';\s*референс\b', stripped, re.I):
            candidate_rows += 1
            # Exact labelled grammar: name: result unit; reference ...; optional flag.
            match = re.fullmatch(r'([^:;]+):\s*([^;]+);\s*референс\s*([^;]*)(?:;[^;]*)?', stripped, re.I)
            if match:
                measurement = RESULT.match(match[2].strip())
                if measurement:
                    unit = match[2].strip()[measurement.end():].strip()
                    # No lost suffix such as a second decimal or unparsed dose schedule.
                    if not unit or re.fullmatch(r'(?:10\^[1-9]\d?/)?[A-Za-zА-Яа-яЁёµμ%][A-Za-zА-Яа-яЁёµμ0-9/^% .·⁹²³-]*', unit):
                        fields = [match[1].strip(), measurement.group().strip(), unit, match[3].strip()]
        else:
            # Other content is retained, never silently claimed to be covered.
            issues.append(LabIssue(code='UNSUPPORTED_CONTENT', source=span))
            continue
        if re.search(r'(?i)\b(?:index_folder|find_relevant_docs|ask_question|system prompt|developer message)\b'
                     r'|\bignore\b.{0,40}\b(?:instructions|extraction|privacy rules)\b', line):
            fields = None
        if fields and fields[0] and len(fields[0]) <= 200:
            result = parse_result(fields[1])
            if result:
                if len(rows) >= 200:
                    issues.append(LabIssue(code='ROW_LIMIT', source=span))
                    continue
                rows.append(LabRow(name=fields[0], result=result, unit=fields[2] or None,
                                   referenceRaw=fields[3] or None, subject='UNKNOWN', source=span, sourceText=line))
                continue
        issues.append(LabIssue(code='UNSUPPORTED_ROW', source=span))
    # Conflicts stay candidates; callers may only select a role with one distinct date.
    for role in DATE_LABELS.values():
        if len({d.iso for d in dates if d.role == role}) > 1 and not any(i.code == 'DATE_CONFLICT' for i in issues):
            issues.append(LabIssue(code='DATE_CONFLICT'))
    if subjects:
        for row in rows:
            row.subject = 'PATIENT'
    payload = dict(schemaVersion=LAB_VERSION, sourceIRHash=ir.irHash, sourceHash=ir.sourceHash,
                   rows=[r.model_dump() for r in rows], dates=[d.model_dump() for d in dates],
                   subjectSources=[s.model_dump() for s in subjects], issues=[i.model_dump() for i in issues],
                   candidateRows=candidate_rows, coverage='SUPPORTED_ROWS_ONLY')
    return Laboratory(**payload, artifactHash=canonical_hash(payload))


def unique_date(lab: Laboratory, role: str) -> str | None:
    dates = {d.iso for d in lab.dates if d.role == role}
    return next(iter(dates)) if len(dates) == 1 else None


def project_laboratory(ir: SourceIR, lab: Laboratory) -> tuple[Extraction, list[str]]:
    # Projection reads source-backed annotation, never independently re-extracts the document.
    payload = lab.model_dump(exclude={'artifactHash'})
    if lab.artifactHash != canonical_hash(payload) or lab.sourceIRHash != ir.irHash or lab.sourceHash != ir.sourceHash:
        raise ValueError('Laboratory artifact references another IR')
    # documentDate/eventDate are legacy generic medical dates, not a resultDate field.
    # Keep the explicit role in the artifact; use STUDY only when RESULT is absent.
    # Invalid/conflicting candidate dates never permit a convenient fallback.
    result_date = None
    if not any(issue.code in {'INVALID_DATE', 'DATE_CONFLICT'} for issue in lab.issues):
        result_date = unique_date(lab, 'RESULT') if any(d.role == 'RESULT' for d in lab.dates) else unique_date(lab, 'STUDY')
    facts = []
    for row in lab.rows:
        if resolve_span(ir.pages, row.source) != row.sourceText:
            raise ValueError('Laboratory row source mismatch')
        facts.append(Fact(type='LAB_RESULT', name=row.name, valueText=row.sourceText,
                          # Legacy scalar must not turn <5 into an exact measurement of 5.
                          valueNumber=float(row.result.numericValue) if row.result.comparator == '=' else None,
                          unit=row.unit, eventDate=result_date, assertionStatus='CONFIRMED', confidence=None,
                          provenance=Provenance(page=ir.pages[row.source.pageIndex].pageNumber, sourceText=row.sourceText)))
    warnings = ['Экспериментальный профиль LAB: извлечены только поддержанные лабораторные строки. '
                'Остальной текст сохранён; полнота документа и клиническая корректность не подтверждены.']
    unresolved = sum(i.code != 'UNSUPPORTED_CONTENT' for i in lab.issues)
    if unresolved:
        warnings.append(f'Лабораторные строки/даты требуют проверки: {unresolved}.')
    return Extraction(documentType='LAB_REPORT', documentDate=result_date,
                      summary=f'Лабораторные строки: {len(facts)}; экспериментальная структурная обработка.',
                      tags=[], facts=facts), warnings
