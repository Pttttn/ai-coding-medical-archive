"""Bounded structural chunks for medical prose; no clinical inference or ontology.

Paragraphs that fit stay intact, including wrapped doses, results and negations.
Long paragraphs prefer table rows, list items and complete sentences. Only a unit
that exceeds the hard limit falls back to whitespace (then character) boundaries.
Overlap repeats whole units up to its budget; it never takes a fragment of one.
Every returned chunk remains an exact substring of the original text.
"""

import re

SPLITTER_VERSION = "medical-structure-v1"

_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)*")
_BULLET = re.compile(r"^[ \t]*(?:[-*+] |\d+[.)] )")
_SENTENCE_END = re.compile(r"[.!?]+[\"'»”)]*(?=\s+|$)")
# Generic abbreviations are punctuation, not independent statements. Decimal
# points never match _SENTENCE_END because the next character is a digit.
_ABBREVIATION = re.compile(r"\b(?:dr|mr|mrs|ms|prof|vs|etc|e\.g|i\.e|г|мг|мл|см|табл|капс|им|т\.д|т\.п)\.$", re.I)


class MedicalTextSplitter:
    def __init__(self, chunk_size: int, chunk_overlap: int = 0):
        if chunk_size < 1 or not 0 <= chunk_overlap < chunk_size:
            raise ValueError("Require 0 <= chunk_overlap < chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @staticmethod
    def _trim(text: str, start: int, end: int) -> tuple[int, int]:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end

    def _fallback(self, text: str, start: int, end: int) -> list[tuple[int, int]]:
        """An over-limit unit cannot be preserved: prefer words, enforce the cap."""
        result = []
        while end - start > self.chunk_size:
            limit = start + self.chunk_size
            boundaries = list(re.finditer(r"\s+", text[start:limit + 1]))
            cut = start + boundaries[-1].start() if boundaries else limit
            if cut == start:
                cut = limit
            span = self._trim(text, start, cut)
            if span[0] < span[1]:
                result.append(span)
            start, end = self._trim(text, cut, end)
        if start < end:
            result.append((start, end))
        return result

    def _sentences(self, text: str, start: int, end: int) -> list[tuple[int, int]]:
        result = []
        cursor = start
        for match in _SENTENCE_END.finditer(text, start, end):
            if _ABBREVIATION.search(text[cursor:match.end()]):
                continue
            span = self._trim(text, cursor, match.end())
            if span[0] < span[1]:
                result.extend(self._bounded(text, *span))
            cursor = match.end()
        span = self._trim(text, cursor, end)
        if span[0] < span[1]:
            result.extend(self._bounded(text, *span))
        return result

    def _bounded(self, text: str, start: int, end: int) -> list[tuple[int, int]]:
        return [(start, end)] if end - start <= self.chunk_size else self._fallback(text, start, end)

    def _paragraph(self, text: str, start: int, end: int) -> list[tuple[int, int]]:
        if end - start <= self.chunk_size:
            return [(start, end)]
        # Rows and list items are independently meaningful. A wrapped list item
        # includes its continuation lines, so a dose or deadline is not detached.
        blocks = []
        cursor = start
        kind = "prose"
        offset = start
        for line in text[start:end].splitlines(keepends=True):
            stripped = line.strip()
            row = stripped.count("|") >= 2 or "\t" in stripped
            bullet = bool(_BULLET.match(line))
            new_kind = "row" if row else "item" if bullet else None
            if new_kind or kind == "row":
                span = self._trim(text, cursor, offset)
                if span[0] < span[1]:
                    blocks.append((*span, kind))
                cursor = offset
                kind = new_kind or "prose"
            offset += len(line)
        span = self._trim(text, cursor, end)
        if span[0] < span[1]:
            blocks.append((*span, kind))
        result = []
        for block_start, block_end, block_kind in blocks:
            if block_end - block_start <= self.chunk_size:
                result.append((block_start, block_end))
            elif block_kind == "row":
                result.extend(self._fallback(text, block_start, block_end))
            else:
                result.extend(self._sentences(text, block_start, block_end))
        return result

    def split_text(self, text: str) -> list[str]:
        units = []
        cursor = 0
        for match in _PARAGRAPH_BREAK.finditer(text):
            start, end = self._trim(text, cursor, match.start())
            if start < end:
                units.extend(self._paragraph(text, start, end))
            cursor = match.end()
        start, end = self._trim(text, cursor, len(text))
        if start < end:
            units.extend(self._paragraph(text, start, end))

        chunks = []
        current: list[tuple[int, int]] = []
        for unit in units:
            if current and unit[1] - current[0][0] > self.chunk_size:
                chunks.append(text[current[0][0]:current[-1][1]])
                # Retain only complete trailing units within both budgets. A
                # large unit yields no overlap instead of severing its meaning.
                overlap = []
                for previous in reversed(current):
                    if (current[-1][1] - previous[0] > self.chunk_overlap
                            or unit[1] - previous[0] > self.chunk_size):
                        break
                    overlap.insert(0, previous)
                current = overlap
            current.append(unit)
        if current:
            chunks.append(text[current[0][0]:current[-1][1]])
        return chunks
