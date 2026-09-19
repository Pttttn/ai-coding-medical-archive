# Local Medical Archive — архитектура

Записано до создания прикладного кода, 2026-09-19. Основание: PROJECT_SPECIFICATION_Local_Medical_Archive_v1.1.md и два исходных задания. Это проект реализации, а не протокол пройденной приёмки.

## Границы и компоненты

Однопользовательский локальный архив. React + TypeScript + Vite отображает кабинет, архив, загрузку, документы/факты, timeline, Ask Archive, консультацию и историю. NestJS владеет REST API, PostgreSQL, оригиналами, неизменяемыми версиями текста, аудитом и устойчивой очередью обработки. ORM: TypeORM, явная начальная миграция. Python FastAPI/FastMCP предоставляет парсинг PDF, извлечение через Ollama и общий движок Corrective RAG на LangGraph. ChromaDB работает внутри Python; BM25 восстанавливается из того же сохранённого набора чанков. LangChain EnsembleRetriever объединяет ранги через RRF.

Нет OCR, внешних LLM API, отправки консультаций, авторизации и многопользовательского режима. API, UI и MCP публикуются на loopback. PostgreSQL и внутренний AI API не публикуются. Архив и MCP имеют разные корпуса и каталоги; MCP разрешён только синтетический sample_docs, без выбора корпуса и произвольных путей.

## Владение данными и целостность

Document хранит метаданные, статус, SHA256 и soft delete. TextRevision хранит исходный текст и страницы каждой версии. MedicalFact хранит значение, статус утверждения источника и отдельный reviewStatus. Provenance ссылается на конкретную версию, цитату и страницу. FactRevision и AuditEvent сохраняют изменения. ProcessingJob и ExtractionRun фиксируют обработку, версии модели/промпта/схемы и безопасные ошибки. Timeline использует медицинскую дату, которая может отсутствовать.

Редактирование текста исключает старую выдачу до переиндексации; удаление исключает документ из всех активных выборок. Повторная обработка не перезаписывает проверенные пользователем факты. Коррекции индексируются с явной отметкой пользователя отдельно от исходных цитат. Оригинальные PDF не изменяются. Seed заранее подготовлен и честно маркирован, новые загрузки используют настоящую модель.

Консультация — локальный снимок минимального контекста. Правила и локальная LLM проверяют вопрос и весь пакет, удаляя идентификаторы. Неизвестные даты не придумываются; числа/дозы/отрицания сохраняются. Экспорт доступен только для текущего подтверждённого SHA256. Любая правка сбрасывает подтверждение. Внешний Markdown не содержит refs, путей и таблицы замен.

## Контракт между компонентами

Публичный API: /api; Swagger: /docs. Имена полей JSON — camelCase. Пагинация `{items,page,pageSize,total}`. Основные маршруты соответствуют §19 спецификации. Ошибка `{message,code?,statusCode}`. ID — UUID. Даты — ISO8601 или null. Document: `{id,title,documentType,documentDate,sourceType,status,summary,tags:string[],createdAt,updatedAt,deletedAt,text?,textVersion?,facts?}`. Списки документов принимают page/pageSize/q/type/tag/status/from/to/deleted/sort/order.

Внутренний Python API (порт 8001, заголовок X-Internal-Token, отдельный от MCP):
- POST /internal/process: `{documentId,version,title,text?,filePath?}` → `{text,pages:[{pageNumber,text}],extraction:{documentType,documentDate,summary,tags,facts:[{type,name,valueText,valueNumber,unit,eventDate,assertionStatus,confidence,provenance:{page,sourceText}}]},warnings,model,promptVersion,schemaVersion,parserVersion}`.
- POST /internal/index: `{documentId,title,version,text,pages?,corrections?:[{id,name,valueText,valueNumber,unit,reviewStatus}]}` → статистика.
- POST /internal/remove: `{documentId}` → `{ok:true}`.
- POST /internal/ask: `{question,documentIds?:string[]}` → `{answer,sources:[{documentId?,source,chunkId,position,pageNumber?,text?}],trace?,insufficientContext?}`.
- POST /internal/consultation: `{question,contexts:[{text}]}` → `{content,warnings:string[]}`.
- GET /health → доступность процесса/моделей (без вызова генерации).

MCP Streamable HTTP /mcp на 8002: index_folder(path,glob), index_status(), find_relevant_docs(query,top_k), ask_question(question). Только mcp_demo. При чистом старте пуст. Shared uploads смонтированы read-only в AI. Python не имеет доступа к PostgreSQL.

## Запуск и проверка

Docker Compose: frontend/nginx 8080, backend 3000, AI 8001 внутренний, MCP 8002, PostgreSQL, Ollama и init моделей. Рабочая сеть internal; загрузчик моделей отделён от архивных данных. Дополнительный compose.host-ollama.yml использует явно настроенный локальный Ollama. Модель по умолчанию qwen2.5:3b, embedding nomic-embed-text; окончательные теги/результаты проверяются и записываются в docs/VALIDATION.md.

План: (1) документация и контракт; (2) параллельно backend, AI/RAG, UI; (3) готовая синтетика (30+ записей, 15+ тегов, 5 исправлений, два года, PDF) и sample_docs 512000+ байт; (4) интеграция/Compose; (5) unit/integration/MCP и реальная модель; (6) проверка UI, документация, матрица приёмки. Тесты и журнал добавляются в ходе работы. Личный REPORT пишет пользователь; AI ведёт явно помеченный технический журнал.
