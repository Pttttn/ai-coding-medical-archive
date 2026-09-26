import { useState } from 'react';
import { Activity, ArrowUpRight, CalendarDays, Filter } from 'lucide-react';
import { Link } from 'react-router-dom';
import { query } from '../api';
import { Empty, ErrorNotice, Loading, PageHeader, Pagination } from '../components';
import { useApi } from '../hooks';
import type { Document, Page, TimelineEvent } from '../types';
import { date, documentTypes, factTypes } from '../utils';

export function TimelinePage() {
  const [filters, setFilters] = useState({ type: '', category: '', from: '', to: '', documentId: '' });
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useApi<Page<TimelineEvent>>(`/timeline?${query({ ...filters, page, pageSize: 20 })}`);
  const docs = useApi<Page<Document>>('/documents?pageSize=100&sort=title&order=ASC');
  const change = (key: keyof typeof filters, value: string) => { setFilters(previous => ({ ...previous, [key]: value, ...(key === 'type' ? { category: '' } : key === 'category' ? { type: '' } : {}) })); setPage(1); };
  return <><PageHeader title="Хронология здоровья" description="Связанные события и медицинские факты в последовательной истории." action={<span className="subtle-pill"><CalendarDays size={15} /> По дате события</span>} />
    <section className="panel timeline-filters"><div className="filters-heading"><Filter size={17} /><strong>Настроить хронологию</strong><button className="text-button" onClick={() => { setFilters({ type: '', category: '', from: '', to: '', documentId: '' }); setPage(1); }}>Сбросить</button></div><div className="filters-grid"><label>Тип события<select value={filters.type} onChange={event => change('type', event.target.value)}><option value="">Все события</option>{Object.entries({ ...documentTypes, ...factTypes }).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Категория<select value={filters.category} onChange={event => change('category', event.target.value)}><option value="">Все категории</option>{Object.entries(factTypes).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Документ<select value={filters.documentId} onChange={event => change('documentId', event.target.value)}><option value="">Все документы</option>{docs.data?.items.map(doc => <option key={doc.id} value={doc.id}>{doc.title}</option>)}</select></label><label>Дата от<input type="date" value={filters.from} onChange={event => change('from', event.target.value)} /></label><label>Дата до<input type="date" min={filters.from} value={filters.to} onChange={event => change('to', event.target.value)} /></label></div></section>
    <ErrorNotice error={error} retry={reload} />{loading ? <Loading /> : data?.items.length ? <><div className="timeline">{data.items.map(item => <article className="timeline-event" key={item.id}><div className="timeline-date">{date(item.eventDate)}</div><span className="timeline-node"><Activity size={16} /></span><div className="panel timeline-card"><span className="fact-category">{factTypes[item.eventType] || documentTypes[item.eventType] || item.eventType}</span><h2>{item.title}</h2><p>{item.description}</p>{item.earlierText && <small className="muted">По предыдущей версии текста; изменённый текст ещё не обработан.</small>}<Link to={`/archive/${item.documentId}`} className="text-link">{item.documentTitle || 'Открыть документ'} <ArrowUpRight size={15} /></Link></div></article>)}</div><Pagination page={page} pageSize={20} total={data.total} onPage={setPage} /></> : !error && <section className="panel"><Empty title="События не найдены">Измените фильтры или добавьте документы. События без известной даты отображаются отдельно без подстановки даты загрузки.</Empty></section>}
  </>;
}

