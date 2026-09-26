import { describe, expect, it } from 'vitest';
import { revisionNotice } from '../utils';

const view = (id: string) => ({ id, status: 'ACTIVE', recipeHash: '0'.repeat(64), textRevisionId: 't1', createdAt: '', activatedAt: null, indexedChunks: 1 });
const text = { textVersion: 1, textRevisions: [{ id: 't1', version: 1, createdAt: '' }] };
describe('processing revision notice', () => {
  it('stays silent for a single activated revision or legacy processing', () => {
    expect(revisionNotice({ ...text, status: 'READY', processingRevision: { active: view('a'), prepared: null } })).toBeNull();
    expect(revisionNotice({ ...text, status: 'INDEXING', processingRevision: { active: null, prepared: view('b') } })).toBeNull();
  });
  it('explains that the previous snapshot is shown while a new one is prepared', () =>
    expect(revisionNotice({ ...text, status: 'INDEXING', processingRevision: { active: view('a'), prepared: view('b') } })).toMatch(/предыдущую версию/));
  it('says the facts belong to the earlier text while an edit is processed or failed', () => {
    const edited = { textVersion: 2, factsTextVersion: 1, textRevisions: [{ id: 't2', version: 2, createdAt: '' }, { id: 't1', version: 1, createdAt: '' }], processingRevision: { active: view('a'), prepared: null } };
    expect(revisionNotice({ ...edited, status: 'EXTRACTING' })).toMatch(/Текст изменён.*версии текста 1.*не используют/);
    expect(revisionNotice({ ...edited, status: 'FAILED' })).toMatch(/не завершилась.*версии текста 1/);
    expect(revisionNotice({ ...edited, status: 'READY', factsTextVersion: 2 })).toBeNull();
  });
  it('explains that a failed reprocess leaves the last successful snapshot', () =>
    expect(revisionNotice({ ...text, status: 'FAILED', processingRevision: { active: view('a'), prepared: null } })).toMatch(/последнюю успешную/));
});
