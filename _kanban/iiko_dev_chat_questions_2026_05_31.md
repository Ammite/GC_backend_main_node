# Вопросы для чата с разработчиками iiko

Контекст: интеграция через iiko Cloud API + Server API (legacy). Реальный клиент — сеть ресторанов «Грузин-Кузин». На текущий момент работает мобильное приложение для официантов с локальной БД (PostgreSQL) и синхронизация в обе стороны.

---

## Что мы сейчас используем

### Cloud API (`https://api-ru.iiko.services`)

Auth: `POST /api/1/access_token` (ApiLogin key).

| Endpoint | Где у нас |
|---|---|
| `POST /api/1/organizations` | синк организаций |
| `POST /api/1/terminal_groups` | синк терминалов |
| `POST /api/1/employees` | синк сотрудников |
| `POST /api/1/employees/info` | детали по сотруднику |
| `POST /api/1/payment_types` | синк типов оплат |
| `POST /api/1/nomenclature` | синк меню (всё ещё) |
| `POST /api/1/reserve/available_restaurant_sections` | секции / столы |
| `POST /api/1/order/create` | создание заказа из приложения |
| `POST /api/1/order/add_items` | дозаказ |
| `POST /api/1/order/change_payments` | сейчас единственный путь оплаты |
| `POST /api/1/order/add_payment` | **не используется** — 401 `Right ... is not allowed` |
| `POST /api/1/order/close` | финализация |
| `POST /api/1/order/cancel` | отмена |
| `POST /api/1/order/by_table` | подобрать заказ открытый на кассе iikoFront |
| `POST /api/1/commands/status` | поллинг async команд |

### Server API (`https://gruzin-cuisine-co.iiko.it`)

Auth: `GET /resto/api/auth?login=...&pass=...` → cookie.

| Endpoint | Зачем |
|---|---|
| `POST /resto/api/v2/reports/olap` | **транзакции, продажи, доставки** — все через OLAP |
| `GET /resto/api/v2/reports/olap/presets` | пресеты |
| `GET /resto/api/v2/reports/olap/columns?reportType=...` | поля отчёта |
| `GET /resto/api/v2/entities/products/list` | альтернативный источник меню |
| `GET /resto/api/v2/entities/products/group/list` | группы |
| `GET /resto/api/v2/entities/products/category/list` | категории |
| `GET /resto/api/v2/entities/accounts/list` | счета (банк, касса) |
| `GET /resto/api/v2/reports/balance/stores` | остатки на складах |
| `GET /resto/api/employees` | + `/roles`, `/salary`, `/schedule/types`, `/attendance/types` |
| `POST /resto/api/employees/attendance/create` | clockout |
| `GET /resto/api/corporation/departments` | + `/counteragents`, `/stores/...` |
| `GET /resto/api/suppliers` | поставщики |
| `GET /resto/api/reports/productExpense` | расход продукта (есть, не уверен что лучший путь) |
| `GET /resto/api/reports/storeReportPresets` | пресеты складских отчётов |
| `POST /resto/api/documents/export/incomingInvoice` | + outgoingInvoice |
| `POST /resto/api/documents/import/incomingInvoice` | + outgoing, inventory |

---

## Вопросы

### 1. Транзакции и продажи — есть ли путь лучше OLAP?

Сейчас тянем через `POST /resto/api/v2/reports/olap` с `reportType=TRANSACTIONS` (а также `SALES`, `DELIVERIES`). Сборка идёт **по одному дню за раз** в цикле — оказалось так надёжнее.

**Проблемы которые видим:**
- Тяжело для сервера iiko: OLAP-отчёты считаются «по требованию», на больших периодах ловим таймауты.
- Нет надёжного «инкрементального» режима — приходится перетягивать всю историю или жонглировать датами.
- На сегодняшний день у нас есть пробел в БД 2026-05-04 → 2026-05-23 — частично из-за того что OLAP не давал данные стабильно.

**Что хочется узнать:**
1. Есть ли webhook / push-уведомления о новых транзакциях / продажах? Чтобы не пуллить?
2. Если только pull — какой правильный размер окна (1 день / 1 час)? Какой rate limit?
3. Есть ли «диффовый» эндпоинт типа «дай всё что изменилось после timestamp X»?
4. Поле `closeTime` в OLAP — это момент финализации чека или ещё что-то?
5. **`POST /api/1/deliveries/by_delivery_date_and_status`** (Cloud) — лучше для доставок, чем OLAP?
6. **`POST /api/1/transactions`** или подобный — есть в Cloud? OpenAPI iiko-cloud-api не показывает.

### 2. Типы расходов / выплат — почему доступен только один?

В нашей `pay_out_types` 17 записей. На фронте пользователь видит **только 1 активный** при создании расхода. Складывается ощущение что:
- либо большинство помечены `disabled` для нашей организации,
- либо у конкретной ApiLogin нет прав на остальные,
- либо привязаны к другому JurPerson.

**Вопросы:**
1. От чего зависит «доступность» типа выплаты для конкретной организации/кассы — права роли, привязка к JurPerson, флаг в самом справочнике?
2. Какой endpoint получает **список разрешённых для текущей организации** типов выплат (а не все вообще)?
3. Сейчас тянем через `GET /resto/api/v2/entities/accounts/list` + наш парсер. Это правильное место?
4. **Создание расхода / выплаты через API** — какой endpoint правильный? (`/cashshifts/transactions/income/`?, `/cashshifts/transactions/outcome/`?). У вас в OpenAPI неоднозначно.

### 3. Атрибуция официанта при продаже

Сейчас:
- При `POST /api/1/order/create` шлём поле `waiterId` (uuid сотрудника).
- В итоговых iiko-отчётах (OLAP) видим что чек атрибутирован **не нашему официанту, а «Интегратор»** — техническому пользователю, под которым api-key.

**Вопросы:**
1. Какое именно поле в `order/create` определяет официанта в чеке? `waiterId`? `tableOrderInfo.openOperatorId`?
2. Достаточно ли передать uuid сотрудника, или сотрудник должен иметь **открытую кассовую смену** на момент создания заказа?
3. Если касса (iikoFront) на терминале не «знает» о нашем официанте — должна ли быть какая-то операция вроде «открыть смену для employee X на terminal Y» через API перед `order/create`?
4. Атрибуция waiterId сохраняется в iikoOffice/OLAP, или там всегда «оператор который физически пробил»?
5. Если правильный путь — не `order/create` а `init_by_table` + потом `change_payments` — поясните цепочку.

### 4. `change_payments` vs `add_payment` — какие у них реальные права

Когда вызываем `POST /api/1/order/add_payment`, iiko возвращает:
```
HTTP/1.1 401 Unauthorized
"Right api/1/order/add_payment is not allowed for this ApiLogin."
```
А `change_payments` для того же заказа с тем же токеном — ✅ 200. Пришлось переключить **всю** ветку оплаты на `change_payments` (и для заказов созданных нами через API, и для заказов поднятых с кассы).

**Вопросы:**
1. Это нормально что у дефолтной ApiLogin нет права на `add_payment`? Где включается?
2. В чём принципиальная разница между `add_payment` и `change_payments` если оба принимают массив платежей?
3. Если по доке iiko «для API-заказов рекомендуется `add_payment`» — что мы теряем, идя через `change_payments`?

### 5. `PaymentSumNotEnough` — service charge

Поведение которое поймали:
- Заказ в нашей БД на 150₸ (3×50, голая цена).
- В iiko после `order/create` получает **165₸** — добавляется 10% service charge.
- При `change_payments` посылаем 150₸ → потом `close` → ошибка `Payment of order #N failed. Reason: PaymentSumNotEnough`.
- При `change_payments` 165₸ → ✅.

Пока сделали в обход: умножаем на 1.10 у себя в коде перед оплатой.

**Вопросы:**
1. Как через Cloud API получить **актуальный итог заказа со всеми надбавками** (`GET /api/1/order/by_id` есть? или поле в `commands/status` ответе?).
2. Есть ли отдельный «settle / total» эндпоинт который сам считает сколько нужно?
3. Service charge привязан к организации (можно отключить?) или к типу заказа / тарифу?
4. Если у заказа есть скидка или промо — кому считать: нам через свой движок или иску через эндпоинт?

### 6. `PaymentType.CanBeExternalProcessed` — где смотреть и кто управляет

Когда шлём оплату с `isProcessedExternally: true` на тип «Каспий банк ИП Амиржан» — `commands/status` ошибка:
```
Payment item of type Каспий банк ИП Амиржан ... cannot be added as external processed.
PaymentType should be CanBeExternalProcessed.
```

В нашей БД из 35 активных типов оплат:
- 6 типов имеют `paymentProcessingType = "Both"` (Glovo, WOLT, Yandex, Starter, Наличные, Бонусы) — работают.
- 29 типов имеют `paymentProcessingType = NULL` — не работают (включая Каспий/БЦК/Халык банки ИП).

**Вопросы:**
1. Поле `CanBeExternalProcessed` отдаётся `POST /api/1/payment_types`? Где смотреть? У нас `paymentProcessingType` NULL у большинства банковских типов.
2. Этот флаг включается в iikoOffice (где?) или зашит на стороне платёжного канала?
3. Если ИП-эквайринг (Каспий/БЦК/Халык) **физически** обрабатывается в кассе — как из приложения сказать «приём оплаты подтверждён, проводи»?
4. Может быть нужен другой флаг в payload (`isProcessedExternally: false` для них?) или отдельный endpoint?

### 7. iiko Cloud дедуплицирует `close` или нет?

Заметили: первый `order/close` с ошибкой `PaymentSumNotEnough` фиксирует `correlationId=X`. Повторный `close` через 1-3 минуты на тот же `orderId` иногда **возвращает тот же `X`** с тем же кэшированным результатом, иногда — новый. Из-за этого retry после починки оплаты «не пробивается».

**Вопросы:**
1. Есть ли кэширование/идемпотентность `order/close` по `orderId`?
2. Если первая попытка close зафиксировала Failed state — как «снять» это состояние и попробовать снова, без отмены заказа?
3. Что значит `Payment of order #N (UUID) failed` в ошибке — это session UUID не самого заказа? Что это за идентификатор?

### 8. `init_by_table` и open-on-cashier сценарий

Пытались дёрнуть `POST /api/1/order/init_by_table` для подбора заказа открытого на iikoFront — получаем `HTTP/1.1 500`.

**Вопросы:**
1. Эндпоинт ещё поддерживается, или deprecated?
2. Какой правильный путь сейчас: открыть стол на iikoFront → подхватить в нашем приложении → продолжить оформление → оплатить? `order/by_table` достаточно или нужно ещё что-то?
3. Какие обязательные поля в `init_by_table` чтобы он не 500-ил?

### 9. External Menu / стоп-листы

Сейчас тянем меню через `POST /api/1/nomenclature` (Cloud) + `GET /resto/api/v2/entities/products/list` (Server). Тащим раз в N часов через cron.

**Вопросы:**
1. Есть ли `POST /api/2/menu` (External Menu) для прайс-листов **в реал-тайме с учётом стоп-листа конкретного терминала**?
2. Webhook / push при изменении стоп-листа?
3. Если в iikoFront товар на стопе, а наше приложение его покажет и пробьёт в `order/create` — какой будет ответ? Можно ли заранее проверить доступность?

### 10. Документы — `incomingInvoice` / `writeoff` / `inventory`

Тянем выгрузку через `POST /resto/api/documents/export/{incomingInvoice|outgoingInvoice}`. Создавать пытаемся через `POST /resto/api/documents/import/{incomingInvoice|outgoingInvoice|incomingInventory}`.

**Вопросы:**
1. Эндпоинты `/documents/import/*` всё ещё актуальны? Какие обязательные поля? Идемпотентность по `externalId`?
2. Хочется единый формат «акт списания» — `POST /resto/api/documents/import/writeoff` существует? У нас сейчас нет.
3. Поле `storeId` — это uuid склада в `/corporation/stores`?

### 11. clockout / attendance

`POST /resto/api/employees/attendance/create` вернул 400:
```
java.lang.IllegalArgumentException:
  Argument for @NotNull parameter 'uuid' of resto/api/v1/helper/EntityResolverHelper.resolveCachedEntity must not be null
```

**Вопросы:**
1. Какие именно UUID обязательны в payload `attendance/create`? У нас вероятно отсутствовал `attendanceTypeId` или `scheduleTypeId` — какие конкретно поля?
2. Есть ли пример XML/JSON корректного запроса?
3. Эндпоинт принимает JSON или только XML?

### 12. Сводный «health» / лимиты

1. Какие rate limits на Cloud API per ApiLogin? И на Server API?
2. Когда возвращается 429 — есть ли `Retry-After`?
3. Какой максимум параллельных запросов от одной интеграции?

---

## Дополнительный материал, который полезно приложить

- Версии iiko ставшие официально supported для нашей интеграции (мы видели 8.x в логах кассы).
- Список UUID организаций нашего клиента (есть в `/api/1/organizations`).
- ApiLogin id (открытая часть, без секрета).
