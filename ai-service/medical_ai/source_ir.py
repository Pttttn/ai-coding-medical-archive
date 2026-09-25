"""Lossless source IR foundation. Normalization never changes stored source pages."""
import hashlib
import json
import re
from typing import Literal

from pydantic import Field, model_validator

from .schemas import Page, StrictModel

IR_VERSION = 'source-ir-v1'
NORMALIZER_VERSION = 'whitespace-map-v1'


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class Span(StrictModel):
    pageIndex: int = Field(ge=0)
    startByte: int = Field(ge=0)
    endByte: int = Field(ge=0)


class Mapping(StrictModel):
    normalizedStartByte: int = Field(ge=0)
    normalizedEndByte: int = Field(ge=0)
    source: Span
    operation: Literal['IDENTITY', 'WHITESPACE']


class Block(StrictModel):
    blockId: str
    kind: Literal['paragraph', 'separator'] = 'paragraph'
    source: Span
    normalizedText: str
    mapping: list[Mapping]


class SourceIR(StrictModel):
    schemaVersion: Literal['source-ir-v1'] = IR_VERSION
    stage: Literal['SOURCE_ONLY'] = 'SOURCE_ONLY'
    documentId: str
    parserVersion: str
    normalizerVersion: Literal['whitespace-map-v1'] = NORMALIZER_VERSION
    sourceHash: str
    pages: list[Page]
    blocks: list[Block]
    irHash: str

    @model_validator(mode='after')
    def verify(self):
        expected = build_source_ir(self.documentId, self.pages, self.parserVersion)
        if self.model_dump() != expected:
            raise ValueError('IR integrity mismatch')
        return self


def resolve_span(pages: list[Page], span: Span) -> str:
    if span.pageIndex >= len(pages) or span.endByte < span.startByte:
        raise ValueError('Invalid source span')
    raw = pages[span.pageIndex].text.encode()
    if span.endByte > len(raw):
        raise ValueError('Source span out of bounds')
    return raw[span.startByte:span.endByte].decode('utf-8', errors='strict')


def build_source_ir(document_id: str, pages: list[Page], parser_version: str) -> dict:
    """Deterministic paragraphs and complete byte mapping, including all whitespace."""
    blocks = []
    for page_index, page in enumerate(pages):
        # Preserve separator blocks too: no source byte disappears during normalization.
        base = 0
        for number, raw in enumerate(re.split(r'(\n[ \t]*\n)', page.text)):
            if not raw:
                continue
            mappings, normalized = [], []
            source_offset = base
            normalized_offset = 0
            segments = []
            cursor = 0
            for whitespace in re.finditer(r'\s+', raw):
                if whitespace.group() == ' ':
                    continue
                if whitespace.start() > cursor:
                    segments.append((raw[cursor:whitespace.start()], 'IDENTITY'))
                segments.append((whitespace.group(), 'WHITESPACE'))
                cursor = whitespace.end()
            if cursor < len(raw):
                segments.append((raw[cursor:], 'IDENTITY'))
            for token, operation in segments:
                rendered = ' ' if operation == 'WHITESPACE' else token
                source_end = source_offset + len(token.encode())
                normalized_end = normalized_offset + len(rendered.encode())
                mappings.append({'normalizedStartByte': normalized_offset, 'normalizedEndByte': normalized_end,
                    'source': {'pageIndex': page_index, 'startByte': source_offset, 'endByte': source_end},
                    'operation': operation})
                normalized.append(rendered)
                source_offset, normalized_offset = source_end, normalized_end
            blocks.append({'blockId': f'p{page_index}:b{number}', 'kind': 'separator' if raw.isspace() else 'paragraph',
                'source': {'pageIndex': page_index, 'startByte': base, 'endByte': base + len(raw.encode())},
                'normalizedText': ''.join(normalized), 'mapping': mappings})
            base += len(raw.encode())
    raw_pages = [p.model_dump() for p in pages]
    payload = {'schemaVersion': IR_VERSION, 'stage': 'SOURCE_ONLY', 'documentId': document_id,
               'parserVersion': parser_version, 'normalizerVersion': NORMALIZER_VERSION,
               'sourceHash': canonical_hash(raw_pages), 'pages': raw_pages, 'blocks': blocks}
    return {**payload, 'irHash': canonical_hash(payload)}
