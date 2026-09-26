import { useState } from 'react';
import type { FormEvent } from 'react';
import { Trash2 } from 'lucide-react';
import { api, json, message } from './api';
import { ErrorNotice, Notice } from './components';
import { date } from './utils';

export type PurgePreview = { id: string; title: string; consultations: { id: string; question: string; createdAt: string; responseCount: number }[] };

/** Permanent deletion of a trashed document. The user sees every consultation that goes with it and types the title. */
export function PurgePanel({ documentId, onPurged }: { documentId: string; onPurged: () => void }) {
  const [preview, setPreview] = useState<PurgePreview | null>(null);
  const [confirmTitle, setConfirmTitle] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function open() {
    setBusy(true); setError('');
    try { setPreview(await api<PurgePreview>(`/documents/${documentId}/purge`)); setConfirmTitle(''); }
    catch (cause) { setError(message(cause)); }
    finally { setBusy(false); }
  }
  async function purge(event: FormEvent) {
    event.preventDefault();
    if (!preview || confirmTitle !== preview.title) return;
    setBusy(true); setError('');
    try { await api(`/documents/${documentId}/purge`, { method: 'POST', body: json({ confirmTitle, consultationIds: preview.consultations.map(c => c.id) }) }); onPurged(); }
    catch (cause) { setError(message(cause)); setPreview(null); }
    finally { setBusy(false); }
  }
  if (!preview) return <><ErrorNotice error={error} /><button className="button secondary small" disabled={busy} onClick={() => void open()}><Trash2 size={15} /> Удалить навсегда</button></>;
  return <form className="panel form-panel" onSubmit={event => void purge(event)}><h2>Удалить навсегда</h2>
    <Notice variant="warning">Будут удалены оригинал, все версии текста, факты и их история, фрагменты поиска и записи журнала этого документа. Восстановить их будет нельзя. Уже сделанные резервные копии не меняются.</Notice>
    {preview.consultations.length > 0 && <Notice variant="warning"><strong>Вместе с документом удалятся консультации, собранные из него, с их запросами и ответами:</strong><ul>{preview.consultations.map(c => <li key={c.id}>{c.question} · {date(c.createdAt)} · ответов: {c.responseCount}</li>)}</ul></Notice>}
    <ErrorNotice error={error} />
    <fieldset disabled={busy}><div className="form-grid"><label className="span-2">Введите название документа «{preview.title}» для подтверждения<input value={confirmTitle} maxLength={200} onChange={event => setConfirmTitle(event.target.value)} autoComplete="off" /></label></div>
      <div className="form-footer"><button className="button secondary" type="button" onClick={() => setPreview(null)}>Отмена</button><button className="button primary" type="submit" disabled={confirmTitle !== preview.title}><Trash2 size={17} /> {busy ? 'Удаляем…' : 'Удалить навсегда'}</button></div></fieldset></form>;
}
