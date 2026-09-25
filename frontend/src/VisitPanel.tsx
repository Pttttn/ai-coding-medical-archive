import { Notice } from './components';
import type { Visit } from './types';

const labels: Record<string, string> = {
  AGREES: 'Разборы совпали', DISAGREES: 'Разборы расходятся', UNRESOLVED: 'Второе чтение не завершено',
  PATIENT: 'Пациент', FAMILY: 'Родственник', OTHER: 'Другой человек', UNKNOWN: 'Не установлено',
  CONFIRMED: 'Указано как установленное', SUSPECTED: 'Подозрение', NEGATED: 'Отрицается / отсутствует',
  NOT_CONFIRMED: 'Пока не подтверждено', RULED_OUT: 'Исключено',
  PRESCRIBED: 'Назначено', TAKING: 'Принимает', NOT_STARTED: 'Не начал приём', NOT_TAKING: 'Не принимает',
  STOPPED: 'Прекратил / завершил приём', NOT_APPLICABLE: 'Не применимо',
  CURRENT: 'На момент записи', HISTORICAL: 'В прошлом', FUTURE: 'Планируется',
};
export function VisitPanel({ visit, pages, version }: { visit: Visit; pages?: { pageNumber: number | null }[]; version?: number }) {
  return <section className="panel"><div className="panel-body"><h2>Клинические утверждения из источника</h2>
    <Notice variant="warning">Экспериментальная разметка модели, требует сверки с оригиналом. «Установленное» означает трактовку источника, а не проверку врачом. Ваши исправления и подтверждения находятся во вкладке «Медицинские факты».</Notice>
    {visit.verifications && <Notice variant="warning">Второе чтение моделью: требуют сверки {visit.verifications.filter(v => v.status !== 'AGREES').length} из {visit.statements.length}. Совпадение разборов не является проверкой врачом. При расхождении запись перенесена в факты как наблюдение с неизвестным статусом.</Notice>}
    <p>Утверждений: {visit.statements.length}. Обработано абзацев: {visit.processedBlocks.length} из {visit.candidateBlocks}. Это не оценка полноты. Представлены заболевания, симптомы и события приёма лекарств; даты не вычисляются.</p>
    {visit.issues.length > 0 && <Notice variant="warning">Проблемы извлечения: {visit.issues.length}. Возможны пропуски, проверьте текст документа.</Notice>}
  </div><div className="table-scroll"><table className="archive-table"><thead><tr><th>Утверждение</th><th>О ком</th><th>Статус в источнике</th><th>Когда</th><th>Источник</th>{visit.verifications && <th>Второе чтение</th>}</tr></thead>
    <tbody>{visit.statements.map((s, i) => <tr key={i}><td>{s.name}</td><td>{labels[s.subject] || s.subject}</td><td>{labels[s.kind === 'MEDICATION' ? s.medicationState : s.assertion]}</td><td>{labels[s.temporality]}</td><td><details><summary>Цитата и контекст</summary><blockquote>{s.sourceText}</blockquote><p>Полный абзац:</p><blockquote>{s.contextText}</blockquote><p>Версия текста {version ?? 'не указана'}{pages?.[s.source.pageIndex]?.pageNumber ? ` · стр. ${pages[s.source.pageIndex].pageNumber}` : ''}</p></details></td>{visit.verifications && <td>{labels[visit.verifications[i]?.status] || 'Нет результата'}{visit.verifications[i]?.status !== 'AGREES' && visit.verifications[i]?.alternative && <details><summary>Другой разбор</summary><p>{labels[visit.verifications[i].alternative!.subject]} · {labels[visit.verifications[i].alternative!.kind === 'MEDICATION' ? visit.verifications[i].alternative!.medicationState : visit.verifications[i].alternative!.assertion]} · {labels[visit.verifications[i].alternative!.temporality]}</p><blockquote>{visit.verifications[i].alternative!.sourceText}</blockquote></details>}</td>}</tr>)}</tbody>
  </table></div></section>;
}
