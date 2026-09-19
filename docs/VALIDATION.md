# Проверки реализации

Дата: 2026-09-19. Документ ведётся AI как технический журнал. Все тестовые документы и вопросы синтетические. Он не заменяет личный REPORT.md и не объявляет всё проектное задание принятым.

**Текущий статус: приложение реализовано и запущено; технические сценарии проверены.** Автоматические тесты: 129 passed. Продолженный CPU application smoke завершился с 20/20 checks за 63.08 с; он использовал уже созданную заметку после сохранённого нестабильного RAG-ответа. Это не безошибочный первый прогон. PDF 4/4, browser 15 проверок, container runtime 5/5, host runtime 7/7 и настоящий MCP HTTP прошли. Известные ограничения модели и действия автора перечислены ниже.

## Среда и модели

Хост: Windows 11 Pro, Intel Core i9-13900K (24 ядра / 32 логических процессора), около 128 ГиБ RAM, NVIDIA RTX 5080 с 16 ГиБ VRAM. Исходные сведения: [hardware.json](evaluation/hardware.json). Docker Desktop 4.87 / Engine 29.7 указан в журнале интеграции [ARCHITECTURE.md](../ARCHITECTURE.md). Backend проверялся на Node.js 24 и отдельной PostgreSQL 16; Linux AI-тесты — в отдельном контейнере.

Реальная RAG-оценка обращалась к локальному Ollama на хосте. Контейнерный application smoke использовал CPU; его время и ошибки нельзя переносить на GPU-прогон или выдавать за контролируемый benchmark. Зависимости закреплены package-lock.json и ai-service/uv.lock.

| Модель | Назначение | Digest финального RAG-прогона |
|---|---|---|
| qwen2.5:3b | Extraction, grading, выбор подтверждённых цитат, privacy | 357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b |
| nomic-embed-text:latest | Эмбеддинги | 0a109f422b47e3a30ba2b10eca18548e944e8a23073ee3f3e947efcf3c45e59f |
| qwen3.5:4b | Отдельный reference host, выбирающий MCP tool | Имя записано в host-agent JSON; digest там не записан |

Digests первых двух моделей: [bounded-final-control.json](evaluation/bounded-final-control.json). Модель reference host не заменяет проектную qwen2.5:3b.

## Локальные наборы тестов

| Набор | Результат | Что проверено |
|---|---:|---|
| Backend Jest | **48 passed** | 21 unit + 27 integration на отдельной PostgreSQL, реальная миграция и REST |
| Frontend Vitest | **22 passed** | Валидация, состояния review/export и компоненты |
| AI/MCP pytest, Linux | **59 passed, 0 skipped** | Индексатор, граф, транспорт, PDF, privacy, traversal/symlink, лимиты генерации и strict JSON |
| Backend lint/build | **PASS** | ESLint, TypeScript и production build |
| Frontend lint/build | **PASS** | ESLint, TypeScript и production build |
| Backend npm audit | **0 runtime-уязвимостей** | Состояние lockfile на дату проверки |

Всего **129 тестов прошли**: 48 backend + 22 frontend + 59 AI/MCP.

Итоговый безопасный журнал повторного backend-прогона: [backend-tests.txt](evaluation/backend-tests.txt).

Backend integration проверяет исправления и исходные значения, неизменяемые ревизии, provenance с неизвестной датой/страницей, сохранение поправок при reprocess, soft delete/restore, удаление из индекса, search/filters/pagination, теги, PDF signature/path, устойчивые задания, OCR-ошибки, audit, exact hash review/export и гонки изменения источника во время RAG/consultation. Проверяется выдача partial parsing warnings без раскрытия rawJson. Шесть новых integration tests покрывают явный выбор контекста при QA-отказе, сохранение correction/rejected markers, source-change race, недоступные источники, лимит 8 документов и предупреждение усечения. AI в этом наборе — явно тестовый unit-double; эти результаты не доказывают качество LLM.

Актуальный Linux-журнал: [linux-bounded-tests.txt](evaluation/linux-bounded-tests.txt), **59 passed, 0 skipped**, 5 предупреждений зависимостей. Проверены также num_predict каждой операции, strict JSON, усечённые/невалидные ответы, неизвестные поля, ограниченный безопасный отказ и сохранение 503 при недоступности модели. Промежуточные [42 passed](evaluation/linux-adversarial-tests.txt) и Windows 29 passed / 1 skipped сохранены в [журнале AI](evaluation/README.md); последние Linux-прогоны действительно выполняли symlink-сценарии.

Воспроизведение:

~~~sh
cd backend
npm ci
# Задать TEST_DATABASE_URL на отдельную PostgreSQL database с "test" в имени.
npm test
npm run lint
npm run build

cd ../frontend
npm ci
npm test
npm run lint
npm run build

cd ../ai-service
uv sync --frozen --group dev --python 3.12
uv run ruff check .
uv run pytest
~~~

Без TEST_DATABASE_URL backend integration suite пропускается: такой запуск не подтверждает все 48 тестов. Integration tests очищают только выбранную выделенную тестовую БД.

## Данные и реальный RAG

Прикладной seed: 36 записей, 6 PDF + 15 транскриптов + 15 заметок, 18 тегов, 2024–2025 годы и 5 исправлений. Оригиналы и готовые извлечения явно синтетические. MCP отделён от архива: 45 уникальных файлов, 662324 байта, все .md/.txt/.py/.js/.ts/.json/.yaml. [Manifest](../evaluation/corpus-manifest.json) содержит происхождение, размеры и SHA256; [21 вопрос](../evaluation/questions.json) хранится вне индексируемого корпуса. Проверка: python scripts/check_corpus.py.

Актуальный контроль после ограничений генерации и strict JSON: [bounded-final-control.json](evaluation/bounded-final-control.json), разбор: [evaluation/README.md](evaluation/README.md). Использованы настоящие локальные модели, не FakeProvider. Исторический [final-control.json](evaluation/final-control.json) дал 19/21 до этих изменений; он сохранён как промежуточный и не является текущей метрикой.

| Проверка | Наблюдаемый результат |
|---|---|
| Первые 10 необычных фактов | **10/10**, верное значение и нужный источник в citations |
| Все 12 exact_fact | **11/12** |
| expectedTextPresent + expectedSourcesCited + abstentionCorrect | **17/21** |
| Нужные источники в top-5, когда они заданы | **19/19 наборов** |
| Нет ответа в корпусе / посторонний вопрос | **2/2 явных отказа**, по 3 retrieval-прохода |

expectedTextPresent — прозрачная проверка подстроки, а не независимая клиническая оценка. Эти числа относятся только к фиксированному синтетическому набору.

Известные непройденные случаи:

- **fact-11, Rowan:** на вопрос о головокружении 2025-01-14 выбрано похожее отрицание из diary/2025-02.md, а не ожидаемый visits/visit-11.md. Буквально верная цитата не отвечает проверяемой дате/событию.
- **overview-01:** вместо обзора типов записей приведены 37 вечерних наблюдений Saffron из visits/visit-03.md; ожидаемый обзор overview.md не процитирован.
- **negation-01, Elm:** система отказалась ответить на вопрос, доказывает ли назначение приём лекарства, хотя visits/visit-12.md содержит указание на неизвестный приём.
- **conflict-01, Spruce:** ответ содержит исходные 17 и исправленные 19 минут из текста исправления, но ссылается только на visits/conflict-b.md; ожидаемый второй источник visits/conflict-a.md не процитирован.

Параметры: chunk size 900, overlap 120, top-k 5, minimum relevant chunks 1, не более 2 corrective-повторов после первого retrieval. Ограничения вывода/context: rewrite и broaden 128/8192 токенов, per-chunk grading 256/8192, grounded answer 1024/8192, extraction 2048/16384, privacy 1024/16384. done_reason=length и невалидный JSON отвергаются, а не принимаются как частичный корректный результат; MODEL_OUTPUT_LIMIT/INVALID отличаются от MODEL_UNAVAILABLE.

[bounded-inference.json](evaluation/bounded-inference.json) фиксирует отдельный реальный host probe и фактические параметры/времена. В нём обработка PDF вернула страничные цитаты, но оставила numeric fields null и добавила неподтверждённое «normal range» в AI-summary. Сводка, полнота, даты и медицинские типы фактов требуют ручной проверки; transport/schema успех не равен клинической точности.

| Chunk size / overlap | Чанки | Нужные источники в top-5 |
|---|---:|---:|
| 900 / 120 | 777 | 19/19 |
| 1400 / 180 | 752 | 19/19 |

Измерения: [900/120](evaluation/retrieval-900-120.json), [1400/180](evaluation/retrieval-1400-180.json). Выбрана 900/120 для меньшего контекста при таком же наблюдаемом recall. Прогрев и кэш различались, поэтому время индексации не сравнивается как чистый benchmark.

После ошибок свободного пересказа финальный генератор вызывает модель для выбора цитат и проверяет их буквальное происхождение. Это уменьшает риск выдуманного пересказа, но не гарантирует правильный выбор факта или полный ответ. Возможны длинные цитаты и язык исходника. Промежуточные неудачные real-*.json сохранены; слово final в старом имени файла не делает его актуальным контролем.

Воспроизведение из ai-service, при подготовленных локальных моделях:

~~~powershell
$env:OLLAMA_BASE_URL='http://127.0.0.1:11434'
$env:DATA_DIR='../.runtime/evaluation-new'
$env:CHUNK_SIZE='900'
$env:CHUNK_OVERLAP='120'
uv run python -m medical_ai.evaluate --output ../docs/evaluation/new-control.json
~~~

Для второго варианта нужны отдельный DATA_DIR, CHUNK_SIZE=1400 и CHUNK_OVERLAP=180; можно добавить --retrieval-only. Время вопросов и corrective trace сохраняются в JSON.

## MCP и host-агент

[MCP HTTP smoke](evaluation/mcp-http-smoke.json) проверил настоящий Streamable HTTP транспорт, ровно четыре tools, сначала 0 файлов/0 чанков, затем 45 файлов/777 чанков, status, hybrid retrieval и ответ о Cedar с правильным кодом. Индексация этого прогона заняла 136.7 секунды. Пустой индекс проверяется в чистом demo-хранилище, не после предыдущей индексации.

Повторный [MCP HTTP smoke в host-Ollama Compose](evaluation/mcp-host-smoke.json) вызвал все четыре tools, сохранил индекс 45 файлов/777 чанков на тех же volumes и вернул правильный код Cedar через ask_question. Это реальная проверка Compose с моделями на хосте.

Дополнительно [MCP Inspector CLI 2.7.0](evaluation/mcp-inspector.json) выполнил tools/list и tools/call index_status через HTTP с exitCode 0. Получены четыре tools и mcp_demo с 45 файлами/777 чанками. Эти две команды не вызывали LLM; это отдельная проверка Inspector, не host-agent selection.

В [host-agent.json](evaluation/host-agent.json) минимальный локальный host на qwen3.5:4b получил metadata от MCP, самостоятельно выбрал ask_question и вернул SYN-CASE-7F29. В пользовательском вопросе не было указания вызвать MCP. Это проверка reference host, **не доказательство подключения и выбора tool в VSCode Copilot или другом IDE пользователя**.

Воспроизведение из корня с Python-окружением ai-service и работающим локальным MCP:

~~~sh
python scripts/mcp_smoke.py --expect-empty
python scripts/host_agent_check.py --model qwen3.5:4b
~~~

Флаг --expect-empty используется только до первой индексации. Reference host требует отдельно подготовленной qwen3.5:4b.

## Browser и сквозной сценарий приложения

[Browser smoke](evaluation/browser-smoke.json): 15 проверок — семь основных desktop-страниц, страница документа и семь mobile-проверок отсутствия горизонтального переполнения. pageErrors=[], externalRequests=[]. Это загрузка/вёрстка и наблюдаемая сеть браузера, а не все пользовательские действия или доказательство отсутствия любого серверного egress.

Скрипт: node scripts/browser_smoke.cjs; требуется Playwright, PLAYWRIGHT_MODULE позволяет указать его путь. HTML, стили, шрифты и Swagger обслуживаются локально.

[Актуальный application smoke](evaluation/application-smoke.json): **20/20 checks, 63.08 с**, с настоящей контейнерной CPU-моделью. Использован явный `--resume-document` для уже созданной и обработанной синтетической заметки. Проверены extraction/индексация, FTS и RAG с источником, исправление и reprocess, неизменяемая цитата, metadata, privacy, запрет непроверенного экспорта, точный SHA256 preview/export, сброс review после правки, исключение удалённого источника, восстановление и audit. Тестовая заметка мягко удалена в конце; активный demo снова содержит 36 READY, 0 FAILED, 0 pending.

Теперь пользователь может явно выбрать до 8 готовых активных документов: это назначенный им контекст, без промежуточной генерации QA. Если documentIds не заданы, автоматический выбор продолжает RAG. Текст берётся из зафиксированной ревизии, исправления и rejected markers сохраняются, generation/textVersion проверяются до privacy и транзакционно после него. При ограничении исходного текста первыми 10000 символами выводится предупреждение о неполноте. Privacy pass, ручной preview и точный hash review/export обязательны в обеих ветках.

[application-first-failure.txt](evaluation/application-first-failure.txt) хранит отдельную более раннюю ошибку EXTRACTION_INVALID; её нельзя путать с последующим timeout или успешным контролем. Дополнительная диагностика: [smoke-extraction-diagnostic.json](evaluation/smoke-extraction-diagnostic.json).

| Проверка развёртывания | Статус |
|---|---|
| Стандартный стек, UI/Swagger/MCP доступны | Наблюдалось локально |
| CPU application smoke с продолжением | **20/20 PASS**, [application-smoke.json](evaluation/application-smoke.json); см. оговорку о повторном RAG-запросе |
| Актуальный bounded PDF smoke | **4/4 PASS**, [pdf-bounded-smoke.json](evaluation/pdf-bounded-smoke.json) |
| Host-Ollama Compose по опубликованной инструкции | **7/7 PASS**, [runtime-host.json](evaluation/runtime-host.json) |
| Container runtime check | **5/5 PASS**, [runtime-container.json](evaluation/runtime-container.json) |
| Host-Ollama MCP и сохранение индекса при переключении | **PASS**, все четыре tools; те же 45 файлов/777 чанков, [mcp-host-smoke.json](evaluation/mcp-host-smoke.json) |

[Актуальный bounded PDF smoke](evaluation/pdf-bounded-smoke.json), тестовый API на 127.0.0.1:13000: text PDF READY за 22.39 с, scan UNSUPPORTED_OCR_REQUIRED за 2.06 с, malformed FAILED за 2.06 с, partial READY за 14.2 с. Предыдущий [pdf-smoke.json](evaluation/pdf-smoke.json) с временем text PDF 212.27 с сохранён как исторический. Для text/partial подтверждены факты и provenance страницы 1; partial PDF вернул предупреждение о пустой странице 2. Эти четыре сценария прошли, но не доказывают поддержку произвольных PDF.

[runtime-container.json](evaluation/runtime-container.json) подтверждает **5/5** проверок scripts/runtime_check.py: API health, готовность qwen2.5:3b/nomic-embed-text и три egress-проверки. Фактические сетевые результаты стандартного runtime: socket из AI к 1.1.1.1:443 завершился code 101 (network unreachable), внешний fetch из backend — timeout; у gateway проверена политика OUTPUT DROP, wget к example.com завершился timeout. Это измеренные отдельные соединения, а не вывод только по Docker internal flag и не проверка всех возможных направлений. Последующий [runtime-host.json](evaluation/runtime-host.json) подтверждает **7/7** проверок host-Ollama режима: API health, готовность локальных моделей, блокировку внешних соединений AI/backend/gateway/host-proxy и ответ 403 на попытку загрузить модель через proxy. Проблема IPv6/getent решена в infra/gateway/15-egress.sh выбором getent ahostsv4 и генерацией явного IPv4 upstream. После переключения Compose [MCP smoke](evaluation/mcp-host-smoke.json) подтвердил сохранность индекса на тех же volumes: 45 файлов/777 чанков. После возвращения к CPU application smoke завершён с указанным выше продолжением; container runtime 5/5 повторно подтверждён на окончательной конфигурации.

## Приватность и внешние действия

Реальные синтетические adversarial privacy проверки: [adversarial-privacy-final.json](evaluation/adversarial-privacy-final.json), **3/3** без заданных идентификаторов и **3/3** с сохранёнными контрольными числами, единицами и отрицаниями. Предыдущая утечка имени сохранена в [adversarial-privacy-real.json](evaluation/adversarial-privacy-real.json) и исправлена. Команды в тексте не исполняются; protocol-команды отклоняются extraction с предупреждением. Факты могут оставаться неполными.

Backend подтверждает exact review/export и исключение внутренних путей/UUID/имён исходных файлов на границе экспорта. MCP path/corpus isolation и symlink-проверки прошли в Linux. Эти результаты не доказывают полной анонимности и не заменяют ручной проверки косвенных идентификаторов.

До окончательной сдачи остаются:

- Личная часть REPORT.md, которую пишет автор, и подтверждение согласования собственной темы.
- GitHub remote, публикация и действительный GitHub Actions run. [Workflow](../.github/workflows/ci.yml) создан; локальные тесты не являются удалённым CI.
- Самостоятельный выбор MCP tool в IDE host пользователя.

Актуальные задачи: [TASKS.md](../TASKS.md). Критерии: §36 [спецификации](../PROJECT_SPECIFICATION.md).

## Сохранённые неудачи сквозных прогонов

Первый CPU прогон достиг 17 checks и завершился timeout генерации: [лог](evaluation/application-pre-bounds-failure.txt). После введения лимитов обнаружена зависимость явного выбора документов от QA-ответа: [лог](evaluation/application-selection-failure.txt). Оба дефекта исправлены. Ещё один запуск не подтвердил контрольный факт с ожидаемым источником: [лог](evaluation/application-rag-intermittent-failure.txt). Повторный API-запрос вернул правильный код и источник, после чего сценарий продолжен на той же записи. Исходный ответ не был записан целиком, поэтому по одному assertion нельзя точно установить, был ли это отказ или неподходящая цитата. [Снимок индекса](evaluation/cpu-copper-index-snapshot.json) подтвердил единственную актуальную запись и правильный исходный текст; устаревших тестовых записей в индексе не было. Этот случай остаётся свидетельством нестабильности небольшой модели, а не удалённым из статистики успехом.
