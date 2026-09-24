from datetime import date

import pytest

from medical_ai.archive_qa import ArchiveRAG, complete_excerpt, resolve_period
from medical_ai.errors import ServiceError


@pytest.mark.parametrize('question,start,end,today,expected', [
    ('за последний год', None, None, date(2026, 9, 24), ('2025-09-24', '2026-09-24')),
    ('за последний год', None, None, date(2024, 2, 29), ('2023-02-28', '2024-02-29')),
    ('за прошлый год', None, None, date(2026, 9, 24), ('2025-01-01', '2025-12-31')),
    ('за 2024 год', None, None, date(2026, 9, 24), ('2024-01-01', '2024-12-31')),
    ('за последний год', '2020-01-01', None, date(2026, 9, 24), ('2020-01-01', None)),
])
def test_period(question, start, end, today, expected):
    assert resolve_period(question, start, end, today) == expected


def test_invalid_period():
    with pytest.raises(ServiceError):
        resolve_period('q', '2026-12-01', '2025-01-01', date.today())


@pytest.mark.parametrize('fragment,source', [
    ('диабет', 'У отца диабет; у пациента не подтверждён.'),
    ('принимает', 'Метформин не принимает.'),
    ('48', 'АЛТ: 48 Ед/л; референс 0-41 Ед/л; выше референса.'),
])
def test_retains_full_line_qualifiers(fragment, source):
    assert complete_excerpt(fragment, source) == source


def evidence_provider(provider):
    original = provider.json
    def respond(task, payload, schema=None):
        if 'archive_evidence' in task:
            return {'evidence': [{'source': s['number'], 'quote': s['text']} for s in payload['sources']]}
        return original(task, payload, schema)
    provider.json = respond


def test_scans_beyond_top_five_and_isolates_allowed_documents(services, provider):
    evidence_provider(provider)
    for i in range(32):
        services.archive.index_document(str(i), f'visit-{i}.md', 1, f'Observation number {i}.')
    services.demo.index_document('public', 'public.md', 1, 'Must not enter private answer.')
    result = services.archive_rag.ask('overview', [str(i) for i in range(30)])
    assert len(result['sources']) == 30
    assert result['coverage']['complete']
    assert result['coverage']['scannedDocuments'] == 30
    assert {s['documentId'] for s in result['sources']} == {str(i) for i in range(30)}


def test_dates_undated_and_missing_index_are_visible(services, provider):
    evidence_provider(provider)
    for i in ['old', 'new', 'undated']:
        services.archive.index_document(i, i+'.md', 1, 'Some observation.')
    catalog = [{'documentId': 'old', 'documentDate': '2024-01-01'},
               {'documentId': 'new', 'documentDate': '2026-01-01'},
               {'documentId': 'missing', 'documentDate': '2026-02-01'},
               {'documentId': 'undated', 'documentDate': None}]
    result = services.archive_rag.ask('last year', documents=catalog, today=date(2026, 9, 24))
    assert [s['documentId'] for s in result['sources']] == ['new']
    assert result['coverage']['eligibleDocuments'] == 2
    assert result['coverage']['missingIndexedDocuments'] == 1
    assert not result['coverage']['complete']
    assert len(result['warnings']) == 3


def test_invalid_quote_retries_then_refuses_without_raw_fallback(services, provider):
    services.archive.index_document('d', 'd.md', 1, 'Patient denies medication intake.')
    calls = []
    def invent(task, payload, schema=None):
        calls.append(payload)
        return {'evidence': [{'source': 1, 'quote': 'Patient takes medication.'}]}
    provider.json = invent
    result = services.archive_rag.ask('medication')
    assert len(calls) == 2
    assert result['reasonCode'] == 'EVIDENCE_VALIDATION_FAILED'
    assert not result['sources']
    assert not result['coverage']['complete']


def test_private_engine_rejects_demo_corpus(services, provider, settings):
    with pytest.raises(ValueError):
        ArchiveRAG(services.demo, provider, settings)


def test_multiline_excerpt_is_contiguous_and_does_not_insert_header():
    source = "Header\nFirst sentence.\n\nSecond sentence.\nFooter"
    assert complete_excerpt("First sentence.\n\nSecond sentence.", source) == "First sentence.\n\nSecond sentence."


def test_separate_lines_restore_intervening_context():
    source = "First finding.\nImportant qualifier.\nLast finding."
    assert complete_excerpt("First finding.\nLast finding.", source) == source


def test_large_archive_reports_partial_coverage(services, provider, settings):
    evidence_provider(provider)
    settings.archive_scan_chunks = 12
    for i in range(16):
        services.archive.index_document(str(i), f'{i}.md', 1, f'Observation {i}.')
    result = services.archive_rag.ask('overview')
    assert result['coverage']['scannedChunks'] == 12
    assert not result['coverage']['complete']
    assert result['warnings']


def test_initial_capitalization_restores_original_with_qualifiers():
    source = "Состояния: предиабет под наблюдением. Диабет не подтверждён."
    assert complete_excerpt("Предиабет под наблюдением. Диабет не подтверждён.", source) == source
    assert complete_excerpt("Предиабет подтверждён. Диабет не подтверждён.", source) is None
