import { Activity, ArrowRight, ArrowUpRight, CheckCheck, Files, Plus, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { DocumentList, Empty, ErrorNotice, HistoryList, Loading, PageHeader } from '../components';
import { useApi } from '../hooks';
import type { DashboardData } from '../types';
import { documentTypes } from '../utils';

export function DashboardPage() {
  const { data, error, loading, reload } = useApi<DashboardData>('/dashboard', 15000);
  return <>
    <PageHeader eyebrow="ВАШЕ ЗДОРОВЬЕ В КОНТЕКСТЕ" title="Всё важное — в одном месте" description="Документы, медицинские события и ответы с опорой на вашу историю." action={<Link className="button primary" to="/upload"><Plus size={18} /> Добавить документ</Link>} />
    <ErrorNotice error={error} retry={reload} />
    {loading && !data ? <Loading /> : data && <>
      <div className="stats-grid">
        <Stat title="Документы в архиве" value={data.totalDocuments} subtitle="Вся история под рукой" icon={<Files size={21} />} />
        <Stat title="Обработано" value={data.processedDocuments} subtitle={`${data.pendingDocuments} в обработке · ${data.failedDocuments} с ошибкой`} icon={<CheckCheck size={21} />} />
        <Stat title="Медицинские факты" value={data.medicalFacts} subtitle="С подтверждением из источников" icon={<Sparkles size={21} />} />
        <Stat title="События в хронологии" value={data.timelineEvents} subtitle="Последовательная история" icon={<Activity size={21} />} />
      </div>
      <div className="dashboard-main-grid">
        <section className="panel activity-panel"><div className="panel-heading"><div><h2>История в документах</h2><p>Документы по медицинской дате</p></div><span className="subtle-pill">По месяцам</span></div>
          {data.documentsOverTime?.length ? <div className="bar-chart" role="img" aria-label={data.documentsOverTime.map(row => `${row.month}: ${row.count}`).join(', ')}>{data.documentsOverTime.slice(-12).map((row, index, rows) => {
            const max = Math.max(1, ...rows.map(value => value.count));
            const label = new Date(`${row.month.slice(0, 7)}-01T12:00:00`);
            return <div className="bar-column" key={row.month}><div className="bar-space"><div className={`bar ${index === rows.length - 1 ? 'highlight' : ''}`} style={{ height: `${Math.max(4, row.count / max * 100)}%` }}><span>{row.count}</span></div></div><span className="bar-label">{Number.isNaN(label.getTime()) ? row.month : label.toLocaleDateString('ru-RU', { month: 'short' }).replace('.', '')}</span><span className="bar-year">{Number.isNaN(label.getTime()) ? '' : label.getFullYear()}</span></div>;
          })}</div> : <Empty title="История только начинается">Добавьте первый документ с медицинской датой.</Empty>}
        </section>
        <section className="insight-card"><div className="insight-icon"><Sparkles size={24} /></div><span className="eyebrow">СПРОСИТЬ АРХИВ</span><h2>Найдите ответ<br />в своей истории</h2><p>Задайте вопрос обычными словами. Локальный AI найдёт подходящие фрагменты и покажет источники.</p><Link className="button light" to="/ask">Задать вопрос <ArrowUpRight size={18} /></Link><div className="insight-decoration" aria-hidden="true"><Activity size={160} strokeWidth={0.6} /></div></section>
      </div>
      <div className="dashboard-bottom-grid">
        <section className="panel"><div className="panel-heading"><div><h2>Последние документы</h2><p>Недавно добавлено в ваш архив</p></div><Link className="text-link" to="/archive">Весь архив <ArrowRight size={15} /></Link></div>{data.recentDocuments?.length ? <DocumentList documents={data.recentDocuments.slice(0, 5)} compact /> : <Empty title="Пока нет документов" action={<Link to="/upload" className="button secondary">Добавить первый</Link>}>Начните с анализа, выписки или личной заметки.</Empty>}</section>
        <section className="panel"><div className="panel-heading"><div><h2>Состав архива</h2><p>Документы по типам</p></div></div><div className="type-distribution">{data.documentsByType?.length ? data.documentsByType.map((row, index) => <div className="distribution-row" key={row.type}><div><span className={`type-dot dot-${index % 4}`} />{documentTypes[row.type] || row.type}<strong>{row.count}</strong></div><div className="progress-track"><div className={`progress-fill fill-${index % 4}`} style={{ width: `${Math.max(1, row.count / Math.max(1, data.totalDocuments) * 100)}%` }} /></div></div>) : <p className="muted">Типы появятся после добавления документов.</p>}</div></section>
      </div>
      <section className="panel recent-activity"><div className="panel-heading"><div><h2>Последние изменения</h2><p>Все действия сохраняются в истории</p></div><Link className="text-link" to="/history">Вся история <ArrowRight size={15} /></Link></div>{data.recentChanges?.length ? <HistoryList items={data.recentChanges.slice(0, 4)} /> : <p className="panel-empty muted">История изменений пока пуста.</p>}</section>
    </>}
  </>;
}
function Stat({ title, value, subtitle, icon }: { title: string; value: number; subtitle: string; icon: React.ReactNode }) {
  return <div className="stat-card"><div className="stat-top"><span>{title}</span><span className="stat-icon">{icon}</span></div><strong>{value ?? 0}</strong><p>{subtitle}</p></div>;
}
