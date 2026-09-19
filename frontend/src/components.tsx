import type { ReactNode } from 'react';
import { ArrowLeft, ArrowRight, Check, CircleAlert, FileText, Inbox, LoaderCircle, RotateCw, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Document, HistoryEvent } from './types';
import { actions, date, dateTime, documentTypes, isProcessing, statuses } from './utils';

export function PageHeader({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description: string; action?: ReactNode }) {
  return <header className="page-heading"><div><div className="eyebrow">{eyebrow || 'МОЙ МЕДИЦИНСКИЙ АРХИВ'}</div><h1>{title}</h1><p>{description}</p></div>{action && <div className="heading-action">{action}</div>}</header>;
}
export function Loading({ label = 'Загружаем данные…' }: { label?: string }) {
  return <div className="loading" role="status"><LoaderCircle className="spin" size={23} /><span>{label}</span></div>;
}
export function ErrorNotice({ error, retry }: { error: string; retry?: () => void }) {
  if (!error) return null;
  return <div className="notice error" role="alert"><CircleAlert size={19} /><div>{error}</div>{retry && <button className="text-button" onClick={retry}><RotateCw size={15} /> Повторить</button>}</div>;
}
export function Notice({ children, variant = 'info' }: { children: ReactNode; variant?: 'info' | 'success' | 'warning' }) {
  return <div className={`notice ${variant}`} role="status">{variant === 'success' ? <Check size={19} /> : <CircleAlert size={19} />}<div>{children}</div></div>;
}
export function Empty({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return <div className="empty"><span className="empty-icon"><Inbox size={30} /></span><h3>{title}</h3><p>{children}</p>{action}</div>;
}
export function Badge({ status }: { status: string }) {
  const type = ['READY', 'PROCESSED', 'COMPLETED', 'CONFIRMED'].includes(status) ? 'success' : ['FAILED', 'REJECTED', 'UNSUPPORTED_OCR_REQUIRED'].includes(status) ? 'danger' : isProcessing(status) ? 'pending' : 'neutral';
  return <span className={`badge ${type}`}><span className={isProcessing(status) ? 'status-dot pulse' : 'status-dot'} />{statuses[status] || status}</span>;
}
export function Tags({ tags = [] }: { tags?: string[] }) {
  return <div className="tags">{tags.map(tag => <span className="tag" key={tag}>{tag}</span>)}</div>;
}
export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return <nav className="pagination" aria-label="Страницы результатов"><span>{total ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)}` : '0'} из {total}</span><div><button className="icon-button" aria-label="Предыдущая страница" disabled={page <= 1} onClick={() => onPage(page - 1)}><ArrowLeft size={17} /></button><span>Страница {page} из {pages}</span><button className="icon-button" aria-label="Следующая страница" disabled={page >= pages} onClick={() => onPage(page + 1)}><ArrowRight size={17} /></button></div></nav>;
}
export function DocumentList({ documents, compact = false }: { documents: Document[]; compact?: boolean }) {
  return <div className={`document-list ${compact ? 'compact' : ''}`}>{documents.map(doc => <Link to={`/archive/${doc.id}`} className="document-row" key={doc.id}><span className={`document-icon ${doc.documentType === 'LAB_REPORT' ? 'blue' : doc.documentType === 'NOTE' ? 'ochre' : ''}`}><FileText size={21} /></span><div className="document-body"><span className="document-title">{doc.title}</span><div className="document-meta">{documentTypes[doc.documentType] || doc.documentType}<span>·</span>{date(doc.documentDate)}</div>{!compact && <Tags tags={doc.tags} />}</div><Badge status={doc.status} /><ArrowRight className="row-arrow" size={17} /></Link>)}</div>;
}
export function HistoryList({ items }: { items: HistoryEvent[] }) {
  return <div className="history-list">{items.map(item => <article className="history-item" key={item.id}><span className="history-mark" /><div><div className="history-title">{actions[item.action] || item.action.replaceAll('_', ' ').toLowerCase()}</div><p>{dateTime(item.createdAt)}{item.documentId && <> · <Link to={`/archive/${item.documentId}`}>Открыть документ</Link></>}</p>{(item.payloadBefore || item.payloadAfter) != null && <details><summary>Подробности изменения</summary><div className="change-grid">{item.payloadBefore != null && <div><span>До изменения</span><pre>{JSON.stringify(item.payloadBefore, null, 2)}</pre></div>}{item.payloadAfter != null && <div><span>После изменения</span><pre>{JSON.stringify(item.payloadAfter, null, 2)}</pre></div>}</div></details>}</div></article>)}</div>;
}
export function CloseButton({ onClick }: { onClick: () => void }) { return <button className="icon-button" aria-label="Закрыть" onClick={onClick}><X size={19} /></button>; }
