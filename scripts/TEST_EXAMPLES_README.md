# Тестовые примеры создания складских документов

## 📋 Описание

Этот файл содержит примеры запросов для создания складских документов с реальными данными из базы данных.

## 🔧 Подготовка

Перед использованием примеров необходимо синхронизировать данные:

```bash
# Синхронизация складов
POST /sync/stores

# Синхронизация концепций
POST /sync/conceptions

# Синхронизация поставщиков
POST /sync/suppliers
```

## 📊 Текущие данные в БД

- **Организации**: ID=1 (Фабрика)
- **Товары**: 
  - ID=3021 (услуги спецтехники)
  - ID=3232 (услуги доставки)
  - ID=3239 (Чекадержатель)
- **Счета**: ID=46 (Инвентарь)

## 📝 Примеры запросов

### 1. Приходная накладная (INCOMING_INVOICE)

**Эндпоинт:** `POST /warehouse/documents`

**Важно:** Концепция "ГК 9 Премьера" (код: 13) будет использована автоматически, если она есть в БД.

```json
{
  "document_type": "INCOMING_INVOICE",
  "date": "15.01.2025",
  "date_incoming": "15.01.2025",
  "organization_id": 1,
  "store_id": 1,
  "supplier_id": 1,
  "invoice": "TEST-INV-001",
  "comment": "Тестовая приходная накладная",
  "items": [
    {
      "item_id": 3021,
      "quantity": 10.0,
      "price": 100.0,
      "amount": 1000.0
    },
    {
      "item_id": 3232,
      "quantity": 5.0,
      "price": 200.0,
      "amount": 1000.0
    }
  ]
}
```

**cURL:**
```bash
curl -X POST 'http://localhost:8000/warehouse/documents' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -d '{
    "document_type": "INCOMING_INVOICE",
    "date": "15.01.2025",
    "date_incoming": "15.01.2025",
    "organization_id": 1,
    "store_id": 1,
    "supplier_id": 1,
    "invoice": "TEST-INV-001",
    "comment": "Тестовая приходная накладная",
    "items": [
      {
        "item_id": 3021,
        "quantity": 10.0,
        "price": 100.0,
        "amount": 1000.0
      }
    ]
  }'
```

### 2. Расходная накладная (OUTGOING_INVOICE)

**Эндпоинт:** `POST /warehouse/documents`

**Важно:** Концепция "ГК 9 Премьера" (код: 13) будет использована автоматически, если она есть в БД.

```json
{
  "document_type": "OUTGOING_INVOICE",
  "date": "15.01.2025",
  "date_incoming": "15.01.2025",
  "organization_id": 1,
  "default_store_id": 1,
  "account_id": 46,
  "comment": "Тестовая расходная накладная",
  "items": [
    {
      "item_id": 3021,
      "quantity": 5.0,
      "price": 100.0,
      "amount": 500.0
    }
  ]
}
```

**cURL:**
```bash
curl -X POST 'http://localhost:8000/warehouse/documents' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -d '{
    "document_type": "OUTGOING_INVOICE",
    "date": "15.01.2025",
    "date_incoming": "15.01.2025",
    "organization_id": 1,
    "default_store_id": 1,
    "account_id": 46,
    "comment": "Тестовая расходная накладная",
    "items": [
      {
        "item_id": 3021,
        "quantity": 5.0,
        "price": 100.0,
        "amount": 500.0
      }
    ]
  }'
```

### 3. Акт списания (WRITEOFF)

**Эндпоинт:** `POST /warehouse/writeoff-documents`

```json
{
  "date_incoming": "2025-01-15",
  "organization_id": 1,
  "store_id": 1,
  "account_id": 46,
  "status": "NEW",
  "comment": "Тестовый акт списания",
  "items": [
    {
      "item_id": 3021,
      "amount": 2.0,
      "cost": 200.0
    }
  ]
}
```

**cURL:**
```bash
curl -X POST 'http://localhost:8000/warehouse/writeoff-documents' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -d '{
    "date_incoming": "2025-01-15",
    "organization_id": 1,
    "store_id": 1,
    "account_id": 46,
    "status": "NEW",
    "comment": "Тестовый акт списания",
    "items": [
      {
        "item_id": 3021,
        "amount": 2.0,
        "cost": 200.0
      }
    ]
  }'
```

## ⚠️ Важные замечания

1. **Концепция**: Концепция "ГК 9 Премьера" (код: 13) используется автоматически для всех документов. Поле `conception_id` можно не указывать.

2. **ID товаров**: Используйте `item_id` (наш внутренний ID) вместо `item_iiko_id`. Система автоматически преобразует его в `iiko_id` при отправке в iiko API.

3. **ID складов, счетов, поставщиков**: Используйте внутренние ID из нашей БД. Система автоматически преобразует их в `iiko_id`.

4. **Формат даты**: 
   - Для приходных/расходных накладных: `"DD.MM.YYYY"` (например, `"15.01.2025"`)
   - Для актов списания: `"YYYY-MM-DD"` (например, `"2025-01-15"`)

5. **Обязательные поля**:
   - Приходная накладная: `document_type`, `date`, `organization_id`, `store_id`, `items`
   - Расходная накладная: `document_type`, `date`, `organization_id`, `default_store_id`, `account_id`, `items`
   - Акт списания: `date_incoming`, `organization_id`, `store_id`, `account_id`, `items`

## 📁 Файлы с примерами

- `test_examples.json` - простые примеры
- `test_examples_full.json` - полные примеры с описаниями и curl командами

## 🔍 Проверка данных в БД

Для проверки доступных данных в БД используйте:

```bash
python scripts/check_test_data.py
```

Этот скрипт покажет все доступные организации, склады, товары, концепции, поставщики и счета.

