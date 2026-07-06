# Research scripts

Одноразовые скрипты для аккуратного исследования iiko API в обход kill switch.

## Правила

- **Только GET / получение данных.** Никаких POST/PUT/DELETE, никаких создания/изменения/удаления.
- **Минимальные периоды** (1-3 дня), один department/organization за раз.
- **Прямой `httpx`-клиент**, не дёргать наш `IikoService` и `iiko_sync` — чтобы не задеть kill switch и не уйти через cron-каналы.
- Credentials читаем из `.env` через `dotenv` (тот же `IIKO_SERVER_API_URL`, `IIKO_LOGIN_KEY`, и т.д.).
- Скрипт **печатает** ответ (JSON/XML pretty), не сохраняет в БД, не пишет в `cache/`.
- Каждый скрипт — самодостаточный файл, имя вида `research_<task>_<тема>.py`.

## Использование

```bash
cd /srv/project/backend_main_node
source venv/bin/activate
python _kanban/scripts/research_<...>.py
```

## Зачем

Kill switch `IIKO_REQUESTS_DISABLED=true` блокирует все запросы через `IikoService`.
Этот флаг **снимается только в самом конце**, на финальной стадии тестов.
Чтобы при разработке всё-таки иметь возможность «посмотреть, что отдаёт iiko»
(например, схему ответа `/employees/salary`), пишем эти отдельные read-only утилиты.
