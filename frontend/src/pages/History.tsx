import { useState } from 'react';
import { Clock3 } from 'lucide-react';
import { Empty, ErrorNotice, HistoryList, Loading, PageHeader, Pagination } from '../components';
import { useApi } from '../hooks';
import type { HistoryEvent, Page } from '../types';

export function HistoryPage() {
  const [page, setPage] = useState(1);
  const { data, loading, error, reload } = useApi<Page<HistoryEvent>>(`/history?page=${page}&pageSize=20`);
  return <><PageHeader title="История изменений" description="Прозрачная история импорта, обработки, правок и восстановления документов." action={<span className="subtle-pill"><Clock3 size={15} /> {data?.total ?? '…'} событий</span>} /><section className="panel"><ErrorNotice error={error} retry={reload} />{loading ? <Loading /> : data?.items.length ? <><HistoryList items={data.items} /><Pagination page={page} pageSize={20} total={data.total} onPage={setPage} /></> : !error && <Empty title="История пока пуста">Добавьте первый документ — каждое действие появится здесь.</Empty>}</section></>;
}
