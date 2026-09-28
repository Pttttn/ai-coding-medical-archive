import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PurgePanel } from '../PurgePanel';

const preview = { id: 'd1', title: 'Синтетический анализ', consultations: [{ id: 'c1', question: 'Синтетический вопрос', createdAt: '2026-09-20T10:00:00Z', responseCount: 2 }] };
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('permanent deletion panel', () => {
  afterEach(() => vi.unstubAllGlobals());
  it('lists linked consultations and deletes only after the exact title is typed', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(reply(preview)).mockResolvedValueOnce(reply({ id: 'd1', purged: true, consultationsDeleted: 1 }, 201));
    vi.stubGlobal('fetch', fetch);
    const onPurged = vi.fn();
    render(<PurgePanel documentId="d1" onPurged={onPurged} />);
    fireEvent.click(screen.getByRole('button', { name: 'Удалить навсегда' }));
    expect(await screen.findByText(/Синтетический вопрос/)).toBeVisible();
    const submit = screen.getAllByRole('button', { name: /Удалить навсегда/ }).at(-1)!;
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Синтетический' } });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: preview.title } });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);
    await waitFor(() => expect(onPurged).toHaveBeenCalledOnce());
    expect(fetch).toHaveBeenLastCalledWith('/api/documents/d1/purge', expect.objectContaining({ method: 'POST', body: JSON.stringify({ confirmTitle: preview.title, consultationIds: ['c1'] }) }));
  });
  it('shows the server refusal and asks to review the list again', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(reply({ ...preview, consultations: [] })).mockResolvedValueOnce(reply({ message: 'Список связанных консультаций изменился; проверьте его снова' }, 409)));
    const onPurged = vi.fn();
    render(<PurgePanel documentId="d1" onPurged={onPurged} />);
    fireEvent.click(screen.getByRole('button', { name: 'Удалить навсегда' }));
    fireEvent.change(await screen.findByRole('textbox'), { target: { value: preview.title } });
    fireEvent.click(screen.getAllByRole('button', { name: /Удалить навсегда/ }).at(-1)!);
    expect(await screen.findByRole('alert')).toHaveTextContent('проверьте его снова');
    expect(onPurged).not.toHaveBeenCalled();
    expect(screen.queryByRole('textbox')).toBeNull();
  });
});
