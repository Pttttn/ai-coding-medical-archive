import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowRight, FileText, LoaderCircle, MessageSquareText, NotebookPen, ShieldCheck, UploadCloud, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api, json, message } from '../api';
import { ErrorNotice, PageHeader } from '../components';
import { MAX_UPLOAD_BYTES, tagsFromInput, validateDocument, validateTags } from '../utils';

const modes = [{ id: 'PDF', title: 'Загрузить PDF', description: 'Анализы, выписки, заключения', icon: FileText }, { id: 'VISIT_TRANSCRIPT', title: 'Транскрипт приёма', description: 'Текст разговора с врачом', icon: MessageSquareText }, { id: 'NOTE', title: 'Личная заметка', description: 'Самочувствие и наблюдения', icon: NotebookPen }];
export function UploadPage() {
  const [mode, setMode] = useState('PDF');
  const [title, setTitle] = useState('');
  const [documentDate, setDocumentDate] = useState('');
  const [tags, setTags] = useState('');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  function chooseFile(next?: File) { if (!next) return; setFile(next); if (!title) setTitle(next.name.replace(/\.pdf$/i, '')); setError(''); }
  async function readTextFile(next?: File) {
    if (!next) return;
    if (!/\.(txt|md)$/i.test(next.name)) { setError('Выберите текстовый файл .txt или .md в UTF-8.'); return; }
    if (next.size > MAX_UPLOAD_BYTES) { setError('Размер текстового файла не должен превышать 20 МБ.'); return; }
    const importedText = await next.text(); if (importedText.trim().length < 3 || importedText.length > 200000) { setError('Текст должен содержать от 3 до 200 000 символов.'); return; } setText(importedText); if (!title) setTitle(next.name.replace(/\.(txt|md)$/i, '')); setError('');
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    const invalid = validateDocument({ title, documentDate, text, file, mode }) || validateTags(tagsFromInput(tags));
    if (invalid) { setError(invalid); return; }
    setError(''); setBusy(true);
    try {
      let result: { id?: string; documentId?: string };
      if (mode === 'PDF') {
        const form = new FormData(); form.append('file', file!); form.append('title', title.trim()); form.append('tags', json(tagsFromInput(tags))); if (documentDate) form.append('documentDate', documentDate);
        result = await api('/documents/upload', { method: 'POST', body: form });
      } else result = await api('/documents/note', { method: 'POST', body: json({ title: title.trim(), documentType: mode, text: text.trim(), documentDate: documentDate || null, tags: tagsFromInput(tags) }) });
      navigate(`/archive/${result.documentId || result.id}`);
    } catch (cause) { setError(message(cause)); }
    finally { setBusy(false); }
  }
  return <><PageHeader title="Добавить в архив" description="Сохраните документ. Локальный AI подготовит краткое содержание и выделит факты." />
    <div className="upload-layout"><form className="panel form-panel" onSubmit={event => void submit(event)} noValidate>
      <fieldset disabled={busy}><legend className="section-legend">Что вы хотите добавить?</legend><div className="mode-grid">{modes.map(({ id, title: name, description, icon: Icon }) => <button type="button" key={id} className={`mode-card ${mode === id ? 'selected' : ''}`} aria-pressed={mode === id} onClick={() => { setMode(id); setError(''); }}><Icon size={23} /><strong>{name}</strong><span>{description}</span></button>)}</div>
      {mode === 'PDF' ? <div className="drop-zone" onDragOver={event => event.preventDefault()} onDrop={event => { event.preventDefault(); chooseFile(event.dataTransfer.files[0]); }}><input className="sr-only" ref={fileInput} type="file" accept=".pdf,application/pdf" aria-label="PDF-файл" onChange={event => chooseFile(event.target.files?.[0])} /><UploadCloud size={34} strokeWidth={1.4} />{file ? <><strong>{file.name}</strong><span>{(file.size / 1024 / 1024).toFixed(2)} МБ</span><button type="button" className="text-button" onClick={() => { setFile(null); if (fileInput.current) fileInput.current.value = ''; }}><X size={14} /> Убрать файл</button></> : <><strong>Перетащите PDF сюда</strong><span>или выберите файл с вашего устройства</span><button type="button" className="button secondary" onClick={() => fileInput.current?.click()}>Выбрать файл</button><small>PDF с текстовым слоем · до 20 МБ</small></>}</div> : <label>Текст {mode === 'NOTE' ? 'заметки' : 'транскрипта'} <span className="required">*</span><textarea minLength={3} maxLength={200000} rows={10} value={text} onChange={event => setText(event.target.value)} placeholder={mode === 'NOTE' ? 'Опишите наблюдения, симптомы или вопросы к врачу…' : 'Вставьте текст приёма. Сохраните числа, единицы измерения и рекомендации…'} /><span className="text-import">Или загрузите текстовый файл (.txt, .md, UTF-8)<input type="file" accept=".txt,.md,text/plain,text/markdown" aria-label="Загрузить текстовый файл" onChange={event => void readTextFile(event.target.files?.[0])} /></span></label>}
      <div className="form-grid"><label className="span-2">Название <span className="required">*</span><input maxLength={200} required value={title} onChange={event => setTitle(event.target.value)} placeholder="Например, общий анализ крови" /></label><label>Медицинская дата<input type="date" value={documentDate} onChange={event => setDocumentDate(event.target.value)} /><small>Дата исследования или события, если известна.</small></label><label>Теги<input value={tags} onChange={event => setTags(event.target.value)} placeholder="анализы, профилактика" /><small>Разделяйте запятыми.</small></label></div><ErrorNotice error={error} /><div className="form-footer"><span className="muted">Обязательные поля отмечены *</span><button type="submit" className="button primary" disabled={busy}>{busy ? <LoaderCircle className="spin" size={18} /> : <ArrowRight size={18} />}{busy ? 'Сохраняем…' : 'Сохранить и обработать'}</button></div></fieldset>
    </form><aside className="upload-aside"><div className="panel guidance"><ShieldCheck size={26} /><h2>Всё остаётся локально</h2><p>Оригинал, текст и извлечённые факты хранятся на вашем устройстве.</p><ol><li><strong>Сохраним оригинал</strong><span>Вы всегда сможете к нему вернуться.</span></li><li><strong>Выделим главное</strong><span>Краткое содержание, теги и медицинские факты.</span></li><li><strong>Свяжем с историей</strong><span>Документ появится в поиске и хронологии.</span></li></ol></div><p className="aside-note">Сканы без текстового слоя не поддерживаются. Извлечения AI нужно проверять по оригиналу.</p></aside></div>
  </>;
}


