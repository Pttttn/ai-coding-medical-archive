import copy

import pytest
from pydantic import ValidationError

from medical_ai.schemas import Page
from medical_ai.source_ir import SourceIR, Span, build_source_ir, resolve_span


@pytest.mark.parametrize('text', ['', ' ', '\n', '  ЛПНП 4,1 ммоль/л < 3,0\n', 'Не\u00a0подтверждён.\n\nНазначен 5 мг; не начал.\n', '🙂\r\nALT −2 >0\tмг/л', 'a\u0085b\u001cc'])
def test_source_mapping_covers_every_original_byte_without_changing_clinical_tokens(text):
    pages = [Page(pageNumber=1, text=text), Page(pageNumber=2, text='')]
    data = build_source_ir('synthetic', pages, 'test-parser')
    ir = SourceIR.model_validate(data)
    recovered = ''.join(resolve_span(pages, b.source) for b in ir.blocks)
    assert recovered == text
    for block in ir.blocks:
        assert ''.join(resolve_span(pages, m.source) for m in block.mapping) == resolve_span(pages, block.source)
    assert build_source_ir('synthetic', pages, 'test-parser') == data


def test_ir_hash_binds_parser_pages_and_mapping():
    original = build_source_ir('synthetic', [Page(text='ЛПНП\t4,1')], 'parser-v1')
    for mutate in [lambda d: d['pages'][0].update(text='ЛПНП 1,4'),
                   lambda d: d['blocks'][0].update(normalizedText='ЛПНП 1,4'),
                   lambda d: d.update(parserVersion='parser-v2')]:
        changed = copy.deepcopy(original)
        mutate(changed)
        with pytest.raises(ValidationError):
            SourceIR.model_validate(changed)


def test_span_rejects_utf8_splits_and_out_of_bounds():
    pages = [Page(text='Я')]
    for span in [Span(pageIndex=0, startByte=0, endByte=1), Span(pageIndex=0, startByte=0, endByte=4)]:
        with pytest.raises((ValueError, UnicodeError)):
            resolve_span(pages, span)


def test_ordinary_prose_uses_compact_identity_map():
    ir = build_source_ir('synthetic', [Page(text='A normal paragraph with many words.')], 'test')
    assert len(ir['blocks'][0]['mapping']) == 1


def test_shared_schema_and_cross_language_fixture_remain_valid():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / 'contracts'
    assert json.loads((root / 'source-ir-v1.schema.json').read_text(encoding='utf-8')) == SourceIR.model_json_schema()
    SourceIR.model_validate_json((root / 'source-ir-v1.synthetic.json').read_text(encoding='utf-8'))


def test_original_bytes_survive_seed_document_normalization():
    import json
    from pathlib import Path
    records = json.loads((Path(__file__).resolve().parents[2] / 'seed/clinical/records.json').read_text(encoding='utf-8'))
    for record in records:
        pages = [Page(**p) for p in record['pages']] or [Page(text=record['text'])]
        ir = SourceIR.model_validate(build_source_ir(record['id'], pages, 'synthetic-test'))
        for i, page in enumerate(pages):
            assert ''.join(resolve_span(pages, b.source) for b in ir.blocks if b.source.pageIndex == i) == page.text
