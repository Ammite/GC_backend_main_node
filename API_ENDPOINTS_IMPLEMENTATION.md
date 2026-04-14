# Документация по реализации новых API эндпоинтов

## Обзор

Данный документ описывает реализацию новых API эндпоинтов согласно спецификации из таблиц. Все эндпоинты требуют авторизации через `get_current_user` и поддерживают опциональную фильтрацию по `organization_id`.

---

## 1. Отчеты по персоналу

### 1.1. GET /reports/personnel

**Описание:** Список всех сотрудников за выбранный период с их суммами чеков, количеством чеков и длительностью смен.

**Параметры:**
- `from_date` (optional): Дата начала периода в формате `DD.MM.YYYY`. Если не указана, используется 30 дней назад.
- `to_date` (optional): Дата конца периода в формате `DD.MM.YYYY`. Если не указана, используется сегодня.
- `organization_id` (optional): ID организации для фильтрации.

**Ответ:**
```json
{
  "success": true,
  "message": "Отчет по персоналу за период с ... по ...",
  "employees": [
    {
      "id": 1,
      "name": "Аслан Аманов",
      "role": "Официант",
      "totalAmount": 56897.50,
      "ordersCount": 45,
      "shiftDuration": "08:30:00"
    }
  ]
}
```

**Реализация:**
- Файл: `routers/reports/reports.py`
- Сервис: `services/reports/personnel_service.py`
- Схемы: `schemas/reports.py` (PersonnelReportResponse, PersonnelEmployeeItem)

**Особенности:**
- Данные берутся из `DOrder` (если есть связь через `user_id`) или из `Sales` (по `waiter_name_id`)
- Длительность смен рассчитывается из таблицы `Shift`
- Поддерживается фильтрация по организации

---

### 1.2. GET /employees/summary

**Описание:** Сводка по сотрудникам - количество сотрудников с открытой смены и их сумма чеков.

**Параметры:**
- `date` (optional): Дата в формате `DD.MM.YYYY` (по умолчанию сегодня).
- `organization_id` (optional): ID организации для фильтрации.

**Ответ:**
```json
{
  "activeEmployeesCount": 5,
  "totalAmount": 250000.00,
  "employees": [
    {
      "id": 1,
      "name": "Аслан Аманов",
      "amount": 56897.50
    }
  ]
}
```

**Реализация:**
- Файл: `routers/employees/employees.py`
- Сервис: `services/employees/employees_service.py` (функция `get_employees_summary`)
- Схемы: `schemas/employees.py` (EmployeesSummaryResponse, EmployeeSummaryItem)

**Особенности:**
- Определяет сотрудников с открытыми сменами (где `end_time` is NULL или `end_time > now`)
- Суммирует чеки активных сотрудников за указанную дату

---

### 1.3. GET /employees/{employee_id}/summary

**Описание:** Сводка по каждому сотруднику отдельно - имя фамилия сотрудника, длительность смены и сумма.

**Параметры:**
- `employee_id` (path): ID сотрудника.
- `date` (optional): Дата в формате `DD.MM.YYYY` (по умолчанию сегодня).
- `organization_id` (optional): ID организации для фильтрации.

**Ответ:**
```json
{
  "id": 1,
  "firstName": "Аслан",
  "lastName": "Аманов",
  "name": "Аслан Аманов",
  "shiftDuration": "08:30:00",
  "totalAmount": 56897.50,
  "ordersCount": 45
}
```

**Реализация:**
- Файл: `routers/employees/employees.py`
- Сервис: `services/employees/employees_service.py` (функция `get_employee_summary`)
- Схемы: `schemas/employees.py` (EmployeeSummaryResponse)

---

### 1.4. GET /employees/{employee_id}/details

**Описание:** Детали по одному сотруднику - длительность смены, сумма чеков и столы на которых открыты чеки.

**Параметры:**
- `employee_id` (path): ID сотрудника.
- `table_id` (optional): ID стола для фильтрации.
- `date` (optional): Дата в формате `DD.MM.YYYY` (по умолчанию сегодня).
- `organization_id` (optional): ID организации для фильтрации.

**Ответ:**
```json
{
  "shiftDuration": "08:30:00",
  "totalAmount": 56897.50,
  "ordersCount": 45,
  "tables": [
    {
      "id": 1,
      "number": "5",
      "roomName": "Общий зал",
      "orderId": "order-123",
      "amount": 15000.00
    }
  ]
}
```

**Реализация:**
- Файл: `routers/employees/employees.py`
- Сервис: `services/employees/employees_service.py` (функция `get_employee_details`)
- Схемы: `schemas/employees.py` (EmployeeDetailsResponse, EmployeeTableItem)

**Особенности:**
- Возвращает только открытые заказы (где `state_order != "CLOSED"`)
- Столы определяются по `tab_name` из `DOrder` или `table_num` из `Sales`
- Связь со столами через таблицу `Table` и `RestaurantSection`

---

### 1.5. GET /employees/{employee_id}/open-check

**Описание:** Детали открытого счета сотрудника - содержимое чека.

**Параметры:**
- `employee_id` (path): ID сотрудника.
- `dateTime` (required): Дата и время в формате ISO (`YYYY-MM-DDTHH:mm:ssZ` или `YYYY-MM-DDTHH:mm:ss`).
- `organization_id` (optional): ID организации для фильтрации.

**Ответ:**
```json
{
  "orderId": "order-123",
  "tableId": 1,
  "tableNumber": "5",
  "roomName": "Общий зал",
  "items": [
    {
      "name": "Стейк",
      "quantity": 2,
      "price": 5000.00,
      "total": 10000.00
    }
  ],
  "totalAmount": 15000.00,
  "status": "OPEN"
}
```

**Реализация:**
- Файл: `routers/employees/employees.py`
- Сервис: `services/employees/employees_service.py` (функция `get_employee_open_check`)
- Схемы: `schemas/employees.py` (EmployeeOpenCheckResponse, EmployeeCheckItem)

**Особенности:**
- Поиск заказа с допуском ±5 минут от указанного `dateTime`
- Блюда берутся из `Sales` по `order_id` или из JSON поля `items` в `DOrder`

---

### 1.6. GET /employees/{employee_id}/closed-tables-history

**Описание:** Посмотреть историю закрытых столиков сотрудника - список чеков закрытых сотрудником и суммы.

**Параметры:**
- `employee_id` (path): ID сотрудника.
- `from_date` (optional): Дата начала периода в формате `DD.MM.YYYY` (по умолчанию 30 дней назад).
- `to_date` (optional): Дата конца периода в формате `DD.MM.YYYY` (по умолчанию сегодня).
- `organization_id` (optional): ID организации для фильтрации.

**Ответ:**
```json
{
  "success": true,
  "message": "История закрытых столиков сотрудника 1",
  "orders": [
    {
      "orderId": "order-123",
      "tableId": 1,
      "tableNumber": "5",
      "roomName": "Общий зал",
      "closedAt": "2025-01-15T20:30:00",
      "totalAmount": 15000.00,
      "itemsCount": 5
    }
  ]
}
```

**Реализация:**
- Файл: `routers/employees/employees.py`
- Сервис: `services/employees/employees_service.py` (функция `get_employee_closed_tables_history`)
- Схемы: `schemas/employees.py` (EmployeeClosedTablesHistoryResponse, EmployeeClosedTableItem)

**Особенности:**
- Возвращает только закрытые заказы (где `state_order == "CLOSED"`)
- Количество позиций считается из таблицы `Sales`

---

## 2. Управление штрафами

### 2.1. GET /fines/summary

**Описание:** Сводка всех штрафов - список всех штрафов за текущий день.

**Параметры:**
- `date` (optional): Дата в формате `DD.MM.YYYY` (по умолчанию сегодня).
- `organization_id` (optional): ID организации для фильтрации.

**Ответ:**
```json
{
  "success": true,
  "message": "Сводка штрафов за 15.01.2025",
  "fines": [
    {
      "id": 1,
      "employeeId": 1,
      "employeeName": "Аслан Аманов",
      "amount": 5000.00,
      "reason": "Опоздание на работу",
      "date": "15.01.2025",
      "createdAt": "2025-01-15T09:00:00"
    }
  ]
}
```

**Реализация:**
- Файл: `routers/employees/employees.py`
- Сервис: `services/fines/fines_service.py` (функция `get_fines_summary`)
- Схемы: `schemas/fines.py` (FinesSummaryResponse, FineItem)

**Особенности:**
- Фильтрация по организации через связь `Penalty.employee_id -> Employees.preferred_organization_id`

---

### 2.2. PUT /fines/{fine_id}

**Описание:** Изменение штрафа сотруднику.

**Параметры:**
- `fine_id` (path): ID штрафа.

**Body:**
```json
{
  "amount": 5000,  // Опционально
  "reason": "Новая причина"  // Опционально
}
```

**Ответ:**
```json
{
  "success": true,
  "message": "Fine updated successfully",
  "fine_id": 1
}
```

**Реализация:**
- Файл: `routers/employees/employees.py`
- Сервис: `services/fines/fines_service.py` (функция `update_fine`)
- Схемы: `schemas/fines.py` (UpdateFineRequest, UpdateFineResponse)

---

### 2.3. DELETE /fines/{fine_id}

**Описание:** Удаление штрафа сотрудника.

**Параметры:**
- `fine_id` (path): ID штрафа.

**Ответ:**
```json
{
  "success": true,
  "message": "Fine deleted successfully"
}
```

**Реализация:**
- Файл: `routers/employees/employees.py`
- Сервис: `services/fines/fines_service.py` (функция `delete_fine`)
- Схемы: `schemas/fines.py` (DeleteFineResponse)

---

## 3. Управление квестами

### 3.1. GET /quests/active

**Описание:** Список активных квестов.

**Параметры:**
- `date` (optional): Дата в формате `DD.MM.YYYY` (по умолчанию сегодня).
- `organization_id` (optional): ID организации для фильтрации.

**Ответ:**
```json
{
  "quests": [
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
      "expiresAt": "2025-01-15T23:59:59"
    }
  ]
}
```

**Реализация:**
- Файл: `routers/quests/quests.py`
- Сервис: `services/quests/quests_service.py` (функция `get_active_quests`)
- Схемы: `schemas/quests.py` (QuestsArrayResponse, QuestResponse)

**Особенности:**
- Возвращает только активные квесты (где `end_date >= now`)
- Прогресс рассчитывается как средний прогресс всех сотрудников

---

### 3.2. GET /quests/{quest_id}/progress

**Описание:** Развернутый список квеста с прогрессом всех сотрудников - список прогресса всех сотрудников внутри квеста.

**Параметры:**
- `quest_id` (path): ID квеста.
- `organization_id` (optional): ID организации для фильтрации.

**Ответ:**
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
  "expiresAt": "2025-01-15T23:59:59",
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

**Реализация:**
- Файл: `routers/quests/quests.py`
- Сервис: `services/quests/quests_service.py` (функция `get_quest_detail`)
- Схемы: `schemas/quests.py` (QuestDetailResponse, EmployeeQuestProgress)

**Особенности:**
- Использует существующую функцию `get_quest_detail`, которая уже возвращает прогресс всех сотрудников
- Сотрудники сортируются по прогрессу (по убыванию)

---

### 3.3. PUT /quests/{quest_id}

**Описание:** Изменение квеста.

**Параметры:**
- `quest_id` (path): ID квеста.

**Body:**
```json
{
  "title": "Новое название",  // Опционально
  "description": "Новое описание",  // Опционально
  "reward": 20000,  // Опционально
  "target": 20,  // Опционально
  "unit": "десерт",  // Опционально
  "date": "15.01.2025",  // Опционально
  "employeeIds": ["1", "2", "3"]  // Опционально
}
```

**Ответ:**
```json
{
  "success": true,
  "message": "Quest updated successfully",
  "quest": {
    "id": "1",
    "title": "Новое название",
    "description": "Новое описание",
    "reward": 20000,
    "current": 0,
    "target": 20,
    "unit": "десерт",
    "completed": false,
    "progress": 0.0,
    "expiresAt": "2025-01-15T23:59:59"
  }
}
```

**Реализация:**
- Файл: `routers/quests/quests.py`
- Сервис: `services/quests/quests_service.py` (функция `update_quest`)
- Схемы: `schemas/quests.py` (UpdateQuestRequest, UpdateQuestResponse)

**Особенности:**
- При обновлении списка сотрудников старые `UserReward` удаляются и создаются новые
- Если не указаны сотрудники, список не изменяется

---

### 3.4. DELETE /quests/{quest_id}

**Описание:** Удаление квеста.

**Параметры:**
- `quest_id` (path): ID квеста.

**Ответ:**
```json
{
  "success": true,
  "message": "Quest deleted successfully"
}
```

**Реализация:**
- Файл: `routers/quests/quests.py`
- Сервис: `services/quests/quests_service.py` (функция `delete_quest`)
- Схемы: `schemas/quests.py` (DeleteQuestResponse)

**Особенности:**
- При удалении квеста также удаляются все связанные записи `UserReward`

---

## Структура файлов

### Новые файлы:

1. **`services/reports/personnel_service.py`**
   - Сервис для отчетов по персоналу
   - Функция: `get_personnel_report()`

2. **`services/fines/fines_service.py`**
   - Сервис для работы со штрафами
   - Функции: `get_fines_summary()`, `update_fine()`, `delete_fine()`

3. **`services/fines/__init__.py`**
   - Инициализация модуля штрафов

### Обновленные файлы:

1. **`routers/reports/reports.py`**
   - Добавлен эндпоинт `GET /reports/personnel`

2. **`routers/employees/employees.py`**
   - Добавлены эндпоинты:
     - `GET /employees/summary`
     - `GET /employees/{employee_id}/summary`
     - `GET /employees/{employee_id}/details`
     - `GET /employees/{employee_id}/open-check`
     - `GET /employees/{employee_id}/closed-tables-history`
     - `GET /fines/summary`
     - `PUT /fines/{fine_id}`
     - `DELETE /fines/{fine_id}`

3. **`routers/quests/quests.py`**
   - Добавлены эндпоинты:
     - `GET /quests/active`
     - `GET /quests/{quest_id}/progress`
     - `PUT /quests/{quest_id}`
     - `DELETE /quests/{quest_id}`

4. **`services/employees/employees_service.py`**
   - Добавлены функции:
     - `get_employees_summary()`
     - `get_employee_summary()`
     - `get_employee_details()`
     - `get_employee_open_check()`
     - `get_employee_closed_tables_history()`

5. **`services/quests/quests_service.py`**
   - Добавлены функции:
     - `get_active_quests()`
     - `update_quest()`
     - `delete_quest()`

6. **`schemas/reports.py`**
   - Добавлены схемы:
     - `PersonnelEmployeeItem`
     - `PersonnelReportResponse`

7. **`schemas/employees.py`**
   - Добавлены схемы:
     - `EmployeeSummaryItem`
     - `EmployeesSummaryResponse`
     - `EmployeeSummaryResponse`
     - `EmployeeTableItem`
     - `EmployeeDetailsResponse`
     - `EmployeeCheckItem`
     - `EmployeeOpenCheckResponse`
     - `EmployeeClosedTableItem`
     - `EmployeeClosedTablesHistoryResponse`

8. **`schemas/fines.py`**
   - Добавлены схемы:
     - `FineItem`
     - `FinesSummaryResponse`
     - `UpdateFineRequest`
     - `UpdateFineResponse`
     - `DeleteFineResponse`

9. **`schemas/quests.py`**
   - Добавлены схемы:
     - `UpdateQuestRequest`
     - `UpdateQuestResponse`
     - `DeleteQuestResponse`

---

## Технические детали

### Источники данных:

1. **Заказы и чеки:**
   - Основной источник: `DOrder` (через `user_id`)
   - Альтернативный источник: `Sales` (через `waiter_name_id` или `order_waiter_id`)

2. **Смены:**
   - Таблица: `Shift`
   - Определение активной смены: `end_time IS NULL OR end_time > NOW()`

3. **Столы и помещения:**
   - Таблица: `Table` (связь через `number` из `DOrder.tab_name` или `Sales.table_num`)
   - Таблица: `RestaurantSection` (помещения)

4. **Штрафы:**
   - Таблица: `Penalty`
   - Связь с сотрудниками через `employee_id`

5. **Квесты:**
   - Таблица: `Reward`
   - Прогресс сотрудников: `UserReward`

### Форматы дат:

- **Query параметры:** `DD.MM.YYYY` (например, "15.01.2025")
- **ISO формат:** `YYYY-MM-DDTHH:mm:ssZ` или `YYYY-MM-DDTHH:mm:ss` (для `dateTime`)
- **Время:** `HH:mm` (например, "09:30")
- **Длительность:** `HH:mm:ss` (например, "08:30:00")

### Обработка ошибок:

- Все эндпоинты используют try-except блоки
- HTTPException с кодом 404 для несуществующих ресурсов
- HTTPException с кодом 500 для внутренних ошибок
- Логирование всех ошибок через `logger.error()`

### Фильтрация по организации:

- Все эндпоинты поддерживают опциональный параметр `organization_id`
- Фильтрация происходит через:
  - `Employees.preferred_organization_id`
  - `DOrder.organization_id`
  - `Sales.organization_id`

---

## Примеры использования

### Получить отчет по персоналу за последний месяц:
```bash
GET /reports/personnel?from_date=01.12.2024&to_date=31.12.2024
```

### Получить сводку по активным сотрудникам:
```bash
GET /employees/summary?date=15.01.2025
```

### Получить детали сотрудника:
```bash
GET /employees/1/details?date=15.01.2025
```

### Получить открытый чек сотрудника:
```bash
GET /employees/1/open-check?dateTime=2025-01-15T14:30:00Z
```

### Получить историю закрытых столиков:
```bash
GET /employees/1/closed-tables-history?from_date=01.01.2025&to_date=31.01.2025
```

### Получить сводку штрафов:
```bash
GET /fines/summary?date=15.01.2025
```

### Обновить штраф:
```bash
PUT /fines/1
Body: {"amount": 5000, "reason": "Новая причина"}
```

### Получить активные квесты:
```bash
GET /quests/active?date=15.01.2025
```

### Обновить квест:
```bash
PUT /quests/1
Body: {"target": 20, "reward": 20000}
```

---

## Зависимости

Все эндпоинты используют следующие модели:
- `models.employees.Employees` - сотрудники
- `models.shifts.Shift` - смены
- `models.d_order.DOrder` - заказы
- `models.sales.Sales` - продажи
- `models.penalty.Penalty` - штрафы
- `models.rewards.Reward` - квесты/награды
- `models.user_reward.UserReward` - прогресс сотрудников по квестам
- `models.user.User` - пользователи системы
- `models.tables.Table` - столы
- `models.restaurant_sections.RestaurantSection` - помещения
- `models.roles.Roles` - роли
- `models.item.Item` - блюда/товары

---

## Статус реализации

✅ Все 13 эндпоинтов реализованы и протестированы на отсутствие ошибок линтера.

**Дата реализации:** 2025-01-19

