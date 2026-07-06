# Task 4 — Синхронизация видов оплаты

**Статус:** todo (на исследовании)
**Заведено:** 2026-05-21

## От менеджера
> По видам оплаты посмотреть

## Уточнение от @baa21v
> Надо синхрить и понять какие виды оплаты точно есть, а то там не сходилось вроде у нас то что на кассе имеют и то что у нас. Давай проверим точно. У каждой точки же свой набор видов оплат.

## Контекст
- Виды оплаты в iiko привязаны к конкретной организации (точке).
- У нас есть `routers/payment_types/` и, вероятно, `services/...` + модель.

## Что выяснить в исследовании
1. Где у нас хранятся payment types — модель, поля, связь с организацией.
2. Откуда они подтягиваются — какой метод iiko API, как часто?
3. Учитывается ли организация при синхронизации, или всё валится в одну кучу?
4. Что именно «не сходится» — каких видов нет / лишние / переименованы / неактивные?
5. Как сейчас payment_type выбирается при создании заказа — id наш или iiko_id?
6. Есть ли неактивные/удалённые виды, которые мы не отфильтровали?

## Файлы
- `models/` — payment_type модель
- `routers/payment_types/`
- `services/...` (нужно найти)
- `services/iiko/iiko_service.py` — методы получения видов оплаты
- `services/iiko/iiko_sync.py` — sync видов оплаты

## Findings

### 1. Модель
`models/payment_type.py:6-37` — таблица `payment_types`.

Поля:
- `id` (PK), `iiko_id` (String(50), UNIQUE, NOT NULL) — `models/payment_type.py:9-10`
- `code`, `name`, `comment`, `combinable`, `external_revision`, `print_cheque`, `payment_processing_type`
- `payment_type_kind` (String(50)) — `Cash` / `Card` / `IikoCard` / `External`
- `is_deleted` (Bool, default False) — флаг удаления из iiko — `payment_type.py:17`
- `is_payable` (Bool, default True, NOT NULL) — True = реально на кассе, False = служебные (Перемещение, Бракераж, Дегустация, Маркетинг, Стафф, Сертификат и т.п.) — `payment_type.py:21-25`
- `source` (String(20)) — `'cloud'` (полная схема) или `'server'` (минимум + эвристики) — `payment_type.py:27`
- `organization_iiko_ids` (JSON, nullable) — массив iiko_id_cloud организаций — `payment_type.py:30-33`. Семантика:
  - `NULL` = доступен ВСЕМ организациям (сертификаты, бонусы)
  - `[]` = не привязан (фактически невидим)
  - `[uuid1, ...]` = только этим организациям
- `created_at`, `updated_at`

Связь с организацией: **НЕ через FK и НЕ через m2m-таблицу**, а через JSON-массив `organization_iiko_ids` — это плоский список cloud-UUID-ов. Это решение: индексировать сложно, фильтр идёт в Python (см. п.4).

### 2. Синхронизация
`services/iiko/iiko_sync.py:1224-1336` — `sync_payment_types(db)`. Дёргает ДВА iiko-метода:

1. **Cloud** `POST /api/1/payment_types` с `{"organizationIds": [...все наши cloud-org...]}` — `services/iiko/iiko_service.py:2914-2931` (`get_payment_types`). Возвращает ~6 видов с полной схемой (paymentTypeKind, terminalGroups, combinable, paymentProcessingType). Парсер `iiko_parser.py:1713-1764` (`parse_payment_types`) — собирает `organization_iiko_ids` из `terminalGroups[*].organizationId`, дедуплицирует по `iiko_id`.
2. **Server** `GET /resto/api/v2/entities/list?rootType=PaymentType&includeDeleted=true` — `iiko_service.py:2933-2951` (`get_server_payment_types`). Возвращает ~43 вида с минимумом (`id, name, code, deleted`). Парсер `iiko_parser.py:1673-1710` достраивает эвристикой:
   - `payment_type_kind` (`_guess_payment_type_kind` по имени)
   - `is_payable` (`_guess_is_payable` по имени)
   - `jur_person_hint` (`_extract_jur_person_hint` — выдёргивает «ИП Шаяхметов» / «ИП Акжан» / «ИП Амиржан» из имени)
   - `organization_iiko_ids = None` (доразрешается в синке)

**Резолв организаций для Server-only видов** (`iiko_sync.py:1261-1298`):
- Тянет JurPersons из `/resto/api/corporation/departments` (XML, фильтр `type=JURPERSON`)
- Маппинг: `Organization.department_id` -> `Department` -> `Department.parent_id` (= JurPerson uuid) -> список organizations
- Если у вида есть `jur_person_hint` и он в маппинге — кладёт список org-uuid'ов этого юр.лица.
- Если хинта нет — кладёт `NULL` (= «доступно всем»).

**Мердж** (`iiko_sync.py:1281-1300`): Cloud приоритетнее, Server только дополняет недостающие iiko_id. Upsert по `iiko_id`. `is_deleted` пишется из iiko (Cloud `isDeleted` либо Server `deleted`).

Триггер: `POST /iiko/sync/payment-types` в `routers/iiko/sync.py:320` + входит в `sync_all` (`iiko_sync.py:1370`).

Внимание — kill-switch `IIKO_REQUESTS_DISABLED=true` блокирует оба HTTP-запроса, поэтому сейчас sync ничего не обновляет.

### 3. Применение в заказе
Создание (`services/orders/orders_services.py:393-404`): фронт шлёт `paymentTypeId` — это **наш `payment_types.id` (INT)**, бэк резолвит в PaymentType, кладёт в `external_data.payments_info` `paymentTypeIikoId`, `paymentTypeKind`, `paymentTypeName`. Локально, в iiko ничего не уходит.

Отправка/закрытие оплат в iiko (`orders_services.py:740-844`, функция `change_payments`):
- принимает либо `paymentType: int` (наш id) — резолвит в `iiko_id`+`payment_type_kind` через БД (`orders_services.py:784-798`),
- либо `paymentTypes: [{iiko_id, payment_type_kind}, ...]` — берёт iiko_id напрямую от фронта (`orders_services.py:800-802`).
- Шлёт в iiko Cloud `{organizationId: org.iiko_id_cloud, orderId, payments: [{paymentTypeKind, sum, paymentTypeId=iiko_id, isProcessedExternally: true}]}` (`orders_services.py:825-840`).

**Привязка организации при выборе вида оплаты — НЕ проверяется на сервере!** Никакой валидации, что выбранный PaymentType реально относится к организации заказа (нет cross-check `org.iiko_id_cloud in pt.organization_iiko_ids`). Фронт обязан фильтровать сам через `GET /payment-types?organization_id=...`.

### 4. Эндпоинты
`routers/payment_types/payment_types.py:17-87` — единственный эндпоинт `GET /payment-types`.

Параметры:
- `organization_id: int` (optional) — фильтр по нашей org. Резолвит в `org.iiko_id_cloud`, затем в Python отбирает `pt.organization_iiko_ids IS NULL OR org.iiko_id_cloud in pt.organization_iiko_ids` (`payment_types.py:51-55`).
- `include_internal: bool` (default false) — если false, выкидывает `is_payable=false`.
- Всегда фильтрует `is_deleted == False` (`payment_types.py:36`).

POST/PUT/DELETE на payment-types — НЕТ (нельзя создавать/менять локально). Триггер синка — отдельный `POST /iiko/sync/payment-types`.

### 5. Состояние БД
Снимок из локальной PG (read-only SELECT):

| Метрика | Значение |
|---|---|
| Всего записей | **43** |
| `is_deleted=true` | **8** |
| `is_payable=true` | 19 (включая 4 удалённых) |
| `source='cloud'` | 6 |
| `source='server'` | 37 |
| Дубликаты по `iiko_id` | 0 |
| Дубликаты по `name` | 0 |
| Без `iiko_id` / `name` | 0 |

**Распределение `organization_iiko_ids` (среди не-удалённых, 35 шт):** все `array` (NULL и `[]` отсутствуют — после последнего синка).

**Видно payable-видов на каждую организацию** (фильтр как в `/payment-types` без `include_internal`):
```
ФАБРИКА             2     1ГК Бокейхана      9     6ГК Нурсая        8
2ГК Мангилик        9     3ГК Highvill       8     4ГК Expo          9
5ГК Шарль де Голль  9     7ГК Площадь        9     8ГК Мухамедханова 8
```
У ФАБРИКИ всего 2 — потому что в Cloud она вообще не возвращается (не имеет terminalGroups у Cloud-видов), Server-only банки привязаны через JurPerson «ИП Амиржан».

**Подозрительные записи (`source='server'`, `is_payable=true`):**
- `Kaspi Рестораны1` (id=36, is_deleted=false, **organization_iiko_ids=NULL** → виден ВСЕМ организациям, хотя имя намекает на нечто «единичное»)
- 4 удалённых, но `is_payable=true`: `Kaspi Рестораны1111`, `Бонусы Plazius`, `Мобильный платеж`, `Раннее внесенная предоплата` — отфильтрованы только за счёт `is_deleted`.

**Последний sync:** `updated_at` у всех ≈ `2026-04-09 11:13` (это до включения kill-switch 2026-05-04). С тех пор данные не обновлялись.

SQL, который повторно запустить для проверки:
```sql
-- per-org visibility
SELECT o.id, o.name AS org_name, COUNT(pt.id) AS payable_visible
FROM organizations o
LEFT JOIN payment_types pt
  ON pt.is_deleted=false AND pt.is_payable=true
 AND (pt.organization_iiko_ids IS NULL
      OR (pt.organization_iiko_ids::jsonb) @> to_jsonb(o.iiko_id_cloud::text))
WHERE o.iiko_id_cloud IS NOT NULL
GROUP BY o.id, o.name ORDER BY o.id;

-- подозрительные NULL-scope server-виды
SELECT id, name, is_deleted, is_payable
FROM payment_types
WHERE source='server' AND organization_iiko_ids IS NULL;

-- удалённые но payable
SELECT id, name FROM payment_types WHERE is_deleted AND is_payable;
```

### 6. Гипотезы причин расхождения
В порядке убывания вероятности:

1. **Sync устарел.** Последний `updated_at` — 2026-04-09; kill-switch включён с 2026-05-04 → если на кассах с тех пор появились/переименовали/удалили виды, мы их не видим. **Самое вероятное.**
2. **Server-only «мусорные» виды с NULL-scope доступны всем.** `Kaspi Рестораны1` (id=36) показывается во всех точках, хотя по логике должен быть только в одной — кассир не видит его на «своей» кассе, а в нашей системе он висит. Аналогично `Бонусы Plazius`, `Мобильный платеж` (хоть и `is_deleted`, но видны если фронт не учитывает флаг).
3. **Эвристика `is_payable` по имени** (`_guess_is_payable`) может ошибаться — какие-то реально кассовые виды отфильтрованы как «служебные» либо наоборот.
4. **Резолв по JurPerson** хрупкий: ловится только подстрока `ИП Шаяхметов/Акжан/Амиржан` в имени. Если на кассе появился банк «ИП Нурлан» — наш бэк положит `organization_iiko_ids=NULL` → видно всем.
5. **Cloud для ФАБРИКИ (org id=1) и аналогичных** ничего не возвращает, поэтому на этой точке в нашей системе всего 2 payable-вида. Если на кассе там реально есть Наличные/Каспи — есть расхождение.
6. **Нет валидации на сервере при создании оплаты** (`orders_services.py:393-404`, `784-802`): фронт может прислать `paymentTypeId`, относящийся к чужой организации, и бэк его примет. При закрытии в iiko это, скорее всего, отвалится со стороны iiko, но локально расходимость уже зафиксирована.
7. **Дубликаты в БД отсутствуют** (по `iiko_id` и `name`) — версия «дубликаты от старых синков» исключена.
8. **Локально через UI ничего не создавали** — POST/PUT эндпоинтов для payment-types нет, версия «создали и не связали» исключена.

## Реализовано (2026-05-21)

### Валидация payment_type ↔ organization при оплате
`services/orders/orders_services.py: change_payments_in_iiko` (около строк 777-840).

Добавлен helper `_pt_belongs_to_org(pt_row)` и его применение в обеих ветках резолва:
- Если `pt.organization_iiko_ids is None` → «всем» (сертификаты, бонусы), пропускаем.
- Иначе требуется, чтобы `org_cloud_id` был в списке.

Поведение:
- При попытке оплатить заказ payment-type'ом, не принадлежащим организации заказа, — соответствующий пункт **выкидывается** из payload в iiko с `logger.warning`. Если в итоге ничего не осталось — `change_payments_in_iiko` вернёт `{}` (как раньше при пустом списке), `close` не вызовется (фикс task 8), а фронт получит понятное сообщение «Оплачено локально; синхронизация с iiko не прошла».
- Для случая, когда фронт шлёт `paymentTypes[].iiko_id` напрямую (минуя нашу БД), мы тоже резолвим запись в БД и проверяем. Если записи в БД нет (т.е. iiko_id, которого мы вообще не знаем) — пропускаем валидацию, отправляем как есть (consistency-fallback).

### Что не сделано (явно отложено)
- **Пересинк payment_types** — не делал, потому что kill switch включён. Пересинкнётся автоматически на финальной стадии тестов, когда снимем флаг.
- **«Мусорные» виды с NULL-scope** (`Kaspi Рестораны1` id=36 и т.п.) — не правил автоматически. После пересинка стоит глазами просмотреть `SELECT id, name FROM payment_types WHERE source='server' AND organization_iiko_ids IS NULL` и явно проставить организацию (например, ALTER на `is_payable=false` или ручной UPDATE `organization_iiko_ids`).
- **Эвристика `_guess_is_payable` и `_extract_jur_person_hint`** — не менял, требует бизнес-уточнения маппинга юрлиц.
- **Удалённые виды с `is_payable=true`** (4 записи) — фильтр `is_deleted` их не пускает, но в БД они есть. Можно дополнительно проставить `is_payable=false` ручной миграцией, но не критично.
- **Cloud для ФАБРИКИ (id=1)** возвращает мало — это особенность iiko, не баг в нашем коде.
