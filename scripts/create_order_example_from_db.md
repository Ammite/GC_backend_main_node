# Пример запроса для создания заказа

## Инструкция

1. Выполните SQL запросы из файла `get_order_data.sql` в вашей БД
2. Используйте полученные данные для заполнения примера ниже

## Структура запроса

```json
{
  "organizationId": <ID из таблицы organizations, опционально>,
  "tableId": <ID из таблицы tables, опционально>,
  "waiterId": <ID из таблицы employees, обязательное>,
  "guests": 2,
  "items": [
    {
      "productId": <ID из таблицы items, обязательное>,
      "amount": <количество, float>,
      "price": <цена за единицу, float>,
      "sum": <сумма = amount * price, float>,
      "comment": "<комментарий, опционально>"
    }
  ],
  "comment": "<комментарий к заказу, опционально>"
}
```

## Пример заполнения

**Важно:** 
- `waiterId` должен быть ID из таблицы `employees`, а не `users`
- Если пользователь с id=10 имеет `iiko_id`, найдите сотрудника с таким же `iiko_id` в таблице `employees`
- Используйте ID сотрудника (employee.id) для поля `waiterId`

### Пример 1: Минимальный запрос

```json
{
  "waiterId": 10,
  "guests": 2,
  "items": [
    {
      "productId": 1,
      "amount": 2.0,
      "price": 1500.0,
      "sum": 3000.0
    },
    {
      "productId": 2,
      "amount": 1.0,
      "price": 2500.0,
      "sum": 2500.0
    }
  ]
}
```

### Пример 2: Полный запрос

```json
{
  "organizationId": 1,
  "tableId": 5,
  "waiterId": 10,
  "guests": 2,
  "items": [
    {
      "productId": 1,
      "amount": 2.0,
      "price": 1500.0,
      "sum": 3000.0,
      "comment": "Без лука"
    },
    {
      "productId": 2,
      "amount": 1.0,
      "price": 2500.0,
      "sum": 2500.0,
      "comment": "Острое"
    }
  ],
  "comment": "Столик у окна"
}
```

## Как получить данные из БД

### 1. Найти сотрудника по пользователю с id=10:

```sql
-- Сначала получите iiko_id пользователя
SELECT iiko_id FROM users WHERE id = 10;

-- Затем найдите сотрудника с таким же iiko_id
SELECT id, name, iiko_id 
FROM employees 
WHERE iiko_id = '<iiko_id из предыдущего запроса>';
```

### 2. Получить два случайных товара:

```sql
SELECT id, name, price 
FROM items 
WHERE deleted = false 
ORDER BY RANDOM() 
LIMIT 2;
```

### 3. Получить стол (опционально):

```sql
SELECT id, number, name 
FROM tables 
WHERE is_deleted = false 
LIMIT 1;
```

### 4. Получить организацию (опционально):

```sql
SELECT id, name 
FROM organizations 
WHERE is_active = true 
LIMIT 1;
```

## Важные замечания

1. **waiterId** - это ID из таблицы `employees`, НЕ из `users`
2. Если пользователь с id=10 не имеет связанного сотрудника, используйте любой ID сотрудника из таблицы `employees`
3. Все ID должны существовать в соответствующих таблицах, иначе запрос вернет ошибку 400
4. `amount`, `price`, `sum` должны быть числами (float)
5. `sum` обычно равно `amount * price`, но может отличаться при скидках
