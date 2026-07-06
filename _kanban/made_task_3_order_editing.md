# Task 3 — Доработать редактирование заказа

**Статус:** todo (на исследовании)
**Заведено:** 2026-05-21

## От менеджера
> Доработать редактирование заказа

## Уточнение от @baa21v
> У нас там был момент, что иико не дает редактировать заказ, только дополнять. И надо это учесть правильно и правильно настроить все.

## Контекст
- Связано с task 8 (полный цикл официанта).
- iiko ограничение: после отправки заказа можно только **добавлять** позиции, нельзя редактировать существующие. Это надо корректно отразить на бэке и в API для фронта.

## Что выяснить в исследовании
1. Какие сейчас эндпоинты по работе с заказом в `routers/orders/` — что они умеют (создать, изменить, добавить позицию, удалить позицию, отправить в iiko, отменить)?
2. Какие методы iiko API используются (`addOrderItems`, `closeOrder`, etc.) и что они на самом деле позволяют — добавить позицию, или редактирование тоже?
3. Различает ли наш бэк состояние заказа: «черновик у нас», «отправлен в iiko (только дополнение)»?
4. Что происходит, если фронт пытается изменить позицию уже отправленного заказа — 200/ошибка/тихий пропуск?
5. Какая логика модификаторов, скидок, разделения чеков?
6. Какие пробелы в покрытии — где фронт ждёт фичу, которой нет?

## Файлы
- `routers/orders/`
- `services/orders/`
- `models/orders.py` (или несколько)
- `services/iiko/iiko_service.py` — методы заказов (`createOrder`, `addOrderItems`, `closeOrder` и т.п.)

## Findings

Все эндпоинты заказов лежат в одном файле `routers/orders/order.py`, бизнес-логика — в `services/orders/orders_services.py`. В `iiko_service.py` ничего специфичного по заказам нет, кроме `get_cloud_orders_by_table`; все POST'ы в iiko Cloud делаются прямо из `orders_services.py` через `iiko_service._make_request(...)`.

### 1. Эндпоинты

| Метод + путь | Что делает | Сервис | file:line |
|---|---|---|---|
| `GET /orders` | Список заказов с фильтрами (organization_id, user_id, state, date/date_from/date_to, limit/offset). Кэш 300с | `get_all_orders` (services/orders/orders_services.py:35) | routers/orders/order.py:34-69 |
| `POST /orders` | Создаёт заказ в нашей БД (state=`CREATED`), и если `IIKO_SEND_ORDERS` true — асинхронно дёргает `POST /api/1/order/create` в iiko Cloud, сохраняет `iiko_id` + correlationId/number/fullSum в `external_data.iiko_create_order` | `create_order_from_app` + `create_order_in_iiko` (orders_services.py:297, :478) | routers/orders/order.py:72-218 |
| `POST /orders/{order_id}/pay` | Меняет статус на `PAID`, добавляет запись в `external_data.payments`/`logs`. Если есть `iiko_id`: двухэтапно вызывает `POST /api/1/order/change_payments` → `POST /api/1/order/close`. Запускает `update_quest_progress_for_order` | `pay_order` + `change_payments_in_iiko` + `close_order_in_iiko` (orders_services.py:980, :740, :617) | routers/orders/order.py:221-287 |
| `PUT /orders/{order_id}` | Редактирует локальный заказ (organizationId/tableId/waiterId/guests/items/comment). Полностью заменяет items, пересоздаёт `t_orders`. **Если есть `iiko_id` — diff'ит старые/новые items по `productIikoId` и дёргает только `POST /api/1/order/add_items`** для НОВЫХ позиций. Удаления/изменения количества/смены стола в iiko не уходят | `update_order` + `add_items_to_iiko_order` (orders_services.py:1059, :868) | routers/orders/order.py:290-412 |
| `POST /orders/{order_id}/cancel` | Меняет статус на `CANCELLED`, сохраняет reason в `external_data.cancel_reason`. Если есть `iiko_id` — вызывает `POST /api/1/order/cancel` с `removalTypeId` (или `IIKO_DEFAULT_REMOVAL_TYPE_ID` из конфига) | `cancel_order` + `cancel_order_in_iiko` (orders_services.py:1197, :668) | routers/orders/order.py:415-486 |

Регистрация роутера — `main.py:148` (тег "orders"). Других эндпоинтов по заказам нет (нет отдельных `/items/add`, `/items/remove`, `/split-cheque`).

### 2. iiko-методы

В `services/iiko/iiko_service.py` есть только один метод по заказам:
- `get_cloud_orders_by_table(organization_id, table_id)` → `POST /api/1/order/by_table` (iiko_service.py:657-666). Используется отдельно (table service), к редактированию заказа не относится.

Точных функций `createOrder`, `addOrderItems`, `closeOrder`, `payOrder` в `iiko_service.py` нет. Все эти вызовы хардкодом сидят в `services/orders/orders_services.py` через `iiko_service._make_request(api_type=IikoApiType.CLOUD, endpoint=..., method="POST", data=...)`:

| iiko endpoint | Обёртка в нашем коде | Что делает по докам |
|---|---|---|
| `POST /api/1/order/create` | `create_order_in_iiko` (orders_services.py:478) | Создаёт зальный заказ в iiko Cloud |
| `POST /api/1/order/add_items` | `add_items_to_iiko_order` (orders_services.py:868). В docstring явно: *"iiko Cloud API не поддерживает удаление/изменение позиций — только добавление"* (orders_services.py:880-881) | **Append-only**: добавляет позиции в существующий заказ. Удалить/изменить через этот метод нельзя |
| `POST /api/1/order/change_payments` | `change_payments_in_iiko` (orders_services.py:740) | Устанавливает оплаты на открытом заказе. Docstring подчёркивает, что вызывать его надо ДО `close`, иначе iiko закроет заказ "без оплат" и в iikoFront он будет "не пробит" (orders_services.py:749-751) |
| `POST /api/1/order/close` | `close_order_in_iiko` (orders_services.py:617). Docstring: *"По официальной спеке (CloseTableOrderRequest) есть только три поля: organizationId, orderId, chequeAdditionalInfo. Никаких paymentItems тут не существует"* (orders_services.py:635-638) | Фискально закрывает уже оплаченный заказ |
| `POST /api/1/order/cancel` | `cancel_order_in_iiko` (orders_services.py:668) | Отменяет заказ. Нужен `removalTypeId` (uuid типа списания) |

Методов "редактирования" существующего заказа (изменить количество, удалить позицию, поменять стол/гостей/официанта) в Cloud API нет — это явно отражено в docstring `add_items_to_iiko_order` и в комментарии в роутере (`routers/orders/order.py:372-375`).

### 3. Состояние заказа

`models/d_order.py`:
- `iiko_id` (String(50), nullable) — есть, заполняется только после успешного `POST /api/1/order/create` (orders_services.py:580-585).
- `state_order` (String(255), nullable) — текстовое поле статуса. Используемые значения: `"CREATED"`, `"PAID"`, `"CANCELLED"` (плюс читается `"CANCELED"` через or-условие в `update_order`). Ни enum'а, ни check-constraint'а нет.
- `deleted` (Boolean) — soft-delete.
- `external_data` (JSON) — туда складываются логи (`logs[]`), payments, cancel_reason, и метаданные iiko-вызовов: `iiko_create_order`, `iiko_add_items`, `iiko_change_payments`, `iiko_close_order`, `iiko_cancel_order`.

**Явного флага "отправлен в iiko" нет.** Прокси на это — `order.iiko_id is not None`: везде в сервисе проверки идут именно так (`if order.iiko_id is None: return {}`). Состояние "локальный черновик до отправки в iiko" фактически отсутствует — заказ либо сразу же при `POST /orders` уходит в iiko (если включён `IIKO_SEND_ORDERS`), либо вообще туда не уходит. Промежуточного "создан локально, ждёт отправки" нет.

### 4. Поведение при edit отправленного

`update_order` (orders_services.py:1059-1194) допускает редактирование при любом `state_order`, кроме `PAID`/`CANCELLED`/`CANCELED` (orders_services.py:1075-1076 — иначе `ValueError` → 400). Т.е. заказ со статусом `CREATED`, но уже отправленный в iiko (с `iiko_id`), редактируется свободно.

Что реально происходит при PUT /orders/{id} на уже отправленном заказе:
1. В нашей БД items **полностью заменяются** новым набором (orders_services.py:1108-1151), `t_orders` пересоздаются, sum пересчитывается, поля organizationId/tableId/guests/comment/waiterId обновляются (orders_services.py:1088-1168).
2. В iiko (роутер, order.py:377-397) делается diff по `productIikoId`: всё, чего не было в `old_items`, считается "новой позицией" и отправляется через `add_items`. Всё остальное (удалённые позиции, изменения amount/price, смена стола/гостей/комментария/официанта) **молча игнорируется** — в iiko ничего не уходит, в логе только info-сообщение "новых позиций для iiko не найдено".

Итог: мы создаём расхождение между нашей БД и iiko. Юзер думает, что отредактировал заказ (200 OK, в нашем GET /orders новый стейт), но в iikoFront стол/гости/количество остались старые, удалённые позиции остались, а новые добавились. Это и есть та проблема, которую упомянул @baa21v.

Никакого 4xx/5xx или предупреждения фронту не возвращается.

Доп. нюанс: diff по `productIikoId` корректно отлавливает только новые товары. Если в обновлённом списке тот же товар, но с другим amount (например, было 1, стало 3) — это не считается "новой позицией", и в iiko 2 дополнительные единицы не уйдут.

### 5. Модификаторы, скидки, разделение чеков

- **Модификаторы**: в `CreateOrderItemRequest`/`UpdateOrderItemRequest` (schemas/orders.py:40-55) полей под модификаторы нет (только productId/amount/price/sum/comment). При построении iiko payload (orders_services.py:516-524 и :910-918) шлются только `productId/type=Product/amount/price/comment`, поле `modifiers` не передаётся. Поддержки нет.
- **Скидки**: в модели DOrder есть колонка `discount` (Numeric) и `discounts_info` (JSON), а также `cheque_additional_info`, но при создании из приложения они всегда заполняются `None` (orders_services.py:431, 440, 442). В payload в iiko никакие `discounts` не пробрасываются. В API запроса полей под скидку нет. Поддержки нет.
- **Чаевые (tips)**: есть, через `PayOrderRequest.tipAmount` (schemas/orders.py:145) — сохраняется в `order.tips` и `external_data.tip_amount`, но в iiko (`change_payments`/`close`) не пробрасывается.
- **Разделение чеков (split)**: эндпоинтов и схем нет вообще. iiko Cloud не имеет split-эндпоинта в нашем коде; вызовов `/api/1/order/split`/`/api/1/order/move_items` нет.
- **Множественные оплаты**: в payload `change_payments_in_iiko` поддерживается список `paymentTypes`, но сумма делится **поровну** между всеми типами (orders_services.py:818-823, см. TODO ниже). Фронт обычно шлёт одиночный `paymentType: int`.
- **Combos** (combo-меню): поле `combos` в DOrder есть, но всегда `None` при создании. Не поддерживается.

### 6. TODO и заглушки

- orders_services.py:816 — `# TODO: расширить схему PayOrderRequest, чтобы фронт мог явно указывать sum по каждой оплате` (сейчас при нескольких типах оплат сумма делится поровну, что неверно для реального split-pay).
- routers/orders/order.py:151 — это упоминание `TODO.md` в docstring (пример из старого TODO-файла), не баг.
- routers/orders/order.py:372-375 — комментарий-объяснение append-only поведения iiko Cloud. Не TODO, но фактически описывает дыру в фиче редактирования.
- В `cancel_order` нет проверки на `state_order == "CREATED"`: можно "отменить" уже отменённый заказ (повторно поставит `CANCELLED` и снова дёрнет `/cancel` в iiko, что вернёт ошибку, но мы её проглотим в except).
- Нет эндпоинтов: `POST /orders/{id}/items` (добавить позицию) и `DELETE /orders/{id}/items/{item_id}` (удалить позицию) — сейчас всё это через PUT с заменой всего items[].
- В `change_payments_in_iiko` единичные WARN-логи о деленнии суммы поровну, но фронту это не возвращается.
- Текстовое поле `state_order` (String 255) без enum/check-constraint — легко зарасти мусором.

### 7. Гипотеза/план фикса

Структурно нужно явно ввести две вещи: (а) состояние "отправлен в iiko или нет" и (б) ограничение операций после отправки.

1. **State machine для заказа** — заменить free-text `state_order` на enum со значениями:
   - `DRAFT` (создан локально, в iiko ещё не уходил, можно делать что угодно);
   - `SENT` (создан в iiko, есть `iiko_id`, **append-only** — только добавление позиций, смена комментария/гостей/стола только локально с пометкой "не синхронизировано");
   - `PAID`, `CANCELLED` (терминальные).
   Переход `DRAFT → SENT` происходит при успешном `POST /api/1/order/create`.

2. **Разделить эндпоинты вместо одного PUT**:
   - `PUT /orders/{id}` — оставить только для `DRAFT` (полное редактирование).
   - `POST /orders/{id}/items` — добавить позиции (работает и в `DRAFT`, и в `SENT`). В `SENT` дёргает `/api/1/order/add_items`.
   - `DELETE /orders/{id}/items/{t_order_id}` — удалить позицию. Доступно только в `DRAFT`; в `SENT` → 409 Conflict с понятным сообщением, что iiko не позволяет удалять позиции из отправленного заказа.
   - `PATCH /orders/{id}/meta` — стол/гости/комментарий/официант. В `SENT` либо запретить с 409, либо разрешить **только локально** и явно вернуть фронту флаг `iiko_synced=false`.

3. **Проверки в роутере**:
   - В `update_order` перед изменением items проверять `order.iiko_id`: если не None — отказ с 409, а не молчаливый no-op.
   - В `add_items_to_iiko_order` — если ответ iiko с ошибкой, прокидывать её в HTTPException, а не глотать в except. Сейчас `except Exception: return {}` (orders_services.py:948-953) маскирует все ошибки iiko, в т.ч. конфликтные.

4. **Diff позиций** — текущая логика «новой позицией считаем то, чего нет в old_items по productIikoId» (order.py:378-386) пропускает увеличение amount. Либо запретить менять amount после отправки (рекомендуется, т.к. iiko это и не умеет), либо для увеличений (`new.amount > old.amount`) отправлять в iiko delta как новую строку.

5. **Модификаторы/скидки** — отдельные задачи, в рамках фикса редактирования трогать не обязательно, но добавить поле `modifiers: List[...]` в `CreateOrderItemRequest` будет полезно, чтобы потом не ломать API.

6. **Split-pay sum** — устранить TODO в orders_services.py:816, добавив поле `sum` в `PayOrderPaymentType` (или сделать `PayOrderRequest.payments: List[{paymentTypeId, sum}]`), чтобы фронт явно задавал сумму по каждому типу.

7. **Логирование** — при попытке "редактировать отправленный заказ" писать в `external_data.logs` запись с `action=EDIT_BLOCKED` и подробностями, что именно фронт пытался поменять — для дебага.

Главное: сейчас бэк делает вид, что редактирование работает (всегда 200 OK), но синхронизация с iiko частичная (только новые позиции). Нужно либо честно блокировать недопустимые операции с 409, либо явно помечать локальные изменения как "не ушли в iiko" и отдавать это фронту, чтобы он показывал нужный UI.

## Реализовано (2026-05-21)

### `PUT /orders/{order_id}`: фронту теперь видно, что не уехало в iiko
`routers/orders/order.py: update_order_endpoint` (около строк 388-450).

Добавлен diff-анализ старых и новых items + проверка изменений meta-полей. Если у заказа есть `iiko_id` (уже отправлен в iiko Cloud) и фронт что-то меняет, что Cloud-API не поддерживает, мы:
1. Пишем в логи `logger.warning` с конкретным списком («удалены позиции X, Y», «изменено количество», «сменили tableId/waiterId/guests/comment»).
2. Возвращаем `message` с явным предупреждением: «Order updated locally. iiko Cloud не поддерживает редактирование отправленного заказа кроме добавления позиций — часть изменений осталась только у нас: …».

Что детектируется:
- удаление позиции (была в old, нет в new);
- изменение количества существующей позиции (`old.amount != new.amount`);
- смена `tableId` / `waiterId` / `guests` / `comment` на уже отправленном заказе.

Что не меняется:
- добавление новых позиций — по-прежнему уходит в iiko через `add_items` (как было).
- если все изменения «легитимные» (только новые позиции) — `message` остаётся прежним «Order updated successfully».

### Что не сделано (отложено, отдельная итерация дизайна)
- **State machine `DRAFT → SENT → PAID → CANCELLED`** с явным enum-полем — большой redesign. Сейчас `state_order` остаётся free-text String.
- **Разделить `PUT /orders/{id}`** на отдельные `POST /orders/{id}/items` (add), `DELETE /orders/{id}/items/{item_id}` (с 409 для SENT), `PATCH /orders/{id}` (meta) — это новая API-схема, ломает текущий фронт. Только с дизайном.
- **409 Conflict вместо `message`-предупреждения** при попытке удалить позицию у отправленного заказа — пока возвращаем 200 + предупреждение, чтобы не сломать фронт. Когда фронт будет готов парсить новые коды — переключим.
- **Модификаторы, split-pay sum, разделение чеков** — отдельные задачи (см. task 8 «отложено»).
- **Перестать глотать ошибки iiko в external `try/except`** — местами действительно стоит пробрасывать, но это связано с поведением фронта, отложил с другими redesign-пунктами.
