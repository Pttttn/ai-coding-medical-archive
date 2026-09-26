import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { DocumentPage } from '../pages/Document';

afterEach(() => vi.unstubAllGlobals());
const doc = { id: 'd1', title: 'Синтетический PDF', documentType: 'LAB_REPORT', documentDate: null, createdAt: '2026-09-26', status: 'READY', tags: [], summary: '', facts: [], textVersion: 2, factsTextVersion: 2, textRevisions: [{ id: 't2', version: 2, createdAt: '' }], reprocessModes: ['CURRENT_TEXT', 'ORIGINAL'], originalFilename: 'demo.pdf' };
const reply = (body: unknown) => ({ ok: true, status: 200, headers: new Headers({ 'Content-Type': 'application/json' }), json: async () => body });
it('sends the chosen reprocess mode and explains what re-parsing the original does', async () => {
  const posts: unknown[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === 'POST') { posts.push({ url, body: init.body ? JSON.parse(init.body as string) : null }); return reply({ jobId: 'j' }); }
    return reply(url.includes('/history') ? { items: [], total: 0 } : doc);
  }));
  render(<MemoryRouter initialEntries={['/archive/d1']}><Routes><Route path="/archive/:id" element={<DocumentPage />} /></Routes></MemoryRouter>);
  const select = await screen.findByLabelText('Режим повторной обработки');
  expect([...(select as HTMLSelectElement).options].map(o => o.value)).toEqual(['', 'CURRENT_TEXT', 'ORIGINAL']);
  fireEvent.change(select, { target: { value: 'ORIGINAL' } });
  expect(screen.getByText(/правка станет предыдущей версией/)).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: /Обработать снова/ }));
  await waitFor(() => expect(posts).toEqual([{ url: '/api/documents/d1/reprocess', body: { mode: 'ORIGINAL' } }]));
  fireEvent.click(await screen.findByRole('button', { name: /Обработать снова/ }));
  await waitFor(() => expect(posts).toHaveLength(2));
  expect(posts[1]).toEqual({ url: '/api/documents/d1/reprocess', body: null });
});
