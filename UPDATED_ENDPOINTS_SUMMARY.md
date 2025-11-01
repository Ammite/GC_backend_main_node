# Обновленные Endpoints - Полные данные

## ✅ Что было исправлено

Все существующие endpoints теперь возвращают **полные данные** вместо только имен.

---

## 📋 Меню (Menu)

### GET /menu

**Было:**
```json
{
  "success": true,
  "message": "got menu",
  "items": [
    {
      "name": "Грузинский обед"
    }
  ]
}
```

**Стало:**
```json
{
  "success": true,
  "message": "got menu",
  "items": [
    {
      "id": 1,
      "iiko_id": "abc123",
      "name": "Грузинский обед",
      "description": "Вкусный грузинский обед",
      "code": "GRU001",
      "price": 2500.00,
      "organization_id": 1,
      "category_id": 5,
      "menu_category_id": 3,
      "product_group_id": 2,
      "weight": 350.0,
      "energy_amount": 650.5,
      "proteins_amount": 25.3,
      "fats_amount": 18.7,
      "carbohydrates_amount": 85.2,
      "type": "dish",
      "measure_unit": "порция",
      "deleted": false
    }
  ]
}
```

**Новые поля:**
- `id` - ID блюда в БД
- `iiko_id` - ID из iiko
- `description` - описание блюда
- `code` - код блюда
- `price` - цена
- `organization_id` - ID организации
- `category_id`, `menu_category_id`, `product_group_id` - категории
- `weight` - вес (граммы)
- `energy_amount` - калорийность
- `proteins_amount` - белки
- `fats_amount` - жиры
- `carbohydrates_amount` - углеводы
- `type` - тип блюда
- `measure_unit` - единица измерения
- `deleted` - удалено ли

---

## 👥 Сотрудники (Employees)

### GET /employees

**Было:**
```json
{
  "success": true,
  "message": "got employees",
  "employees": [
    {
      "id": 1,
      "iiko_id": "emp123",
      "name": "Аслан Аманов",
      "login": "aslan",
      "first_name": "Аслан",
      "last_name": "Аманов",
      "phone": "+7 777 123 4567",
      "email": "aslan@example.com",
      "main_role_code": "waiter",
      "preferred_organization_id": 1,
      "deleted": false
    }
  ]
}
```

**Стало:**
```json
{
  "success": true,
  "message": "got employees",
  "employees": [
    {
      "id": 1,
      "iiko_id": "emp123",
      "name": "Аслан Аманов",
      "login": "aslan",
      "first_name": "Аслан",
      "middle_name": "Бекович",
      "last_name": "Аманов",
      "phone": "+7 777 123 4567",
      "cell_phone": "+7 707 123 4567",
      "email": "aslan@example.com",
      "address": "г. Алматы, ул. Абая 150",
      "main_role_code": "waiter",
      "role_codes": ["waiter", "cashier"],
      "preferred_organization_id": 1,
      "organizations_id": [1, 2],
      "hire_date": "2023-01-15",
      "fire_date": null,
      "birthday": "1995-05-20",
      "code": "EMP001",
      "card_number": "1234567890",
      "taxpayer_id_number": "123456789012",
      "deleted": false
    }
  ]
}
```

**Новые поля:**
- `middle_name` - отчество
- `cell_phone` - мобильный телефон
- `address` - адрес
- `role_codes` - массив кодов ролей
- `organizations_id` - массив ID организаций
- `hire_date` - дата найма
- `fire_date` - дата увольнения
- `birthday` - дата рождения
- `code` - код сотрудника
- `card_number` - номер карты
- `taxpayer_id_number` - ИНН

---

## 📦 Заказы (Orders)

### GET /orders

**Было:**
```json
{
  "success": true,
  "message": "got orders",
  "orders": [
    {
      "name": "1"
    }
  ]
}
```

**Стало:**
```json
{
  "success": true,
  "message": "got orders",
  "orders": [
    {
      "id": 1,
      "iiko_id": "order123",
      "organization_id": 1,
      "terminal_group_id": 2,
      "order_type_id": 1,
      "external_number": "ORD-001",
      "phone": "+7 777 123 4567",
      "guest_count": 4,
      "tab_name": "Стол 5",
      "sum_order": 15800.00,
      "discount": 1000.00,
      "service": 1580.00,
      "bank_commission": 158.00,
      "state_order": "closed",
      "time_order": "2025-01-15T14:30:00",
      "user_id": 3,
      "customer": {
        "name": "Иван Иванов",
        "phone": "+7 777 123 4567"
      },
      "items": [...],
      "payments": [
        {
          "type": "card",
          "amount": 15800
        }
      ],
      "tips": {
        "amount": 500
      },
      "order_items": [
        {
          "id": 101,
          "item_id": 25,
          "item_name": "Цезарь",
          "count": 2,
          "price": 2500.00,
          "comment": "Без сухариков"
        },
        {
          "id": 102,
          "item_id": 30,
          "item_name": "Хинкали",
          "count": 10,
          "price": 350.00,
          "comment": null
        }
      ],
      "deleted": false
    }
  ]
}
```

**Новые поля:**
- `id` - ID заказа
- `iiko_id` - ID из iiko
- `organization_id` - ID организации
- `terminal_group_id` - ID группы терминалов
- `order_type_id` - ID типа заказа
- `external_number` - внешний номер
- `phone` - телефон клиента
- `guest_count` - количество гостей
- `tab_name` - название счета (стол)
- `sum_order` - сумма заказа
- `discount` - скидка
- `service` - сервисный сбор
- `bank_commission` - комиссия банка
- `state_order` - статус заказа
- `time_order` - время заказа
- `user_id` - ID официанта
- `customer` - данные клиента (JSON)
- `items` - блюда (JSON из iiko)
- `payments` - платежи (JSON)
- `tips` - чаевые (JSON)
- `order_items` - **детализированные позиции заказа**:
  - `id` - ID позиции
  - `item_id` - ID блюда
  - `item_name` - название блюда
  - `count` - количество
  - `price` - цена за единицу
  - `comment` - комментарий к позиции
- `deleted` - удален ли

---

## 🔍 Примеры использования на фронтенде

### Меню
```javascript
// Получить меню
const response = await api.get('/menu', {
  params: {
    organization_id: 1,
    category_id: 5,
    limit: 50
  }
});

// Теперь доступны все данные
response.data.items.forEach(item => {
  console.log(`${item.name} - ${item.price} тг`);
  console.log(`Калории: ${item.energy_amount}`);
  console.log(`Вес: ${item.weight}г`);
});
```

### Сотрудники
```javascript
// Получить сотрудников
const response = await api.get('/employees', {
  params: {
    organization_id: 1,
    role_code: 'waiter'
  }
});

// Теперь доступны все данные
response.data.employees.forEach(emp => {
  console.log(`${emp.name} (${emp.code})`);
  console.log(`Телефон: ${emp.phone}`);
  console.log(`Email: ${emp.email}`);
  console.log(`Роли: ${emp.role_codes.join(', ')}`);
  console.log(`Дата найма: ${emp.hire_date}`);
});
```

### Заказы
```javascript
// Получить заказы
const response = await api.get('/orders', {
  params: {
    organization_id: 1,
    state: 'closed',
    limit: 20
  }
});

// Теперь доступны все данные
response.data.orders.forEach(order => {
  console.log(`Заказ #${order.external_number}`);
  console.log(`Сумма: ${order.sum_order} тг`);
  console.log(`Гостей: ${order.guest_count}`);
  console.log(`Стол: ${order.tab_name}`);
  
  // Позиции заказа
  order.order_items.forEach(item => {
    console.log(`  - ${item.item_name} x${item.count} = ${item.price * item.count} тг`);
  });
});
```

---

## 📊 Сравнительная таблица

| Endpoint | Было полей | Стало полей | Улучшение |
|----------|-----------|-------------|-----------|
| GET /menu | 1 | 16 | +1500% |
| GET /employees | 11 | 21 | +91% |
| GET /orders | 1 | 20+ | +1900% |

---

## ✨ Дополнительные улучшения

### 1. Связанные данные
- **Orders** теперь включают детализированные позиции (`order_items`) с названиями блюд
- Используется `joinedload` для оптимизации запросов

### 2. Правильные типы данных
- Все числовые поля конвертируются в `float`
- Даты конвертируются в ISO формат
- JSON поля передаются как есть

### 3. Опциональные поля
- Все поля, которые могут быть `null`, помечены как `Optional`
- Это обеспечивает корректную работу с неполными данными

---

## 🎯 Что теперь можно делать на фронтенде

### Меню
✅ Отображать полную информацию о блюде  
✅ Показывать калорийность и БЖУ  
✅ Фильтровать по категориям  
✅ Отображать цены и вес  

### Сотрудники
✅ Показывать полную контактную информацию  
✅ Отображать все роли сотрудника  
✅ Показывать даты найма и увольнения  
✅ Фильтровать по организациям  

### Заказы
✅ Отображать детализацию заказа  
✅ Показывать все позиции с ценами  
✅ Рассчитывать итоговые суммы  
✅ Отображать информацию о клиенте  
✅ Показывать способы оплаты  

---

## 🚀 Готово к использованию!

Все endpoints теперь возвращают полные данные и готовы к интеграции с фронтендом.

Для тестирования используйте:
```bash
python test_new_api_endpoints.py
```

Документация для фронтенда: `API_FRONTEND_GUIDE.md`

