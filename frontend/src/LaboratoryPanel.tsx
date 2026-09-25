import { Notice } from './components';
import type { Laboratory } from './types';

export function LaboratoryPanel({ lab, pages, version }: { lab: Laboratory; pages?: { pageNumber: number | null }[]; version?: number }) {
  const unresolved = lab.issues.filter(issue => issue.code !== 'UNSUPPORTED_CONTENT').length;
  const labels: Record<string, string> = { RESULT: 'Дата результата', SPECIMEN: 'Дата взятия материала', STUDY: 'Дата исследования' };
  return <section className="panel laboratory-panel">
    <div className="panel-body"><h2>Лабораторные строки из источника</h2>
      <Notice variant="warning">Экспериментальное извлечение. Показаны исходные строки; ваши исправления и подтверждения находятся во вкладке «Медицинские факты». Наличие строки не означает диагноз или проверку врачом.</Notice>
      <p>Распознано строк: {lab.rows.length} из {lab.candidateRows} обнаруженных кандидатов. Это не оценка полноты всего документа.</p>
      {unresolved > 0 && <Notice variant="warning">Требуют проверки: {unresolved} строк или дат. Сверьте текст документа.</Notice>}
      <ul>{lab.dates.map((entry, index) => <li key={index}>{labels[entry.role] || entry.role}: {entry.raw}</li>)}</ul>
    </div>
    <div className="table-scroll"><table className="archive-table"><thead><tr><th>Показатель</th><th>Результат</th><th>Единица</th><th>Референс источника</th><th>Источник</th></tr></thead>
      <tbody>{lab.rows.map((row, index) => <tr key={index}><td>{row.name}</td><td><strong>{row.result.raw}</strong></td><td>{row.unit || 'Не указана'}</td><td>{row.referenceRaw || 'Не указан'}</td>
        <td><details><summary>Цитата</summary><blockquote>{row.sourceText}</blockquote><p>Версия текста {version ?? 'не указана'}{pages?.[row.source.pageIndex]?.pageNumber ? ` · стр. ${pages[row.source.pageIndex].pageNumber}` : ''}</p><p>Субъект: {row.subject === 'PATIENT' ? 'пациент (указан в источнике)' : 'не установлен'}</p></details></td></tr>)}</tbody>
    </table></div>
  </section>;
}
