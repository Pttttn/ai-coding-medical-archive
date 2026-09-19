# Local Medical Archive

Локальный однопользовательский медицинский архив: документы и заметки, проверяемые AI-факты, временная шкала, поиск с источниками и подготовка текста для ручной консультации. React + NestJS + PostgreSQL + Python Corrective RAG + Ollama. **Все поставляемые данные синтетические.**

## Быстрый запуск

Нужен Docker с Compose 2.24.4+; рекомендуется минимум 12 ГБ доступной RAM и 12 ГБ диска. CPU поддерживается, быстродействие зависит от оборудования. GPU не обязателен. Интернет нужен только для первой загрузки образов, зависимостей и весов. Для запуска не нужен `.env` и не нужны API-ключи:

```sh
docker compose up --build
```

Обычный повторный запуск и проверочный сценарий задания: `docker compose up`. Сервис `model-init` автоматически подготавливает `qwen2.5:3b` и `nomic-embed-text`, не имея доступа к архиву. После завершения подготовки runtime-сервисы работают в изолированной сети. Backend автоматически применяет миграции и идемпотентный seed. Первое индексирование видно в статусах документов.

| Сервис | Адрес |
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

На Docker Desktop Ollama должен принимать соединения через `host.docker.internal:11434`; при необходимости задайте `OLLAMA_HOST=0.0.0.0:11434` для процесса Ollama и перезапустите его. Не открывайте порт в публичную сеть. На Linux конфигурация использует `host-gateway`; host firewall должен разрешать только Docker-подсеть. Внутренние сервисы общаются с фиксированным Ollama proxy, который разрешает inference/metadata маршруты и запрещает произвольные URL и загрузку моделей. Точный проверенный вариант среды фиксируется в docs/VALIDATION.md.

## Сценарий демонстрации

1. Откройте кабинет: 36 записей за 2024–2025 годы, распределение типов и история изменений.
2. В архиве выполните поиск, измените фильтр/страницу; откройте лабораторный отчёт и исходный PDF.
3. Посмотрите цитату факта, измените значение, проверьте историю; исходная цитата останется прежней.
4. Создайте заметку или загрузите PDF с текстовым слоем. Дождитесь локальной обработки; сканы получают понятный статус UNSUPPORTED_OCR_REQUIRED, OCR в MVP нет.
5. Задайте вопрос об архиве. Ответ содержит реальные источники; недостаток данных не подменяется выдуманным ответом.
6. Подготовьте консультацию, отредактируйте preview, подтвердите именно текущий текст и скачайте Markdown. Любая последующая правка сбросит разрешение на экспорт.
7. Удалите документ, проверьте корзину и восстановление. Удалённый документ не участвует в новых ответах и консультациях.

## MCP

Готовая конфигурация VSCode Copilot находится в `.vscode/mcp.json`. Сервер Streamable HTTP имеет ровно четыре инструмента с предметными описаниями:

```text
index_status()                         # пусто при первом чистом запуске
index_folder(path="./sample_docs", glob="**/*")
index_status()                         # файлы, чанки, время
find_relevant_docs(query="Cedar visit", top_k=5)
ask_question(question="What is the reference code of the Cedar visit?")
```

Приложение автоматически индексирует `archive`, а публичный MCP использует отдельный `mcp_demo`, поэтому первый MCP-индекс пуст. MCP может читать только synthetic `sample_docs`, не личный архив. Файлы кода индексируются как текст и не выполняются. `index_folder` и `find_relevant_docs` используют эмбеддинги без генеративной LLM; `index_status` не вызывает модели. `ask_question` проходит rewrite → BM25/vector RRF → LLM grading каждого чанка → generate, при нехватке контекста не более двух broaden/retrieve повторов.

Предметный вопрос для проверки выбора host-агентом: «What is the reference code of the Cedar visit?» Не добавляйте подсказку «вызови MCP». Запишите фактический вызов и ответ своего host; тест транспорта не доказывает автономный выбор инструмента IDE.

## Проверочные факты

Эталоны находятся вне корпуса в `evaluation/questions.json`. Минимум десять необычных фактов доступны непосредственно в файлах:

| Вопрос / объект | Ожидаемый факт | Источник в sample_docs |
|---|---|---|
| Cedar reference code | SYN-CASE-7F29 | visits/visit-01.md |
| Amber follow-up interval | 11 weeks | visits/visit-02.md |
| Saffron evening observations | 37 | visits/visit-03.md |
| Juniper collection date | 2024-02-17 | visits/visit-04.md |
| Willow route length | 1730 metres | visits/visit-05.md |
| Birch room | B-217 | visits/visit-06.md |
| Orchid result | 4.73 mmol/L | visits/visit-07.md |
| Maple notebook | violet, triangle on cover | visits/visit-08.md |
| Pine review date | 2025-09-23 | visits/visit-09.md |
| Hazel prepared questions | 9 | visits/visit-10.md |
| Rowan dizziness | explicitly denied | visits/visit-11.md |
| Elm prescription | 2.5 mg daily, intake unknown | visits/visit-12.md |

Комплект: 45 уникальных индексируемых файлов, **662324 байта**, все `.md .txt .py .js .ts .json .yaml`. Manifest, SHA256 и происхождение: `evaluation/corpus-manifest.json`. Генератор не требуется при запуске. Проверка готовых файлов: `python scripts/check_corpus.py`.

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

Backend integration tests используют отдельную PostgreSQL БД из `TEST_DATABASE_URL`, никогда личную базу. Например: `postgresql://archive:local-test-password@127.0.0.1:5432/archive_test`. Имя базы должно содержать `test`; без этой переменной 21 integration test пропускается. Обычные CI-тесты не требуют GPU или LLM API, используют явно тестовые адаптеры. Реальная оценка Ollama выполняется отдельно; её команды, измеренные результаты, параметры chunking и ограничения находятся в `docs/VALIDATION.md` и `docs/evaluation/`. Workflow GitHub Actions настроен на типы/lint, тесты и сборку всех контейнеров. Удалённый запуск CI ещё не выполнялся: GitHub remote не задан.

## Приватность и ограничения

Публичного хостинга, авторизации, OCR, изображений/DICOM и автоматической медицинской диагностики нет. Приложение предназначено для доверенного локального устройства. AI-факты требуют проверки; confidence модели не является вероятностью правильности. Редкие сведения могут идентифицировать человека даже после удаления имён. Проверяйте preview перед ручной передачей. Автоматической отправки наружу нет.

Для личного архива запускайте отдельный проект и volumes без seed:

```sh
docker compose -p medical-personal -f compose.yaml -f compose.personal.yaml up
```

Остановите demo, чтобы освободить порты, или задайте другие через `.env`. MCP и в этом режиме предоставляет только синтетический корпус. Soft delete сохраняет оригиналы и историю, не является физическим стиранием. Шифрование диска и резервные копии управляются пользователем.

Архитектура: `ARCHITECTURE.md`. Полная спецификация: `PROJECT_SPECIFICATION.md`. Реальный статус: `TASKS.md`, `docs/VALIDATION.md`. Личную часть `REPORT.md` должен написать автор; технические AI-вставки помечены. Согласование темы, публикация GitHub и проверка CI на удалённом репозитории не выдаются за выполненные локальными тестами.

## Проверенный локальный запуск и диагностика

В рабочей среде порт 3000 уже занят другим приложением. Поэтому локальный, исключённый из Git `.env` содержит `API_PORT=13000`: проверенный Swagger доступен на http://127.0.0.1:13000/docs. На чистом clone без `.env` используется 3000. Не останавливайте постороннее приложение ради освобождения порта.

```sh
docker compose ps
docker compose logs --tail=100 model-init ai backend
curl http://127.0.0.1:3000/api/health
```

Начальная загрузка весов занимает несколько минут и зависит от сети. Ошибка `MODEL_UNAVAILABLE` означает, что операция не завершена: проверьте модели, состояние Ollama и повторите её. При отсутствии текстового слоя PDF OCR не запускается; у PDF с частично доступным текстом показывается предупреждение. Ручные исправления фактов сохраняются при повторной обработке.

Runtime-сеть `private` имеет `internal: true`. Порты публикует отдельный nginx gateway с собственным OUTPUT firewall: разрешены только три фиксированных upstream. Для настройки этих правил только gateway и опциональный host Ollama proxy получают `NET_ADMIN`. Нельзя запускать их с отключённым firewall или подменять фиксированный proxy универсальным URL-переадресатором. Пересоздание зависимостей через Compose перезапускает gateway для обновления адресов upstream.

Следующие сквозные проверки запускайте из корня репозитория в Python-окружении ai-service, только на синтетическом demo; они создают и затем мягко удаляют свои тестовые записи:

```sh
python scripts/check_corpus.py
python scripts/verify_seed.py
python scripts/smoke.py --base http://127.0.0.1:3000
# Нужны зависимости ai-service (включая pypdf и FastMCP):
python scripts/pdf_smoke.py --base http://127.0.0.1:3000
python scripts/mcp_smoke.py
python scripts/host_agent_check.py
```

Для reference host заранее подготовьте отдельную модель `ollama pull qwen3.5:4b` либо укажите `--model` с поддержкой tool calls. Основное приложение продолжает использовать qwen2.5:3b. Последние две команды обращаются к настоящему MCP и локальной модели; host-agent check требует запущенного Ollama на хосте. Параметры и отдельная полная RAG-оценка описаны в `docs/evaluation/README.md`. Browser smoke (`scripts/browser_smoke.cjs`) требует Playwright и Chromium/Edge; переменные `PLAYWRIGHT_MODULE` и `BROWSER_CHANNEL` позволяют выбрать установленный локальный runtime. Результаты лежат в `docs/evaluation/`, подробная матрица — в `docs/VALIDATION.md`.

Для повторной демонстрации **пустого синтетического MCP** можно сбросить только его индекс, сохранив архив и оригиналы:

```sh
docker compose stop ai
docker compose run --rm --no-deps ai python -m medical_ai.reset_demo
docker compose up -d ai gateway
```

В host-режиме добавьте `-f compose.yaml -f compose.host-ollama.yaml` к каждой команде Compose. Не заменяйте этот сброс удалением общих volumes.

## Проверенные режимы и текущие ограничения

Оба режима реально запущены на Docker Desktop: стандартный контейнерный Ollama (CPU) и `compose.host-ollama.yaml` с локальным Ollama на хосте. `scripts/runtime_check.py --mode container|host --api http://127.0.0.1:3000` проверяет готовность моделей и блокировку внешних соединений. Host-прокси фиксирует IPv4-адрес `host.docker.internal`, поскольку Docker Desktop может возвращать IPv6 первым; в его allowlist доступны только inference и metadata.

Для консультации можно явно выбрать до восьми готовых документов. Такой выбор используется напрямую и не зависит от способности QA-модели ответить на вопрос. Без выбора документы подбираются через RAG. Версии источников проверяются до и после privacy pass; при усечении контекста выводится предупреждение.

Актуальная реальная RAG-оценка: `docs/evaluation/bounded-final-control.json`, **17/21**, включая **10/10** обязательных фактов. Система может ошибиться в дате, ответить слишком узко или отказать при наличии ответа. Исходные цитаты проверяются, но семантическая правильность выбора источника не гарантируется. AI-summary и типы/значения извлечённых фактов также требуют ручной проверки. Полный разбор и промежуточные прогоны сохранены в `docs/evaluation/README.md`.
