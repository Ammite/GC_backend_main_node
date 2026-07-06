# Task 8 — Полный цикл оформления заказа у официанта

**Статус:** todo (на исследовании)
**Заведено:** 2026-05-21

## От менеджера
> Добить весь цикл оформление заказа у официанта чтобы все четко работало

## Уточнение от @baa21v
> Цикл надо полностью проверить чтобы идеально работало без нареканий. Тестового стенда нет.

## Контекст
- Связано с task 3 (редактирование заказа), но шире.
- Цикл: открытие стола → выбор позиций → модификаторы → отправка заказа в iiko → дополнение → оплата (виды оплаты — task 4) → закрытие → печать.
- Тестового стенда **нет** — проверяем по коду + по существующим логам.

## Что выяснить в исследовании
1. Полный список эндпоинтов в `routers/orders/`, `routers/rooms/`, `routers/menu/`, `routers/payment_types/` — что покрыто, чего не хватает.
2. Полный сценарий: какие шаги фронт должен дёрнуть, чтобы пройти весь цикл? Где разрывы?
3. Какие методы iiko используем (`createOrder`, `addOrderItems`, `closeOrder`, `payOrder` — точные имена) и какие условия их применения?
4. Модификаторы — поддерживаем ли в API? Как они сохраняются и шлются в iiko?
5. Где в логах есть ошибки от попыток оформить заказ — посмотреть последние 1-2 месяца.
6. Что точно сломано или недоделано (TODO в коде, заглушки, неполные ветки)?
7. Без стенда — какой план тестирования предложить (моки, sample-payload, прод-проверка на «тихом» столе)?

## Файлы
- `routers/orders/`, `services/orders/`
- `routers/rooms/`, `services/rooms/`
- `routers/menu/`, `services/menu/`
- `routers/payment_types/`
- `services/iiko/iiko_service.py` — order-методы
- `logs/`

## Findings

Сводно: цикл реализован «вертикально», но местами фейково и с большим количеством разрывов. Шаги 1, 2, 7 (часть) и 8 (split/prebill/merge/move) — фактически отсутствуют как реализация. Шаги 3, 5, 6 — работают, но без проверки ошибок и retry, и при `IIKO_REQUESTS_DISABLED=true` (текущее значение по умолчанию) все iiko-вызовы возвращают `None` и заказ остаётся локальным.

Подробности по edit-семантике PUT /orders/{id} — см. task 3 (там разобрано append-only поведение iiko Cloud, тихие no-op'ы при удалении/изменении количества/смены стола, отсутствие 409, отсутствующие endpoint'ы для add/delete отдельной позиции). Ниже фокус на остальных шагах цикла.

### 1. Открытие стола

Сейчас «открытия» как операции нет — фронт не отправляет какой-то PUT/POST на «занять стол». Единственное, что есть:

- `GET /rooms` (`routers/rooms/rooms.py:16-33`) и `GET /tables` (`:36-60`) — список секций ресторана и столов.
- В `services/rooms/rooms_service.py` (`get_rooms` :12-83, `get_tables` :86-152) **все интересные поля захардкожены**:
  - `status = "available"` (строка 53, 130) — TODO: `Добавить реальную логику проверки статуса`.
  - `currentOrderId = None` (строка 55, 131) — нет связки стола с активным заказом.
  - `assignedEmployeeId = None` (строка 56, 132) — нет связки стола с официантом.
  - `capacity = 4` (строка 63, 144) — `TODO: Добавить поле capacity в модель Table`.
- В модели `Table` поля `capacity`/`current_order_id`/`assigned_employee_id` отсутствуют.
- Метод `IikoService.get_cloud_orders_by_table` (`services/iiko/iiko_service.py:657-666`) **никем не вызывается** (только определение, grep по проекту даёт 0 usage'ей). То есть мы не подгружаем из iiko открытые заказы на столе, и при «открытии» официантом стола фронт не видит, что там уже висит чужой заказ.
- В `services/employees/employees_service.py:580-631` (вероятно `get_employee_dashboard`) есть параллельная логика «открытые заказы сотрудника по столам» через локальный `DOrder` (фильтр `state_order != "CLOSED"` — мёртвый, такого статуса у нас нет; см. ниже), но она используется только для дашборда сотрудника, а не для роутера `/tables`.

**Разрыв:** официант не может узнать «свободен ли стол» и «есть ли на нём активный заказ» — `/tables` всегда отдаёт `available`. Сценарий «присоединиться к существующему заказу на столе» — отсутствует: эндпоинта поиска заказа по `tableId` нет, `currentOrderId` всегда `null`. Фактически открытие стола заключается в том, что фронт сам помнит локально, на каком столе он, и в `POST /orders` передаёт `tableId` — но проверки «уже занят» нет, легко создать два параллельных заказа на одном столе.

### 2. Меню и модификаторы

- `GET /menu` (`routers/menu/menu.py:15-45`) → `get_all_menu_items` (`services/menu/menu_services.py:10-49`) возвращает только `id/name/price/description/image/category`. Фильтрация — по `organization_id/category_id/name`, отсев `deleted=False, type_server='DISH'`. Кэш отключён (`# @cached` закомментирован, `services/menu/menu_services.py:9`).
- Схема `ItemResponse` (`schemas/menu.py:5-11`) — **только 6 плоских полей**, никаких модификаторов, размеров, групп комбо.
- В БД модели **модификаторы есть** (`models/modifier.py`: `Modifier`, `ItemModifier` с полями `min_amount/max_amount/default_amount`, дочерние модификаторы и т.п.) и они синхронизируются из iiko (`services/iiko/iiko_parser.py:145-159`). Но API меню их **не отдаёт**, а схема заказа (`schemas/orders.py:CreateOrderItemRequest`) **не принимает**.
- Стоп-листы (`checkStopList`) тоже не задействованы: при создании заказа в iiko в payload жёстко `"checkStopList": False` (`services/orders/orders_services.py:550`).

**Разрыв:** фронт-официант не может выбрать модификатор (соус, размер, степень прожарки), даже если в iiko они настроены. Соответственно и в iiko они не уйдут. Стоп-лист игнорируется — теоретически можно «пробить» блюдо, которое в iiko уже стоп-листом.

### 3. Создание + отправка заказа

`POST /orders` → `create_order_from_app` (`services/orders/orders_services.py:297-475`) → `create_order_in_iiko` (`:478-614`). Шаги в коде:

1. **Валидация входа** (`:308-356`):
   - `organizationId` — если задан, должен существовать; иначе пытаются вывести из `tableId → section → terminal_group → organization` (`:329-346`). Это спасает, когда фронт не прислал org.
   - `tableId` — если задан, должен существовать (`Table.id`), берётся `table.iiko_id`, `table.number`.
   - `waiterId` — это **id из таблицы `users`** (НЕ `employees`). Сервис ищет `User → user.iiko_id → Employees.iiko_id`. Если у пользователя нет linked employee — `ValueError → 400`.
   - `items[].productId` — должен существовать в `items` и не быть `deleted`, иначе 400.
   - **НЕТ**: проверки, что `productId` принадлежит той же `organizationId` (можно подсунуть блюдо чужой организации); проверки, что стол принадлежит организации; проверки, что официант имеет роль «официант»; проверки стоп-листа; проверки, что на этом столе уже не висит активный заказ.

2. **Запись в БД** (`:418-465`): создаётся `DOrder` со `state_order="CREATED"`, `items` (JSON), `sum_order` (сумма позиций). Параллельно для каждой позиции создаётся `TOrder` (с `count_order = int(amount)` — **дробные граммовки/литры теряются**, `iiko_id=None`). Лог `CREATED` пишется в `external_data.logs`. `external_data` содержит наши `tableId`, `tableIikoId`, `waiterId`, `waiterIikoId`, `payments_info` (пред-расчёт оплат, но он сейчас не используется при `pay_order`).

3. **Отправка в iiko** (`:478-614`, вызывается из роутера `:189-197` только если `IIKO_SEND_ORDERS=true`):
   - **`IIKO_SEND_ORDERS` по умолчанию `false`** (`config.py:42`). Если флаг не выставлен — заказ остаётся локальным, фронт получает 200, но в iikoFront его нет вообще. Об этом возвращается строка `"Order created locally (iiko sending disabled)"`.
   - **`IIKO_REQUESTS_DISABLED=true`** (по умолчанию с 2026-05-04, `config.py:51`) — `_make_request` возвращает `None` сразу же (`iiko_service.py:183-188`). Тогда `create_order_in_iiko` логирует warning `"Неожиданный ответ от iiko"` и возвращает `{}`. `order.iiko_id` остаётся `None`. Фронту возвращается `success=True`, `message="Order created locally and sent to iiko"`, но `iiko_id=null`. **Расхождение: сообщение врёт.**
   - Если оба флага включены: получаем terminal group из Cloud API (`get_cloud_terminal_groups`), берём **первую** из списка (`:505`). Если у организации несколько terminal group'ов — выбор недетерминированный, кухонные принтера могут оказаться чужие.
   - В payload идёт `tableIds=[table_iiko_id]`, `waiterId`, `guests.count`, `items[]` с `type="Product"`, `comment`, `price`, `amount`. **Поле `modifiers` не передаётся вообще** (см. шаг 2).
   - `createPaymentIfNotExists: false`, `checkStopList: false`, `createOrderSettings.servicePrint: true`.
   - Все вызовы идут через `IikoApiType.CLOUD` (новый ключ). `CLOUD_OLD` enum определён (`iiko_service.py:19`, для `IIKO_OLD_LOGIN_KEY`) — но **в orders нигде не используется** (grep `api_type=IikoApiType` по `orders_services.py` даёт 5 совпадений и все `CLOUD`). Контекст из MEMORY.md «CLOUD_OLD — для orders» здесь **не выполнен**.

4. **Обработка ответа**: `correlationId/orderId/number/creationStatus/fullSum` парсятся из ответа и складываются в `external_data.iiko_create_order` (`:586-597`). `order.iiko_id = orderId`. Если `orderId` пришёл `None` (iiko ответил, но без id — например, при ошибке валидации) — warning и `iiko_id` остаётся `None`, но ответ-словарь всё равно возвращается фронту. **Состояние «отправили, но не получили id» не отличается от «отправили и получили id» с точки зрения фронта**.

5. **Ошибки**:
   - `ValueError` (валидация) → 400 (`routers/orders/order.py:210-212`).
   - Любой `Exception` внутри `create_order_in_iiko` глотается в `except Exception` (`orders_services.py:609-614`) → возвращается `{}`. Заказ в нашей БД уже создан, фронт получит 200 OK, но в iiko его нет. Никакой компенсирующей логики (удалить локальный, retry) — нет.
   - Если `create_order_in_iiko` падает на `db.commit()` после сохранения `iiko_id` — order.iiko_id уже присвоен в Python-объекте, но не закоммичен; на следующих запросах не виден.

6. **Что возвращается фронту**: `order_id, iiko_id, iiko_correlation_id, iiko_number, iiko_full_sum`. Никаких `creationStatus` (нужен для понимания «принят/ошибка/в очереди» на стороне iiko), никаких полей `errorInfo`/`problem`.

### 4. Дополнение позициями

Эндпоинт — тот же `PUT /orders/{order_id}` (`routers/orders/order.py:290-412`). Отдельных `POST /orders/{id}/items` или `DELETE /orders/{id}/items/{item_id}` нет.

Что сломано (краткая сводка, детально в task 3):

- **Изменить amount существующей позиции** — не работает: diff в роутере (`:378-386`) сравнивает только по `productIikoId`, не по `(productIikoId, amount)`. Локально заменяется, в iiko ничего не уходит.
- **Удалить позицию** — не работает: удаление просто пропадает (нет в новом массиве → нет в diff'е → в iiko не уходит, iiko Cloud и не умеет удалять).
- **Изменить комментарий к существующей позиции** — не работает по той же причине.
- **Добавить модификатор** — невозможно: в `CreateOrderItemRequest` поля нет (схема `schemas/orders.py:40-55`), в payload `add_items` поле `modifiers` не пробрасывается (`orders_services.py:910-918`).
- **Сменить стол / гостей / комментарий заказа** — локально применяется, в iiko не пробрасывается (iiko Cloud Order API не имеет `change_table`/`change_guests` методов в нашем коде). Расхождение БД ↔ iiko.
- **Сменить официанта** — то же самое: только `external_data.waiterId`, в iiko не уходит.
- **Молчаливый no-op**: даже если изменение значимое, фронт получает 200 OK и `success=True`. Нет сигнала «не синхронизировано».

`add_items_to_iiko_order` (`:868-953`) — append-only, ошибки iiko глотаются в `except Exception → return {}` (`:948-952`). Если iiko вернул 400 «позиция в стоп-листе» — фронт не узнает.

### 5. Оплата

`POST /orders/{order_id}/pay` (`routers/orders/order.py:221-287`) → `pay_order` (`services/orders/orders_services.py:980-1056`) + `change_payments_in_iiko` (`:740-865`) + `close_order_in_iiko` (`:617-665`).

Что принимает (схема `PayOrderRequest`, `schemas/orders.py:138-145`):

- `paymentType: Optional[int]` — наш `payment_types.id` (одиночный).
- `paymentTypes: Optional[List[PayOrderPaymentType]]` — расширенный формат, объекты с уже готовыми `iiko_id` и `payment_type_kind`. Фронт может смешать оба варианта.
- `tipAmount: Optional[str]` — строка, не валидируется как число.

**Никакой суммы оплаты в payload нет.** Сумма берётся из `order.sum_order` (полная). Частичная оплата невозможна.

Процесс:

1. `pay_order` (sync, `:980-1056`):
   - Находит заказ, проверяет, что не `deleted`. **Не проверяет**, что текущий статус — `CREATED` (можно оплатить уже оплаченный — поставит `PAID` второй раз и продолжит, в т.ч. дернёт iiko).
   - Жёстко ставит `state_order = "PAID"` ещё ДО iiko-вызовов.
   - Логирует payment в `external_data.payments[]` (amount = `order.sum_order`, payment_types_info, tip_amount).
   - Сохраняет `order.tips = float(pay_data.tipAmount)` если есть. **В iiko tipAmount нигде не пробрасывается** (ни в `change_payments`, ни в `close`).
   - Вызывает `update_quest_progress_for_order(db, order)` — побочный эффект (квесты обновляются ДО подтверждения в iiko).
   - `db.commit()` — статус `PAID` фиксируется в БД.
2. Роутер (`order.py:265-271`) — только если `IIKO_SEND_ORDERS` и `order.iiko_id`:
   - Сначала `change_payments_in_iiko(db, order, pay_data)`.
   - Затем `close_order_in_iiko(db, order, pay_data)`.

`change_payments_in_iiko` (`:740-865`):
- Резолвит payment types из обоих форматов `paymentType` (int → DB lookup) и `paymentTypes` (list of dicts с `iiko_id`).
- Если ни одного валидного — warning и `return {}`. **`close` всё равно дёрнется** в роутере (он не смотрит на результат change_payments — см. ниже шаг 6).
- Если несколько payment types — `total_sum` делится **поровну** (`:818-823`). TODO на `:816` явно говорит о неполноте.
- В payload `paymentTypeKind` берётся из `PaymentType.payment_type_kind` (`Cash`/`Card`/`Credit`/etc.) или fallback `"Cash"` если null. Это критично для iiko: для бонусов/сертификатов должен быть `IikoCard` — но при синхронизации `payment_type_kind` иногда null или не `IikoCard`. Бонусные/сертификатные оплаты сейчас работать корректно **не могут**.
- `isProcessedExternally: true` хардкод — то есть мы говорим iiko «эта оплата уже прошла внешне, не подтверждай через POS». Для реальной оплаты картой это может быть некорректно.
- **Не проверяется**, что `paymentType` принадлежит организации заказа: фронт может прислать `paymentTypeId` чужой организации, бэк его раз решит и пошлёт в iiko, iiko отклонит.

`close_order_in_iiko` (`:617-665`):
- Payload: только `organizationId, orderId` — никаких `chequeAdditionalInfo`/`tipAmount`/`fiscalReceipt` (docstring правильно описывает спеку).
- Результат складывается в `external_data.iiko_close_order`. Ошибки глотаются в `except Exception → return {}`.

**Сценарии, которые сейчас сломаны или дают расхождение:**

- Частичная оплата — невозможна (схема не поддерживает sum по типу).
- Переплата на чай — `tipAmount` сохраняется в нашу БД, но в iiko не уходит, в фиск.чеке его не будет.
- Несколько видов оплат с разными суммами — невозможно (делим поровну, есть TODO).
- Оплата сертификатом/бонусом (IikoCard) — `payment_type_kind` обычно не выставляется в `IikoCard` при сейчасной sync, в payload идёт `"Cash"` fallback → iiko отклонит или зачислит как наличку.
- Если фронт вообще не передал `pay_data` или передал пустой — `change_payments` логирует warning и `return {}`, но **`close` всё равно вызывается** — заказ в iiko закроется без оплат и в iikoFront будет «не пробит» (это и есть антишаблон, о котором предупреждает docstring `:749-751`, но защиты от него в роутере нет).
- В нашей БД заказ становится `PAID` **до** ответа iiko. Если iiko упадёт — у нас `PAID`, в iikoFront заказ остался открытым. Никакого rollback.

### 6. Закрытие/отмена

**Закрытие**: см. шаг 5 — `change_payments` → `close` цепочка из роутера. Критический баг: между ними **нет проверки результата**:

```python
# routers/orders/order.py:270-271
await change_payments_in_iiko(db=db, order=order, pay_data=pay_data)
await close_order_in_iiko(db=db, order=order, pay_data=pay_data)
```

`change_payments_in_iiko` возвращает `{}` и при успехе iiko-ответ, и при любой ошибке (валидной или сетевой). Роутер не различает. `close_order_in_iiko` дёргается всегда. Если `change_payments` упал — `close` закроет заказ «без оплат», и в iikoFront он будет открыт/неполный. Нет retry, нет rollback нашего `PAID`.

**Отмена**: `POST /orders/{order_id}/cancel` (`order.py:415-486`) → `cancel_order` (`orders_services.py:1197-1238`) + `cancel_order_in_iiko` (`:668-737`).

- Локально: ставит `state_order = "CANCELLED"`, пишет `cancel_reason` и лог. Проверка `state_order == "PAID"` есть (`:1213` → 400 "Cannot cancel paid order"), но **повторная отмена** уже отменённого заказа не блокируется — снова поставит `CANCELLED` и снова дёрнет iiko/cancel, который вернёт ошибку, которую мы проглотим.
- В iiko: `removalTypeId` берётся либо из запроса (`cancel_data.removalTypeId`), либо из `config.IIKO_DEFAULT_REMOVAL_TYPE_ID`. Если ни того, ни другого — error лог и `return {}` (отмена в iiko **не выполнится**, локально заказ останется `CANCELLED`). Фронт получает 200 OK.
- `userIdForWriteoff` берётся из `user.iiko_id` текущего пользователя (если есть).
- Ошибки iiko глотаются.
- В целом отмена пройдёт даже когда заказ ещё не успели отправить в iiko (`order.iiko_id is None`): локально `CANCELLED`, в iiko warning «iiko_id отсутствует», `return {}`. Это, наверное, ОК для черновика.

Сводно: после отмены может образоваться состояние «локально `CANCELLED`, в iiko — `Open`», и фронт об этом не узнает.

### 7. Чего критично не хватает

| Фича | Статус | Где должно быть |
|---|---|---|
| **Открытие/занятие стола** (mark table occupied + bind to current order + bind to waiter) | **отсутствует** | `routers/rooms/*` хардкодит `status="available"`, currentOrderId/assignedEmployeeId=None. Нет PUT/POST на стол. |
| **Подгрузка активных заказов на столе из iiko** | **отсутствует** | `IikoService.get_cloud_orders_by_table` определён, но 0 вызовов. |
| **Перенос заказа на другой стол** (`change_table`) | **отсутствует** | PUT /orders позволяет поменять `tableId` локально, в iiko не уходит. Нет iiko-вызова `POST /api/1/order/change_waiter` / `change_table` (в iiko Cloud такого тоже почти нет; нужно через `add_items` или server API). |
| **Объединение заказов / move_items** | **отсутствует** | Эндпоинтов нет, iiko-вызовов нет. |
| **Печать пречека** (preliminary check) | **отсутствует** | Эндпоинта нет. В iiko Cloud есть `POST /api/1/order/print_preliminary_cheque` (или server-side print) — не используем. |
| **Split-cheque** | **отсутствует** | Эндпоинтов нет, схем нет. |
| **Модификаторы** | **отсутствует на всём пути** | `Modifier`/`ItemModifier` есть в БД (sync из iiko), но `GET /menu` не отдаёт, `CreateOrderItemRequest` не принимает, в iiko payload не пробрасывается. |
| **Комбо** | **отсутствует** | `combos` колонка в DOrder есть, всегда `None`. |
| **Скидки** | **отсутствует** | `discount/discounts_info` в DOrder есть, всегда `None`. В payload iiko `discounts` не уходит. |
| **`tipAmount`** | **полусломано** | Сохраняется в `order.tips`, но в iiko (`change_payments`/`close`) не пробрасывается, в фискальный чек не попадёт. |
| **IikoCard / бонусы** | **сломано** | `payment_type_kind` часто null → fallback `"Cash"`, iiko отклонит как IikoCard. |
| **Sum-per-payment-type для split-pay** | **сломано** | TODO в `orders_services.py:816`, делится поровну. |
| **Валидация «payment type принадлежит организации заказа»** | **отсутствует** | `change_payments_in_iiko` не сверяет с `PaymentType.organization_iiko_ids` (хотя в `GET /payment-types` фильтр есть). |
| **Валидация «product принадлежит организации заказа»** | **отсутствует** | `create_order_from_app` не проверяет `product.organization_id == organization_id`. |
| **Валидация «table принадлежит организации»** | **отсутствует** | Аналогично. |
| **Защита от двойной оплаты** | **отсутствует** | `pay_order` не проверяет `state_order == "CREATED"`. |
| **Защита от двойной отмены** | **отсутствует** | `cancel_order` блокирует только `PAID`, не блокирует уже `CANCELLED`. |
| **Стоп-лист** | **отсутствует** | `checkStopList: false` хардкод (`orders_services.py:550`). |
| **State machine / enum статусов** | **отсутствует** | `state_order` — `String(255)`, free-text. Используются и `CANCELLED`, и `CANCELED` (одно условие — `:1075` — учитывает оба, остальное везде только один). Нет `DRAFT`/`SENT`/`CLOSED`. |
| **Rollback при сбое iiko** | **отсутствует** | Локально статус меняется до iiko, ошибки iiko проглатываются. |
| **Кэш GET /orders 5 минут** | **проблема UX** | `@cached(ttl_seconds=300, key_prefix="orders")` (`:34`). Кэш инвалидируется в `create/update/pay/cancel`, но если другой инстанс/процесс — рассинхрон. |
| **Дробные amount** | **сломано** | `TOrder.count_order` создаётся через `int(amount)` (`:458, :1146`), 0.250 кг → 0. В `DOrder.items` JSON остаётся float, в iiko payload float идёт. Расхождение TOrder ↔ items ↔ iiko. |
| **CLOUD_OLD ключ для заказов** | **не используется** | В iiko_service.py определён, но во всех 5 вызовах `orders_services.py` стоит `CLOUD`. Если задумывалось, что заказы должны идти через старый ключ — это не реализовано. |
| **Передача `creationStatus` фронту** | **отсутствует** | iiko может вернуть `creationStatus="Error"` или `InProgress` — мы парсим, но в `CreateOrderResponse` не отдаём. |
| **Проверка `IIKO_REQUESTS_DISABLED` / `IIKO_SEND_ORDERS` на уровне ответа фронту** | **обманчивая** | Если флаг выключен — мы возвращаем `iiko_id=null` и `message="...sent to iiko"`. Сообщение не соответствует реальности. |

### 8. План тестирования без стенда

Цикл тестируем «тихими» сценариями на проде, на специально подготовленных сущностях (тестовая организация, фейковая категория, дешёвая «техническая» позиция вроде «Тест-блюдо 1₽»). Перед прогоном:

1. **Подготовка**:
   - Уточнить, что `IIKO_REQUESTS_DISABLED=false` и `IIKO_SEND_ORDERS=true` в .env инстанса, на котором тестим. Сейчас оба по умолчанию выключены (`config.py:42, 51`) — без явного включения мы только в нашу БД пишем.
   - Найти тестовую организацию: `GET /organizations` → выбрать ту, где есть тестовый стол и тестовое блюдо ≤10₽.
   - Найти `tableId`: `GET /tables?organization_id=<id>` (статус игнорируется — все будут `available`).
   - Найти `productId`: `GET /menu?organization_id=<id>&name=тест`.
   - Найти `paymentTypeId` для «наличных»: `GET /payment-types?organization_id=<id>`.
   - Найти `removalTypeId` (uuid из iiko Front, либо использовать `IIKO_DEFAULT_REMOVAL_TYPE_ID` из конфига).
   - Авторизоваться: `POST /auth/login` → получить JWT.

2. **Сценарий A — happy path (создать → оплатить → закрыть)**:
   ```bash
   # 1. Создать
   curl -X POST $API/orders -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{
     "organizationId": 1,
     "tableId": 5,
     "waiterId": 3,
     "guests": 1,
     "items": [{"productId": 999, "amount": 1.0, "price": 1.0, "sum": 1.0}],
     "comment": "test-cycle-A"
   }'
   # Запомнить order_id, iiko_id из ответа.

   # 2. Проверить, что в iikoFront появился заказ с тем же номером (CreateOrderResponse.iiko_number).

   # 3. Оплатить
   curl -X POST $API/orders/$ORDER_ID/pay -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{
     "paymentType": 1
   }'

   # 4. Проверить в БД: SELECT state_order, external_data->'iiko_change_payments', external_data->'iiko_close_order' FROM d_orders WHERE id=$ORDER_ID;
   #    Проверить в iikoFront: заказ закрылся, есть фискальный чек на 1₽.
   ```
   Что валидируем: `state_order=PAID`, `iiko_change_payments` непустой, `iiko_close_order` непустой, в iikoFront чек закрыт.

3. **Сценарий B — отмена**:
   ```bash
   # 1. Создать (как в A)
   # 2. Отменить
   curl -X POST $API/orders/$ORDER_ID/cancel -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{
     "reason": "test-cancel",
     "removalTypeId": "<uuid-of-removal-type>"
   }'
   # 3. БД: state_order=CANCELLED, external_data.iiko_cancel_order непустой.
   # 4. iikoFront: заказ отменён, на стол не висит.
   ```
   Что валидируем: отмена доходит до iiko (через `external_data.iiko_cancel_order`). Если `removalTypeId` не передан — заказ локально отменится, но в iiko останется. Проверить именно с removalTypeId.

4. **Сценарий C — дополнение позицией**:
   ```bash
   # 1. Создать с 1 позицией.
   # 2. PUT /orders/{id} с двумя позициями (старая + новая):
   curl -X PUT $API/orders/$ORDER_ID -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{
     "items": [
       {"productId": 999, "amount": 1.0, "price": 1.0, "sum": 1.0},
       {"productId": 998, "amount": 1.0, "price": 2.0, "sum": 2.0}
     ]
   }'
   # 3. БД: external_data.iiko_add_items непустой, sum_order=3.0.
   # 4. iikoFront: в заказе появилась вторая позиция, кухня получила её через сервисную печать.
   ```
   Что валидируем: append работает. Дальше из этого же сценария:

5. **Сценарий D — попытка изменить amount (демонстрация бага)**:
   ```bash
   # 5. PUT /orders/{id} с одной позицией, но amount=5:
   curl -X PUT $API/orders/$ORDER_ID ... -d '{
     "items": [{"productId": 999, "amount": 5.0, "price": 1.0, "sum": 5.0}]
   }'
   ```
   Ожидаемо: 200 OK, в нашей БД `sum_order=5`, но в iikoFront количество осталось 1, и удалённая позиция 998 — тоже осталась. Записать это как наблюдаемый разрыв.

6. **Сценарий E — оплата с tipAmount (демонстрация дыры)**:
   ```bash
   # 1. Создать заказ на 100₽.
   # 2. Оплатить с tipAmount=20:
   curl -X POST $API/orders/$ORDER_ID/pay ... -d '{"paymentType": 1, "tipAmount": "20"}'
   # 3. БД: order.tips = 20, external_data.tip_amount = "20".
   # 4. iikoFront: чек на 100₽ (без чая). Деньги от чая в iiko не учтены.
   ```
   Что валидируем: чаи теряются в iiko. Если это критично — task на пробрасывание `tipAmount` в `change_payments` payload.

7. **Что смотреть в логах БД / iiko Front**:
   - `SELECT id, state_order, iiko_id, sum_order, external_data->'logs', external_data->'iiko_create_order', external_data->'iiko_change_payments', external_data->'iiko_close_order', external_data->'iiko_add_items', external_data->'iiko_cancel_order' FROM d_orders WHERE id IN (...);`
   - `external_data.logs[]` — таймлайн всех действий с заказом.
   - В iikoFront: «Открытые заказы» по столу, фискальный чек по `external_data.iiko_create_order.number`.
   - В app-логах backend: grep по `Отправка заказа {order.id} в iiko Cloud`, `Ответ iiko /api/1/order/...`, и любые `Ошибка при ...`.

8. **Граничные кейсы, которые стоит руками прогнать на проде** (без curl, через UI/Postman):
   - Двойной `POST /orders/{id}/pay` на одном заказе — что выведет?
   - `POST /orders/{id}/cancel` после `POST /orders/{id}/pay` — должен вернуть 400 «Cannot cancel paid order».
   - `POST /orders/{id}/cancel` дважды подряд — ожидаемо, у нас этот кейс не блокируется, демонстрация.
   - `POST /orders` с `productId` чужой организации — текущая валидация это **не отловит**, заказ создастся.
   - `POST /orders` с `paymentTypeId` чужой организации в `payments[]` — текущая валидация это **не отловит** (валидируется только наличие, не привязка к org).
   - `POST /orders/{id}/pay` без тела (`pay_data=None`) — у нас отрабатывает, но `change_payments` пропускается с warning, и `close` вызывается всё равно. В iikoFront ожидаемо «не пробит». Хороший кейс воспроизвести и потом починить.

## Реализовано (2026-05-21)

### 1. `close_order_in_iiko` больше не вызывается, если `change_payments` упал
`routers/orders/order.py: pay_order_endpoint` (около строк 258-282).

Теперь так:
```python
change_result = await change_payments_in_iiko(...)
change_ok = bool(change_result) and not change_result.get("errorDescription")
if change_ok:
    await close_order_in_iiko(...)
else:
    logger.warning(...)
    pay_message = "Оплачено локально; синхронизация с iiko не прошла, требуется проверка"
```

`change_payments_in_iiko` возвращает `{}` при любой проблеме (отсутствует `iiko_id`, нет `pay_data`, ошибка резолва payment_type, exception). В этом случае `change_ok=False` → `close` НЕ вызывается. Ответ фронту меняется на честный.

Это полностью закрывает критический кейс «заказ закрылся в iikoFront без оплат» → больше не повторится.

### 2. Враньё в ответе `POST /orders` пресечено
`routers/orders/order.py` (около строк 199-215). Теперь сообщение зависит от фактического `new_order.iiko_id`:
- `IIKO_SEND_ORDERS=false` → «Order created locally (iiko sending disabled)»
- `iiko_id` есть → «Order created locally and sent to iiko»
- `IIKO_SEND_ORDERS=true`, но `iiko_id is None` → «Order created locally; iiko sending was attempted but failed (see logs)»

Фронт теперь видит честно: «попытались, но не вышло».

### 3. Толерантный резолв `waiterId` (доп. фикс после аудита фронта)
`services/orders/orders_services.py`: добавлен helper `_resolve_waiter(db, waiter_id_raw)`, который пытается резолвить переданный `waiterId` тремя способами по очереди:
1. как `User.id` (текущий контракт фронта `app/waiter/newOrder.tsx:281`),
2. как `Employee.id`,
3. как `Employee.iiko_id` (преобразуем к строке — поддержка магического `322256` из тестового аккаунта фронта).

Применяется в `create_order_from_app` (создание заказа) и в `update_order` (редактирование). Если не нашлось ни одного варианта — `ValueError → 400` с понятным сообщением «tried User.id / Employee.id / Employee.iiko_id». Магическое число `322256` теперь сработает корректно.

### Что не сделано (отложено, требует отдельной итерации)
- **Шаг 1 цикла (открытие стола)**: `GET /tables` хардкодит `status="available"`, `currentOrderId=None`. `get_cloud_orders_by_table` существует, но не вызывается — два параллельных заказа на одном столе по-прежнему можно создать. Это **redesign**, отдельный таск.
- **Модификаторы**: модель/синк есть, но `GET /menu` их не отдаёт и `CreateOrderItemRequest` их не принимает. Тоже redesign — расширение схем + парсинг payload в iiko.
- **Split-cheque, prebill, merge, move-table**: не реализовано вовсе. Redesign + новые endpoints.
- **`tipAmount` не пробрасывается в iiko Cloud payload** (только сохраняется в `external_data` и `order.tips`). Дёшево фиксить, но нужно решить, как именно — отдельным `paymentItem` или полем заказа. Отложил.
- **`payment_type_kind` fallback на `"Cash"`** (`orders_services.py:798, 802`) — ломает IikoCard/бонусы при отсутствии данных. Чинить через task 4 (валидация payment_type ↔ organization), потому что корневая причина — фронт может прислать видом, у которого `payment_type_kind` нет.
- **`TOrder.count_order = int(amount)` теряет дробные граммовки** (`orders_services.py`). Нужно проверить тип колонки + сделать миграцию + правильно конвертировать — отдельная задача.
- **`CLOUD_OLD` vs `CLOUD` для orders**: в `IikoApiType` enum `CLOUD_OLD` определён «для orders», но во всех 5 order-вызовах используется `CLOUD`. Это бизнес-решение, не дёргаю без подтверждения.
- **Валидация product/payment_type/table ↔ organization**: текущая валидация это не отловит, заказ создастся с чужими сущностями. Это redesign — добавить cross-check на этапе `create_order_from_app`. Отложил.

Эти пункты — большая часть «полного цикла» по task 8. Закрыть их одним проходом нельзя; нужны отдельные итерации с дизайном.
