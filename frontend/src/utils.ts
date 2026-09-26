import type { Document } from './types';
export const documentTypes: Record<string, string> = {
  LAB_REPORT: 'Результаты анализов', VISIT: 'Приём врача', VISIT_TRANSCRIPT: 'Транскрипт приёма',
  DISCHARGE_SUMMARY: 'Выписка', PRESCRIPTION: 'Назначение', IMAGING_REPORT: 'Исследование',
  PROCEDURE_REPORT: 'Процедура', NOTE: 'Личная заметка', OTHER: 'Другой документ',
};
export const factTypes: Record<string, string> = {
  CONDITION: 'Состояние', SYMPTOM: 'Симптом', MEDICATION: 'Лекарство', LAB_RESULT: 'Анализ',
  PROCEDURE: 'Процедура', RECOMMENDATION: 'Рекомендация', OBSERVATION: 'Наблюдение', OTHER: 'Другое',
};
export const assertions: Record<string, string> = {
  CONFIRMED: 'Указано в источнике', SUSPECTED: 'Предполагается',
  NEGATED: 'Отрицается', PRESCRIBED: 'Назначено', UNKNOWN: 'Не уточнено',
};
export const reviews: Record<string, string> = { UNREVIEWED: 'Не проверено', CONFIRMED: 'Проверено', CORRECTED: 'Исправлено вами', REJECTED: 'Отклонено' };
export const statuses: Record<string, string> = {
  UPLOADED: 'В очереди', PARSING: 'Читаем документ', EXTRACTING: 'Извлекаем факты', INDEXING: 'Индексируем', UNSUPPORTED_OCR_REQUIRED: 'Нет текстового слоя', PENDING: 'В очереди', QUEUED: 'В очереди', PROCESSING: 'Обрабатывается', PROCESSED: 'Обработан',
  READY: 'Обработан', COMPLETED: 'Обработан', FAILED: 'Ошибка обработки', NEEDS_OCR: 'Нет текстового слоя',
};
export const actions: Record<string, string> = {
  INDEXING_COMPLETED: 'Документ доступен для поиска', SYNTHETIC_SEED_IMPORTED: 'Добавлен синтетический демодокумент', TAG_CREATED: 'Создан тег', TAG_RENAMED: 'Переименован тег', TAG_DELETED: 'Удалён тег', TEXT_EDITED: 'Сохранена новая версия текста', CONSULTATION_EDITED: 'Изменён пакет консультации', DOCUMENT_UPLOADED: 'Загружен документ', DOCUMENT_CREATED: 'Создана запись', NOTE_CREATED: 'Создана заметка',
  METADATA_UPDATED: 'Изменены метаданные', DOCUMENT_UPDATED: 'Изменён документ', TEXT_UPDATED: 'Обновлён текст',
  AI_EXTRACTION_COMPLETED: 'Завершена AI-обработка', EXTRACTION_COMPLETED: 'Завершено извлечение',
  PROCESSING_COMPLETED: 'Завершена обработка', PROCESSING_FAILED: 'Ошибка обработки',
  FACT_CORRECTED: 'Исправлен медицинский факт', FACT_UPDATED: 'Проверен медицинский факт',
  DOCUMENT_REPROCESSED: 'Повторная обработка', REPROCESS_REQUESTED: 'Запрошена обработка',
  DOCUMENT_DELETED: 'Документ перемещён в корзину', DOCUMENT_RESTORED: 'Документ восстановлен',
  CONSULTATION_PREPARED: 'Подготовлена консультация', CONSULTATION_REVIEWED: 'Проверена консультация',
  CONSULTATION_UPDATED: 'Изменён пакет консультации', CONSULTATION_EXPORTED: 'Экспортирована консультация',
};
export const date = (value?: string | null) => value ? new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(value)) : 'Дата не указана';
export const dateTime = (value: string) => new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
export const dateInput = (value?: string | null) => value?.slice(0, 10) || '';
export const countLabel = (count: number, forms: [string, string, string]) => `${count} ${forms[count % 100 > 10 && count % 100 < 20 ? 2 : count % 10 === 1 ? 0 : count % 10 >= 2 && count % 10 <= 4 ? 1 : 2]}`;
export const isProcessing = (status: string) => ['UPLOADED', 'PARSING', 'EXTRACTING', 'INDEXING', 'PENDING', 'QUEUED', 'PROCESSING'].includes(status);
export const tagsFromInput = (value: string) => [...new Set(value.split(',').map(tag => tag.trim()).filter(Boolean))];

export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
export function validateDocument(input: { title: string; documentDate: string; text?: string; file?: File | null; mode: string }): string | null {
  if (!input.title.trim()) return 'Укажите название документа.';
  if (input.title.trim().length > 200) return 'Название должно быть не длиннее 200 символов.';
  if (input.documentDate && (!/^\d{4}-\d{2}-\d{2}$/.test(input.documentDate) || Number.isNaN(Date.parse(input.documentDate)) || new Date(input.documentDate).toISOString().slice(0, 10) !== input.documentDate)) return 'Укажите существующую дату.';
  if (input.mode === 'PDF') {
    if (!input.file) return 'Выберите PDF-файл.';
    if (!/\.pdf$/i.test(input.file.name) || (input.file.type && input.file.type !== 'application/pdf')) return 'Поддерживаются только PDF-файлы с текстовым слоем.';
    if (input.file.size > MAX_UPLOAD_BYTES) return 'Размер файла не должен превышать 20 МБ.';
    if (input.file.size === 0) return 'Выбранный файл пуст.';
  } else if (!input.text?.trim()) return 'Введите текст записи.';
  else if (input.text.trim().length < 3 || input.text.length > 200000) return 'Текст должен содержать от 3 до 200 000 символов.';
  return null;
}

export function canExportConsultation(savedContent: string, currentContent: string, contentHash: string, reviewedHash: string | null | undefined): boolean {
  return Boolean(contentHash && reviewedHash === contentHash && currentContent === savedContent);
}


export function validateTags(tags: string[]): string | null { return tags.length > 30 ? 'Допускается не более 30 тегов.' : tags.some(tag => tag.length > 80) ? 'Тег должен быть не длиннее 80 символов.' : null; }


export function hasFactCorrection(fact: { reviewStatus: string; originalValue?: Record<string, unknown>; [key: string]: unknown }): boolean {
  if (fact.reviewStatus === 'CORRECTED') return true;
  if (!fact.originalValue) return false;
  return ['type', 'name', 'valueText', 'valueNumber', 'unit', 'eventDate', 'assertionStatus'].some(key => Object.hasOwn(fact.originalValue!, key) && (fact[key] ?? null) !== (fact.originalValue![key] ?? null));
}

/** Facts and search always show one activated processing revision; say so while a newer one is pending or failed. */
export function revisionNotice(doc: Pick<Document, 'status' | 'processingRevision' | 'textVersion' | 'textRevisions'>): string | null {
  const active = doc.processingRevision?.active;
  // After a text edit the old snapshot no longer describes the document and is not shown.
  const currentText = doc.textRevisions?.find(r => r.version === doc.textVersion)?.id;
  if (!active || active.textRevisionId !== currentText) return null;
  if (doc.status === 'FAILED') return 'Новая обработка не завершилась. Факты и поиск показывают последнюю успешную версию обработки.';
  if (doc.processingRevision?.prepared || isProcessing(doc.status)) return 'Пока идёт обработка, факты и поиск показывают предыдущую версию целиком. Новая версия появится сразу вся, когда будет готов её поисковый индекс.';
  return null;
}
