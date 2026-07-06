# Task 6 — Расследование 91-дневного запроса 2026-05-04 + аудит нагрузки на iiko

**Статус:** todo (на исследовании, ПРИОРИТЕТ)
**Заведено:** 2026-05-21

## От менеджера
> Узнать почему был запрос 4 мая, на иико запрос за период в 91 день, мы вроде оптимизировали чтобы таких больших запросов не было. И в целом посмотреть проект, чтобы уменьшить нагрузку на сервера иико.

## Уточнение от @baa21v
> Kill switch добавили *после* того как увидели что запрос такой сработал. Давай разберемся где этот запрос был и почему он был по логам. Прикрепил скрин от поддержки иико.

## Скрин от поддержки iiko (Алексей Кисляков, Legacy_support_team)
> «Коллеги, ошибка по памяти будет продолжаться, пока вы не сообщите клиенту, что память сервера рассчитана автоматически для работы в открытом периоде, это **65 дней**. И если смотреть тяжёлые отчёты за бОльший период, памяти может не хватить. Что и происходит.»
>
> Логи 2026-05-04 17:00:32:
> ```
> 17:00:32,163 DEBUG <YyetboW9><Hamza><85.198.88.117>[h-8080-exec-0049](rr.Restri…
> 17:00:32,163 DEBUG <YyetboW9><Hamza><85.198.88.117>[h-8080-exec-0049](rr.Restri…
> 17:00:32,163 INFO  <YyetboW9><Hamza><85.198.88.117>[h-8080-exec-0049](rul.Activ…
> 17:00:32,173 DEBUG <YyetboW9><Hamza><85.198.88.117>[h-8080-exec-0049](rbro.Olap…
> 17:00:32,174 INFO  <YyetboW9><Hamza><85.198.88.117>[h-8080-exec-0049](rbro.Olap…
> ```
> «Тут было 91 день. В перезапуске. Добавил памяти на время.»

Никита Григорьев в 17:38: «добавил(а) Елена Ким в наблюдатели задачи».

## Контекст
- Лимит iiko: **65 дней** на открытом периоде.
- Был запрос с периодом **91 день** → не хватило памяти серверу → пожаловались.
- На 2026-02-24 мы делали day-by-day цикл для `get_writeoff_documents`, `get_incoming_invoices`, `get_outgoing_invoices` — но 91-дневный запрос 4 мая прошёл *мимо* этого, значит:
  - либо чанкование не покрывает все методы;
  - либо есть отдельный «жирный» метод (отчёты, OLAP, аналитика);
  - либо где-то фронт может задать произвольный диапазон.
- Логи поддержки указывают на компонент `rbro.Olap...` → это OLAP-отчёты iiko, возможно `getOlapReport` или аналог.

## Что выяснить в исследовании
1. **Где в коде** есть вызовы iiko с date_from/date_to **без чанкования** на ≤65 дней? Перечислить все методы.
2. **Логи 2026-05-04 в `logs/`** — найти, какой именно наш эндпоинт инициировал запрос. От кого пришёл, какой период, какой iiko-метод вызвал.
3. Есть ли в коде вызовы OLAP-отчётов (`rbro.Olap…` намекает на OLAP)? Что используется — `getOlapReport`, что-то другое?
4. Какие user-facing эндпоинты позволяют задать произвольный диапазон дат (особенно аналитика, отчёты, profit_loss, статистика)?
5. Есть ли периодические задачи (cron / startup / scheduler) с большими периодами по умолчанию?
6. Предложить **общий механизм чанкования** — например wrapper, который на любой iiko-метод с date_from/date_to режет на куски по 30 дней, чтобы новые методы не забывали.

## Файлы
- `services/iiko/iiko_service.py` — все методы с date params
- `services/iiko/iiko_sync.py`
- `services/analytics/`, `services/profit_loss/`, `services/reports/`, `services/transactions_and_statistics/`
- `routers/analytics/`, `routers/profit_loss/`, `routers/reports/`
- `logs/` — за 2026-05-04
- `main.py` — стартовые задачи, scheduler

## Findings

> Дата исследования: 2026-05-21. Read-only анализ.

### TL;DR — кто послал 91-дневный запрос

Виновник — `IikoService.get_transactions_by_modification_date(from_date, to_date)` в
`services/iiko/iiko_service.py:1000-1066`. Метод **уже** разбивает внешний цикл по
`DateSecondary.DateTyped` (дата модификации) по 1 дню, **НО** дополнительно навешивает
второй фильтр `DateTime.DateTyped` (дата создания транзакции) с захардкоженным окном
`to_date - 90 дней … to_date + 1 день` = **91 день**, и этот 91-дневный фильтр улетает в
каждом POST на `/resto/api/v2/reports/olap`. Именно его и видела поддержка iiko
4 мая ~17:00 в строке `rbro.Olap…`.

Триггер 4 мая 2026:
- `/sync/cron/sync` (вызывается кроном по apikey) → `_cron_sync_job`
  (`routers/iiko/sync.py:1282-1388`) → `iiko_sync.sync_by_modification_date(db, today, today)`
  (`services/iiko/iiko_sync.py:2039-2186`) → `service.get_transactions_by_modification_date(today, today)`
  (`iiko_service.py:1000-1066`) → POST `/resto/api/v2/reports/olap`
  c `DateTime.DateTyped.from = 2026-02-03`, `DateTime.DateTyped.to = 2026-05-05` (91 день).
- Параметр `from_date/to_date` модификации в этот момент = «сегодня…сегодня», но
  захардкоженный 90-дневный сдвиг в `iiko_service.py:1018` всё равно даёт 91 день.

Кроме того, есть user-facing эндпоинт `/sync/by-modification-date`
(`routers/iiko/sync.py:688-735`), у которого `from_date` по умолчанию = `now - 90 дней`
(`routers/iiko/sync.py:698`). Если оба периода широкие, получаем умножение 90×91.

### 1. Методы без чанкования (services/iiko/iiko_service.py)

| Метод | Строки | Параметры | Чанкование? | iiko endpoint | Риск |
|-------|--------|-----------|-------------|---------------|------|
| `get_transactions(from_date, to_date)` | 971-983 | `from_date`, `to_date` | НЕТ — весь период одним POST | `/resto/api/v2/reports/olap` (OLAP) | **Высокий**: вся «дыра» периода влетает в один OLAP. Используется в `sync_transactions` (iiko_sync.py:1459) и `sync_warehouse_documents_from_transactions` (iiko_sync.py:2222). |
| `get_sales(from_date, to_date)` | 985-998 | `from_date`, `to_date` | НЕТ — весь период одним POST | `/resto/api/v2/reports/olap` (OLAP) | **Высокий**: то же самое. Вызывается в `sync_sales` (iiko_sync.py:1656). |
| `get_transactions_by_modification_date(from_date, to_date)` | 1000-1066 | `from_date`, `to_date` | Частично: внешний цикл по дням, НО фильтр `DateTime.DateTyped` захардкожен на ±90 дней (строки 1017-1019) и улетает в каждой итерации | `/resto/api/v2/reports/olap` (OLAP) | **КРИТИЧЕСКИЙ — это виновник 91-дневного запроса 4 мая.** |
| `get_server_transactions_report(report_data)` | 1068-1075 | `report_data` (целиком), iiko filters | НЕТ (низкоуровневый враппер) | `/resto/api/v2/reports/olap` (OLAP) | Зависит от вызывающего. Используется в `get_transactions`, `get_sales`, `get_transactions_by_modification_date`. |
| `get_server_sales_report(report_data)` | 1077-1084 | `report_data` | НЕТ (низкоуровневый враппер) | `/resto/api/v2/reports/olap` (OLAP) | То же. |
| `get_server_deliveries_report(report_data)` | 1086-1093 | `report_data` | НЕТ (низкоуровневый враппер) | `/resto/api/v2/reports/olap` (OLAP) | Никем не вызывается в проекте, но публичный метод. |
| `get_server_product_expense_report(department, date_from, date_to)` | 1116-1127 | `date_from`, `date_to` | НЕТ — весь период | `/resto/api/reports/productExpense` (Server report) | **Средний**: не OLAP, но всё ещё «тяжёлый отчёт». Никем не вызывается сейчас. |
| `get_server_shifts(date_from, date_to, employee_id)` | 1300-1367 | `date_from`, `date_to` | НЕТ — весь период одним GET | `/resto/api/employees/attendance` (XML) | **Средний**: используется в `sync_shifts` (iiko_sync.py:1944). `sync_shifts` по дефолту запрашивает 30 дней (iiko_sync.py:1934), но HTTP-эндпоинт `/sync/shifts` (sync.py:346) позволяет произвольный период. |
| `get_payrolls(date_from, date_to, department, include_deleted)` | 2815-2846 | `date_from`, `date_to` | НЕТ — весь период | `/resto/api/v2/payrolls/list` | **Средний**: эндпоинт `/documents/payrolls` (documents.py:774-833) принимает произвольный период от пользователя без валидации. В `pay_out_service.py:224` вызывается с окном ±30 дней — допустимо. |
| `get_product_groups(date_from, date_to, prefer_cloud)` | 1211-1213 | даты опциональные | НЕТ | пробрасывается в `get_server_product_groups` | **Низкий**: даты редко используются. |
| `get_server_product_groups(date_from, date_to)` | 690-701 | `date_from`, `date_to` | НЕТ | `/resto/api/v2/entities/products/group/list` | **Низкий**: даты опциональны и обычно `None`. |

**Уже chunked (для справки, не трогаем):**
- `get_writeoff_documents` (1422-1490) — day-by-day цикл (`while current <= end`).
- `get_incoming_invoices` (2101-2163) — day-by-day цикл.
- `get_outgoing_invoices` (2165-2227) — day-by-day цикл.

### 2. OLAP-методы (намёк `rbro.Olap…`)

OLAP endpoint в коде = `POST /resto/api/v2/reports/olap` (Server API). Используется в:

- `services/iiko/iiko_service.py:1072` — `get_server_transactions_report`
- `services/iiko/iiko_service.py:1081` — `get_server_sales_report`
- `services/iiko/iiko_service.py:1090` — `get_server_deliveries_report`

Соседние OLAP-эндпоинты iiko (не отчёты, лёгкие):
- `/resto/api/v2/reports/olap/presets` (1099) — `get_server_report_presets`
- `/resto/api/v2/reports/olap/columns` (1106) — `get_server_report_fields`

Все три «тяжёлых» OLAP-метода вызывают `_make_request(IikoApiType.SERVER, ...)` без всякого
чанкования по дате — потому что чанкуют уже верхнеуровневые методы (или должны чанковать).

Реально вызываемые цепочки до OLAP:
1. `get_transactions` → `get_server_transactions_report` (без чанкования)
2. `get_sales` → `get_server_sales_report` (без чанкования)
3. `get_transactions_by_modification_date` → `get_server_transactions_report` (есть чанкование по дате модификации, но внутри 91-дневное окно по дате создания)

### 3. Логи 2026-05-04

`logs/` содержит только 2 файла, оба — это stdout редиректы curl от cron:
- `/srv/project/backend_main_node/logs/sync_cron.log` (48 MB, 2572 строк, mtime 2026-05-21 03:00)
- `/srv/project/backend_main_node/logs/daily_sync_cron.log` (110 KB, 198 строк, mtime 2026-05-21 04:00)

**Записей с датой 4 мая 2026 в этих логах нет.** Логи содержат только JSON-ответы от
`/sync/cron/sync` и `/sync/cron/daily-sync`, причём:
- Содержимое полей `dates_synced` доходит максимум до `2026-03-19` (после этого cron
  стал получать ответ `{"success":true,"message":"Синхронизация запущена в фоне","task_id":"..."}`
  — то есть сборка ушла в фоновый режим, и результат больше в stdout не пишется).
- В файлах вообще нет таймстампов (curl progress-output + чистый JSON-ответ без даты).
- IP пользователя в скрине поддержки (`85.198.88.117`, user `Hamza`) — это с большой
  вероятностью идентификаторы сервера iiko-side для нашего апи-логина (не наш user).
  В нашей БД пользователя `Hamza` искать смысла нет — это легит iiko-логин для Server API.

**Точный инициирующий запрос в наших логах найти невозможно** — приложение FastAPI
никуда внутри `logs/` свои логи не пишет (`logging.basicConfig` в `main.py:16` идёт в
stderr, а stdout/stderr приложения cron не редиректит). Чтобы поймать инициатор, нужно:
- посмотреть логи systemd/journalctl для FastAPI-сервиса за 2026-05-04 17:00 UTC;
- либо включить логирование в файл в `main.py:16`.

Но по коду путь очевиден: cron-таска `/sync/cron/sync` стреляет каждую минуту (видно
по 324 вызовам в одном лог-файле), и каждый раз вызывает `sync_by_modification_date`,
который дёргает OLAP с 91-дневным окном на создание транзакций.

### 4. Эндпоинты с произвольным диапазоном дат

User-facing (требуют JWT, могут привести к большому iiko-запросу косвенно через sync):

| Метод | Путь | Файл:строка | Идёт ли запрос в iiko? |
|-------|------|-------------|--------------------------|
| GET | `/analytics` | `routers/analytics/analytics.py:18-50` | Нет, только локальная БД (`services/analytics/analytics_service.py`) |
| POST | `/recalculate-employee-metrics` (analytics) | `routers/analytics/analytics.py:53-…` | Нет, локальная БД |
| GET | `/reports/profit-loss` | `routers/profit_loss/profit_loss.py:16-61` | Нет |
| GET | `/reports/profit-loss/detail` | `routers/profit_loss/profit_loss.py:64-97` | Нет |
| GET | `/reports/orders` | `routers/reports/reports.py:17-49` | Нет |
| GET | `/reports/moneyflow` | `routers/reports/reports.py:52-84` | Нет |
| GET | `/reports/sales-dynamics` | `routers/reports/reports.py:87-119` | Нет |
| GET | `/reports/personnel` | `routers/reports/reports.py:122-155` | Нет |
| GET | `/documents/payrolls` | `routers/documents/documents.py:774-833` | **ДА** — напрямую `iiko_service.get_payrolls(date_from, date_to)` без чанкования. Принимает произвольный диапазон. |
| GET | `/expenses` | `routers/expenses/expenses.py:174` | Нет (локальные данные) |
| GET | `/orders` | `routers/orders/order.py:40-41` | Нет (локальные данные) |
| GET | `/warehouse/documents` | `routers/warehouse/warehouse.py:148-175` | Нет (локальные данные) |

**Sync-эндпоинты** (`routers/iiko/sync.py`) — все требуют JWT (кроме `/sync/cron/*`),
многие имеют дефолты по 7 дней. Опасные дефолты:

| Эндпоинт | Дефолт `from_date` | Чанкуется? | Файл:строка |
|----------|-------------------|------------|-------------|
| `POST /sync/by-modification-date` | **`now - 90 дней`** | через `get_transactions_by_modification_date` (см. п.1) | `sync.py:688-735` (default: 698) |
| `POST /sync/shifts` | `now - 30 дней` (передаётся внутри `iiko_sync.sync_shifts`) | НЕТ (см. п.1) | `sync.py:346-395` |
| `POST /sync/transactions` | `now - 7 дней` | да, day-by-day в роутере (sync.py:564-582) | `sync.py:528-607` |
| `POST /sync/sales` | `now - 7 дней` | да, day-by-day (sync.py:637-655) | `sync.py:610-685` |
| `POST /sync/writeoff-documents` | `now - 7 дней` | да (внутренний day-by-day в сервисе) | `sync.py:1039-1077` |
| `POST /sync/incoming-invoices` | `now - 7 дней` | да | `sync.py:1080-1117` |
| `POST /sync/outgoing-invoices` | `now - 7 дней` | да | `sync.py:1120-1157` |
| `POST /sync/all-documents` | `now - 7 дней` | да | `sync.py:1160-1198` |
| `POST /sync/recalculate-daily-metrics` | `now` | не релевантно (локальная БД) | `sync.py:814-923` |
| `POST /sync/recalculate-employee-metrics` | `now` | не релевантно | `sync.py:926-1036` |

### 5. Фоновые задачи / стартовые задачи / cron

`main.py`:
- `lifespan` (строки 38-42): только `init_db()` и `include_routers()`. Никаких scheduler,
  никаких `asyncio.create_task`, никаких APScheduler/Celery. Нет ничего, что само ходило
  бы в iiko при старте.
- В проекте нет ни APScheduler, ни Celery, ни BackgroundScheduler — `grep -rE
  "scheduler|APScheduler|celery"` дал только упоминания cron-эндпоинтов в docstrings.

Внешний cron (системный) бьёт по двум эндпоинтам (видно по логам `sync_cron.log` и
`daily_sync_cron.log`):

1. **`/sync/cron/sync?apikey=...`** (`routers/iiko/sync.py:1545-1575`) → запускает в фоне
   `_cron_sync_job` (sync.py:1282-1388). Внутри:
   - `iiko_sync.sync_accounts(db)` (без дат)
   - `iiko_sync.sync_by_modification_date(db, today, today)` ← **источник 91-дневного OLAP**
   - `iiko_sync.sync_employees(db)` (без дат)
   - `iiko_sync.sync_shifts(db, now - 7 дней, today)` (7 дней одним запросом, без чанкования внутри `get_server_shifts`)
   - пересчёт `recalculate_daily_employee_metrics_for_date` по уникальным датам из ответа

2. **`/sync/cron/daily-sync?apikey=...`** (`routers/iiko/sync.py:1578-...`) → запускает в
   фоне `_daily_sync_job` (sync.py:1391-1542). Внутри только:
   - `sync_organizations`, `sync_cloud_org_ids`, `sync_roles`, `sync_items_cloud`,
     `sync_terminal_groups`, `sync_terminals`, `sync_restaurant_sections`, `sync_tables`,
     `sync_conceptions`, `sync_suppliers`, `sync_stores`, `sync_salaries`
   - `sync_all_documents(db, yesterday, today)` — 1 день, безопасно (плюс уже chunked).
   Длинных периодов не использует.

Других периодических задач нет.

### 6. Предложение по wrapper-у чанкования

Концепция (не пишем код, только эскиз):

1. **Декоратор `@iiko_date_chunked(max_days=30, date_args=("date_from","date_to"))`**,
   который на любой `async def` метод `IikoService` смотрит сигнатуру, находит указанные
   две даты, и если их разница > `max_days`, прозрачно делает несколько вызовов
   нижележащего метода с непересекающимися окнами по `max_days` дней и склеивает результат
   (для `List[…]` — extend, для `Dict` с `data`/`response` — extend по ключу, для XML —
   объединение элементов; стратегия задаётся параметром `merge="list"|"response_key"|"xml"`).
2. **Жёсткий guardrail в `_make_request`**: если в `data["filters"]` любого
   `/resto/api/v2/reports/olap` запроса разница между `from` и `to` любого фильтра
   > 31 дня → лог `ERROR` + (по флагу) `raise IikoPeriodTooLargeError`. Это поймает в
   рантайме новые «жирные» вызовы, добавленные мимо декоратора.
3. **Применить декоратор сразу к** `get_transactions`, `get_sales`,
   `get_transactions_by_modification_date` (заменив там захардкоженные 90 дней на
   динамическое окно ≤30 дней), `get_server_shifts`, `get_payrolls`,
   `get_server_product_expense_report`.
4. **Дефолты HTTP-эндпоинтов** (`sync.py:698` и `iiko_sync.py:1934`) уменьшить или
   принудительно ограничить и параметры пользователя: если фронт передал
   `to_date - from_date > MAX_DAYS_PUBLIC`, отвечать 400.
5. **Тест-обёртка**: моки на `_make_request` с проверкой, что ни один POST на
   `/resto/api/v2/reports/olap` не уходит с окном > 31 дня.

Так новые методы (например, будущий `get_olap_deliveries(date_from, date_to)`)
автоматически получат чанкование, если разработчик навесит декоратор; а если забудет —
guardrail в `_make_request` это поймает до того, как iiko снова пожалуется.

## Реализовано (2026-05-21)

### Шаг 1 — сжали окно `DateTime.DateTyped` с 90 до 60 дней

`services/iiko/iiko_service.py:1000-1066` (`get_transactions_by_modification_date`):

- Было: `date_created_from = to_date − 90 дней` → 91-дневный фильтр (выходит за лимит iiko 65 дней).
- Стало: `date_created_from = to_date − 60 дней` → 61-дневный фильтр (под лимит iiko с запасом).

Бизнес-решение @baa21v: в этой сети правки задним числом обычно укладываются в 60 дней; этого достаточно. Если потребуется ловить правки старше 60 дней — заводим отдельный «глубокий» job.

Логи и docstring обновлены — больше не пишет «3 месяцев / весь период», а «окно 60 дней».

### Шаг 2 — чанкование `get_transactions` и `get_sales` по дням

`services/iiko/iiko_service.py:971-998` (теперь `:971-1042`):

- Оба метода переписаны по той же схеме, что и `get_transactions_by_modification_date`: внешний `while current_date <= end_date` цикл по дням, каждый день — отдельный POST на OLAP (фильтр `[day_start, day_start+1)`), результаты `extend`-ятся в общий список.
- `try/except` на каждой итерации, при ошибке итерация падает, но цикл продолжается — как и в существующем `get_transactions_by_modification_date`.
- Поведение для вызывающих (`sync_transactions`, `sync_sales`, `sync_warehouse_documents_from_transactions`) не меняется: входная сигнатура та же, выход тот же `Optional[List[Dict]]`. Но больше нельзя случайно отправить в iiko OLAP «91 день одним куском».

### Шаг 3 — валидация диапазона на user-facing эндпоинтах

`routers/iiko/sync.py:688-712` (`POST /sync/by-modification-date`):
- Дефолт `from_date = now − 90 дней` → теперь `now − 60 дней` (под лимит iiko).
- Добавлена валидация: если `to_date − from_date > 60 дней`, отдаём 400.
- Добавлен `except HTTPException: raise` перед общим `except Exception`, чтобы 400 не превратился в проглоченный `{"success": False}`.

`routers/documents/documents.py:774-820` (`GET /documents/payrolls`):
- Добавлена валидация: если `date_to − date_from > 60 дней`, отдаём 400.
- Существующий `except HTTPException: raise` уже корректно пропускает 400.

## Финальное решение (2026-05-24)

@baa21v подтвердил политику:
> **Чанки по дню, максимум окно — 60 дней.**

То есть:
- Любой запрос в iiko с date-from/date-to разрезается по дню (1 POST на день).
- Если пользователь/код просит окно > 60 дней — возвращаем 400 (для public-эндпоинтов) или режем до 60 (для cron).
- Правки задним числом старше 60 дней клиент **не закрывает** в нашей синхронизации — это бизнес-trade-off (если очень понадобится, заведём отдельный «глубокий» job, который раз в неделю проходит 180 дней).

**Закрывает вопрос #2** из `questions_for_client_call.md` («Глубина правок задним числом в iiko»). Решение: 60 дней.

### Что сделано в финальной итерации (2026-05-24)

1. **Константа и хелперы** в `services/iiko/iiko_service.py` (вверху модуля):
   - `MAX_IIKO_DATE_WINDOW_DAYS = 60`
   - `iter_day_chunks(date_from, date_to)` — генератор `(start, end_exclusive)` по дням, с проверкой окна
   - `assert_iiko_date_window(date_from, date_to, label)` — без чанкования, бросает `ValueError`
   - `_to_date(value)` — нормализация `datetime/date/str → date`

2. **Дочанкованы все методы с date-params:**
   - `get_server_shifts` — теперь день-по-день, ранее одним XML-запросом за весь период
   - `get_payrolls` — теперь день-по-день, ранее одним запросом
   - `get_server_product_expense_report` — добавлена валидация 60 дней (аггрегированный отчёт, чанковать по дням нельзя без потери агрегации)

3. **Guardrail в `_make_request`** (safety net):
   - Метод `IikoService._check_olap_date_window(report_data)` проверяет `data["filters"]` для всех известных date-ключей (`DateTime.DateTyped`, `DateSecondary.DateTyped`, `OpenDate.Typed`, `CloseDate.Typed`)
   - В `_make_request` для endpoint `/resto/api/v2/reports/olap` вызывается перед отправкой
   - При окне > 60 дней — `logger.error` (не raise, не ломаем прод; ловим регрессии в логах)
   - Это автоматическая защита: если кто-то добавит новый OLAP-метод и забудет чанкование, мы сразу увидим в логах

4. **60-дневная валидация на user-facing endpoints:**
   - `POST /sync/shifts` — добавлена (раньше принимал любой диапазон)
   - `POST /sync/transactions` — добавлена
   - `POST /sync/sales` — добавлена
   - `POST /sync/by-modification-date` — была раньше
   - `GET /documents/payrolls` — была раньше
   - Везде проброс `except HTTPException: raise` перед общим `except`, чтобы 400 не превратилось в `{"success": false}`

5. **Smoke-импорт зелёный** (`from main import app`).

### Использование в новых методах

Если будешь добавлять новый метод с date-params:
```python
from services.iiko.iiko_service import iter_day_chunks, MAX_IIKO_DATE_WINDOW_DAYS

async def get_something_new(self, date_from, date_to):
    try:
        chunks = list(iter_day_chunks(date_from, date_to))
    except ValueError as e:
        logger.error(f"...: {e}")
        return None
    result = []
    for day_start, day_end_exclusive in chunks:
        ...
    return result
```

Если метод вызывает OLAP — guardrail в `_make_request` автоматически найдёт ошибку в логах при первом же запросе.

