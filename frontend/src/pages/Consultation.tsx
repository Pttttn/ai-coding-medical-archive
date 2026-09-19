import { useEffect, useState } from 'react';
import { ArrowRight, CheckCheck, Copy, Download, FileCheck2, FileText, LoaderCircle, Search, ShieldCheck } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, json, message, query } from '../api';
import { ErrorNotice, Loading, Notice, PageHeader, Pagination } from '../components';
import { useApi, useDebounce } from '../hooks';
import type { Consultation, Document, Page } from '../types';
import { canExportConsultation, date, documentTypes } from '../utils';

export function ConsultationPage() {
  const [params, setParams] = useSearchParams();
  const [question, setQuestion] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const q = useDebounce(search);
  const documents = useApi<Page<Document>>(`/documents?${query({ page, pageSize: 8, status: 'READY', q })}`);
  const [consultation, setConsultation] = useState<Consultation | null>(null);
  const [draft, setDraft] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const selectedId = params.get('id');
  useEffect(() => {
    if (!selectedId || consultation?.id === selectedId) return;
    const controller = new AbortController();
    setBusy('load');
    api<Consultation>(`/consultations/${selectedId}`, { signal: controller.signal }).then(value => { setConsultation(value); setDraft(value.content); setQuestion(value.question); setSelected(value.sourceRefs.map(source => source.documentId)); }).catch(cause => { if (!controller.signal.aborted) setError(message(cause)); }).finally(() => { if (!controller.signal.aborted) setBusy(''); });
    return () => controller.abort();
  }, [selectedId, consultation?.id]);
  const dirty = Boolean(consultation && draft !== consultation.content);
  const reviewed = consultation ? canExportConsultation(consultation.content, draft, consultation.contentHash, consultation.reviewedHash) : false;
  const resetFeedback = () => { setError(''); setSuccess(''); };
  function edit(value: string) {
    setDraft(value); setAcknowledged(false); setSuccess('');
    setConsultation(previous => previous ? { ...previous, reviewedHash: null } : null);
  }
  async function prepare() {
    resetFeedback();
    if (question.trim().length < 3 || question.length > 4000) { setError('Вопрос должен содержать от 3 до 4000 символов.'); return; }
    setBusy('prepare'); setAcknowledged(false);
    try {
      const value = await api<Consultation>('/consultations/prepare', { method: 'POST', body: json({ question: question.trim(), ...(selected.length ? { documentIds: selected } : {}) }) });
      setConsultation(value); setDraft(value.content); setParams({ id: value.id });
    } catch (cause) { setError(message(cause)); }
    finally { setBusy(''); }
  }
  async function saveDraft() {
    if (!consultation) return;
    resetFeedback(); setBusy('save'); setAcknowledged(false);
    try { const value = await api<Consultation>(`/consultations/${consultation.id}`, { method: 'PATCH', body: json({ content: draft }) }); setConsultation(value); setDraft(value.content); setSuccess('Правки сохранены. Проверьте текущий текст перед экспортом.'); }
    catch (cause) { setError(message(cause)); }
    finally { setBusy(''); }
  }
  async function review() {
    if (!consultation || !acknowledged || dirty) return;
    resetFeedback(); setBusy('review');
    try { const value = await api<Consultation>(`/consultations/${consultation.id}/review`, { method: 'POST', body: json({ contentHash: consultation.contentHash }) }); setConsultation(value); setSuccess('Текущая версия проверена. Можно скопировать или сохранить Markdown.'); }
    catch (cause) { setError(message(cause)); }
    finally { setBusy(''); }
  }
  async function exportContent(copy: boolean) {
    if (!consultation || !reviewed) return;
    resetFeedback(); setBusy(copy ? 'copy' : 'export');
    try {
      const content = await api<string>(`/consultations/${consultation.id}/export`);
      if (content !== consultation.content) throw new Error('Сохранённая версия изменилась. Откройте и проверьте актуальный текст перед экспортом.');
      if (copy) { await navigator.clipboard.writeText(content); setSuccess('Проверенный пакет скопирован в буфер обмена.'); }
      else { const url = URL.createObjectURL(new Blob([content], { type: 'text/markdown;charset=utf-8' })); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'consultation.md'; document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); setSuccess('Markdown-файл сохранён.'); }
    } catch (cause) { setError(message(cause)); }
    finally { setBusy(''); }
  }
  return <><PageHeader eyebrow="ПОДГОТОВКА К ВНЕШНЕЙ КОНСУЛЬТАЦИИ" title="Важный контекст. Без лишнего." description="Соберите минимальный пакет, проверьте обезличенный текст и передайте его самостоятельно." />
    <div className="consultation-steps"><span className="active"><b>1</b> Вопрос и контекст</span><i /><span className={consultation ? 'active' : ''}><b>2</b> Проверка текста</span><i /><span className={reviewed ? 'active' : ''}><b>3</b> Ручной экспорт</span></div>
    <ErrorNotice error={error} />{success && <Notice variant="success">{success}</Notice>}
    <div className="consultation-layout"><section className="panel consultation-setup"><div className="panel-heading"><div><h2>Вопрос и документы</h2><p>Только то, что нужно для вашего вопроса</p></div></div><div className="panel-body"><label>Вопрос для консультации<textarea rows={4} minLength={3} maxLength={4000} value={question} disabled={Boolean(busy)} onChange={event => setQuestion(event.target.value)} placeholder="Что вы хотите обсудить? Не добавляйте имя, контакты и номера документов." /></label><div className="selection-heading"><h3>Документы для контекста</h3><span className="number-badge">{selected.length}</span></div><p className="muted small-text">Выберите документы или оставьте выбор пустым — архив найдёт релевантные фрагменты.</p><label className="search-field"><Search size={16} /><input aria-label="Поиск документов для консультации" value={search} onChange={event => { setSearch(event.target.value); setPage(1); }} placeholder="Найти документ…" /></label><ErrorNotice error={documents.error} retry={documents.reload} />{documents.loading ? <Loading /> : <div className="document-selection">{documents.data?.items.length ? documents.data.items.map(doc => <label key={doc.id} className={`selection-item ${selected.includes(doc.id) ? 'selected' : ''}`}><input type="checkbox" checked={selected.includes(doc.id)} disabled={Boolean(busy)} onChange={event => setSelected(previous => event.target.checked ? [...previous, doc.id] : previous.filter(id => id !== doc.id))} /><FileText size={18} /><span><strong>{doc.title}</strong><small>{documentTypes[doc.documentType]} · {date(doc.documentDate)}</small></span></label>) : <p className="muted">Готовые документы не найдены.</p>}</div>}{documents.data && documents.data.total > 8 && <Pagination page={page} pageSize={8} total={documents.data.total} onPage={setPage} />}{selected.length > 0 && <button className="text-button" disabled={Boolean(busy)} onClick={() => setSelected([])}>Снять выбор со всех документов</button>}<button className="button primary full-width" disabled={Boolean(busy)} onClick={() => void prepare()}>{busy === 'prepare' ? <LoaderCircle className="spin" size={18} /> : <ShieldCheck size={18} />}{busy === 'prepare' ? 'Готовим безопасный контекст…' : consultation ? 'Подготовить новый пакет' : 'Подготовить пакет'}<ArrowRight size={17} /></button></div></section>
      <section className={`panel consultation-preview ${!consultation ? 'preview-placeholder' : ''}`}>{busy === 'load' ? <Loading /> : consultation ? <><div className="panel-heading"><div><h2>Точный текст для передачи</h2><p>Можно отредактировать перед проверкой</p></div><span className={`subtle-pill ${reviewed ? 'verified' : ''}`}>{reviewed ? <><CheckCheck size={15} /> Проверено</> : 'Черновик'}</span></div><div className="panel-body">{consultation.warnings?.length > 0 && <Notice variant="warning"><strong>Проверьте перед экспортом</strong><ul>{consultation.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></Notice>}<label className="sr-only" htmlFor="consultation-preview">Текст пакета консультации</label><textarea id="consultation-preview" className="payload-editor" maxLength={100000} rows={19} value={draft} onChange={event => edit(event.target.value)} disabled={Boolean(busy)} spellCheck={false} /><div className="draft-status"><span>{draft.length.toLocaleString('ru-RU')} символов{dirty && ' · Есть несохранённые правки'}</span><button className="button secondary small" disabled={!dirty || Boolean(busy) || !draft.trim()} onClick={() => void saveDraft()}>{busy === 'save' ? 'Сохраняем…' : 'Сохранить правки'}</button></div><ReviewControls dirty={dirty} reviewed={reviewed} acknowledged={acknowledged} busy={Boolean(busy)} onAcknowledge={setAcknowledged} onReview={() => void review()} onCopy={() => void exportContent(true)} onExport={() => void exportContent(false)} />
      {consultation.sourceRefs?.length > 0 && <details className="context-details"><summary>Выбранный локальный контекст · {consultation.sourceRefs.length} источников</summary><p className="muted">Эти ссылки и исходные фрагменты остаются в архиве и не включаются в экспорт.</p>{consultation.sourceRefs.map(source => <p key={source.documentId}><Link to={`/archive/${source.documentId}`}>{source.title}</Link> · версия {source.textVersion}</p>)}{consultation.contexts?.map((context, index) => <blockquote key={index}>{context.text}</blockquote>)}</details>}</div></> : <><div className="preview-illustration"><FileCheck2 size={49} strokeWidth={1.3} /><ShieldCheck size={25} /></div><h2>Здесь появится ваш пакет</h2><p>Локальная модель отберёт контекст и обработает идентификаторы. Проверьте каждую строку перед передачей.</p><span className="local-label"><i /> Без автоматической отправки</span></>}</section>
    </div><div className="consultation-footnote"><ShieldCheck size={18} /><p>Деперсонализация может ошибаться. Проверьте имена, контакты, адреса, номера документов и другие узнаваемые детали. Экспорт содержит только проверенный текст.</p></div>
  </>;
}

export function ReviewControls({ dirty, reviewed, acknowledged, busy, onAcknowledge, onReview, onCopy, onExport }: { dirty: boolean; reviewed: boolean; acknowledged: boolean; busy: boolean; onAcknowledge: (value: boolean) => void; onReview: () => void; onCopy: () => void; onExport: () => void }) {
  return <div className="review-controls"><label className="review-checkbox"><input type="checkbox" checked={acknowledged} disabled={dirty || busy || reviewed} onChange={event => onAcknowledge(event.target.checked)} /><span>Я прочитал(а) текущий текст и проверил(а), что в нём нет персональных идентификаторов, а медицинские сведения сохранены верно.</span></label>{dirty && <p className="small-text muted">Сначала сохраните правки, затем проверьте новую версию.</p>}<div className="export-actions">{!reviewed && <button className="button primary" disabled={dirty || !acknowledged || busy} onClick={onReview}><CheckCheck size={17} /> Подтвердить проверку</button>}<button className="button secondary" disabled={!reviewed || dirty || busy} onClick={onCopy}><Copy size={16} /> Копировать</button><button className="button secondary" disabled={!reviewed || dirty || busy} onClick={onExport}><Download size={16} /> Markdown</button></div><small>Любая правка снимает подтверждение текущей версии.</small></div>;
}


