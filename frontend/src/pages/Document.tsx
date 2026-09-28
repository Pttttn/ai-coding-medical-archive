import { VisitPanel } from '../VisitPanel';
import { useState } from 'react';
import { LaboratoryPanel } from '../LaboratoryPanel';
import type { FormEvent } from 'react';
import { ArrowLeft, ArchiveRestore, Check, ExternalLink, FileText, History, Pencil, Quote, RotateCw, Save, Sparkles, Trash2 } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { PurgePanel } from '../PurgePanel';
import { api, json, message } from '../api';
import { Badge, Empty, ErrorNotice, HistoryList, Loading, Notice, Pagination, Tags } from '../components';
import { useApi } from '../hooks';
import type { Document, Fact, FactRevision, FactSource, HistoryEvent, Page, TextRevision } from '../types';
import { assertions, date, dateInput, dateTime, documentTypes, factTypes, hasFactCorrection, isProcessing, reviews, revisionNotice, tagsFromInput, validateDocument, validateTags } from '../utils';

export function DocumentPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const state = useApi<Document>(`/documents/${id}`, 5000);
  const [tab, setTab] = useState('facts');
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [busy, setBusy] = useState(false);
  const doc = state.data;
  async function action(type: 'delete' | 'restore' | 'reprocess') {
    setBusy(true); setError(''); setSuccess('');
    try { await api(`/documents/${id}${type === 'delete' ? '' : `/${type}`}`, { method: type === 'delete' ? 'DELETE' : 'POST' }); setSuccess(type === 'delete' ? 'Документ перемещён в корзину. Его можно восстановить.' : type === 'restore' ? 'Документ восстановлен.' : 'Документ добавлен в очередь обработки.'); state.reload(); }
    catch (cause) { setError(message(cause)); }
    finally { setBusy(false); }
  }
  if (state.loading && !doc) return <Loading />;
  if (!doc) return <ErrorNotice error={state.error || 'Документ не найден.'} retry={state.reload} />;
  return <><Link className="back-link" to="/archive"><ArrowLeft size={16} /> К архиву документов</Link>
    <header className="document-heading"><div className="document-hero-icon"><FileText size={29} strokeWidth={1.5} /></div><div><div className="eyebrow">{documentTypes[doc.documentType] || doc.documentType}</div><h1>{doc.title}</h1><div className="document-meta">{date(doc.documentDate)}<span>·</span>Добавлен {date(doc.createdAt)}</div></div><Badge status={doc.status} /></header>
    <div className="document-actions"><Tags tags={doc.tags} /><div>{!doc.deletedAt && <><button className="button secondary small" onClick={() => setEditing(!editing)}><Pencil size={15} /> Изменить</button><button className="button secondary small" disabled={busy || isProcessing(doc.status)} onClick={() => void action('reprocess')}><RotateCw size={15} /> Обработать снова</button></>}{doc.originalFilename && !doc.deletedAt && <a className="button secondary small" href={`/api/documents/${id}/original`} target="_blank" rel="noreferrer"><ExternalLink size={15} /> Оригинал</a>}<button className="icon-button" aria-label={doc.deletedAt ? 'Восстановить документ' : 'Переместить документ в корзину'} disabled={busy} onClick={() => void action(doc.deletedAt ? 'restore' : 'delete')}>{doc.deletedAt ? <ArchiveRestore size={18} /> : <Trash2 size={18} />}</button></div></div>
    <ErrorNotice error={error || state.error} />{success && <Notice variant="success">{success}</Notice>}
    {doc.isSeed && <Notice>Синтетический демодокумент. Первоначальные извлечения подготовлены заранее для демонстрации; повторная обработка использует локальную модель.</Notice>}{doc.deletedAt && <><Notice variant="warning">Документ находится в корзине и исключён из поиска и хронологии.</Notice><PurgePanel documentId={doc.id} onPurged={() => navigate('/archive?deleted=true')} /></>}
    {doc.processingWarnings && doc.processingWarnings.length > 0 && <Notice variant="warning"><strong>Обратите внимание на результат обработки</strong><ul>{doc.processingWarnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></Notice>}{isProcessing(doc.status) && <Notice>Обработка выполняется локально. Статус и результаты обновятся автоматически.</Notice>}{revisionNotice(doc) && <Notice>{revisionNotice(doc)}</Notice>}
    {['FAILED', 'UNSUPPORTED_OCR_REQUIRED'].includes(doc.status) && <Notice variant="warning">{doc.status === 'UNSUPPORTED_OCR_REQUIRED' ? 'В PDF не найден текстовый слой. Добавьте документ с выделяемым текстом или вставьте текст вручную.' : `Не удалось завершить обработку. ${doc.latestJob?.errorCode || ''} Повторите её после проверки локальной модели.`}</Notice>}
    {editing && <MetadataEditor doc={doc} onSaved={() => { setEditing(false); state.reload(); setSuccess('Изменения сохранены.'); }} onCancel={() => setEditing(false)} />}
    <section className="summary-panel"><span className="summary-icon"><Sparkles size={22} /></span><div><h2>Краткое содержание <span className="subtle-pill">{doc.isSeed ? 'Синтетическое демо' : doc.laboratory ? 'Разбор строк' : 'AI'}</span></h2><p>{doc.summary || 'Краткое содержание появится после обработки документа.'}</p></div></section>
    <div className="archive-tabs document-tabs"><button className={tab === 'facts' ? 'active' : ''} onClick={() => setTab('facts')}>Медицинские факты{doc.facts && <span className="number-badge">{doc.facts.length}</span>}</button>{doc.visit && <button className={tab === 'visit' ? 'active' : ''} onClick={() => setTab('visit')}>Клинические утверждения</button>}{doc.laboratory && <button className={tab === 'laboratory' ? 'active' : ''} onClick={() => setTab('laboratory')}>Лабораторные строки</button>}<button className={tab === 'text' ? 'active' : ''} onClick={() => setTab('text')}>Текст документа</button><button className={tab === 'history' ? 'active' : ''} onClick={() => setTab('history')}><History size={15} /> История</button></div>
    {tab === 'facts' && <><p className="facts-note">Утверждение источника и ваша проверка отображаются отдельно. Откройте цитату перед подтверждением или исправлением.</p>{doc.facts?.length ? <div className="facts-grid">{doc.facts.map(fact => <FactCard key={`${fact.id}-${fact.updatedAt}-${fact.reviewStatus}-${fact.valueText}-${fact.valueNumber}`} fact={fact} disabled={Boolean(doc.deletedAt)} onSaved={state.reload} />)}</div> : <div className="panel"><Empty title="Фактов пока нет">Они появятся после обработки, если в документе найдётся подходящая медицинская информация.</Empty></div>}</>}
    {tab === 'visit' && (doc.visit ? <VisitPanel visit={doc.visit} pages={doc.pages} version={doc.textVersion} /> : <Notice>Результат обработки сейчас недоступен.</Notice>)}
    {tab === 'laboratory' && (doc.laboratory ? <LaboratoryPanel lab={doc.laboratory} pages={doc.pages} version={doc.textVersion} /> : <Notice>Результат обработки сейчас недоступен.</Notice>)}
    {tab === 'text' && <TextPanel doc={doc} onSaved={state.reload} />}
    {tab === 'history' && <DocumentHistory id={doc.id} />}
  </>;
}

function MetadataEditor({ doc, onSaved, onCancel }: { doc: Document; onSaved: () => void; onCancel: () => void }) {
  const [title, setTitle] = useState(doc.title);
  const [documentType, setType] = useState(doc.documentType);
  const [documentDate, setDate] = useState(dateInput(doc.documentDate));
  const [tags, setTags] = useState(doc.tags.join(', '));
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function save(event: FormEvent) {
    event.preventDefault();
    const invalid = validateDocument({ title, documentDate, text: 'metadata', mode: 'NOTE' }) || validateTags(tagsFromInput(tags));
    if (invalid) { setError(invalid); return; }
    setBusy(true); setError('');
    try { await api(`/documents/${doc.id}`, { method: 'PATCH', body: json({ title: title.trim(), documentType, documentDate: documentDate || null, tags: tagsFromInput(tags) }) }); onSaved(); }
    catch (cause) { setError(message(cause)); }
    finally { setBusy(false); }
  }
  return <form className="panel form-panel metadata-editor" onSubmit={event => void save(event)}><h2>Редактировать документ</h2><fieldset disabled={busy}><div className="form-grid"><label className="span-2">Название<input value={title} maxLength={200} onChange={event => setTitle(event.target.value)} required /></label><label>Тип документа<select value={documentType} onChange={event => setType(event.target.value)}>{Object.entries(documentTypes).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Медицинская дата<input type="date" value={documentDate} onChange={event => setDate(event.target.value)} /></label><label className="span-2">Теги через запятую<input value={tags} onChange={event => setTags(event.target.value)} /></label></div><ErrorNotice error={error} /><div className="form-footer"><button className="button secondary" type="button" onClick={onCancel}>Отмена</button><button className="button primary" type="submit"><Save size={17} /> {busy ? 'Сохраняем…' : 'Сохранить'}</button></div></fieldset></form>;
}

function TextPanel({ doc, onSaved }: { doc: Document; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(doc.text || '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState<TextRevision | null>(null);
  const editable = ['NOTE', 'VISIT_TRANSCRIPT', 'TEXT'].includes(doc.sourceType) || ['NOTE', 'VISIT_TRANSCRIPT'].includes(doc.documentType) && doc.sourceType !== 'PDF';
  async function save() {
    if (text.trim().length < 3 || text.length > 200000) { setError('Текст должен содержать от 3 до 200 000 символов.'); return; }
    setBusy(true); setError('');
    try { await api(`/documents/${doc.id}`, { method: 'PATCH', body: json({ text }) }); setEditing(false); setRevision(null); onSaved(); }
    catch (cause) { setError(message(cause)); }
    finally { setBusy(false); }
  }
  async function loadRevision(version: string) {
    setError('');
    if (!version) { setRevision(null); return; }
    try { setRevision(await api<TextRevision>(`/documents/${doc.id}/text-revisions/${version}`)); }
    catch (cause) { setError(message(cause)); }
  }
  return <section className="panel text-panel"><div className="panel-heading"><div><h2>Текст документа</h2><p>Версия {revision?.version || doc.textVersion || 1}. Исходный файл хранится отдельно.</p></div><div className="inline-actions">{doc.textRevisions && doc.textRevisions.length > 1 && <select aria-label="Версия текста" value={revision?.version || ''} onChange={event => void loadRevision(event.target.value)}><option value="">Текущая версия</option>{doc.textRevisions.filter(item => item.version !== doc.textVersion).map(item => <option key={item.id} value={item.version}>Версия {item.version} · {date(item.createdAt)}</option>)}</select>}{editable && !doc.deletedAt && !revision && <button className="button secondary small" onClick={() => { setText(doc.text || ''); setEditing(!editing); }}><Pencil size={15} /> {editing ? 'Отмена' : 'Редактировать текст'}</button>}</div></div><ErrorNotice error={error} />{editing ? <div className="panel-body"><Notice>Сохраним новую версию текста и запустим обработку. Старые версии останутся в истории.</Notice><textarea maxLength={200000} aria-label="Текст документа" rows={18} value={text} onChange={event => setText(event.target.value)} /><button className="button primary" disabled={busy} onClick={() => void save()}><Save size={16} /> {busy ? 'Сохраняем…' : 'Сохранить новую версию'}</button></div> : <pre className="document-text">{revision ? revision.text || revision.content || 'Версия не содержит текста.' : doc.text || 'Текст ещё не извлечён.'}</pre>}</section>;
}

function FactCard({ fact, disabled, onSaved }: { fact: Fact; disabled: boolean; onSaved: () => void }) {
  const corrected = hasFactCorrection({ ...fact });
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [error, setError] = useState('');
  const [source, setSource] = useState<FactSource | null>(null);
  const [busy, setBusy] = useState(false);
  const [valueText, setValueText] = useState(fact.valueText || '');
  const [valueNumber, setValueNumber] = useState(fact.valueNumber == null ? '' : String(fact.valueNumber));
  const [unit, setUnit] = useState(fact.unit || '');
  const [name, setName] = useState(fact.name);
  const [eventDate, setEventDate] = useState(dateInput(fact.eventDate));
  const [assertionStatus, setAssertion] = useState(fact.assertionStatus);
  async function sourceToggle() {
    setExpanded(!expanded);
    if (!source) { setBusy(true); try { setSource(await api<FactSource>(`/facts/${fact.id}/source`)); } catch (cause) { setError(message(cause)); } finally { setBusy(false); } }
  }
  async function update(reviewStatus: string) {
    setBusy(true); setError('');
    const correction = reviewStatus === 'CORRECTED' ? { name, valueText: valueText || null, valueNumber: valueNumber === '' ? null : Number(valueNumber), unit: unit || null, eventDate: eventDate || null, assertionStatus } : {};
    if (!name.trim() || (valueNumber !== '' && !Number.isFinite(Number(valueNumber)))) { setError('Проверьте название и числовое значение.'); setBusy(false); return; }
    try { await api(`/facts/${fact.id}`, { method: 'PATCH', body: json({ ...correction, reviewStatus }) }); setEditing(false); onSaved(); }
    catch (cause) { setError(message(cause)); }
    finally { setBusy(false); }
  }
  return <article className={`panel fact-card ${fact.reviewStatus === 'REJECTED' ? 'rejected' : ''}`}><div className="fact-topline"><span className="fact-category">{factTypes[fact.type] || fact.type}</span><span className={`review-label ${fact.reviewStatus.toLowerCase()}`}>{reviews[fact.reviewStatus] || fact.reviewStatus}</span></div>{corrected && fact.reviewStatus !== 'CORRECTED' && <p className="small-text muted">Значение исправлено пользователем.</p>}<h3>{fact.name}</h3><div className="fact-value">{fact.valueNumber != null ? <strong>{fact.valueNumber} {fact.unit}</strong> : null}{fact.valueText && <p>{fact.valueText}</p>}</div><div className="fact-meta"><span>{assertions[fact.assertionStatus] || fact.assertionStatus}</span><span>{date(fact.eventDate)}</span>{fact.confidence != null && <span title="Оценка модели, не клиническая достоверность">Оценка AI: {Math.round(fact.confidence * 100)}%</span>}</div>
    <ErrorNotice error={error} />
    <div className="fact-actions"><button className="text-button" onClick={() => void sourceToggle()} aria-expanded={expanded}><Quote size={16} /> {expanded ? 'Скрыть источник' : 'Цитата и источник'}</button><button className="icon-button" aria-label={`История факта ${fact.name}`} aria-expanded={showHistory} onClick={() => setShowHistory(!showHistory)}><History size={16} /></button>{!disabled && <button className="icon-button" aria-label={`Исправить факт ${fact.name}`} onClick={() => setEditing(!editing)}><Pencil size={16} /></button>}</div>
    {expanded && <div className="provenance">{busy && !source ? <Loading label="Открываем источник…" /> : source && <><blockquote>{source.sourceText || 'Для этого факта не найдена подтверждающая цитата.'}</blockquote><p>{source.documentTitle} · версия {source.textVersion}{source.pageNumber ? ` · стр. ${source.pageNumber}` : ''}</p>{corrected && <small>Цитата относится к исходному документу. Текущее значение исправлено пользователем.</small>}{!disabled && <div className="inline-actions"><button className="button secondary small" disabled={busy || !source.sourceText} onClick={() => void update('CONFIRMED')}><Check size={15} /> Подтвердить</button><button className="text-button danger-text" disabled={busy} onClick={() => void update('REJECTED')}>Отклонить факт</button></div>}</>}</div>}
    {editing && <form className="fact-editor" onSubmit={event => { event.preventDefault(); void update('CORRECTED'); }}><fieldset disabled={busy}><label>Название<input required maxLength={300} value={name} onChange={event => setName(event.target.value)} /></label><label>Текстовое значение<textarea rows={3} maxLength={10000} value={valueText} onChange={event => setValueText(event.target.value)} /></label><div className="form-grid"><label>Число<input type="number" step="any" value={valueNumber} onChange={event => setValueNumber(event.target.value)} /></label><label>Единицы<input maxLength={100} value={unit} onChange={event => setUnit(event.target.value)} /></label><label>Дата события<input type="date" value={eventDate} onChange={event => setEventDate(event.target.value)} /></label><label>Утверждение источника<select value={assertionStatus} onChange={event => setAssertion(event.target.value)}>{Object.entries(assertions).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label></div><p className="muted">Исправление будет отмечено как ваше и сохранено в истории.</p><button className="button primary small" type="submit"><Save size={15} /> Сохранить исправление</button></fieldset></form>}
    {showHistory && <FactHistory id={fact.id} />}
  </article>;
}
function FactHistory({ id }: { id: string }) {
  const { data, error, loading } = useApi<Page<FactRevision>>(`/facts/${id}/history?page=1&pageSize=20`);
  return <div className="fact-revisions"><h4>История факта</h4><ErrorNotice error={error} />{loading ? <Loading /> : data?.items.length ? data.items.map(item => <details key={item.id}><summary>{dateTime(item.createdAt)} · {reviews[item.changeType] || item.changeType}</summary><div className="change-grid"><pre>{JSON.stringify(item.oldValue, null, 2)}</pre><pre>{JSON.stringify(item.newValue, null, 2)}</pre></div></details>) : <p className="muted">Факт пока не изменялся.</p>}</div>;
}
function DocumentHistory({ id }: { id: string }) {
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useApi<Page<HistoryEvent>>(`/documents/${id}/history?page=${page}&pageSize=15`);
  return <section className="panel"><ErrorNotice error={error} retry={reload} />{loading ? <Loading /> : data?.items.length ? <><HistoryList items={data.items} /><Pagination page={page} pageSize={15} total={data.total} onPage={setPage} /></> : <Empty title="Нет изменений">Действия с документом будут сохранены здесь.</Empty>}</section>;
}




