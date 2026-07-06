# GET /reports/profit-loss/detail

Детализация статьи P&L по организациям (точкам). Для статей из транзакций возвращает список отдельных транзакций внутри каждой организации.

## Query параметры

| Параметр        | Тип    | Обязательный | Описание |
|-----------------|--------|-------------|----------|
| item_id         | string | да | ID статьи из ответа `/reports/profit-loss` (поле `id` в объектах `revenue_by_category` и `expenses_by_type`) |
| item_type       | string | да | `"revenue"` или `"expense"` |
| date_from       | string | да | Начало периода DD.MM.YYYY |
| date_to         | string | да | Конец периода DD.MM.YYYY |
| organization_id | int    | нет | ID организации для фильтрации. Если не передан — возвращает все организации |

## Возможные значения item_id

### Доходы (item_type = "revenue")

| item_id | Описание | details |
|---------|----------|---------|
| `revenue_kitchen` | Кухня | нет |
| `revenue_bar` | Бар | нет |
| `revenue_other` | Прочее | нет |
| `revenue_increase_total` | Наценка (обслуживание) | нет |
| `revenue_additional` | Дополнительная выручка | нет |
| `factory_revenue` | Фабрика | нет |
| `revenue_other_income:{название}` | Доп. доходы (динамические, из транзакций) | **да** |

### Расходы (item_type = "expense")

| item_id | Описание | details |
|---------|----------|---------|
| `expense_account:{название}` | Расходы по статьям (Аренда, Зарплата и т.д.) | **да** |
| `cost_goods_total` | Итого себестоимость | нет |
| `cost_goods_category:{категория}` | Себестоимость по категории | нет |
| `bank_commission` | Комиссия банков | нет |

## Структура ответа

```json
{
  "success": true,
  "item_id": "expense_account:Аренда",
  "item_type": "expense",
  "item_name": "Аренда",
  "total": 22400965.0,
  "by_organization": [
    {
      "organization_id": 1,
      "organization_name": "ФАБРИКА",
      "amount": 1650000.0,
      "details": [
        {
          "comment": "аренда за апрель",
          "date": "03.04.2026",
          "amount": 1650000.0,
          "name": null
        }
      ]
    },
    {
      "organization_id": 2,
      "organization_name": "4ГК Expo",
      "amount": 1550000.0,
      "details": [
        {
          "comment": "ГК 4 за апрель",
          "date": "03.04.2026",
          "amount": 1550000.0,
          "name": null
        }
      ]
    }
  ]
}
```

## Поля объекта details

| Поле    | Тип           | Описание |
|---------|---------------|----------|
| comment | string / null | Комментарий к транзакции |
| date    | string / null | Дата в формате DD.MM.YYYY |
| amount  | float         | Сумма транзакции (абсолютное значение) |
| name    | string / null | ФИО создателя (пока не заполняется) |

`details` = `null` для статей, которые берутся не из транзакций (выручка из sales, себестоимость, комиссия банков).

## Примеры запросов

**Расходы по статье "Аренда" за апрель:**
```
GET /reports/profit-loss/detail?item_id=expense_account:Аренда&item_type=expense&date_from=01.04.2026&date_to=30.04.2026
```

**То же самое, но только по одной организации:**
```
GET /reports/profit-loss/detail?item_id=expense_account:Аренда&item_type=expense&date_from=01.04.2026&date_to=30.04.2026&organization_id=1
```

**Выручка Кухни (без details):**
```
GET /reports/profit-loss/detail?item_id=revenue_kitchen&item_type=revenue&date_from=01.04.2026&date_to=30.04.2026
```
