# Повтор проверки PR №2

Техническая AI-запись от 22 сентября 2026. Все входы синтетические. Используется штатный `scripts/evaluate_public.py`, без изменения вопросов, эталонов, источников или критериев PASS. Ошибки остаются в знаменателе. Отчёты `pr2-review-*.json` относятся к указанным в них моделям/окружениям; `v125-llm-models.json` сохраняет отдельные наблюдения проверяющего.

## Host Ollama

Установите зависимости `ai-service`, выполните `ollama pull nomic-embed-text` и `ollama pull qwen3.5:2b`. Из корня, PowerShell:

```powershell
$env:LLM_MODEL = 'qwen3.5:2b'
$env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
$env:DATA_DIR = Join-Path $PWD ('.local-evaluation/run-' + [guid]::NewGuid().ToString('N'))
Remove-Item Env:MCP_DEMO_DIR -ErrorAction SilentlyContinue
& ./ai-service/.venv/Scripts/python.exe scripts/evaluate_public.py --output "$env:DATA_DIR/result.json"
```

Для 4b или прежней 3b заранее скачайте соответствующую модель, замените `LLM_MODEL` и создайте новый каталог. Не используйте `--limit`, если сравниваете полный счёт. Для qwen3 клиент сам передаёт `think:false`; отдельного патча не требуется.

## Контейнерный Ollama стандартного Compose

Запустите обычный `docker compose up -d --build --wait --wait-timeout 1800` по README. Следующие команды PowerShell используют уже работающий AI и его конфигурацию модели; создают отдельный временный индекс, не меняют индексы архива/MCP и не требуют Python на хосте. Если Compose запущен с `-p`, используйте тот же `-p` во всех командах.

```powershell
$evalRoot = (docker compose exec -T ai python -c "import tempfile; print(tempfile.mkdtemp(prefix='public-eval-'))").Trim()
docker compose exec -T ai python -c "from pathlib import Path; p=Path('$evalRoot'); (p/'scripts').mkdir(); (p/'evaluation').mkdir(); (p/'ai-service').mkdir(); (p/'sample_docs').symlink_to('/app/sample_docs'); (p/'ai-service/medical_ai').symlink_to('/app/medical_ai')"
docker compose cp scripts/evaluate_public.py "ai:$evalRoot/scripts/evaluate_public.py"
docker compose cp scripts/evaluation_support.py "ai:$evalRoot/scripts/evaluation_support.py"
docker compose cp scripts/evaluate_stability.py "ai:$evalRoot/scripts/evaluate_stability.py"
docker compose cp ai-service/uv.lock "ai:$evalRoot/ai-service/uv.lock"
docker compose cp evaluation/questions.json "ai:$evalRoot/evaluation/questions.json"
docker compose exec -T -e PYTHONPATH=/app -e "DATA_DIR=$evalRoot/data" -e "MCP_DEMO_DIR=$evalRoot/demo" ai python "$evalRoot/scripts/evaluate_public.py" --output "$evalRoot/result.json"
New-Item -ItemType Directory -Force .local-evaluation | Out-Null
docker compose cp "ai:$evalRoot/result.json" .local-evaluation/container-result.json
```

В повторе использован проект `lma-pr2-review`, пять новых пустых томов, автоматическая загрузка моделей, Docker build cache. CPU-размещение подтверждено `ollama ps` и `size_vram=0`; версия Ollama и ресурсы Docker записаны в `pr2-review-environment.json`. Это не точная копия CPU-машины проверяющего и не обещание одинаковой скорости/качества.

## Дополнительные сценарии

API, PDF, MCP HTTP, privacy и runtime запускались скриптами `smoke.py`, `pdf_smoke.py`, `mcp_smoke.py`, `mcp_privacy_check.py`, `runtime_check.py` с отдельными `--output`. Для изолированного проекта использованы API 28000 / MCP 28002 и `runtime_check.py --project lma-pr2-review`.

Первоначальный PDF smoke не прошёл: модель не указала необязательное поле страницы, цитаты отклонены. После изменения схемы (поле обязательно, может быть null для plain text) сценарий прошёл 4/4. Оба результата сохранены; проверка источника не ослаблена. Дополнительный прямой повтор извлечения того же PDF прошёл на host 2b и 4b, без сохранения сырого содержимого.

Метрики и ограничения: [VALIDATION](../VALIDATION.md). Mock/HTTP tests подтверждают поведение кода, реальные evaluations — лишь наблюдаемое поведение выбранной модели на конкретном наборе.
