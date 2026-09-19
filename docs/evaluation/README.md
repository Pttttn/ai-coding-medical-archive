# Реальные оценки v1.2

Технический журнал AI от 19 сентября 2026; только синтетические данные и локальные модели. [Полная матрица](../VALIDATION.md). [Исторические оценки v1.1](README_v1.1.md) используют другой корпус/вопросы и не подтверждают новый контракт.

## Текущий публичный результат

[v12-public-rag.json](v12-public-rag.json): **17/21**, первые десять фактов **10/10**, все exact facts **12/12**. Проверено 20 публичных payload; остальные закрыты ошибкой проверки. Не прошли: overview-01, multi-01, negation-01, conflict-01. Каждый результат включает expectedTextPresent, expectedSourcesCited, abstentionCorrect, privacyPassed и passed. Источник проверяется локально по responseRef/S1; реальные пути, chunk IDs и trace в публичный payload не добавляются. В JSON есть digests моделей и SHA256 реально использованных модулей.

Метрика — проверяемый substring/source proxy, а не независимая клиническая оценка. Отказ privacy не является утечкой, но снижает полезность и не считается успешным ответом. Сохранность контрольных медицинских фраз дополнительно проверяют [8 HTTP случаев](v12-mcp-privacy.json) и [3 ручных случая](v12-manual-privacy.json).

## Сравнение структурного chunking

| Размер/overlap | Чанки | Raw RAG: текст + источник + отказ |
|---|---:|---:|
| 900/120 | 773 | 17/21 |
| 1400/180 | 749 | 17/21 |

Вторая конфигурация: [v12-public-rag-1400.json](v12-public-rag-1400.json). Этот эксперимент завершён до последних узких privacy-правок; таблица сравнивает **raw RAG**, а не утверждает приёмку конечного публичного контракта 1400/180. По умолчанию сохранены 900/120. Структурные unit tests отдельно проверяют связь анализ/значение/единица, препарат/доза, рекомендация/срок и отрицание. Длинная единица, не помещающаяся в лимит, имеет явный ограниченный fallback.

## Повторение

Из корня, в Python-окружении ai-service (зависимости через uv sync --frozen):

```powershell
$env:OLLAMA_BASE_URL='http://127.0.0.1:11434'
$env:DATA_DIR=(Join-Path $PWD '.runtime/evaluation-v12')
Remove-Item Env:MCP_DEMO_DIR -ErrorAction SilentlyContinue
python scripts/evaluate_public.py --output docs/evaluation/v12-public-rag-repeat.json
python scripts/mcp_smoke.py --output docs/evaluation/v12-mcp-repeat.json
python scripts/mcp_privacy_check.py --output docs/evaluation/v12-privacy-repeat.json
python scripts/host_agent_check.py --output docs/evaluation/v12-host-repeat.json
```

Для 1400/180 задайте CHUNK_SIZE=1400, CHUNK_OVERLAP=180 и отдельный DATA_DIR. Для ручных cases из ai-service: `python -m tests.real_privacy_evaluation --output ../docs/evaluation/v12-manual-repeat.json`. Сценарии по умолчанию пишут текущие v12-файлы, поэтому для сохранения истории задавайте новый --output. MCP/host требуют запущенного Compose; host — также локальную модель с tool calls.

## Сохранённые неудачи

- before-email-order: 2/21, строгая проверка блокировала повреждённые regex-подстановкой контакты.
- before-name-cues: базовые проверки проходили, но просмотр настоящего find обнаружил вымышленное имя без метки. Эти файлы не считаются успешной privacy-приёмкой.
- before-address-guard: ручной набор 2/3; ложный отказ на 15 Pine Street. После поправки — 3/3, при этом явные медицинские единицы даже под Address/Clinic по-прежнему защищены.
- before-address-guard RAG: сохранён как отдельный контроль предыдущей ревизии.

Содержательные исходные runtime logs и локальные таблицы соответствий не публикуются. Сохранённые тестовые JSON содержат только синтетику; видимые исходные fake names в исторических неудачах намеренно показывают обнаруженный дефект.
