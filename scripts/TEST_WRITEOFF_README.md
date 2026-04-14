# Тестирование создания складских документов

## Описание

Скрипт `test_writeoff_document.py` предназначен для тестирования эндпоинтов создания складских документов:
- `/documents/writeoff` - акты списания
- `/documents/incoming-invoice` - приходные накладные
- `/documents/outgoing-invoice` - расходные накладные

## Использование

### 1. Проверка данных в БД

Перед запуском теста убедитесь, что в БД есть:
- Товар с iiko_id `e99b7b0d-9913-494b-9f55-293e3b6ee163` (ID: 3181)
- Активный счет (account_id)
- Активный склад (store) для организации товара

### 2. Запуск теста

#### Полный тест (получение счетов + создание акта списания):
```bash
cd /srv/project/backend_main_node
source venv/bin/activate
PYTHONPATH=/srv/project/backend_main_node python scripts/test_writeoff_document.py
```

#### Только получение списка счетов:
```bash
PYTHONPATH=/srv/project/backend_main_node python scripts/test_writeoff_document.py --accounts
```

#### Только создание акта списания:
```bash
PYTHONPATH=/srv/project/backend_main_node python scripts/test_writeoff_document.py --writeoff
```

#### Указать другой URL API:
```bash
PYTHONPATH=/srv/project/backend_main_node python scripts/test_writeoff_document.py --url http://localhost:8000
```

### 3. Использование curl

#### Получить список счетов:
```bash
curl -X GET "http://localhost:8008/documents/accounts" \
  -H "Content-Type: application/json"
```

#### Создать акт списания:
```bash
curl -X POST "http://localhost:8008/documents/writeoff" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": 46,
    "date": "2025-01-15T14:30",
    "comment": "Тестовый акт списания",
    "items": [
      {
        "id": 3181,
        "amount": 1.0
      }
    ]
  }'
```

#### Создать приходную накладную:
```bash
curl -X POST "http://localhost:8008/documents/incoming-invoice" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-01-15T14:30",
    "comment": "Тестовая приходная накладная",
    "supplier_id": 1,
    "invoice": "INV-001",
    "items": [
      {
        "id": 3181,
        "quantity": 10.0,
        "price": 100.0,
        "amount": 1000.0
      }
    ]
  }'
```

#### Создать расходную накладную:
```bash
curl -X POST "http://localhost:8008/documents/outgoing-invoice" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025-01-15T14:30",
    "comment": "Тестовая расходная накладная",
    "account_id": 46,
    "items": [
      {
        "id": 3181,
        "quantity": 5.0,
        "price": 100.0,
        "amount": 500.0
      }
    ]
  }'
```

## Формат запросов

### POST /documents/writeoff (Акт списания)

```json
{
  "account_id": 46,
  "date": "2025-01-15T14:30",
  "comment": "Комментарий к документу",
  "items": [
    {
      "id": 3181,
      "amount": 1.0
    }
  ]
}
```

**Поля:**
- `account_id` (обязательное): ID счета из таблицы `accounts_list`
- `date` (обязательное): Дата со временем в формате `YYYY-MM-DDTHH:MM` или ISO
- `comment` (опциональное): Комментарий к документу
- `items` (обязательное): Массив позиций документа
  - `id` (обязательное): ID товара из таблицы `items`
  - `amount` (обязательное): Количество товара (должно быть > 0)

### POST /documents/incoming-invoice (Приходная накладная)

```json
{
  "date": "2025-01-15T14:30",
  "comment": "Комментарий к документу",
  "supplier_id": 1,
  "invoice": "INV-001",
  "items": [
    {
      "id": 3181,
      "quantity": 10.0,
      "price": 100.0,
      "amount": 1000.0
    }
  ]
}
```

**Поля:**
- `date` (обязательное): Дата со временем в формате `YYYY-MM-DDTHH:MM` или `DD.MM.YYYY`
- `comment` (опциональное): Комментарий к документу
- `supplier_id` (опциональное): ID поставщика из таблицы `suppliers`
- `invoice` (опциональное): Номер счет-фактуры
- `items` (обязательное): Массив позиций документа
  - `id` (обязательное): ID товара из таблицы `items`
  - `quantity` (обязательное): Количество товара (должно быть > 0)
  - `price` (обязательное): Цена за единицу (должно быть >= 0)
  - `amount` (опциональное): Сумма (если не указана, рассчитывается как quantity * price)

### POST /documents/outgoing-invoice (Расходная накладная)

```json
{
  "date": "2025-01-15T14:30",
  "comment": "Комментарий к документу",
  "account_id": 46,
  "items": [
    {
      "id": 3181,
      "quantity": 5.0,
      "price": 100.0,
      "amount": 500.0
    }
  ]
}
```

**Поля:**
- `date` (обязательное): Дата со временем в формате `YYYY-MM-DDTHH:MM` или `DD.MM.YYYY`
- `comment` (опциональное): Комментарий к документу
- `account_id` (опциональное): ID счета из таблицы `accounts_list`
- `items` (обязательное): Массив позиций документа
  - `id` (обязательное): ID товара из таблицы `items`
  - `quantity` (обязательное): Количество товара (должно быть > 0)
  - `price` (обязательное): Цена за единицу (должно быть >= 0)
  - `amount` (опциональное): Сумма (если не указана, рассчитывается как quantity * price)

## Формат ответа

### Успешный ответ:
```json
{
  "success": true,
  "message": "Акт списания успешно создан",
  "iiko_id": "uuid-документа-в-iiko",
  "document_id": 123
}
```

### Ошибка:
```json
{
  "detail": "Описание ошибки"
}
```

## Текущие тестовые данные

- **Товар iiko_id**: `e99b7b0d-9913-494b-9f55-293e3b6ee163`
- **Товар ID**: 3181
- **Товар name**: Макароны по флотски с фаршем стафф
- **Счет ID**: 46
- **Счет name**: Инвентарь
- **Склад ID**: 1
- **Склад name**: Тестовый склад

## Примечания

1. Скрипт автоматически определяет `organization_id` из товаров
2. **Все эндпоинты всегда используют склад с iiko_id `5849a5b1-1a73-40c3-a2dd-fd32f35325a2`**
3. Если склад с этим iiko_id не найден в БД, он все равно будет использован напрямую при отправке в iiko API
4. Все товары в запросе должны принадлежать одной организации
5. Если у товара нет `organization_id`, используется значение по умолчанию (1)
6. Для приходных накладных всегда используется концепция "ГК 9 Премьера" (код: 13)
7. Для приходных накладных можно указать поставщика (`supplier_id`) и номер счет-фактуры (`invoice`)
8. Для расходных накладных можно указать счет (`account_id`) для списания товаров

