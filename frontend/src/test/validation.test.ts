import { describe, expect, it } from 'vitest';
import { MAX_UPLOAD_BYTES, canExportConsultation, hasFactCorrection, validateTags, tagsFromInput, validateDocument } from '../utils';

const note = { title: 'Самочувствие', documentDate: '', mode: 'NOTE', text: 'Самочувствие стабильное.' };
describe('document input validation', () => {
  it('accepts a note with unknown medical date', () => expect(validateDocument(note)).toBeNull());
  it('rejects a whitespace title', () => expect(validateDocument({ ...note, title: '  ' })).toMatch(/название/));
  it('rejects an empty transcript', () => expect(validateDocument({ ...note, mode: 'VISIT_TRANSCRIPT', text: ' ' })).toMatch(/текст/));
  it('rejects invalid calendar dates without normalizing them', () => expect(validateDocument({ ...note, documentDate: '2025-02-30' })).toMatch(/дату/));
  it('requires a file in PDF mode', () => expect(validateDocument({ ...note, mode: 'PDF' })).toMatch(/PDF/));
  it('rejects an unsupported extension', () => expect(validateDocument({ ...note, mode: 'PDF', file: new File(['x'], 'image.png', { type: 'image/png' }) })).toMatch(/PDF/));
  it('rejects a misleading MIME type', () => expect(validateDocument({ ...note, mode: 'PDF', file: new File(['x'], 'report.pdf', { type: 'image/png' }) })).toMatch(/PDF/));
  it('rejects an empty PDF', () => expect(validateDocument({ ...note, mode: 'PDF', file: new File([], 'report.pdf', { type: 'application/pdf' }) })).toMatch(/пуст/));
  it('rejects a file larger than the server limit', () => { const file = new File(['x'], 'report.pdf', { type: 'application/pdf' }); Object.defineProperty(file, 'size', { value: MAX_UPLOAD_BYTES + 1 }); expect(validateDocument({ ...note, mode: 'PDF', file })).toMatch(/20 МБ/); });
  it('normalizes repeated tags without dropping distinct values', () => expect(tagsFromInput(' анализы, кардиология, анализы, ')).toEqual(['анализы', 'кардиология']));
});
describe('reviewed consultation invariants', () => {
  it('allows export only for exact saved content and the current reviewed hash', () => expect(canExportConsultation('text', 'text', 'hash-v2', 'hash-v2')).toBe(true));
  it('blocks a stale reviewed hash', () => expect(canExportConsultation('text', 'text', 'hash-v2', 'hash-v1')).toBe(false));
  it('blocks local edits before they are saved', () => expect(canExportConsultation('text', 'edited text', 'hash-v2', 'hash-v2')).toBe(false));
  it('blocks missing review and empty hashes', () => { expect(canExportConsultation('text', 'text', 'hash', null)).toBe(false); expect(canExportConsultation('text', 'text', '', '')).toBe(false); });
});

describe('aligned server limits and correction provenance', () => {
  it('enforces the 200-character title and 3-character text bounds', () => {
    expect(validateDocument({ ...note, title: 'a'.repeat(201) })).toMatch(/200/);
    expect(validateDocument({ ...note, text: 'ab' })).toMatch(/3/);
  });
  it('rejects more than 30 tags or a tag over 80 characters', () => {
    expect(validateTags(Array.from({length:31}, (_,i) => `tag${i}`))).toMatch(/30/);
    expect(validateTags(['a'.repeat(81)])).toMatch(/80/);
  });
  it('preserves a manual correction label after the user confirms the corrected value', () => {
    expect(hasFactCorrection({reviewStatus:'CONFIRMED', valueNumber:15, originalValue:{valueNumber:12}})).toBe(true);
    expect(hasFactCorrection({reviewStatus:'CONFIRMED', valueNumber:12, originalValue:{valueNumber:12}})).toBe(false);
  });
});
