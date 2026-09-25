import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ConsultationPage } from '../pages/Consultation';

const draft = {
  id: 'draft-id', question: 'Какие обследования нужны?', content: 'Контекст без идентификаторов.',
  contentHash: 'a'.repeat(64), reviewedHash: null, status: 'NEEDS_REVIEW', warnings: [], sourceRefs: [], contexts: [], createdAt: '2026-01-01T00:00:00Z',
};
const response = (value: unknown) => ({ ok: true, status: 200, headers: new Headers({ 'Content-Type': 'application/json' }), json: async () => value });

afterEach(() => vi.unstubAllGlobals());
describe('consultation page review lifecycle', () => {
  it('sends the currently displayed hash for review and invalidates it on every local edit, even if reverted', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.startsWith('/api/documents')) return response({ items: [], total: 0, page: 1, pageSize: 8 });
      if (url.startsWith('/api/consultations?')) return response({items:[],total:0,page:1,pageSize:5});
      if (url.endsWith('/review')) {
        expect(JSON.parse(init?.body as string)).toEqual({ contentHash: draft.contentHash });
        return response({ ...draft, reviewedHash: draft.contentHash, status: 'REVIEWED' });
      }
      return response(draft);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<MemoryRouter initialEntries={['/consultation?id=draft-id']}><ConsultationPage /></MemoryRouter>);
    const editor = await screen.findByRole('textbox', { name: 'Текст пакета консультации' });
    expect(editor).toHaveValue(draft.content);
    expect(screen.getByRole('button', { name: 'Копировать' })).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить проверку' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Копировать' })).toBeEnabled());
    fireEvent.change(editor, { target: { value: `${draft.content} Новая строка.` } });
    expect(screen.getByRole('button', { name: 'Копировать' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Markdown' })).toBeDisabled();
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    fireEvent.change(editor, { target: { value: draft.content } });
    expect(screen.getByRole('button', { name: 'Копировать' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Подтвердить проверку' })).toBeDisabled();
  });

  it('does not copy a different server version than the exact preview', async () => {
    const clipboard = { writeText: vi.fn() };
    vi.stubGlobal('navigator', { clipboard });
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.startsWith('/api/documents')) return response({ items: [], total: 0, page: 1, pageSize: 8 });
      if (url.startsWith('/api/consultations?')) return response({items:[],total:0,page:1,pageSize:5});
      if (url.endsWith('/export')) return { ok: true, status: 200, headers: new Headers({ 'Content-Type': 'text/markdown' }), text: async () => 'Изменённая версия из другой вкладки.' };
      return response({ ...draft, reviewedHash: draft.contentHash, status: 'REVIEWED' });
    }));
    render(<MemoryRouter initialEntries={['/consultation?id=draft-id']}><ConsultationPage /></MemoryRouter>);
    const copy = await screen.findByRole('button', { name: 'Копировать' });
    await waitFor(() => expect(copy).toBeEnabled());
    fireEvent.click(copy);
    expect(await screen.findByRole('alert')).toHaveTextContent('Сохранённая версия изменилась');
    expect(clipboard.writeText).not.toHaveBeenCalled();
  });
});
