# Изменения API — 12.04.2026

## Новые эндпоинты

### 1. GET /reports/profit-loss/detail

Детализация статьи P&L по организациям (точкам).

**Query параметры:**

| Параметр  | Тип    | Обязательный | Описание |
|-----------|--------|-------------|----------|
| item_id   | string | да | ID статьи из ответа /reports/profit-loss (поле `id` в объектах `revenue_by_category` и `expenses_by_type`) |
| item_type | string | да | `"revenue"` или `"expense"` |
| date_from | string | да | Начало периода DD.MM.YYYY |
| date_to   | string | да | Конец периода DD.MM.YYYY |

**Пример запроса:**
```
GET /reports/profit-loss/detail?item_id=revenue_kitchen&item_type=revenue&date_from=01.04.2026&date_to=12.04.2026
```

**Пример ответа:**
```json
{
  "success": true,
  "item_id": "revenue_kitchen",
  "item_type": "revenue",
  "item_name": "Кухня",
  "total": 150000.0,
  "by_organization": [
    {"organization_id": 1, "organization_name": "Ресторан 1", "amount": 90000.0},
    {"organization_id": 2, "organization_name": "Ресторан 2", "amount": 60000.0}
  ]
}
```

**Возможные значения item_id:**

Доходы (item_type = "revenue"):
- `revenue_kitchen` — Кухня
- `revenue_bar` — Бар
- `revenue_other` — Прочее
- `revenue_increase_total` — Наценка (обслуживание)
- `revenue_additional` — Дополнительная выручка
- `revenue_other_income:{название счёта}` — Доп. доходы (динамические)

Расходы (item_type = "expense"):
- `expense_account:{название статьи}` — Расходы по статьям (Аренда, Зарплата и т.д.)
- `cost_goods_total` — Итого себестоимость
- `cost_goods_category:{категория}` — Себестоимость по категории
- `bank_commission` — Комиссия банков

---

### 2. POST /employees/recreate-credentials

Пересоздание логинов и паролей для всех сотрудников.
Не трогает пользователей: admin, ofik, integrator.
Требует авторизации (Bearer token).

**Без параметров.**

**Пример ответа:**
```json
{
  "success": true,
  "message": "Обработано сотрудников: 25",
  "total": 25,
  "credentials": [
    {
      "employee_id": 1,
      "employee_name": "Иван Петров",
      "login": "ivan.petrov",
      "password": "aB3kLm9x"
    }
  ]
}
```

---

## Изменённые эндпоинты

### Все перечисленные эндпоинты получили новые опциональные query-параметры:

- `date_from` (string, DD.MM.YYYY) — начало периода
- `date_to` (string, DD.MM.YYYY) — конец периода

Если переданы date_from + date_to — они имеют приоритет над date + period.
Старые параметры (date, period) работают как раньше — обратная совместимость сохранена.

| Эндпоинт | Что ещё изменилось |
|----------|-------------------|
| GET /analytics | Добавлены date_from, date_to |
| GET /reports/orders | date стал опциональным (раньше required). Добавлены date_from, date_to |
| GET /reports/moneyflow | date стал опциональным (раньше required). Добавлены date_from, date_to |
| GET /reports/profit-loss | Добавлены date_from, date_to |
| GET /reports/sales-dynamics | Добавлены date_from, date_to (альтернатива date + days) |
| POST /recalculate-employee-metrics | Теперь принимает даты и в формате DD.MM.YYYY (помимо YYYY-MM-DD) |

---

### Изменение схемы ответа GET /reports/profit-loss

Объекты в списках `revenue_by_category` и `expenses_by_type` получили новое поле `id` (string).

**revenue_by_category:**
```json
{"id": "revenue_kitchen", "category": "Кухня", "amount": 100000.0}
```

**expenses_by_type:**
```json
{"id": "expense_account:Аренда", "transaction_type": "EXPENSES", "transaction_name": "Аренда", "amount": 50000.0}
{"id": "cost_goods_total", "transaction_type": "EXPENSES", "transaction_name": "Итого себестоимость", "amount": 30000.0}
{"id": "bank_commission", "transaction_type": "EXPENSES", "transaction_name": "Комиссия банков (в)", "amount": 5000.0}
```

Поле `id` используется для запроса детализации через `/reports/profit-loss/detail`.

---

## Багфикс: квесты не обновлялись при оплате заказа

Проблема: в external_data заказа поле waiterId содержит User.id, а quest_service искал Employee.id — не находил сотрудника.
Исправлено: теперь quest_service находит User по waiterId, затем Employee через iiko_id.
