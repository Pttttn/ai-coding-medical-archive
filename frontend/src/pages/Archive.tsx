import { useState } from 'react';
import { ArrowDownUp, ArchiveRestore, FileText, Plus, Search, SlidersHorizontal, Trash2 } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, message, query } from '../api';
import { Badge, Empty, ErrorNotice, Loading, PageHeader, Pagination, Tags } from '../components';
import { useApi, useDebounce } from '../hooks';
import type { Document, Page } from '../types';
import { date, documentTypes, statuses } from '../utils';

export function ArchivePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState(searchParams.get('q') || '');
  const deferredSearch = useDebounce(search);
  const [filterOpen, setFilterOpen] = useState(false);
  const [mutationError, setMutationError] = useState('');
  const [busyId, setBusyId] = useState('');
  const page = Math.max(1, Number(searchParams.get('page') || 1));
  const trash = searchParams.get('deleted') === 'true';
  const filters = { type: searchParams.get('type') || '', tag: searchParams.get('tag') || '', status: searchParams.get('status') || '', from: searchParams.get('from') || '', to: searchParams.get('to') || '' };
  const sort = searchParams.get('sort') || 'createdAt';
  const order = searchParams.get('order') || 'DESC';
  const path = `/documents?${query({ page, pageSize: 12, ...filters, q: deferredSearch, deleted: String(trash), sort, order })}`;
  const { data, error, loading, reload } = useApi<Page<Document>>(path, 10000);
  const set = (values: Record<string, string>) => {
    setSearchParams(previous => { const next = new URLSearchParams(previous); next.set('page', '1'); Object.entries(values).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key)); return next; });
  };
  async function changeTrash(doc: Document) {
    setMutationError(''); setBusyId(doc.id);
    try { await api(`/documents/${doc.id}${trash ? '/restore' : ''}`, { method: trash ? 'POST' : 'DELETE' }); reload(); }
    catch (cause) { setMutationError(message(cause)); }
    finally { setBusyId(''); }
  }
  const activeFilters = Object.values(filters).filter(Boolean).length;
  return <>
    <PageHeader title="Архив документов" description="Ваша медицинская история — собранная, упорядоченная и доступная." action={<Link className="button primary" to="/upload"><Plus size={18} /> Добавить документ</Link>} />
    <div className="archive-tabs"><button className={!trash ? 'active' : ''} onClick={() => set({ deleted: 'false' })}>Все документы</button><button className={trash ? 'active' : ''} onClick={() => set({ deleted: 'true' })}><Trash2 size={15} /> Корзина</button><span>{data?.total ?? '…'} документов</span></div>
    <section className="panel archive-panel">
      <div className="archive-toolbar"><label className="search-field"><Search size={19} /><input maxLength={500} aria-label="Поиск по архиву" placeholder="Поиск по названию и содержимому…" value={search} onChange={event => { setSearch(event.target.value); set({ q: event.target.value }); }} /></label><button className={`button secondary ${filterOpen ? 'selected' : ''}`} onClick={() => setFilterOpen(!filterOpen)} aria-expanded={filterOpen}><SlidersHorizontal size={17} /> Фильтры {activeFilters > 0 && <span className="number-badge">{activeFilters}</span>}</button><label className="sort-field"><ArrowDownUp size={16} /><select aria-label="Сортировка документов" value={`${sort}:${order}`} onChange={event => { const [nextSort, nextOrder] = event.target.value.split(':'); set({ sort: nextSort, order: nextOrder }); }}><option value="createdAt:DESC">Сначала новые</option><option value="createdAt:ASC">Сначала старые</option><option value="documentDate:DESC">По медицинской дате</option><option value="title:ASC">По названию</option><option value="status:ASC">По статусу</option></select></label></div>
      {filterOpen && <div className="filters-grid"><label>Тип документа<select value={filters.type} onChange={event => set({ type: event.target.value })}><option value="">Все типы</option>{Object.entries(documentTypes).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Статус<select value={filters.status} onChange={event => set({ status: event.target.value })}><option value="">Все статусы</option>{['UPLOADED', 'PARSING', 'EXTRACTING', 'INDEXING', 'READY', 'FAILED', 'UNSUPPORTED_OCR_REQUIRED'].map(status => <option key={status} value={status}>{statuses[status]}</option>)}</select></label><label>Тег<input maxLength={80} value={filters.tag} onChange={event => set({ tag: event.target.value })} placeholder="Например, кардиология" /></label><label>Дата от<input type="date" value={filters.from} onChange={event => set({ from: event.target.value })} /></label><label>Дата до<input type="date" min={filters.from} value={filters.to} onChange={event => set({ to: event.target.value })} /></label><button className="text-button" onClick={() => set({ type: '', tag: '', status: '', from: '', to: '' })}>Сбросить фильтры</button></div>}
      <ErrorNotice error={error || mutationError} retry={error ? reload : undefined} />
      {loading && !data ? <Loading /> : data?.items.length ? <><div className="table-scroll"><table className="archive-table"><thead><tr><th>Документ</th><th>Медицинская дата</th><th>Добавлен</th><th>Статус</th><th><span className="sr-only">Действия</span></th></tr></thead><tbody>{data.items.map(doc => <tr key={doc.id}><td><div className="table-document"><span className={`document-icon ${doc.documentType === 'LAB_REPORT' ? 'blue' : doc.documentType === 'NOTE' ? 'ochre' : ''}`}><FileText size={21} /></span><div><Link className="document-title" to={`/archive/${doc.id}`}>{doc.title}</Link><div className="document-meta">{documentTypes[doc.documentType] || doc.documentType}</div><Tags tags={doc.tags} /></div></div></td><td className="nowrap">{date(doc.documentDate)}</td><td className="nowrap muted">{date(doc.createdAt)}</td><td><Badge status={doc.status} /></td><td><button className="icon-button" disabled={busyId === doc.id} aria-label={trash ? `Восстановить ${doc.title}` : `Переместить в корзину ${doc.title}`} onClick={() => void changeTrash(doc)}>{trash ? <ArchiveRestore size={18} /> : <Trash2 size={17} />}</button></td></tr>)}</tbody></table></div><Pagination page={page} pageSize={12} total={data.total} onPage={next => set({ page: String(next) })} /></> : !error && <Empty title={trash ? 'Корзина пуста' : 'Документы не найдены'} action={!search && !activeFilters && !trash ? <Link className="button primary" to="/upload"><Plus size={17} /> Добавить документ</Link> : undefined}>{trash ? 'Удалённые документы можно будет восстановить здесь.' : search || activeFilters ? 'Попробуйте другой запрос или измените фильтры.' : 'Загрузите PDF, вставьте транскрипт приёма или создайте личную заметку.'}</Empty>}
    </section>
  </>;
}

