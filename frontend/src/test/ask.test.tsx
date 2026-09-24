import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { AskPage } from '../pages/Ask';

afterEach(() => vi.unstubAllGlobals());
it('sends selected dates and displays incomplete coverage instead of silently claiming a complete answer', async () => {
  const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
    expect(JSON.parse(init?.body as string)).toEqual({ question: 'Какие отклонения?', dateFrom: '2025-09-24', dateTo: '2026-09-24' });
    return { ok: true, status: 200, headers: new Headers({ 'Content-Type': 'application/json' }), json: async () => ({
      answer: 'Проверенная цитата.', sources: [], warnings: ['Часть документов не просмотрена.'],
      coverage: { eligibleDocuments: 32, scannedDocuments: 20, complete: false, period: { from: '2025-09-24', to: '2026-09-24', asOf: '2026-09-24' } },
    }) };
  });
  vi.stubGlobal('fetch', fetchMock);
  render(<MemoryRouter><AskPage /></MemoryRouter>);
  fireEvent.change(screen.getByLabelText('Вопрос к архиву'), { target: { value: 'Какие отклонения?' } });
  fireEvent.change(screen.getByLabelText('С', { exact: true }), { target: { value: '2025-09-24' } });
  fireEvent.change(screen.getByLabelText('По', { exact: true }), { target: { value: '2026-09-24' } });
  fireEvent.click(screen.getByRole('button', { name: 'Спросить архив' }));
  expect(await screen.findByText(/Просмотрено документов: 20 из 32/)).toHaveTextContent('Обзор неполный');
  expect(screen.getByText('Часть документов не просмотрена.')).toBeVisible();
});
