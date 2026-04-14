# Тестирование накладных в iiko API

## Описание

Скрипт `test_invoices_iiko.py` предназначен для прямого тестирования запросов в iiko API для приходных и расходных накладных (без HTTP эндпоинтов).

## Использование

### Базовый запуск (тестирует обе накладные):

```bash
cd /srv/project/backend_main_node
source venv/bin/activate
PYTHONPATH=/srv/project/backend_main_node python scripts/test_invoices_iiko.py
```

### Только приходная накладная:

```bash
PYTHONPATH=/srv/project/backend_main_node python scripts/test_invoices_iiko.py --incoming
```

### Только расходная накладная:

```bash
PYTHONPATH=/srv/project/backend_main_node python scripts/test_invoices_iiko.py --outgoing
```

### С кастомными параметрами:

```bash
PYTHONPATH=/srv/project/backend_main_node python scripts/test_invoices_iiko.py \
  --item-id "e99b7b0d-9913-494b-9f55-293e3b6ee163" \
  --date "2025-01-20T15:00" \
  --comment "Мой тестовый комментарий"
```

## Конфигурация

Все тестовые данные можно изменить в скрипте в переменной `TEST_CONFIG`:

```python
TEST_CONFIG = {
    "item_iiko_id": "e99b7b0d-9913-494b-9f55-293e3b6ee163",
    "store_iiko_id": "5849a5b1-1a73-40c3-a2dd-fd32f35325a2",  # Фиксированный склад
    "date": "2025-01-15T14:30",
    "comment": "Тестовая накладная из скрипта",
    "supplier_iiko_id": None,  # Будет получен из БД, если есть
    "account_id": None,  # Будет получен из БД, если есть
    "invoice": "TEST-INV-001",
}
```

## Что тестируется

### Приходная накладная (XML формат):
- Формирование XML запроса
- Обязательные поля: `num`, `sum`, `product`
- Использование фиксированного store (`5849a5b1-1a73-40c3-a2dd-fd32f35325a2`)
- Использование фиксированной концепции ("ГК 9 Премьера", код "13")
- Отправка запроса в iiko API
- Парсинг ответа валидации

### Расходная накладная (JSON формат):
- Формирование JSON запроса
- Обязательные поля: `num`, `productId`, `amount`
- Использование фиксированного store (`5849a5b1-1a73-40c3-a2dd-fd32f35325a2`)
- Использование фиксированной концепции ("ГК 9 Премьера", код "13")
- Отправка запроса в iiko API
- Парсинг ответа

## Форматы запросов

### Приходная накладная (XML):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<document>
  <dateIncoming>15.01.2025</dateIncoming>
  <status>NEW</status>
  <defaultStore>5849a5b1-1a73-40c3-a2dd-fd32f35325a2</defaultStore>
  <conception>guid-концепции</conception>
  <conceptionCode>13</conceptionCode>
  <items>
    <item>
      <num>1</num>
      <product>e99b7b0d-9913-494b-9f55-293e3b6ee163</product>
      <amount>1.0</amount>
      <sum>100.0</sum>
      <store>5849a5b1-1a73-40c3-a2dd-fd32f35325a2</store>
    </item>
  </items>
</document>
```

### Расходная накладная (JSON):
```json
{
  "dateIncoming": "2025-01-15T14:30",
  "status": "NEW",
  "defaultStoreId": "5849a5b1-1a73-40c3-a2dd-fd32f35325a2",
  "conceptionId": "guid-концепции",
  "conceptionCode": "13",
  "items": [
    {
      "num": 1,
      "productId": "e99b7b0d-9913-494b-9f55-293e3b6ee163",
      "amount": 1.0,
      "price": 100.0,
      "sum": 100.0
    }
  ]
}
```

## Примечания

1. Скрипт всегда использует фиксированный склад `5849a5b1-1a73-40c3-a2dd-fd32f35325a2`
2. Скрипт всегда использует фиксированную концепцию "ГК 9 Премьера" (код "13")
3. Скрипт автоматически получает поставщика и счет из БД, если они не указаны в конфигурации
4. Все запросы и ответы выводятся в консоль для анализа

