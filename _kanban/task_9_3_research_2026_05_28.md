# Task 9.3 — Research /api/1/order/by_table (2026-05-28)

## Запросы

Read-only probe Бокейхана (org 5), 8 столов из секций "Зал"/"Бар"/"Доставка". Сырые ответы в `_kanban/scripts/output_new_server/by_table_probe.json`.

## Находки

### 1. Параметры endpoint — множественные, не единственные

В нашем `get_cloud_orders_by_table` шлётся `{organizationId, tableId}` (единственное). iiko отвечает **HTTP 400**:

```
"errorDescription": "Value cannot be null. (Parameter 'organizationIds')"
"error": "INVALID_BODY_JSON_FORMAT"
```

Правильный формат:
```json
{
  "organizationIds": ["<uuid>"],
  "tableIds": ["<uuid>", "<uuid>", ...]
}
```

Преимущество: можно дёрнуть **батчем** все столы организации одним запросом. Минимум нагрузки на iiko.

**Правка:** `services/iiko/iiko_service.py:get_cloud_orders_by_table` (line 874) — поменять параметры на множественные.

### 2. Структура ответа

```json
{
  "correlationId": "<uuid>",
  "orders": [...]
}
```

При успешном запросе с пустым результатом — `orders: []`.

### 3. ⚠ Главное: `by_table` НЕ показывает iikoFront-заказы без init_by_table

8 столов одной точки → `orders: []`. Двух интерпретаций:
1. На столах сейчас нет открытых заказов (возможно)
2. **Заказы открыты на iikoFront, но не привязаны к Cloud — by_table их не видит**, пока не вызвать `init_by_table` (документация iiko: by_table возвращает только заказы, для которых уже есть Cloud-объект)

Это означает архитектуру 9.3:
- Сначала **init_by_table per table** — создаёт Cloud-сессию из iikoFront-заказа
- Только потом **by_table** возвращает данные с `waiterId`/items/sums

init_by_table — **write-операция** (трогает iiko). Решение клиента нужно: делать ли её на боевом, как часто, и по каким столам.

## Открытые вопросы

1. Действительно ли на 1ГК Бокейхана не было заказов в 14:08-14:09 (рабочее время) — или by_table их просто не видит без init?
2. Кто будет триггерить init_by_table — мы для каждого стола раз в N минут, или только когда официант открыл стол на нашем UI?
3. Что возвращает init_by_table структурно — `waiterId`, items, sums?

## Дополнительная разведка 1×init_by_table

Один аккуратный probe (Бокейхана, TG "Бокейхана 8" `111cb2c2-...`, стол №1 `21c88609-...`):

**POST /api/1/order/init_by_table** ответил **HTTP 500 "Internal error"** с correlationId `f641e183-be53-4fa1-bd0a-76aceb8b33d5`. Сырой ответ в `_kanban/scripts/output_new_server/init_by_table_probe.json`.

Возможные причины:
- На столе нет активного iikoFront-заказа → 500 (некрасиво, но похоже на поведение iiko)
- Неверный payload (нет обязательных полей)
- terminalGroupId/tableId несовместимы
- iiko Cloud не поддерживает init_by_table для этой инсталляции

**Повторный by_table после неудачной init** — `orders: []` (логично, init не прошёл).

Дальше нужны:
- Поддержка iiko с этим correlationId — пусть скажут что упало внутри
- Или проба на столе с **точно** открытым заказом (нужно прямо в момент — официант фронта подтверждает)
- Или проба в нерабочее время с целым набором столов

## TODO

- [x] Параметры by_table множественные — подтверждено
- [x] by_table без init возвращает 200 с пустым массивом (1 batched probe)
- [x] init_by_table даёт 500 на холостом столе (1 probe)
- [x] Поправить `get_cloud_orders_by_table` — параметры на множественные ✓ done 2026-05-28
- [ ] Запросить iiko-поддержку по correlationId `f641e183-be53-4fa1-bd0a-76aceb8b33d5`
- [ ] Тест init_by_table на столе с активным заказом (нужна синхронизация с клиентом)

## TODO

- [ ] Поправить `get_cloud_orders_by_table` — параметры на множественные (это безопасный фикс, делается без HTTP)
- [ ] Получить согласие на 1-2 init_by_table запроса на тестовом столе (например, в нерабочее время)
- [ ] После init: дёрнуть by_table — увидеть структуру `waiterId`, items, status
