# Свёрка цикла заказа с iiko Cloud API (2026-05-28)

## Источники
- OpenAPI schema: https://github.com/salesduck/iiko-cloud-api (`index.d.ts`, генерация из `https://api-ru.iiko.services/api/1`)
- Письмо iiko AI-бота поддержки (`[#ID-349227607]`), 2026-04-15 → 2026-05-28
- Probe HTTP-кодов через `curl -X POST .../api/1/order/<endpoint>` без auth (401 = есть, 404 = нет)

## Главное: OpenAPI salesduck устарел

Probe показал что **add_payment** и **order/cancel** возвращают 401 (endpoint существует), хотя в публичной OpenAPI схеме их нет. Письмо iiko-бота подтверждает `add_payment` для сценария 1.

⚠️ **Не доверять отсутствию в salesduck как «endpoint не существует»** — официальный actual API шире чем публичная схема.

## Цикл заказа от iiko-бота (письмо `[#ID-349227607]`)

**Сценарий 1 (наш — заказ создаётся через API):**
1. `POST /api/1/organizations`
2. `POST /api/2/menu` или `/api/2/menu/by_id` ← External Menu (9.4)
3. `POST /api/1/order/create`
4. `POST /api/1/order/add_payment` ← наш 9.2
5. `POST /api/1/order/close`

**Сценарий 2 (с кассы iikoFront):**
1. `POST /api/1/order/init_by_table` ← создаёт Cloud-сессию из POS-заказа (9.3)
2. `POST /api/1/order/by_table` (фильтр по `statuses: [NEW, BILL]` и дате)
3. `POST /api/1/order/change_payments` (не оплата, а сохранение информации)
4. `POST /api/1/order/close` (только если сумма платежей == сумме заказа)

Все методы — commands. Возвращают `correlationId`, статус через `/api/1/commands/status`.

## Матрица соответствия наш код ↔ iiko

| Endpoint | В нашем коде | OpenAPI | Probe | Наш payload OK? |
|---|---|---|---|---|
| `order/create` | ✓ `orders_services.py:create_order_in_iiko` | ✓ | 401 | 🟡 лишние `createPaymentIfNotExists` + `checkStopList` (deprecated, игнорятся) |
| `order/add_items` | ✓ `add_items_to_iiko_order` | ✓ | 401 | 🟢 OK |
| `order/close` | ✓ `close_order_in_iiko` | ✓ | 401 | 🟢 OK |
| `order/change_payments` | ✓ `change_payments_in_iiko` (scenario 2) | ✓ | 401 | 🟢 OK |
| `order/add_payment` | ✓ `add_payments_in_iiko` (scenario 1, task 9.2) | ❌ нет в OpenAPI | 401 | 🟡 endpoint подтверждён, payload не сверен публично |
| `order/cancel` | ✓ `cancel_order_in_iiko` | ❌ нет в OpenAPI (есть только `deliveries/cancel`) | 401 | 🟡 endpoint есть, поле `removalComment` не в публичной схеме |
| `order/by_table` | ✓ (research, не используется) | ✓ | 401 | 🟢 OK после фикса множественных параметров (task 9.3) |
| `order/init_by_table` | ❌ нет в коде (TODO 9.3) | ✓ | 401 | n/a |
| `commands/status` | ✓ `iiko_service.wait_command` (task 9.1) | ✓ | 401 | 🟢 OK |
| `/api/2/menu` (External Menu) | ❌ нет (TODO 9.4) | n/a | n/a | используем локальную копию из Server API |

## Риски на демо клиенту

1. **`add_payment` payload** — наша гипотеза «один payment». Если iiko требует обёртку или массив — упадёт. Безопасный путь: иметь fallback на `change_payments` через try/except.
2. **`order/cancel` поле `removalComment`** — не документировано публично. Может быть проигнорировано или дать 400. Тест на боевом — единственный надёжный способ.
3. **External Menu (9.4)** — наша локальная БД-копия меню может быть stale (стоп-листы устарели). Если на демо официант пытается заказать товар который iiko уже снял со стопа — iiko вернёт ошибку валидации в `commands/status`.
4. **Атрибуция waiterId** — известно что не работает; в iiko-отчётах заказ всё равно покажется как «Интегратор» создал.

## Безопасные действия без HTTP

- [x] Фикс параметров `by_table` (множественные) — сделано
- [ ] Убрать `createPaymentIfNotExists` + `checkStopList` из payload `order/create` (косметика, не сломает)
- [ ] Добавить fallback в `add_payments_in_iiko`: если первый ответ 400 — пробовать `change_payments`
- [ ] Дополнить `get_cloud_orders_by_table` опц. параметром `statuses` (фильтрация активных)

## Открытые вопросы для iiko-поддержки

1. Точная JSON-схема `add_payment` (поля payload)
2. Точная JSON-схема `order/cancel` (поле `removalComment`)
3. Почему 500 на `init_by_table` для холостого стола (correlationId `f641e183-be53-4fa1-bd0a-76aceb8b33d5`)
4. Можно ли через `add_payment` отправлять несколько платежей сразу, или строго по одному запросу на платёж?
