# Новые API Endpoints

Документация по всем новым API endpoints, созданным согласно спецификации из `API_INFO_FROM_FRONTEND.md`.

## 📋 Содержание

1. [Квесты (Мотивация)](#квесты-мотивация)
2. [Зарплата](#зарплата)
3. [Аналитика](#аналитика)
4. [Отчеты](#отчеты)
5. [Смены](#смены)
6. [Помещения и Столы](#помещения-и-столы)
7. [Дополнительные Endpoints](#дополнительные-endpoints)

---

## 🎯 Квесты (Мотивация)

### GET /waiter/{waiter_id}/quests

Получить квесты официанта на определенную дату.

**Query Parameters:**
- `date` (optional): Дата в формате "DD.MM.YYYY"
- `organization_id` (optional): ID организации для фильтрации

**Response:**
```json
{
  "quests": [
    {
      "id": "1",
      "title": "Квест на сегодня",
      "description": "Продай 15 десерт",
      "reward": 15000,
      "current": 3,
      "target": 15,
      "unit": "десерт",
      "completed": false,
      "progress": 20,
      "expiresAt": "2025-01-15T23:59:59Z"
    }
  ]
}
```

### GET /quests/{quest_id}

Получить детальную информацию о квесте (для CEO).

**Query Parameters:**
- `organization_id` (optional): ID организации для фильтрации

**Response:**
```json
{
  "id": "1",
  "title": "Квест на сегодня",
  "description": "Продай 15 десерт",
  "reward": 15000,
  "current": 10,
  "target": 15,
  "unit": "десерт",
  "completed": false,
  "progress": 66.67,
  "expiresAt": "2025-01-15T23:59:59Z",
  "totalEmployees": 5,
  "completedEmployees": 2,
  "employeeNames": ["Аслан Аманов", "Аида Таманова"],
  "date": "15.01.2025",
  "employeeProgress": [
    {
      "employeeId": "1",
      "employeeName": "Аслан Аманов",
      "progress": 100,
      "completed": true,
      "points": 15,
      "rank": 1
    }
  ]
}
```

### POST /quests

Создать новый квест (для CEO).

**Request Body:**
```json
{
  "title": "Продай 15 десерт",
  "description": "Продай 15 десерт за смену",
  "reward": 15000,
  "target": 15,
  "unit": "десерт",
  "date": "15.01.2025",
  "employeeIds": ["1", "2", "3"],
  "organization_id": 1
}
```

---

## 💰 Зарплата

### GET /waiter/{waiter_id}/salary

Получить зарплату официанта за день.

**Query Parameters:**
- `date` (required): Дата в формате "DD.MM.YYYY"
- `organization_id` (optional): ID организации для фильтрации

**Response:**
```json
{
  "date": "15.01.2025",
  "tablesCompleted": 39,
  "totalRevenue": 1000192,
  "salary": 58192,
  "salaryPercentage": 5,
  "bonuses": 5157,
  "questBonus": 15000,
  "questDescription": "Бонус определенный сумма",
  "penalties": 0,
  "totalEarnings": 78349,
  "breakdown": {
    "baseSalary": 50035,
    "percentage": 5,
    "bonuses": [
      {
        "type": "performance",
        "amount": 5157,
        "description": "Бонус за отличную работу"
      }
    ],
    "penalties": [],
    "questRewards": [
      {
        "questId": "1",
        "questName": "Продай 15 десерт",
        "reward": 15000
      }
    ]
  },
  "quests": [...]
}
```

---

## 📊 Аналитика

### GET /analytics

Получить аналитику (для CEO).

**Query Parameters:**
- `date` (optional): Дата в формате "DD.MM.YYYY"
- `period` (optional): Период ("day" | "week" | "month")
- `organization_id` (optional): ID организации для фильтрации

**Response:**
```json
{
  "metrics": [
    {
      "id": 1,
      "label": "Выручка",
      "value": "19 589 699 тг",
      "change": {
        "value": "-28%",
        "trend": "down"
      }
    }
  ],
  "reports": [...],
  "orders": [...],
  "financial": [...],
  "inventory": [...],
  "employees": [...]
}
```

---

## 📈 Отчеты

### GET /reports/orders

Получить отчеты по заказам.

**Query Parameters:**
- `date` (required): Дата в формате "DD.MM.YYYY"
- `period` (optional): Период ("day" | "week" | "month")
- `organization_id` (optional): ID организации для фильтрации

**Response:**
```json
{
  "checks": {
    "id": 12332,
    "label": "Средний чек",
    "value": "15 800 тг"
  },
  "returns": {
    "id": 31341,
    "label": "Сумма возвратов",
    "value": "-15 800 тг",
    "type": "negative"
  },
  "averages": [...]
}
```

### GET /reports/moneyflow

Получить денежные отчеты.

**Query Parameters:**
- `date` (required): Дата в формате "DD.MM.YYYY"
- `period` (optional): Период ("day" | "week" | "month")
- `organization_id` (optional): ID организации для фильтрации

**Response:**
```json
{
  "dishes": {...},
  "writeoffs": {...},
  "expenses": {...},
  "incomes": {...}
}
```

---

## ⏰ Смены

### GET /shifts

Получить информацию о смене.

**Query Parameters:**
- `date` (optional): Дата в формате "DD.MM.YYYY"
- `employee_id` (optional): ID сотрудника для фильтрации
- `organization_id` (optional): ID организации для фильтрации

**Response:**
```json
{
  "id": "shift-2025-01-15",
  "date": "15.01.2025",
  "startTime": "09:00",
  "endTime": null,
  "elapsedTime": "04:56:25",
  "openEmployees": 5,
  "totalAmount": 19589699,
  "finesCount": 0,
  "motivationCount": 3,
  "questsCount": 3,
  "status": "active"
}
```

### GET /waiter/{waiter_id}/shift/status

Проверить активность смены официанта.

**Query Parameters:**
- `organization_id` (optional): ID организации для фильтрации

**Response:**
```json
{
  "isActive": true,
  "shiftId": "123",
  "startTime": "09:00",
  "elapsedTime": "04:56:25"
}
```

---

## 🏢 Помещения и Столы

### GET /rooms

Получить список помещений.

**Query Parameters:**
- `organization_id` (optional): ID организации для фильтрации

**Response:**
```json
{
  "rooms": [
    {
      "id": "1",
      "name": "Общий зал",
      "capacity": 50,
      "tables": [...]
    }
  ]
}
```

### GET /tables

Получить список столов.

**Query Parameters:**
- `room_id` (optional): ID помещения для фильтрации
- `status` (optional): Статус стола ("available" | "occupied" | "disabled" | "all")
- `organization_id` (optional): ID организации для фильтрации

**Response:**
```json
{
  "tables": [
    {
      "id": "1",
      "number": "1",
      "roomId": "1",
      "roomName": "Общий зал",
      "capacity": 4,
      "status": "available",
      "currentOrderId": null,
      "assignedEmployeeId": null
    }
  ]
}
```

---

## 🔨 Дополнительные Endpoints

### POST /fines

Создать штраф для сотрудника.

**Request Body:**
```json
{
  "employeeId": "1",
  "employeeName": "Аслан Аманов",
  "reason": "Опоздание на работу",
  "amount": 5000,
  "date": "15.01.2025"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Fine created successfully",
  "fine_id": 123
}
```

### PUT /employees/{employee_id}/shift-time

Обновить время смены сотрудника.

**Request Body:**
```json
{
  "shiftTime": "09:30"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Shift time updated successfully"
}
```

---

## 📝 Общие замечания

### Авторизация

Все endpoints требуют авторизации через:
- Bearer Token в заголовке `Authorization: Bearer <token>`
- Или API токен в query параметре `?token=<api_token>`

### Фильтрация по организации

Все endpoints поддерживают необязательный параметр `organization_id` для фильтрации данных по конкретной организации.

### Форматирование данных

- **Даты**: "DD.MM.YYYY" (например, "15.01.2025")
- **Время**: "HH:mm" (например, "09:30")
- **Длительность**: "HH:mm:ss" (например, "04:56:25")
- **ISO даты**: "YYYY-MM-DDTHH:mm:ssZ" (например, "2025-01-15T09:30:00Z")

### Структура проекта

```
├── routers/
│   ├── quests/          # Роутеры для квестов
│   ├── salary/          # Роутеры для зарплаты
│   ├── analytics/       # Роутеры для аналитики
│   ├── reports/         # Роутеры для отчетов
│   ├── shifts/          # Роутеры для смен
│   └── rooms/           # Роутеры для помещений и столов
├── services/
│   ├── quests/          # Бизнес-логика квестов
│   ├── salary/          # Бизнес-логика зарплаты
│   ├── analytics/       # Бизнес-логика аналитики
│   ├── reports/         # Бизнес-логика отчетов
│   ├── shifts/          # Бизнес-логика смен
│   └── rooms/           # Бизнес-логика помещений и столов
└── schemas/
    ├── quests.py        # Pydantic схемы для квестов
    ├── salary.py        # Pydantic схемы для зарплаты
    ├── analytics.py     # Pydantic схемы для аналитики
    ├── reports.py       # Pydantic схемы для отчетов
    ├── shifts.py        # Pydantic схемы для смен
    ├── rooms.py         # Pydantic схемы для помещений и столов
    └── fines.py         # Pydantic схемы для штрафов
```

---

## 🧪 Тестирование

Для тестирования всех новых endpoints используйте скрипт:

```bash
python test_new_api_endpoints.py
```

Перед запуском:
1. Убедитесь, что сервер запущен (`python main.py`)
2. Замените токен в скрипте на ваш реальный токен
3. Убедитесь, что в БД есть тестовые данные

---

## ✅ Статус реализации

- ✅ Квесты (GET /waiter/:id/quests, GET /quests/:id, POST /quests)
- ✅ Зарплата (GET /waiter/:id/salary)
- ✅ Аналитика (GET /analytics)
- ✅ Отчеты (GET /reports/orders, GET /reports/moneyflow)
- ✅ Смены (GET /shifts, GET /waiter/:id/shift/status)
- ✅ Помещения и столы (GET /rooms, GET /tables)
- ✅ Дополнительные endpoints (POST /fines, PUT /employees/:id/shift-time)

---

## 📌 TODO

- [ ] Обновить существующие endpoints для employees согласно API документации
- [ ] Обновить существующие endpoints для menu согласно API документации
- [ ] Обновить существующие endpoints для orders согласно API документации
- [ ] Добавить реальные данные о расходах, списаниях, доходах
- [ ] Добавить поле capacity в модель Table
- [ ] Добавить связь между столом и заказом для определения статуса стола
- [ ] Расширить логику расчета бонусов в зарплате
- [ ] Добавить кеширование для аналитики и отчетов

