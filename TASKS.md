# Состояние v1.2

Обновлено 19 сентября 2026. Это технический статус AI. [Матрица проверок](docs/VALIDATION.md), [карта консультации](docs/CONSULTATION_CHANGES.md).

- [x] Полная спецификация v1.2 согласована с конспектом без расширения MVP; v1.1 сохранена.
- [x] Форматы MD/TXT/PDF, 42 файла, 661410 байт обычного текста; corpus manifest проходит после Git LF-нормализации.
- [x] Структурные чанки, версия splitter, удаление старых запрещённых форматов при reindex; источники и коррекции разделены.
- [x] Общий rules + local LLM privacy слой для ручной консультации и всей публичной выдачи MCP.
- [x] Очищенные S1/responseRef, локальная таблица соответствий, безопасные агрегаты/ошибки; private archive недоступен через MCP.
- [x] 143 AI tests в Linux без skips, Ruff; настоящие MCP 8/8 privacy, manual 3/3, application 20/20, runtime 5/5, самостоятельный host выбор ask_question.
- [x] Полный реальный RAG 17/21, первые 10 — 10/10; сравнение 900/120 и 1400/180. Неудачи сохранены и описаны, не отмечены успешными.
- [x] Проект опубликован в [GitHub](https://github.com/ruslan-yusupov-open/ai-coding-medical-archive); исправлена найденная первым CI проблема CRLF/LF.
- [x] GitHub Actions для e02afee: backend 48 + frontend 22 + AI 143 = **213 passed**, lint/build и все Docker images PASS. [Run 35442666973](https://github.com/ruslan-yusupov-open/ai-coding-medical-archive/actions/runs/35442666973).

- [x] Повторный аудит формальных критериев и консультации: [REQUIREMENTS_AUDIT](docs/REQUIREMENTS_AUDIT.md), с явными незакрытыми условиями сдачи.
- [x] Реальный чистый GitHub clone / пустые тома / автоматическая загрузка весов: application 20/20, PDF 4/4, browser 15, MCP 42/773, runtime 5/5. Down/up сохранил содержимое 11 таблиц и индексов.
- [x] Чёткий README clone/cd/up и readiness; AI проверяет ready=true, gateway ждёт healthy и проверяет UI/API.

## Открытые ограничения и действия автора

- [ ] Известные model cases: overview-01, multi-01, negation-01, conflict-01. Точность и полная анонимность вне контрольного набора не гарантируются.
- [x] Авторская хронология и реальные запросы предоставлены пользователем; REPORT.md оформлен по ним, технические уточнения и разбор AI отделены.
- [ ] Подтвердить принятие темы, отправленной автором на утверждение 14 сентября, и новую дату защиты; 28 сентября перенесено, новая дата не названа.
- [ ] Проверить MCP именно в выбранном IDE. Reference host уже проверен, результат ему не приписывается.

Прежние backend 48 / frontend 22, PDF и browser проверки доступны в docs/VALIDATION_v1.1.md. Они не подменяют новые реальные модельные оценки.
