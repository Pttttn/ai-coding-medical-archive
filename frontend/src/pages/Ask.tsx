import { useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowRight, ArrowUpRight, BookOpen, FileText, LoaderCircle, Search, ShieldCheck, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api, json, message } from '../api';
import { ErrorNotice, Notice, PageHeader } from '../components';
import type { AskAnswer } from '../types';

const prompts = ['Есть ли у пациента хронические заболевания?', 'Подозревали ли диабет и чем закончилось обследование?', 'Был ли повышен холестерин?', 'Какие отклонения в анализах были за последний год?', 'Были ли травмы головы?', 'Какие обследования есть в архиве?', 'Что рекомендовали на последнем приёме?', 'Как менялись показатели анализов?'];
export function AskPage() {
  const [question, setQuestion] = useState('');
  const [askedQuestion, setAskedQuestion] = useState('');
  const [answer, setAnswer] = useState<AskAnswer | null>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (question.trim().length < 3 || question.length > 4000) { setError('Вопрос должен содержать от 3 до 4000 символов.'); return; }
    if (dateFrom && dateTo && dateFrom > dateTo) { setError('Начало периода должно быть не позже конца.'); return; }
    setError(''); setBusy(true); setAnswer(null); setAskedQuestion(question.trim());
    try { setAnswer(await api<AskAnswer>('/ask', { method: 'POST', body: json({ question: question.trim(), dateFrom: dateFrom || undefined, dateTo: dateTo || undefined }) })); }
    catch (cause) { setError(message(cause)); }
    finally { setBusy(false); }
  }
  return <><PageHeader eyebrow="ОТВЕТЫ С ОПОРОЙ НА ИСТОЧНИКИ" title="Спросить архив" description="Найдите нужное в своей медицинской истории — задайте вопрос обычными словами." />
    <div className="ask-layout"><div><form className="panel ask-form" onSubmit={event => void submit(event)}><div className="ask-heading"><span className="summary-icon"><Sparkles size={23} /></span><div><h2>Что вы хотите узнать?</h2><p>Ответ строится на документах вашего архива.</p></div></div><label className="sr-only" htmlFor="archive-question">Вопрос к архиву</label><textarea id="archive-question" minLength={3} maxLength={4000} rows={4} value={question} onChange={event => setQuestion(event.target.value)} placeholder="Например, какие рекомендации были даны на последнем приёме?" disabled={busy} /><fieldset className="ask-period" disabled={busy}><legend>Период по датам документов (необязательно)</legend><label>С<input type="date" value={dateFrom} onChange={event => setDateFrom(event.target.value)} /></label><label>По<input type="date" value={dateTo} onChange={event => setDateTo(event.target.value)} /></label><p>Если даты не заданы, используем период из вопроса или всю историю.</p></fieldset><div className="ask-form-bottom"><span><ShieldCheck size={15} /> Обрабатывается локально</span><button className="button primary" type="submit" disabled={busy}>{busy ? <LoaderCircle size={17} className="spin" /> : <ArrowRight size={17} />}{busy ? 'Ищем ответ…' : 'Спросить архив'}</button></div></form><ErrorNotice error={error} />
      {!answer && !busy && <div className="suggestions"><span className="eyebrow">МОЖНО НАЧАТЬ С ЭТОГО</span>{prompts.map(prompt => <button key={prompt} onClick={() => setQuestion(prompt)}>{prompt}<ArrowUpRight size={16} /></button>)}</div>}
      {busy && <section className="panel answer-loading" role="status"><LoaderCircle size={25} className="spin" /><h3>Изучаем ваш архив</h3><p>Просматриваем документы и проверяем цитаты. Обзор истории занимает больше времени, чем поиск одного показателя. Локальной модели может понадобиться несколько минут.</p><div className="processing-steps"><span><Search size={15} /> Поиск</span><span><BookOpen size={15} /> Проверка контекста</span><span><Sparkles size={15} /> Ответ</span></div></section>}
      {answer && <section className="panel answer-panel" aria-live="polite"><div className="answered-question">{askedQuestion}</div><div className="answer-heading"><span className="summary-icon"><Sparkles size={20} /></span><h2>Ответ архива</h2></div>{answer.coverage && <div className="coverage-summary"><p>Просмотрено документов: {answer.coverage.scannedDocuments} из {answer.coverage.eligibleDocuments}. {answer.coverage.complete ? "Все доступные фрагменты просмотрены; полноту найденных сведений проверьте по источникам." : "Обзор неполный."}</p><p>Период: {answer.coverage.period.from || "с начала истории"} — {answer.coverage.period.to || "без верхней границы"}. Относительные даты рассчитаны на {answer.coverage.period.asOf}.</p></div>}{answer.warnings?.map(warning => <Notice key={warning} variant="warning">{warning}</Notice>)}<div className="answer-text">{answer.answer}</div><div className="sources-heading"><BookOpen size={17} /><h3>Источники</h3><span className="number-badge">{answer.sources.length}</span></div>{answer.sources.length ? <div className="sources-list">{answer.sources.map((source, index) => <article className="source-card" key={`${source.chunkId}-${index}`}><span className="source-number">{index + 1}</span><div>{source.documentId ? <Link to={`/archive/${source.documentId}`} className="text-link">{source.source || 'Документ архива'}<ArrowUpRight size={14} /></Link> : <strong>{source.source}</strong>}<p className="source-location">{source.documentDate && `${source.documentDate} · `}{source.pageNumber ? `Страница ${source.pageNumber}` : `Фрагмент ${source.position + 1}`}</p>{source.text && <blockquote>{source.text}</blockquote>}</div></article>)}</div> : <p className="muted">Подтверждающие источники не найдены.</p>}{answer.trace != null && <details className="trace-details"><summary>Как выполнялся поиск</summary><pre>{JSON.stringify(answer.trace, null, 2)}</pre></details>}</section>}
    </div><aside><div className="panel guidance"><BookOpen size={25} /><h2>Ответ можно проверить</h2><p>Рядом с ответом появятся фрагменты документов. Откройте источник, чтобы увидеть полный контекст.</p><div className="guidance-divider" /><h3>Чем точнее вопрос,<br />тем полезнее ответ</h3><p>Добавьте название показателя, период или вид обследования, если они известны.</p></div><div className="aside-note"><FileText size={16} /><p>Архив помогает находить сведения. Медицинские решения обсудите с лечащим врачом.</p></div></aside></div>
  </>;
}

