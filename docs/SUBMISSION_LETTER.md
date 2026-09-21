# Сопроводительное письмо к сдаче проектной работы

**Тема:** Сдача проектной работы — Local Medical Archive

Здравствуйте!

Направляю на проверку проектную работу **Local Medical Archive — локальный медицинский архив с Corrective RAG и MCP**.

[Репозиторий проекта на GitHub](https://github.com/ruslan-yusupov-open/ai-coding-medical-archive).

Приложение позволяет хранить медицинские документы и заметки, просматривать факты с привязкой к источникам, историю изменений и временную шкалу, задавать вопросы локальной модели и готовить деперсонализированный текст для ручной консультации. Отдельный MCP-сервер предоставляет подключаемому агенту поиск и ответы по синтетическому демонстрационному корпусу. Реализация учитывает уточнения консультации: медицинские форматы PDF/TXT/MD, гибридный поиск BM25 + vector → RRF и проверку исходящей MCP-выдачи локальной моделью.

Для запуска нужны Git и Docker с Compose. Из нового каталога:

```sh
git clone https://github.com/ruslan-yusupov-open/ai-coding-medical-archive.git
cd ai-coding-medical-archive
docker compose up
```

При первом запуске модели загружаются автоматически; требуется интернет и время на подготовку. API-ключи не нужны. После готовности сервисов доступны [интерфейс](http://127.0.0.1:8080) и [Swagger](http://127.0.0.1:3000/docs). Все поставляемые медицинские данные синтетические.

Материалы для проверки:

- [README: запуск, демонстрация и проверочные факты](https://github.com/ruslan-yusupov-open/ai-coding-medical-archive/blob/main/README.md).
- [ARCHITECTURE: архитектура и план до реализации](https://github.com/ruslan-yusupov-open/ai-coding-medical-archive/blob/main/ARCHITECTURE.md), [REPORT: история работы с AI и независимая проверка](https://github.com/ruslan-yusupov-open/ai-coding-medical-archive/blob/main/REPORT.md).
- [Конфигурация MCP для VS Code](https://github.com/ruslan-yusupov-open/ai-coding-medical-archive/blob/main/.vscode/mcp.json). Endpoint: `http://127.0.0.1:8002/mcp`; первоначально индекс пуст, для подготовки демо нужно вызвать `index_folder("./sample_docs")`. Корпус содержит 42 файла и более 500 КБ текста.
- [Результаты тестов и ограничения](https://github.com/ruslan-yusupov-open/ai-coding-medical-archive/blob/main/docs/VALIDATION.md), [матрица соответствия требованиям](https://github.com/ruslan-yusupov-open/ai-coding-medical-archive/blob/main/docs/REQUIREMENTS_AUDIT.md), [GitHub Actions](https://github.com/ruslan-yusupov-open/ai-coding-medical-archive/actions).

21 сентября я дополнительно проверил установку с нуля в Docker на отдельном MacBook: проект развернулся и работает нормально. В документации также сохранены автоматизированные проверки и реальные оценки локальной модели. Известные ограничения качества RAG указаны открыто: расширенный набор — 17/21, первые десять контрольных фактов — 10/10.

Прошу проверить работу. Буду благодарен за замечания и обратную связь.
