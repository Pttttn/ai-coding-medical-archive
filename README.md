# Local Medical Archive

Локальный однопользовательский медицинский архив: документы и заметки, проверяемые AI-факты, временная шкала, поиск с источниками и подготовка текста для ручной консультации. React + NestJS/TypeORM + PostgreSQL + Python Corrective RAG + Ollama. **Все поставляемые медицинские данные синтетические.**

Актуальные требования: [спецификация v1.2](PROJECT_SPECIFICATION_Local_Medical_Archive_v1.2.md). [Изменения по конспекту консультации](docs/CONSULTATION_CHANGES.md) отделяют пояснения преподавателя от принятых решений проекта. Приватность публичного MCP и ручная консультация используют общие правила и локальную LLM; это разные способы передачи данных.

## Быстрый запуск

Нужен Docker с Compose 2.24.4+; рекомендуется минимум 12 ГБ доступной RAM и 12 ГБ диска. CPU поддерживается, быстродействие зависит от оборудования. GPU не обязателен. Интернет нужен для первой загрузки образов, зависимостей и весов. Для стандартного запуска не нужны `.env` и API-ключи:

```sh
docker compose up --build
```

Повторный запуск: `docker compose up`. `model-init` автоматически подготавливает `qwen2.5:3b` и `nomic-embed-text`, не имея доступа к архиву. Runtime-сервисы работают в изолированной сети. Backend применяет явные миграции и идемпотентный seed. Первое индексирование видно в статусах документов.

| Сервис | Адрес по умолчанию |
|---|---|
| Интерфейс | http://127.0.0.1:8080 |
| Swagger | http://127.0.0.1:3000/docs |
| REST API | http://127.0.0.1:3000/api |
| Синтетический MCP | http://127.0.0.1:8002/mcp |

Все опубликованные порты привязаны к loopback. PostgreSQL и внутренний Python API не опубликованы. Шрифты, JS/CSS и Swagger обслуживаются локально. Остановка без удаления данных: `docker compose down`. Не используйте `down -v` для личного архива.

## Режим с Ollama на хосте

Заранее установите Ollama и подготовьте модели:

```sh
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
docker compose -f compose.yaml -f compose.host-ollama.yaml up --build
```

На Docker Desktop Ollama должен принимать соединения через `host.docker.internal:11434`; при необходимости задайте `OLLAMA_HOST=0.0.0.0:11434` для процесса Ollama и перезапустите его. Не открывайте порт в публичную сеть. На Linux используется `host-gateway`; host firewall должен разрешать только Docker-подсеть. Фиксированный локальный Ollama proxy разрешает inference/metadata, запрещает произвольные URL и загрузку моделей. Реально проверенные среды и режимы перечислены в [VALIDATION](docs/VALIDATION.md).

## Сценарий демонстрации кабинета

1. Откройте кабинет: 36 записей за 2024–2025 годы, распределение типов и история изменений.
2. Выполните поиск, измените фильтр/страницу, откройте лабораторный отчёт и исходный PDF.
3. Исправьте AI-факт и проверьте историю: исходная цитата и версия документа остаются прежними.
4. Создайте заметку/транскрипт, вставив текст TXT/MD, либо загрузите PDF с текстовым слоем. Дождитесь локальной обработки. Для скана возвращается `UNSUPPORTED_OCR_REQUIRED`; OCR не выполняется.
5. Задайте вопрос об архиве. В локальном кабинете доступны полные источники; недостаток данных не подменяется выдуманным ответом.
6. Подготовьте консультацию, отредактируйте preview, подтвердите текущий текст и скачайте Markdown. Правка сбрасывает подтверждение; экспорт проверяет точный hash.
7. Удалите документ, проверьте корзину и восстановление. Удалённый документ не участвует в новых ответах и консультациях.

## MCP и граница выдачи

Готовая конфигурация VSCode Copilot находится в [.vscode/mcp.json](.vscode/mcp.json). Настоящий Streamable HTTP сервер предоставляет четыре выбранных проектом инструмента. Консультация допускает изменение списка; расширять его для MVP не требуется.

```text
index_status()                         # EMPTY на чистом demo-хранилище
index_folder(path="./sample_docs", glob="**/*")
index_status()                         # безопасные числовые агрегаты
find_relevant_docs(query="Cedar follow-up interval", top_k=5)
ask_question(question="How many days until the follow-up recommended in the Cedar visit?")
```

| Инструмент | Что выполняет и возвращает |
|---|---|
| `index_folder` | Только разрешённый синтетический корень; parsing, chunking и локальные embeddings. Выход — счётчики, без имён файлов/путей/исходных ошибок. Генеративная LLM не вызывается |
| `index_status` | `status`, фиксированный `corpus`, числа файлов/чанков и параметры chunking. Нет содержимого, списка источников и вызова моделей |
| `find_relevant_docs` | BM25 + vector → RRF; правила и **локальная privacy LLM** очищают все фрагменты. Нет генерации предметного ответа, rewrite или relevance grading |
| `ask_question` | Полный Corrective RAG: rewrite → hybrid/RRF → LLM grading → ответ, максимум два broaden/retrieve повтора. Затем проверяются ответ и все источники |

Приложение автоматически индексирует `archive`, а MCP использует отдельный `mcp_demo`, поэтому при первом чистом запуске MCP пуст. Публичные tools не принимают переключатель корпуса, не читают личный архив и не разрешают произвольные пути или выход через symlink. Медицинские форматы: `.pdf` с текстом, `.txt`, `.md`; семь исходных форматов задания больше не обязательны.

Содержательная выдача имеет свежий непрозрачный `responseRef`, очищенный текст и обозначения источников `S1`, `S2`. `ask_question` возвращает `answer`, `sources: [{reference, text}]`, `insufficientContext`; `find_relevant_docs` — `chunks: [{reference, text}]`. Оба результата содержат `privacy.status = "checked"` и безопасные предупреждения. Исходные названия, пути, `documentId`, `chunkId`, произвольные metadata и trace не публикуются. Соответствие `responseRef + S1` реальному источнику хранится только локально в demo SQLite; MCP-tool для его раскрытия нет.

При ошибке privacy, недоступной модели или невалидном результате возвращается фиксированная безопасная ошибка `PUBLIC_OUTPUT_UNAVAILABLE`, без сырого fallback. Прямой запрос ФИО/номера карты не отключает очистку. Ошибки аргументов и tools также не отражают исходный ввод или stack trace. Это проверяемое поведение, а не гарантия полной анонимности.

Предметный вопрос для проверки выбора host-агентом: «How many days until the follow-up recommended in the Cedar visit?» Не добавляйте подсказку «вызови MCP». Запишите фактический вызов и ответ своего host; Inspector и reference host не заменяют проверку именно выбранного IDE.

## Корпус и проверочные факты

Эталоны расположены вне индекса в [evaluation/questions.json](evaluation/questions.json). Положительные факты относятся к разрешённому содержанию, а не к идентификаторам пациента/документа. Ответ описывает, **что записано в синтетическом источнике**, а не медицинскую правильность этих вымышленных сведений.

| Вопрос / объект | Ожидаемый факт | Локальный источник в sample_docs |
|---|---|---|
| Cedar follow-up interval | 17 days | visits/visit-01.md |
| Amber follow-up interval | 11 weeks | visits/visit-02.md |
| Saffron evening observations | 37 | visits/visit-03.md |
| Juniper collection date | 2024-02-17 | visits/visit-04.md |
| Willow route length | 1730 metres | visits/visit-05.md |
| Birch breathing exercise | 6 minutes | visits/visit-06.md |
| Orchid result | 4.73 mmol/L | visits/visit-07.md |
| Maple observation period | 7 consecutive mornings | visits/visit-08.md |
| Pine review date | 2025-09-23 | visits/visit-09.md |
| Hazel prepared questions | 9 | visits/visit-10.md |
| Rowan dizziness | explicitly denied | visits/visit-11.md |
| Elm prescription | 2.5 mg daily, intake unknown | visits/visit-12.md |

Комплект v1.2: **42 файла, 663711 файловых байт**, PDF/TXT/MD. Один только текст TXT/MD занимает **661410 байт** и превышает порог 512000 без учёта бинарного размера PDF. Происхождение, размеры и SHA256: [corpus-manifest.json](evaluation/corpus-manifest.json). Генератор не нужен при запуске. `python scripts/check_corpus.py` проверяет готовый корпус и manifest; текст генерируется с LF для одинаковых SHA256 на Windows и Linux.

В отрицательных privacy-fixtures намеренно присутствуют вымышленные имена, контакты и номера карты, в том числе в имени файла и цитате. Они синтетические и нужны, чтобы проверить очистку всей выдачи. Запросы этих идентификаторов не должны возвращать их через answer, find, metadata или ошибки. Сохранение числа/единицы/дозы/отрицания проверяется отдельно от удаления идентификатора.

Структурный splitter сохраняет целые абзацы, если они помещаются; длинные блоки делит по строкам таблиц, пунктам и предложениям. Overlap повторяет целые смысловые единицы в пределах бюджета. Только отдельная единица длиннее предела разбивается по словам/символам. Чанки остаются точными подстроками источника. Проверяются связи анализ/значение/единица, препарат/доза, рекомендация/срок и отрицание. Это не медицинская онтология и не гарантия семантики любого документа. Версия splitter включена в fingerprint: после обновления выполните `index_folder` для переиндексации существующего demo.

## Разработка и тесты

```sh
cd frontend
npm ci
npm run lint
npm test
npm run build
cd ../backend
npm ci
npm run lint
npm test
npm run build
cd ../ai-service
uv sync --frozen --group dev --python 3.12
uv run ruff check .
uv run pytest
```

Backend integration tests используют отдельную PostgreSQL БД из `TEST_DATABASE_URL`, никогда личную базу. Например: `postgresql://archive:local-test-password@127.0.0.1:5432/archive_test`. Имя базы должно содержать `test`; без переменной integration-набор пропускается. Детерминированные CI-тесты используют явно тестовые адаптеры моделей и не доказывают качество настоящего Ollama.

[GitHub-репозиторий опубликован](https://github.com/ruslan-yusupov-open/ai-coding-medical-archive). Workflow проверяет lint/типы, тесты и сборку. Прежний удалённый CI завершился ошибкой проверки corpus manifest из-за различия LF/CRLF; генератор исправлен на LF и проверка SHA256 усилена. Новый [удалённый прогон e02afee](https://github.com/ruslan-yusupov-open/ai-coding-medical-archive/actions/runs/35442666973) прошёл; детали и фактические результаты сохранены в VALIDATION.

## Реальные проверки v1.2

Следующие команды запускайте из корня в Python-окружении `ai-service` только на синтетическом demo. Application/PDF smoke создают и мягко удаляют свои тестовые записи. Замените 3000 на значение `API_PORT`, если оно переопределено.

```sh
python scripts/check_corpus.py
python scripts/verify_seed.py
python scripts/smoke.py --base http://127.0.0.1:3000
python scripts/pdf_smoke.py --base http://127.0.0.1:3000
python scripts/mcp_smoke.py --output docs/evaluation/v12-mcp-http-smoke.json
python scripts/host_agent_check.py --output docs/evaluation/v12-host-agent.json
```

Для проверки пустого MCP после безопасного reset добавьте `--expect-empty` в `mcp_smoke.py`. Для reference host заранее выполните `ollama pull qwen3.5:4b` или укажите `--model` с поддержкой tool calls. Основной RAG продолжает использовать `qwen2.5:3b`. Host-agent check обращается к локальному Ollama на хосте и настоящему MCP; это воспроизводимый reference host, не доказательство проверки VSCode Copilot.

Полный evaluation v1.2 вызывает настоящий Ollama и публичную privacy-границу, хранит только проверенные исходящие payloads; идентичность источника сравнивается локально. Используйте отдельный `DATA_DIR`, чтобы не изменять рабочие индексы. Пример PowerShell из корня после установки зависимостей:

```powershell
$env:DATA_DIR = Join-Path $PWD '.local-evaluation/v12-public-900'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
Remove-Item Env:MCP_DEMO_DIR -ErrorAction SilentlyContinue
& .\ai-service\.venv\Scripts\python.exe scripts/evaluate_public.py --output docs/evaluation/v12-public-rag.json
```

Для POSIX shell:

```sh
env -u MCP_DEMO_DIR DATA_DIR="$PWD/.local-evaluation/v12-public-900" OLLAMA_BASE_URL=http://127.0.0.1:11434 \
  ai-service/.venv/bin/python scripts/evaluate_public.py --output docs/evaluation/v12-public-rag.json
```

Если в среде был задан `MCP_DEMO_DIR`, удалите эту переменную перед evaluation, чтобы использовать отдельный demo внутри нового DATA_DIR. Для сравнения задайте другой каталог и `CHUNK_SIZE=1400`, `CHUNK_OVERLAP=180`; defaults — 900/120. `--limit 10` позволяет отдельно проверить первые десять случаев, но не заменяет полный прогон. Команда фиксирует факт, источник, отказ и privacy раздельно, сохраняет неудачи и время. Запуск и наличие скрипта не означают успешную приёмку: текущие результаты и ограничения находятся в [VALIDATION](docs/VALIDATION.md) и [evaluation README](docs/evaluation/README.md).

Browser smoke (`scripts/browser_smoke.cjs`) требует Playwright и Chromium/Edge; `PLAYWRIGHT_MODULE` и `BROWSER_CHANNEL` выбирают установленный runtime.

## Приватность и границы

Нет публичного хостинга, авторизации, OCR, изображений/DICOM и автоматической медицинской диагностики. Приложение предназначено для доверенного локального устройства. AI-факты требуют проверки; confidence не является вероятностью правильности. Редкие сведения могут идентифицировать человека даже после удаления имён.

Личный архив готовит пакет по цепочке правила → локальная LLM → preview → точный review hash → ручной Copy/Markdown. Внешних SDK/AI API, ключей провайдеров и автоматической отправки консультации нет. MCP отдельно отвечает подключённому host-агенту по синтетике: **такая выдача передаёт данные хосту**, даже без внешнего SDK на сервере. Дальнейшее использование хостом не становится локальным лишь потому, что наш Ollama локальный.

Для личного архива запускайте отдельный проект и volumes без seed:

```sh
docker compose -p medical-personal -f compose.yaml -f compose.personal.yaml up
```

Освободите порты остановкой demo или переопределите их через `.env`. MCP и в этом режиме предоставляет только синтетический корпус. Soft delete сохраняет оригиналы и историю, а не стирает их физически. Шифрование диска и резервные копии управляются пользователем.

[ARCHITECTURE](ARCHITECTURE.md) описывает решения, [TASKS](TASKS.md) — статус. Личный [REPORT](REPORT.md) пишет автор; технические AI-вставки помечены. Публикация GitHub не подтверждает принятие темы, личный отчёт, IDE-проверку или итоговую приёмку. По конспекту защита 28 сентября 2026 перенесена; новая дата не подтверждена.

## Локальная диагностика и безопасный reset

В рабочей среде 3000 занят другим приложением. Локальный исключённый из Git `.env` содержит `API_PORT=13000`: Swagger доступен на http://127.0.0.1:13000/docs. На чистом clone без `.env` используется 3000. Не останавливайте постороннее приложение ради порта.

```sh
docker compose ps
docker compose logs --tail=100 model-init ai backend
curl http://127.0.0.1:3000/api/health
```

Runtime-сеть `private` имеет `internal: true`. Порты публикует локальный nginx gateway с OUTPUT firewall, разрешающим только фиксированные upstream. Только gateway и опциональный host Ollama proxy получают `NET_ADMIN` для этих правил. Это сетевые прокси, **не внешний LLM-gateway**. Не отключайте firewall и не заменяйте фиксированный proxy произвольным URL-переадресатором. Пересоздание зависимостей через Compose перезапускает gateway для обновления upstream.

Загрузка весов зависит от сети. `MODEL_UNAVAILABLE` во внутреннем API или безопасный отказ MCP означает, что операция не завершена; проверьте Ollama и повторите. Сырые данные не являются запасным результатом privacy. Частичный PDF сопровождается предупреждением; ручные поправки сохраняются при reprocess.

Чтобы воспроизвести пустой MCP, сбросьте только синтетический индекс, сохранив архив:

```sh
docker compose stop ai
docker compose run --rm --no-deps ai python -m medical_ai.reset_demo
docker compose up -d ai gateway
```

В host-режиме добавляйте `-f compose.yaml -f compose.host-ollama.yaml` к каждой команде. Не заменяйте reset удалением общих volumes. Проверка runtime: `python scripts/runtime_check.py --mode container --api http://127.0.0.1:3000`; для host-режима укажите `--mode host`.

## Ограничения и исторические результаты

Оба Compose-режима ранее проверялись на Docker Desktop: контейнерный CPU Ollama и host Ollama. История v1.1 и ограничения сохранены в docs/evaluation. Результат `bounded-final-control.json` — **исторический: 17/21, первые 10/10 на прежнем корпусе и контракте**. Он не оценивает нынешний splitter, изменённые факты и публичную privacy-границу v1.2. Новые результаты фиксируются отдельными файлами `v12-*`, без переноса старых процентов.

Маленькая модель может выбрать неправильную дату/источник, дать слишком узкий ответ или отказаться при достаточном контексте. Проверка цитаты не доказывает семантическую правильность выбора. Summary и извлечённые факты требуют ручного просмотра. Строгая privacy-проверка также может отказать, если не удаётся безопасно сохранить смысл.

Для консультации можно выбрать до восьми готовых документов напрямую, без предварительного QA-ответа; без выбора контекст подбирается RAG. Версии источников проверяются до и после privacy, усечение контекста показывает предупреждение. Это не расширяет доступ внешнего MCP к личному архиву.

## Подтверждённые проверки v1.2

[Полная матрица](docs/VALIDATION.md): 143 AI tests в Linux, MCP privacy 8/8, manual privacy 3/3, application smoke 20/20, runtime 5/5. Реальный публичный RAG: **17/21**, первые десять фактов **10/10**; оставшиеся ошибки и закрытые отказы перечислены в отчёте. Reference host действительно сам выбрал ask_question. Результаты v1.1 сохранены отдельно и не подменяют эти проверки.

Опубликованный [GitHub CI для e02afee](https://github.com/ruslan-yusupov-open/ai-coding-medical-archive/actions/runs/35442666973) также прошёл: **213 тестов**, lint/build и сборка всех Docker-образов.
