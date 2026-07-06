# Task 2 — Расходы не отправляются в iiko

**Статус:** todo (на исследовании)
**Заведено:** 2026-05-21

## От менеджера
> Не отправляются запросы расходов в иико

## Уточнение от @baa21v
> Наврядли из-за kill switch. Надо посмотреть что фронт отправляет, там эта проблема до этого была. Посмотри по логам может.

## Контекст
- Kill switch (`IIKO_REQUESTS_DISABLED=true`) включён с 2026-05-04 — но пользователь говорит, что проблема была *до* этого.
- «Расходы» в проекте — это:
  - расходные накладные (`create_outgoing_invoice_in_iiko` → `services/warehouse/invoice_service.py`),
  - акты списания (`create_writeoff_document_in_iiko` → `services/warehouse/writeoff_service.py`),
  - возможно «расходы» как операции из `services/expenses/expenses_management_service.py`.
- Эндпоинты:
  - `POST /documents/writeoff`
  - `POST /documents/outgoing-invoice` (`routers/documents/documents.py`)
  - `POST /warehouse/...` (`routers/warehouse/warehouse.py`)
  - `routers/expenses/` — отдельная сущность расходов.

## Что выяснить в исследовании
1. Какие именно «расходы» имеются в виду — накладные, списания, операционные расходы? Какие эндпоинты вообще существуют для отправки в iiko?
2. По логам: есть ли вызовы этих эндпоинтов от фронта за последние 1–2 месяца? Если есть — с какими payload, какой ответ?
3. Есть ли расхождение между schema, которое ждёт бэк, и тем, что шлёт фронт? Валидационные 422?
4. Что возвращает iiko при попытках (если шли до kill switch) — какие коды и сообщения?
5. Есть ли уже сейчас в коде «тихие» места, где расход сохраняется в БД, но не уходит в iiko из-за условия / try-except?
6. Когда именно проблема началась — есть ли коммит, который мог сломать?

## Файлы
- `routers/documents/documents.py`, `routers/warehouse/warehouse.py`, `routers/expenses/expenses.py`
- `services/warehouse/invoice_service.py`, `services/warehouse/writeoff_service.py`
- `services/expenses/expenses_management_service.py`
- `services/iiko/iiko_service.py` — методы расхода
- `logs/`

## Findings

### 1. Эндпоинты

Все «расходного типа» точки входа, которые так или иначе шлют запрос в iiko:

| Метод + путь | Файл:line | Сервис | Метод в IikoService | iiko endpoint |
|---|---|---|---|---|
| `POST /documents/writeoff` | `routers/documents/documents.py:49` | `services/warehouse/writeoff_service.py:52` `create_writeoff_document_in_iiko` | `IikoService.create_writeoff_document` (`services/iiko/iiko_service.py:1492`) | `POST {server}/resto/api/v2/documents/writeoff` (Server API, JSON) |
| `POST /documents/outgoing-invoice` | `routers/documents/documents.py:382` | `services/warehouse/invoice_service.py:400` `create_outgoing_invoice_in_iiko` | `IikoService.create_outgoing_invoice` (`iiko_service.py:1903`) | `POST {server}/resto/api/documents/import/outgoingInvoice` (Server API, XML) |
| `POST /documents/incoming-invoice` | `routers/documents/documents.py:222` | `services/warehouse/invoice_service.py:62` `create_incoming_invoice_in_iiko` | `IikoService.create_incoming_invoice` (`iiko_service.py:1832`) | `POST {server}/resto/api/documents/import/incomingInvoice` (Server API, XML) |
| `POST /documents/inventory` | `routers/documents/documents.py:571` | `services/warehouse/invoice_service.py:727` `create_inventory_in_iiko` | `IikoService.create_inventory` (`iiko_service.py:1986`) | `POST {server}/resto/api/documents/import/incomingInventory` (XML) |
| `POST /warehouse/documents` (legacy, `include_in_schema=False`) | `routers/warehouse/warehouse.py:36` | разруливает по `document_type`: WRITEOFF блокируется, INCOMING_INVOICE/OUTGOING_INVOICE — через те же сервисы | то же, что выше | то же |
| `POST /warehouse/writeoff-documents` (legacy, hidden) | `routers/warehouse/warehouse.py:310` | `writeoff_service.create_writeoff_document_in_iiko` | то же | то же |
| `POST /documents/pay-out` | `routers/documents/documents.py:836` | `services/cash/pay_out_service.create_pay_out_in_iiko` | (изъятие из кассы) | — |
| `POST /expenses` (управление расходами + опционально pay-out в iiko) | `routers/expenses/expenses.py:81` | `services/expenses/expenses_management_service.create_expense` + `create_pay_out_in_iiko` | iiko pay-out | — |

Большинство фронтовых вызовов «расход» — это `POST /documents/outgoing-invoice` (расходная накладная) и `POST /documents/writeoff` (акт списания), плюс `POST /expenses` для операционных расходов (изъятия).

### 2. Логика отправки

«Тихие» места, где документ может сохраниться у нас, но не уйти в iiko, либо где запрос вообще не отправится:

**A. Глобальный kill switch `IIKO_REQUESTS_DISABLED`** (`config.py:51`, default `true` начиная с 2026-05-04).
В `iiko_service.py:143` метод `_get_server_token()` возвращает `None`, если флаг включён. В `create_writeoff_document/outgoing_invoice/incoming_invoice` это приводит к `return None` (`writeoff` — строка 1521-1523, `outgoing_invoice` — 1918-1920) ещё до `httpx`-запроса. Далее сервисы возвращают `{"success": False, "message": "Не удалось создать ... в iiko API"}` и фронт получает 400 «Ошибка создания …». **Документ при этом в БД НЕ сохраняется** (см. ниже) — но и не уходит в iiko.

**B. Расходная накладная — потеря iiko_id, но коммит в БД** (`invoice_service.py:582-599`).
После `create_outgoing_invoice` возврат от iiko парсится из XML и пытается достать `id`. Если `iiko_id is None`, всё что делается — `logger.warning(...)`, **а документ всё равно коммитится** (строки 598-599 → 620 → 704 `db.commit()`). То есть при «странном» ответе iiko расходная накладная попадает в нашу БД с `iiko_id=None`, но валидация по `valid` в iiko НЕ проверяется при отсутствии `iiko_id` — функция всё равно возвращает `success: True`. Это значит: если iiko вернул `valid=false`, эта ветка пропустит ошибку.
**Более того:** проверки `iiko_response.get("valid", False)` в `outgoing_invoice` нет в виде ранней остановки — в отличие от `incoming_invoice` (где есть строки 262-272 `if not iiko_response.get("valid", False): return error`). Для расходной накладной такого блока нет вообще, т.е. **iiko ошибка «valid=false, errorMessage=…» молча игнорируется**, и пользователь видит «успех».

**C. Расходная накладная — `accountToCode`/`conceptionCode`/store жёстко зашиты в код.**
Даже если фронт прислал `accountToCode`, он перезатирается только если `account_id` отсутствует (`invoice_service.py:486-500`). Концепция всегда `DEFAULT_CONCEPTION_IIKO_ID="7e97ff39-…"` (строка 520), склад всегда `DEFAULT_STORE_IIKO_ID="5849a5b1-…"` (строка 482) — эти UUID привязаны к одной конкретной точке. На любой другой организации iiko может стабильно возвращать «valid=false / storeNotFound» — и из-за пункта B это будет молчаливый «успех» у нас, но реальной накладной в iiko не появится.

**D. Акт списания — `iiko_id` опциональный + при HTTP-ошибке сохранение идёт.**
`writeoff_service.py:214-220`: если `iiko_response is None`, возвращаем early `success: False`. Это нормально. Но `iiko_response` — это `result.json()` от Server API; если iiko вернул 200 OK с пустым/неожиданным телом, `iiko_id` будет `None` (строка 234), и **документ всё равно сохранится в БД** (строки 238-281) с `iiko_id=None`. Функция вернёт `success: True`. То есть «расход списан у нас, но не в iiko» — реальный сценарий.

**E. `create_writeoff_document_in_iiko` не проверяет `valid` поле.**
В отличие от incoming_invoice, тут нет проверки `if not iiko_response.get("valid", False): return error`. Server API `/api/v2/documents/writeoff` возвращает JSON; если там `valid=false`, оно молча игнорируется.

**F. Внешний `try/except Exception` в обоих сервисах (`invoice_service.py:716-724`, `writeoff_service.py:293-301`)** — ловит ВСЁ, делает `db.rollback()` и возвращает `{"success": False, "message": f"Ошибка …: {str(e)}"}`. Это не «тихий», а «громкий» путь — фронт получит 400 с описанием. Не страшно.

**G. `POST /expenses` (`routers/expenses/expenses.py:114-167`)** — если у organization не задан `department_id` или у department нет `iiko_id`, **расход сохраняется локально, но в iiko НИЧЕГО не уходит**, ответ при этом `success: True` с припиской `(для этой организации не задан департамент — в iiko не отправлено)`. Это известная «тихая» дорога: фронт видит «успех», iiko не получил ничего. Жалоба менеджера «не отправляются расходы» очень похожа на эту ветку.

### 3. Schema

#### `POST /documents/writeoff` ← `SimpleWriteoffDocumentRequest` (`schemas/warehouse.py:231`)
- `storeId` — Optional[int]. В `TESTING_MODE=true` берётся фиксированный `DEFAULT_STORE_IIKO_ID`. В продакшене (`TESTING_MODE=false`) — **обязательно**, иначе 400 «Поле storeId обязательно».
- `conceptionId` — Optional[int].
- `account_id` — **обязателен** (int, наш id из `account_list`). Если несуществующий → 404.
- `date` — **обязательно**, строка, парсится по форматам `dd.mm.YYYY`, `YYYY-MM-DD`, `YYYY-MM-DDTHH:MM`, ISO. Если фронт шлёт что-то типа `"2025-01-15 14:30"` (с пробелом, без `T`) — упадёт `ValueError → 500 Internal server error`.
- `comment` — Optional[str].
- `items: List[SimpleWriteoffItemRequest]` (`min_length=1`) — каждый: `id: int` (наш Item.id), `amount: float > 0`, `price`/`sum` опциональны.
  - Если `sum=None` и `price=None` → `cost=None`, и iiko может это завернуть.
  - Если фронт прислал `amount=0` → Pydantic 422 (`gt=0`).

#### `POST /documents/outgoing-invoice` ← `SimpleOutgoingInvoiceRequest` (`schemas/warehouse.py:304`)
- `storeId` — Optional[int]. В продакшене обязателен.
- `conceptionId` — Optional[int].
- `dateIncoming: str` — **обязателен**, ожидается `dd.mm.YYYY`. parse_date терпит и ISO, но если фронт шлёт без формата → 400.
- `comment`, `accountToCode`, `supplier` — все Optional. Но **`accountToCode` иiko фактически нужен**: если фронт его не пришлёт, в iiko запрос уйдёт без `accountToCode` (так как в сервисе он добавляется только при `account_to_code` в payload или из `account_id` — см. `invoice_service.py:486-500`; в Simple-схеме `account_id` НЕТ, только `accountToCode`). Это **большая дыра в Simple-схеме расходной накладной**: счёт корреспондента не приходит, iiko вероятно вернёт `valid=false`, и из-за п.B мы об этом молча промолчим.
- `items: List[SimpleInvoiceItemRequest]` (`min_length=1`) — `id: int`, `amount > 0`, `price >= 0`, `sum >= 0` (ВСЕ обязательные). Если фронт пришлёт `price`/`sum` строкой или пропустит — 422.

#### Поля, в которых 422 наиболее вероятен:
- Пустой `items` → 422.
- `amount <= 0` → 422.
- В `outgoing/incoming` нет `price` или `sum` → 422 (`price: float` без `default=None`).
- `account_id` строкой вместо int (writeoff) → 422.

### 4. Логи

В директории `/srv/project/backend_main_node/logs/` есть только два файла:
- `daily_sync_cron.log` (112 KB, последняя запись 2026-05-21 04:00)
- `sync_cron.log` (48 MB, последняя запись 2026-05-21 03:00)

**Это логи cron-скриптов синхронизации (curl-вывод `daily_sync` + `sync_cron`), а не логи FastAPI приложения.** В них видны только результаты `GET`-синхронизации документов от iiko (например, `outgoing_invoices: created 25/27, errors 0`), но **никаких записей входящих запросов от фронта** (POST /documents/writeoff, /documents/outgoing-invoice) НЕТ.

Backend (PID 766174, `/srv/project/backend_main_node/venv/bin/python3 main.py`, запущен deploy 04.05) пишет логи только в stdout/stderr процесса, файловый handler в `main.py` не настроен (там только `logging.basicConfig(level=INFO, format=...)` — строка 15). Файлов с записями HTTP-запросов на хосте нет: `grep` по `/var/log`, `/srv` и всему ФС не нашёл ни одной строки с `outgoing-invoice`, `create_outgoing_invoice`, `Расходная накладная`, `Акт списания`, `documents/writeoff`. То есть **проверить «что именно слал фронт» по логам сейчас НЕЛЬЗЯ** — логи не сохраняются на диск.

Что нужно для нормального дебага: либо переключить unit/service на лог-файл (systemd journal / `--log-file`), либо включить middleware-логирование запросов в `main.py`. Без этого все жалобы «фронт что-то не то шлёт» придётся отслеживать через DevTools у пользователя.

### 5. История изменений

В текущем репо локальная история «выровнена» — большинство файлов попали одним коммитом `b8a1233 "all"` (2026-04-14, ammiteus@localhost), который добавил с нуля:
- `routers/documents/documents.py` (+909)
- `schemas/warehouse.py` (+410)
- `services/warehouse/invoice_service.py` (+929)
- `services/warehouse/writeoff_service.py` (+302)
- `services/warehouse/warehouse_service.py` (+481)
- `services/expenses/expenses_management_service.py` (+277)

Это «squash»-импорт, поэтому реальной по-коммитной истории по этим файлам в репо не сохранилось. С этой датой совпадает по времени:
- `CHANGELOG_API_2026_04_12.md` — изменения API за 2026-04-12;
- следующий мерж — `0f5b3aa` (Merge main).

После 14.04.2026 файлы `invoice_service.py`/`writeoff_service.py` НЕ менялись — `git log -10 -- <file>` показывает только `b8a1233`. То есть «коммит, который сломал расходы» в локальной истории не виден; либо проблема была с самого момента «всё одним коммитом залили», либо реальный поломавший коммит остался в форках Ammite (PR #46/#47/#48/#49 — в этих PR-ах нет изменений warehouse-сервисов, судя по subject-ам: fiscal cheque, account sync logging, revenue category, get_expenses_from_transactions logging).

Релевантный недавний коммит `b59c25c` — про fiscal cheque + account sync logging; не трогает выходных накладных/списаний.

### 6. Гипотезы

В порядке убывания вероятности:

**Гипотеза 1 (самая вероятная) — фронт зовёт `POST /expenses`, а у организации не задан `department.iiko_id`.**
`routers/expenses/expenses.py:157-158`: «расход создан локально, но `(для этой организации не задан департамент — в iiko не отправлено)`», при этом ответ `success: true`. Менеджер видит, что в нашей админке расход появляется, но в iiko его нет. Это ровно описание «не отправляются запросы расходов в iiko». Проверить: `SELECT id, name, department_id FROM organizations` и `SELECT id, name, iiko_id FROM departments WHERE iiko_id IS NULL`. Также посмотреть запись в нашей таблице expenses — она будет, но в iiko-логах изъятие отсутствует.

**Гипотеза 2 — Simple-схема расходной накладной (`POST /documents/outgoing-invoice`) НЕ передаёт `account_id` / `accountToCode`, iiko возвращает `valid=false`, но сервис всё равно делает `success: true` и сохраняет документ у нас.**
В `SimpleOutgoingInvoiceRequest` поле `accountToCode` опционально, а `account_id` вообще отсутствует. `invoice_service.py:582-714` НЕ проверяет `iiko_response.get("valid")` (в отличие от incoming_invoice). Так что любой iiko reject (нет счёта, нет товара, неверная концепция/склад) молча превращается в «расходная накладная успешно создана» у нас. Фронт может слать корректные id товаров — но без счёта iiko валидация падает. Проверка: посмотреть в нашей таблице `warehouse_documents` записи с `document_source='OUTGOING_INVOICE'` и `iiko_id IS NULL` — это ровно те, что не доехали.

**Гипотеза 3 — `TESTING_MODE=false` в проде + фронт шлёт без `storeId` → 400 «Поле storeId обязательно».**
В обоих Simple-схемах в продакшене `storeId` обязателен (`documents.py:166-170` для writeoff, `:488-489` для outgoing). Если фронт продолжает слать payload «как в TESTING_MODE» (без `storeId`), бэк отвечает 400 — внешне выглядит как «не отправляются». Это укладывается в формулировку «проблема была до kill switch». Проверка: уточнить у фронта актуальный payload, и/или у девопса — что в `.env` сейчас стоит `TESTING_MODE`.

(Дополнительно стоит начать **писать логи FastAPI в файл** — иначе в следующий раз снова придётся гадать.)

## Реализовано (2026-05-21)

### 1. Расходная накладная — больше не молчит при iiko ошибке
`services/warehouse/invoice_service.py: create_outgoing_invoice_in_iiko` (около строк 573-630):
- Добавлена ранняя проверка `iiko_response.get("valid") is False` → возвращаем `success: False` с понятным сообщением (читаем `errorMessage` / `error` / `message` из ответа iiko), документ в БД **не сохраняется**.
- Добавлена проверка «нет id и нет явного valid=true» → тоже `success: False`, в БД ничего не пишем.
- Это закрывает «Гипотеза 2» из findings и пункт B/C из секции «Логика отправки».

### 2. Акт списания — то же самое
`services/warehouse/writeoff_service.py: create_writeoff_document_in_iiko` (около строк 214-260):
- Добавлены те же две проверки (`valid=false` и «нет id и нет valid=true»).
- Раньше при отсутствии `iiko_id` документ всё равно сохранялся в БД с `iiko_id=None`. Теперь — нет.

### 3. `POST /expenses` — больше не «тихий success» при отсутствии department.iiko_id
`routers/expenses/expenses.py: create_expense_endpoint` (около строк 114-145):
- Pre-check **до** создания локального расхода: если у organization нет привязанного `Department` с `iiko_id` — отвечаем 400 с понятным сообщением, локальный расход НЕ создаётся.
- Раньше расход создавался локально и возвращался `success: true` с припиской «в iiko не отправлено» — фронт это игнорировал, при повторных попытках копились дубликаты. Теперь — явная ошибка.

### Что не сделано (явно отложено)
- **«Гипотеза 3» — `TESTING_MODE=false` + фронт не шлёт `storeId`**: это не баг в нашем коде, а несоответствие фронта/бэка. Требует уточнения у фронта актуального payload и у devops — что стоит в `.env`. Не моя зона.
- **Хардкоды `DEFAULT_STORE_IIKO_ID`/`DEFAULT_CONCEPTION_IIKO_ID`/`accountToCode`** в расходной накладной — они привязаны к одной конкретной точке («ИП Шаяхметов»). На других организациях iiko может стабильно возвращать `storeNotFound`. Это бизнес-вопрос (нужны per-org дефолты или явный обязательный input от фронта). Не дёргаю без согласования.
- **Файловое логирование FastAPI** — пересекается с task 1 («auth-логи в stdout»). Разумнее общим конфигом, отдельной задачей.
- **`POST /expenses` без `organization_id`** — текущая логика просто пропускает iiko-отправку без ошибки. Я не правил, потому что это легитимный кейс «локальный расход для общего пула». Если бизнес скажет, что это всегда ошибка — закрутим.
