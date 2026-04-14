# API Reference

Полная документация по всем эндпоинтам backend API для системы управления ресторанами на базе iiko.

---

## Содержание

1. [Общая информация](#общая-информация)
2. [Таблица ID сущностей](#таблица-id-сущностей)
3. [Аутентификация](#1-аутентификация)
4. [Профиль](#2-профиль)
5. [Сотрудники и штрафы](#3-сотрудники-и-штрафы)
6. [Заказы](#4-заказы)
7. [Смены](#5-смены)
8. [Квесты](#6-квесты)
9. [Задачи](#7-задачи)
10. [Зарплата](#8-зарплата)
11. [Аналитика](#9-аналитика)
12. [Отчёты](#10-отчёты)
13. [Расходы](#11-расходы)
14. [Организации](#12-организации)
15. [Меню](#13-меню)
16. [Товары](#14-товары)
17. [Залы и столы](#15-залы-и-столы)
18. [Популярные блюда](#16-популярные-блюда)
19. [P&L отчёт](#17-pl-отчёт)
20. [Концепции и поставщики](#18-концепции-и-поставщики)
21. [Департаменты](#19-департаменты)
22. [Документы](#20-документы)
23. [Склад](#21-склад)
24. [Кэш](#22-кэш)
25. [DB индексы](#23-db-индексы)
26. [iiko Sync (админ)](#24-iiko-sync-админ)

---

## Общая информация

### Авторизация

Большинство эндпоинтов требуют JWT Bearer token:
- **Header:** `Authorization: Bearer <token>`
- **Query param (альтернатива):** `?token=<token>`

Токен выдаётся при `/login` или `/register`, срок действия — **5 дней**.

Исключения (без авторизации):
- `POST /login`
- `POST /register`
- `POST /sync/cron/sync` (аутентификация по `apikey` query param)
- `POST /sync/cron/daily-sync` (аутентификация по `apikey` query param)
- `POST /db/*` (эндпоинты управления индексами)

### Формат дат

| Контекст | Формат | Пример |
|----------|--------|--------|
| Query параметры (большинство) | DD.MM.YYYY | `01.03.2026` |
| Query параметры (sync/admin) | YYYY-MM-DD | `2026-03-01` |
| Timestamps в ответах | ISO 8601 | `2026-03-01T12:00:00` |
| Время смены | HH:mm | `09:30` |
| Длительность | HH:mm:ss | `08:30:00` |

### Стандартный формат ответа

Большинство эндпоинтов возвращают:
```json
{
  "success": true,
  "message": "описание результата",
  ...дополнительные поля
}
```

### Обработка ошибок

- **400** — Некорректный запрос (неправильный формат даты, невалидные параметры)
- **401** — Не авторизован (невалидный или просроченный токен)
- **404** — Ресурс не найден
- **500** — Внутренняя ошибка сервера

> **Важно:** `/login` и `/register` возвращают HTTP 200 даже при ошибке (с `success: false`), а не 401.

### Пагинация

Эндпоинты со списками поддерживают пагинацию через `limit` и `offset`:
- `limit` — количество записей (обычно default=100, max=1000 или 5000)
- `offset` — смещение (default=0)

---

## Таблица ID сущностей

| Сущность | Внутренний ID | iiko ID | Примечания |
|----------|--------------|---------|------------|
| Organization | `id` (int) | `iiko_id` (str), `iiko_id_cloud` (str) | Cloud и Server API используют разные UUID |
| Employee | `id` (int) | `iiko_id` (str) | User связан через общий `iiko_id` |
| User | `id` (int) | `iiko_id` (str) | Связь User ↔ Employee через `iiko_id` |
| DOrder (заказ) | `id` (int) | `iiko_id` (str) | iiko_id заполняется после синхронизации |
| Item (товар) | `id` (int) | `iiko_id` (str) | Используется в документах |
| Shift | `id` (int) | `iiko_id` (str) | |
| Table (стол) | `id` (int) | `iiko_id` (str) | |
| Room (зал) | `id` (int) | `iiko_id` (str) | |
| Quest | `id` (int) | — | Только внутренний ID |
| Penalty (штраф) | `id` (int) | — | Только внутренний ID |
| Task (задача) | `id` (int) | — | Только внутренний ID |
| Account (счёт) | `id` (int) | `iiko_id` (str) | |
| Department | `id` (int) | `iiko_id` (str) | |
| Conception | `id` (int) | `iiko_id` (str) | |
| Supplier | `id` (int) | `iiko_id` (str) | |
| Store (склад) | `id` (int) | `iiko_id` (str) | |
| Expense | `id` (int) | — | Только внутренний ID |
| WarehouseDocument | `id` (int) | `iiko_id` (str) | |

> **Ключевое правило:** В API запросах/ответах используются **внутренние ID** (int), если не указано иное. Система сама конвертирует внутренние ID в iiko UUID при необходимости.

---

## 1. Аутентификация

**Файл:** `routers/auth/auth.py` | **Теги:** auth

### POST /login

**Авторизация:** Нет

Авторизация пользователя. Возвращает JWT токен.

**Request Body** (`LoginRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `login` | string | Да | Логин пользователя |
| `password` | string | Да | Пароль пользователя |

**Response** (`LoginResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат операции |
| `message` | string | Описание результата |
| `user_id` | int \| null | Внутренний ID пользователя |
| `access_token` | string \| null | JWT токен (срок действия 5 дней) |
| `token_type` | string \| null | Тип токена (`"bearer"`) |
| `role` | string \| null | Роль пользователя |
| `name` | string \| null | Имя сотрудника |

**Заметки по ID:** `user_id` — внутренний ID из таблицы `users`.

**Возможные ошибки:**
- HTTP 200 с `success: false` — неверный логин/пароль (НЕ 401)

---

### POST /register

**Авторизация:** Нет

Регистрация нового пользователя.

**Request Body** (`LoginRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `login` | string | Да | Логин нового пользователя |
| `password` | string | Да | Пароль |

**Response** (`LoginResponse`): Аналогично `/login`.

**Заметки по ID:** `user_id` — внутренний ID созданного пользователя.

**Возможные ошибки:**
- HTTP 200 с `success: false` — пользователь с таким логином уже существует

---

### PUT /change-password

**Авторизация:** Да (manager или owner)

Сменить пароль сотруднику по его `employee_id`.

**Request Body** (`ChangePasswordRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `employee_id` | int | Да | **Внутренний** ID сотрудника (Employee.id) |
| `new_password` | string | Да | Новый пароль |

**Response:**

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат операции |
| `message` | string | Описание результата |

**Заметки по ID:** `employee_id` — внутренний ID. Цепочка поиска: `Employee.id` → `Employee.iiko_id` → `User.iiko_id` → обновление пароля User.

**Возможные ошибки:**
- 404 — Сотрудник не найден
- 404 — У сотрудника нет учётной записи
- 500 — Ошибка при смене пароля

---

## 2. Профиль

**Файл:** `routers/profile/profile.py` | **Теги:** profile

### GET /profile

**Авторизация:** Да

Получить профиль текущего пользователя (по токену).

**Response** (`UserProfileResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `id` | int | Внутренний ID пользователя |
| `name` | string \| null | Имя |
| `login` | string | Логин |
| `role` | string \| null | Роль |
| `organization_id` | int \| null | ID организации |
| `employee_id` | int \| null | Внутренний ID связанного сотрудника |
| `stats` | object \| null | Статистика: `shiftDuration`, `totalAmount`, `ordersCount` |

**Заметки по ID:** `id` — User.id (внутренний), `employee_id` — Employee.id (внутренний).

---

### GET /users/{user_id}/profile

**Авторизация:** Да

Получить профиль пользователя по userId (для владельца/менеджера).

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `user_id` | int | **Внутренний** ID пользователя (User.id) |

**Response:** Аналогично `GET /profile`.

**Возможные ошибки:**
- 404 — Пользователь не найден

---

## 3. Сотрудники и штрафы

**Файл:** `routers/employees/employees.py` | **Теги:** employees

### GET /employees

**Авторизация:** Да

Получить список сотрудников с информацией о текущих сменах.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `name` | string | Нет | Фильтр по имени |
| `login` | string | Нет | Фильтр по логину |
| `organization_id` | int | Нет | **Внутренний** ID организации |
| `role_code` | string | Нет | Фильтр по коду роли |
| `deleted` | bool | Нет | Фильтр по удалённым |
| `status` | string | Нет | Фильтр по статусу |
| `date` | string | Нет | Дата (DD.MM.YYYY) |
| `limit` | int | Нет | Лимит (0-5000, default=100) |
| `offset` | int | Нет | Смещение (default=0) |

**Response** (`EmployeeWithShiftsArrayResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `employees` | array | Список сотрудников |

Каждый сотрудник:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | Внутренний ID |
| `name` | string | Имя |
| `deleted` | bool | Удалён ли |
| `role` | string | Роль |
| `avatarUrl` | string | URL аватара |
| `totalAmount` | string | Сумма продаж |
| `shiftTime` | string | Время начала смены |
| `isActive` | bool | Активна ли смена |

---

### POST /fines

**Авторизация:** Да

Создать штраф для сотрудника.

**Request Body** (`CreateFineRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `employeeId` | string | Да | **Внутренний** ID сотрудника |
| `employeeName` | string | Да | Имя сотрудника |
| `reason` | string | Да | Причина штрафа |
| `amount` | float | Да | Сумма штрафа |
| `date` | string | Да | Дата (DD.MM.YYYY) |

**Response** (`CreateFineResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `fine_id` | int | Внутренний ID созданного штрафа |

**Заметки по ID:** `employeeId` — внутренний ID. Цепочка: `Employee.id` → `Employee.iiko_id` → `User.iiko_id` для связи штрафа с пользователем.

---

### PUT /employees/{employee_id}/shift-time

**Авторизация:** Да

Обновить время смены сотрудника (start_time последней смены за сегодня).

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `employee_id` | int | **Внутренний** ID сотрудника |

**Request Body** (`UpdateShiftTimeRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `shiftTime` | string | Да | Новое время (формат HH:mm) |

**Response** (`UpdateShiftTimeResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |

---

### GET /employees/summary

**Авторизация:** Да

Получить сводку по сотрудникам — количество с открытой сменой и сумма чеков.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date` | string | Нет | Дата (DD.MM.YYYY, default=сегодня) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`EmployeesSummaryResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `activeEmployeesCount` | int | Количество активных сотрудников |
| `totalAmount` | float | Общая сумма |
| `employees` | array | Список: `id` (int), `name` (string), `amount` (float) |

---

### GET /employees/{employee_id}/summary

**Авторизация:** Да

Получить сводку по конкретному сотруднику.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `employee_id` | int | **Внутренний** ID сотрудника |

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date` | string | Нет | Дата (DD.MM.YYYY) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`EmployeeSummaryResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | Внутренний ID |
| `firstName` | string | Имя |
| `lastName` | string | Фамилия |
| `name` | string | Полное имя |
| `shiftDuration` | string | Длительность смены (HH:mm:ss) |
| `totalAmount` | float | Сумма продаж |
| `ordersCount` | int | Количество заказов |

---

### GET /employees/{employee_id}/details

**Авторизация:** Да

Получить детали сотрудника — смена, чеки и столы с открытыми заказами.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `employee_id` | int | **Внутренний** ID сотрудника |

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `table_id` | int | Нет | Фильтр по столу |
| `date` | string | Нет | Дата (DD.MM.YYYY) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`EmployeeDetailsResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `shiftDuration` | string | Длительность смены |
| `totalAmount` | float | Общая сумма |
| `ordersCount` | int | Количество заказов |
| `tables` | array | Столы: `id`, `number`, `roomName`, `orderId`, `amount` |

---

### GET /employees/{employee_id}/open-check

**Авторизация:** Да

Получить детали открытого счёта сотрудника — содержимое чека.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `employee_id` | int | **Внутренний** ID сотрудника |

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `dateTime` | string | Да | Дата и время (ISO: YYYY-MM-DDTHH:mm:ssZ) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`EmployeeOpenCheckResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `orderId` | string | ID заказа |
| `tableId` | int | ID стола |
| `tableNumber` | string | Номер стола |
| `roomName` | string | Название зала |
| `items` | array | Позиции: `name`, `quantity`, `price`, `total` |
| `totalAmount` | float | Итоговая сумма |
| `status` | string | Статус заказа |

---

### GET /employees/{employee_id}/closed-tables-history

**Авторизация:** Да

История закрытых столиков сотрудника — список чеков и суммы.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `employee_id` | int | **Внутренний** ID сотрудника |

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `from_date` | string | Нет | Начало периода (DD.MM.YYYY, default=30 дней назад) |
| `to_date` | string | Нет | Конец периода (DD.MM.YYYY, default=сегодня) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`EmployeeClosedTablesHistoryResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `orders` | array | Закрытые заказы |

Каждый заказ:

| Поле | Тип | Описание |
|------|-----|----------|
| `orderId` | string | ID заказа |
| `tableId` | int | ID стола |
| `tableNumber` | string | Номер стола |
| `roomName` | string | Зал |
| `closedAt` | string | Время закрытия (ISO) |
| `totalAmount` | float | Сумма |
| `itemsCount` | int | Количество позиций |

---

### GET /fines/summary

**Авторизация:** Да

Получить сводку всех штрафов за текущий день.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date` | string | Нет | Дата (DD.MM.YYYY, default=сегодня) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`FinesSummaryResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `fines` | array | Список штрафов |

Каждый штраф:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | Внутренний ID штрафа |
| `employeeId` | int | Внутренний ID сотрудника |
| `employeeName` | string | Имя |
| `amount` | float | Сумма |
| `reason` | string | Причина |
| `date` | string | Дата |
| `createdAt` | string | Дата создания (ISO) |

---

### PUT /fines/{fine_id}

**Авторизация:** Да

Изменить штраф сотруднику.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `fine_id` | int | **Внутренний** ID штрафа |

**Request Body** (`UpdateFineRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `amount` | float | Нет | Новая сумма |
| `reason` | string | Нет | Новая причина |

**Response** (`UpdateFineResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `fine_id` | int | ID изменённого штрафа |

---

### DELETE /fines/{fine_id}

**Авторизация:** Да

Удалить штраф сотрудника.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `fine_id` | int | **Внутренний** ID штрафа |

**Response** (`DeleteFineResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |

---

### POST /employees/create-users

**Авторизация:** Да (manager или owner)

Создать учётные записи для всех сотрудников, у которых нет пользователя. Логин = имя сотрудника, пароль — случайный (8 символов).

**Request Body:** Нет

**Response:**

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `count` | int | Количество созданных пользователей |
| `users` | array | Список с логинами и паролями (для передачи менеджеру) |

---

## 4. Заказы

**Файл:** `routers/orders/order.py` | **Теги:** orders

### GET /orders

**Авторизация:** Да

Получить список заказов.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | int | Нет | **Внутренний** ID организации |
| `user_id` | int | Нет | **Внутренний** ID пользователя |
| `state` | string | Нет | Статус заказа |
| `date` | string | Нет | Дата |
| `limit` | int | Нет | Лимит (1-1000, default=100) |
| `offset` | int | Нет | Смещение (default=0) |

**Response** (`OrderArrayResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `orders` | array | Список заказов |

Каждый заказ:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | Внутренний ID заказа |
| `organization_name` | string | Название организации |
| `table` | int | Номер стола |
| `room` | string | Зал |
| `status` | string | Статус |
| `sum_order` | float | Сумма заказа |
| `final_sum` | float | Итоговая сумма |
| `bank_commission` | float | Банковская комиссия |
| `items` | array | Позиции заказа |

---

### POST /orders

**Авторизация:** Да

Создать новый заказ. Все ID в теле запроса — **внутренние**. Система автоматически конвертирует их в iiko UUID.

**Request Body** (`CreateOrderRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `organizationId` | int | Нет | **Внутренний** ID организации |
| `tableId` | int | Нет | **Внутренний** ID стола → конвертируется в iiko_id |
| `waiterId` | int | Нет | **Внутренний** ID сотрудника → конвертируется в iiko_id |
| `guests` | int | Нет | Количество гостей |
| `items` | array | Да | Позиции заказа |
| `comment` | string | Нет | Комментарий |

Каждая позиция (`CreateOrderItemRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `productId` | int | Да | **Внутренний** ID товара → конвертируется в iiko_id |
| `amount` | float | Да | Количество (> 0) |
| `price` | float | Да | Цена за единицу (>= 0) |
| `sum` | float | Да | Сумма позиции (>= 0) |
| `comment` | string | Нет | Комментарий к позиции |

**Response** (`CreateOrderResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `order_id` | int | **Внутренний** ID созданного заказа |
| `iiko_id` | string \| null | UUID заказа в iiko (может быть null до синхронизации) |
| `iiko_correlation_id` | string \| null | Correlation ID из iiko |
| `iiko_number` | string \| null | Номер заказа в iiko |
| `iiko_full_sum` | float \| null | Полная сумма из iiko |

**Заметки по ID:** `organizationId`, `tableId`, `waiterId`, `productId` — ВСЕ внутренние ID. Система конвертирует в iiko_id автоматически.

---

### POST /orders/{order_id}/pay

**Авторизация:** Да

Оплатить заказ. Меняет статус с CREATED на PAID. Если `IIKO_SEND_ORDERS` включён — закрывает заказ в iiko.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `order_id` | int | **Внутренний** ID заказа |

**Response** (`PayOrderResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `order_id` | int | ID заказа |
| `status` | string | Новый статус |

**Возможные ошибки:**
- 404 — Заказ не найден
- 400 — Заказ уже оплачен или отменён

---

### PUT /orders/{order_id}

**Авторизация:** Да

Обновить заказ. Можно менять только заказы со статусом CREATED. Позиции полностью заменяются.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `order_id` | int | **Внутренний** ID заказа |

**Request Body** (`UpdateOrderRequest`): Все поля опциональны, аналогично `CreateOrderRequest`.

**Response** (`UpdateOrderResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `order_id` | int | ID обновлённого заказа |

**Возможные ошибки:**
- 404 — Заказ не найден
- 400 — Нельзя редактировать заказ (не в статусе CREATED)

---

### POST /orders/{order_id}/cancel

**Авторизация:** Да

Отменить заказ. Можно отменить только неоплаченные заказы.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `order_id` | int | **Внутренний** ID заказа |

**Request Body** (`CancelOrderRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `reason` | string | Нет | Причина отмены |

**Response** (`CancelOrderResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `order_id` | int | ID заказа |
| `status` | string | Новый статус (CANCELLED) |

---

## 5. Смены

**Файл:** `routers/shifts/shifts.py` | **Теги:** shifts

### GET /shifts

**Авторизация:** Да

Получить информацию о сменах: время, количество сотрудников, выручка, штрафы, квесты.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date` | string | Нет | Дата (DD.MM.YYYY, default=сегодня) |
| `employee_id` | int | Нет | **Внутренний** ID сотрудника |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`ShiftResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | string | ID смены |
| `date` | string | Дата |
| `startTime` | string | Время начала |
| `endTime` | string \| null | Время окончания |
| `elapsedTime` | string | Прошедшее время |
| `openEmployees` | int | Количество сотрудников на смене |
| `totalAmount` | float | Общая сумма |
| `finesCount` | int | Количество штрафов |
| `motivationCount` | int | Мотивации |
| `questsCount` | int | Квесты |
| `status` | string | Статус |

---

### GET /waiter/{waiter_id}/shift/status

**Авторизация:** Да

Получить статус смены официанта: активна ли, время начала, прошедшее время.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `waiter_id` | int | **Внутренний** ID сотрудника (Employee.id) |

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`ShiftStatusResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `isActive` | bool | Активна ли смена |
| `shiftId` | string \| null | ID смены |
| `startTime` | string \| null | Время начала |
| `elapsedTime` | string \| null | Прошедшее время |

---

### POST /waiter/{waiter_id}/shift/start

**Авторизация:** Да

Начать смену официанта. Если смена уже активна — возвращает существующий ID. Также выполняет clockin в iiko.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `waiter_id` | int | **Внутренний** ID сотрудника |

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | int | Нет | ID организации (для будущего использования) |

**Response** (`StartShiftResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `shiftId` | int | Внутренний ID смены |

---

### POST /waiter/{waiter_id}/shift/end

**Авторизация:** Да

Завершить смену официанта. Устанавливает `end_time` на текущее время. Выполняет clockout в iiko.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `waiter_id` | int | **Внутренний** ID сотрудника |

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | int | Нет | ID организации (для будущего использования) |

**Response** (`EndShiftResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `shiftId` | int | ID завершённой смены |
| `startTime` | string | Время начала |
| `endTime` | string | Время окончания |

---

## 6. Квесты

**Файл:** `routers/quests/quests.py` | **Теги:** quests

### GET /waiter/{waiter_id}/quests

**Авторизация:** Да

Получить квесты официанта на определённую дату с прогрессом выполнения.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `waiter_id` | int | **Внутренний** ID сотрудника |

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date` | string | Нет | Дата (DD.MM.YYYY, default=сегодня) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`QuestsArrayResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `quests` | array | Список квестов |

Каждый квест (`QuestResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | string | ID квеста (строка) |
| `title` | string | Название |
| `description` | string | Описание |
| `reward` | float | Награда |
| `current` | int | Текущий прогресс |
| `target` | int | Цель |
| `unit` | string | Единица измерения |
| `completed` | bool | Выполнен ли |
| `progress` | float | Прогресс (0-1) |
| `expiresAt` | string | Дата окончания (ISO) |

---

### POST /quests

**Авторизация:** Да (CEO)

Создать новый квест.

**Request Body** (`CreateQuestRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `title` | string | Да | Название квеста |
| `description` | string | Нет | Описание |
| `reward` | float | Да | Награда |
| `target` | int | Да | Целевое значение |
| `unit` | string | Да | Единица измерения |
| `date` | string | Да | Дата (DD.MM.YYYY) |
| `employeeIds` | array[string] | Нет | **Внутренние** ID сотрудников |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`CreateQuestResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `quest` | object | Созданный квест (QuestResponse) |

---

### GET /quests/active

**Авторизация:** Да

Получить список активных квестов.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date` | string | Нет | Дата (DD.MM.YYYY, default=сегодня) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`QuestsArrayResponse`): Аналогично `GET /waiter/{waiter_id}/quests`.

---

### GET /quests/{quest_id}

**Авторизация:** Да

Получить детальную информацию о квесте (для CEO) с прогрессом всех сотрудников.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `quest_id` | int | **Внутренний** ID квеста |

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`QuestDetailResponse`): Расширяет QuestResponse полями:

| Поле | Тип | Описание |
|------|-----|----------|
| `totalEmployees` | int | Всего сотрудников |
| `completedEmployees` | int | Выполнивших квест |
| `employeeNames` | array[string] | Имена сотрудников |
| `date` | string | Дата |
| `employeeProgress` | array | Прогресс каждого сотрудника |

---

### GET /quests/{quest_id}/progress

**Авторизация:** Да

Получить квест с расширенным списком прогресса каждого сотрудника.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `quest_id` | int | **Внутренний** ID квеста |

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`QuestDetailResponse`): Аналогично `GET /quests/{quest_id}`.

---

### PUT /quests/{quest_id}

**Авторизация:** Да

Изменить квест. Все поля опциональны.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `quest_id` | int | **Внутренний** ID квеста |

**Request Body** (`UpdateQuestRequest`): Все поля опциональны, аналогично `CreateQuestRequest`.

**Response** (`UpdateQuestResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `quest` | object | Обновлённый квест |

---

### DELETE /quests/{quest_id}

**Авторизация:** Да

Удалить квест.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `quest_id` | int | **Внутренний** ID квеста |

**Response** (`DeleteQuestResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |

---

## 7. Задачи

**Файл:** `routers/tasks/tasks.py` | **Теги:** tasks

### GET /tasks

**Авторизация:** Да

Получить список задач с опциональной фильтрацией.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | int | Нет | **Внутренний** ID организации |
| `user_id` | int | Нет | **Внутренний** ID пользователя |
| `due_date` | string | Нет | Дата (DD.MM.YYYY) |

**Response** (`TaskListResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `tasks` | array | Список задач |

Каждая задача (`TaskResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | Внутренний ID задачи |
| `title` | string | Заголовок |
| `description` | string | Описание |
| `user_id` | int | ID пользователя-исполнителя |
| `user_name` | string \| null | Имя исполнителя |
| `organization_id` | int \| null | ID организации |
| `is_completed` | bool | Выполнена ли |
| `due_date` | string \| null | Срок |
| `created_at` | string \| null | Дата создания |

---

### POST /tasks

**Авторизация:** Да

Создать новую задачу.

**Request Body** (`CreateTaskRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `title` | string | Нет | Заголовок |
| `description` | string | Да | Описание задачи |
| `user_id` | int | Да | **Внутренний** ID исполнителя (User.id) |
| `organization_id` | int | Нет | **Внутренний** ID организации |
| `due_date` | string | Нет | Срок (DD.MM.YYYY) |

**Response** (`CreateTaskResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `task` | object | Созданная задача (TaskResponse) |

---

### POST /tasks/{task_id}/complete

**Авторизация:** Да

Переключить статус выполнения задачи (complete/uncomplete).

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `task_id` | int | **Внутренний** ID задачи |

**Response** (`CompleteTaskResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `task` | object | Обновлённая задача |

**Возможные ошибки:**
- 404 — Задача не найдена

---

## 8. Зарплата

**Файл:** `routers/salary/salary.py` | **Теги:** salary

### GET /waiter/{waiter_id}/salary

**Авторизация:** Да

Получить зарплату официанта за день — оклад, бонусы, штрафы, награды за квесты.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `waiter_id` | int | **Внутренний** ID сотрудника (Employee.id) |

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date` | string | Да | Дата (DD.MM.YYYY) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`SalaryResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `date` | string | Дата |
| `tablesCompleted` | int | Закрытых столов |
| `totalRevenue` | float | Общая выручка |
| `salary` | float | Итоговая зарплата |
| `salaryPercentage` | float | Процент от продаж |
| `bonuses` | float | Бонусы |
| `questBonus` | float | Бонус за квесты |
| `questDescription` | string | Описание квеста |
| `penalties` | float | Штрафы |
| `totalEarnings` | float | Итого заработок |
| `breakdown` | object | Детализация: baseSalary, percentage, bonuses, penalties, questRewards |
| `quests` | array | Квесты за день |

**Возможные ошибки:**
- 404 — Официант не найден или некорректная дата

---

### GET /waiter/{waiter_id}/sales-today

**Авторизация:** Да

Получить сумму продаж официанта за день и количество чеков.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `waiter_id` | int | **Внутренний** ID сотрудника |

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date` | string | Нет | Дата (DD.MM.YYYY, default=сегодня) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`WaiterSalesResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `date` | string | Дата |
| `totalAmount` | float | Сумма продаж |
| `ordersCount` | int | Количество чеков |

---

## 9. Аналитика

**Файл:** `routers/analytics/analytics.py` | **Теги:** reports

### GET /analytics

**Авторизация:** Да

Получить аналитику (для CEO): выручка, чеки, средний чек, расходы, доходы, заказы, финансы, запасы, топ сотрудников.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date` | string | Нет | Дата (DD.MM.YYYY) |
| `period` | string | Нет | Период: `day` \| `week` \| `month` (default=`day`) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`AnalyticsResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `metrics` | array | Основные метрики: id, label, value, change |
| `reports` | array | Отчёты: id, title, value, date, type |
| `orders` | array | Метрики заказов |
| `financial` | array | Финансовые метрики |
| `inventory` | array | Запасы |
| `employees` | array | Топ сотрудников: id, name, amount, avatar, average_check, checks_count, returns_count |

---

### POST /recalculate-employee-metrics

**Авторизация:** Да

Пересчитать таблицу `daily_employee_analytics` за период.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `from_date` | string | Нет | Начало периода (**YYYY-MM-DD**) |
| `to_date` | string | Нет | Конец периода (**YYYY-MM-DD**, default=сегодня) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

> **Внимание:** Формат дат здесь — YYYY-MM-DD, а не DD.MM.YYYY.

**Response:**

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `data` | object | `dates_processed`, `total_employees_processed`, `errors` |

---

## 10. Отчёты

**Файл:** `routers/reports/reports.py` | **Префикс:** `/reports` | **Теги:** reports

### GET /reports/orders

**Авторизация:** Да

Получить отчёты по заказам: средний чек, возвраты, средние показатели, популярные блюда.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date` | string | Да | Дата (DD.MM.YYYY) |
| `period` | string | Нет | `day` \| `week` \| `month` (default=`day`) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`OrderReportsResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `checks` | object | Метрика чеков: id, label, value, type |
| `returns` | object | Метрика возвратов |
| `averages` | array | Средние показатели с трендами |

---

### GET /reports/moneyflow

**Авторизация:** Да

Получить денежные отчёты: себестоимость блюд, списания, расходы, доходы.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date` | string | Да | Дата (DD.MM.YYYY) |
| `period` | string | Нет | `day` \| `week` \| `month` (default=`day`) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`MoneyFlowResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `dishes` | object | Себестоимость: label, value, data (name, amount, quantity) |
| `writeoffs` | object | Списания: label, value, data (item, quantity, reason) |
| `expenses` | object | Расходы: label, value, type, data (reason, amount, date) |
| `incomes` | object | Доходы: label, value, income_by_category, income_by_pay_type |

---

### GET /reports/sales-dynamics

**Авторизация:** Да

Получить динамику продаж за последние N дней.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `days` | int | Нет | Количество дней (default=7) |
| `date` | string | Нет | Дата (DD.MM.YYYY) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

> Фильтрует продажи: исключает `cashier = 'Удаление позиций'` и `order_deleted = 'DELETED'`.

**Response** (`SalesDynamicsResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `total_revenue` | float | Общая выручка |
| `total_checks` | int | Всего чеков |
| `overall_average_check` | float | Средний чек |
| `daily_data` | array | По дням: `date`, `revenue`, `checks_count`, `average_check` |

---

### GET /reports/personnel

**Авторизация:** Да

Получить отчёт по персоналу за период.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `from_date` | string | Нет | Начало (DD.MM.YYYY, default=30 дней назад) |
| `to_date` | string | Нет | Конец (DD.MM.YYYY, default=сегодня) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`PersonnelReportResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `employees` | array | Сотрудники: `id`, `name`, `role`, `totalAmount`, `ordersCount`, `shiftDuration` (HH:mm:ss) |

---

## 11. Расходы

**Файлы:** `routers/expenses/expenses.py` | **Два роутера:**
- Аналитика: **префикс** `/reports` | **теги:** reports
- Управление: **префикс** `/expenses` | **теги:** expenses

### GET /reports/expenses

**Авторизация:** Да

Получить аналитику по расходам: суммы и транзакции по типам счетов (EXPENSES, EQUITY, EMPLOYEES_LIABILITY, DEBTS_OF_EMPLOYEES).

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date` | string | Нет | Дата (DD.MM.YYYY) |
| `period` | string | Нет | `day` \| `week` \| `month` (default=`day`) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`ExpensesAnalyticsResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `expenses_amount` | float | Общая сумма расходов |
| `data` | array | Расходы по типам: `transaction_type`, `transaction_name`, `transaction_amount`, `transactions[]` |

---

### POST /expenses

**Авторизация:** Да

Создать расход. Также пытается синхронизировать с iiko через `create_pay_out_in_iiko()`.

**Request Body** (`CreateExpenseRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `organization_id` | int | Нет | **Внутренний** ID организации |
| `expense_type` | string | Да | UUID типа расхода (из iiko) |
| `amount` | float | Да | Сумма |
| `date` | string | Да | Дата (DD.MM.YYYY) |
| `comment` | string | Нет | Комментарий |
| `account_id` | string | Нет | ID счёта |

**Response** (`CreateExpenseResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `expense_id` | int | Внутренний ID созданного расхода |

**Заметки по ID:** `expense_type` — UUID из iiko (не внутренний ID).

---

### GET /expenses

**Авторизация:** Да

Получить список расходов с фильтрацией.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | int | Нет | **Внутренний** ID организации |
| `expense_type` | string | Нет | Тип расхода |
| `from_date` | string | Нет | Начало (DD.MM.YYYY) |
| `to_date` | string | Нет | Конец (DD.MM.YYYY) |
| `limit` | int | Нет | Лимит (default=100) |
| `offset` | int | Нет | Смещение (default=0) |

**Response** (`ExpensesListResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `expenses` | array | Список расходов |
| `total` | float | Общая сумма |

---

### GET /expenses/{expense_id}

**Авторизация:** Да

Получить детали расхода.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `expense_id` | int | **Внутренний** ID расхода |

**Response** (`ExpenseDetailResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `expense` | object | Детали расхода |

**Возможные ошибки:** 404 — Расход не найден

---

### PUT /expenses/{expense_id}

**Авторизация:** Да

Обновить расход.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `expense_id` | int | **Внутренний** ID расхода |

**Request Body** (`UpdateExpenseRequest`): Все поля опциональны, аналогично `CreateExpenseRequest`.

**Response** (`UpdateExpenseResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `expense_id` | int | ID обновлённого расхода |

---

### DELETE /expenses/{expense_id}

**Авторизация:** Да

Удалить расход.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `expense_id` | int | **Внутренний** ID расхода |

**Response** (`DeleteExpenseResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |

---

## 12. Организации

**Файл:** `routers/organizations/organizations.py` | **Теги:** organizations

### GET /organizations

**Авторизация:** Да

Получить список организаций.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `name` | string | Нет | Фильтр по имени |
| `code` | string | Нет | Фильтр по коду |
| `is_active` | bool | Нет | Фильтр по активности |
| `limit` | int | Нет | Лимит (1-1000, default=100) |
| `offset` | int | Нет | Смещение (default=0) |

**Response** (`OrganizationArrayResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `organizations` | array | Список организаций |

Каждая организация (`OrganizationResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | Внутренний ID |
| `name` | string | Название |
| `code` | string \| null | Код |
| `is_active` | bool | Активна |
| `address` | string \| null | Адрес |
| `latitude` | float \| null | Широта |
| `longitude` | float \| null | Долгота |

---

## 13. Меню

**Файл:** `routers/menu/menu.py` | **Теги:** menu

### GET /menu

**Авторизация:** Да

Получить список позиций меню.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | int | Нет | **Внутренний** ID организации |
| `category_id` | int | Нет | **Внутренний** ID категории |
| `name` | string | Нет | Фильтр по имени |
| `limit` | int | Нет | Лимит (1-1000, default=100) |
| `offset` | int | Нет | Смещение (default=0) |

**Response** (`MenuArrayResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `items` | array | Позиции меню |

Каждая позиция (`ItemResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | Внутренний ID товара |
| `name` | string | Название |
| `price` | float | Цена |
| `description` | string \| null | Описание |
| `image` | string \| null | URL изображения |
| `category` | string \| null | Категория |

---

## 14. Товары

**Файл:** `routers/goods/goods.py` | **Теги:** goods

### GET /goods

**Авторизация:** Да

Получить товары по категориям (складские позиции: Заготовки и дочерние группы).

**Query Parameters:** Нет

**Response** (`GoodsArrayResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | "Получено категорий: {count}" |
| `categories` | array | Категории с товарами |

Каждая категория:

| Поле | Тип | Описание |
|------|-----|----------|
| `category_id` | int | **Внутренний** ID категории |
| `category_iiko_id` | string | **iiko ID** категории |
| `category_name` | string | Название |
| `items` | array | Товары: `id`, `iiko_id`, `name`, `price`, `code`, `amount`, `amount_unit`, `description` |

**Заметки по ID:** Возвращает оба типа ID: `category_id` (внутренний) и `category_iiko_id` (iiko UUID). Товары также содержат `id` и `iiko_id`.

---

## 15. Залы и столы

**Файл:** `routers/rooms/rooms.py` | **Теги:** rooms

### GET /rooms

**Авторизация:** Да

Получить список помещений (секций ресторана) с их столами.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`RoomsArrayResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `rooms` | array | Список залов |

Каждый зал:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | string | ID зала |
| `name` | string | Название |
| `capacity` | int | Вместимость |
| `tables` | array | Столы зала |

---

### GET /tables

**Авторизация:** Да

Получить список столов с их статусами.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `room_id` | int | Нет | **Внутренний** ID зала |
| `status` | string | Нет | Статус: `available` \| `occupied` \| `disabled` \| `all` |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`TablesArrayResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `tables` | array | Список столов |

Каждый стол (`TableResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | string | ID стола |
| `number` | string | Номер |
| `roomId` | string | ID зала |
| `roomName` | string | Название зала |
| `capacity` | int | Вместимость |
| `status` | string | Статус |
| `currentOrderId` | string \| null | ID текущего заказа |
| `assignedEmployeeId` | string \| null | ID закреплённого сотрудника |

---

## 16. Популярные блюда

**Файл:** `routers/popular_dishes/popular_dishes.py` | **Префикс:** `/reports` | **Теги:** reports

### GET /reports/popular-dishes

**Авторизация:** Да

Получить отчёт о популярных и непопулярных блюдах.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date` | string | Нет | Дата (DD.MM.YYYY) |
| `period` | string | Нет | `day` \| `week` \| `month` (default=`day`) |
| `organization_id` | int | Нет | **Внутренний** ID организации |
| `limit` | int | Нет | Кол-во блюд в топе (1-100, default=10) |

> Фильтрует: исключает `cashier = 'Удаление позиций'` и `order_deleted = 'DELETED'`.

**Response** (`PopularDishesResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `popular_dishes` | array | Популярные блюда |
| `unpopular_dishes` | array | Непопулярные блюда |
| `total_dishes_sold` | int | Всего продано блюд |
| `total_revenue` | float | Общая выручка |

Каждое блюдо (`DishItem`):

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | ID |
| `name` | string | Название |
| `quantity` | int | Количество продаж |
| `revenue` | float | Выручка |
| `average_price` | float | Средняя цена |

---

## 17. P&L отчёт

**Файл:** `routers/profit_loss/profit_loss.py` | **Префикс:** `/reports` | **Теги:** reports

### GET /reports/profit-loss

**Авторизация:** Да

Получить отчёт о прибылях и убытках (Profit & Loss Report).

Формула: **Прибыль = Выручка - Расходы - Банковская комиссия**. **Маржа = (Прибыль / Выручка) × 100%**.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date` | string | Нет | Дата (DD.MM.YYYY) |
| `period` | string | Нет | `day` \| `week` \| `month` (default=`day`) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`ProfitLossResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `total_revenue` | float | Общая выручка |
| `revenue_by_category` | array | Выручка по категориям: `category`, `amount` |
| `total_expenses` | float | Общие расходы |
| `expenses_by_type` | array | Расходы по типам: `transaction_type`, `transaction_name`, `amount` |
| `bank_commission` | float | Банковская комиссия |
| `gross_profit` | float | Валовая прибыль |
| `profit_margin` | float \| null | Маржа (%) |

---

## 18. Концепции и поставщики

**Файл:** `routers/conceptions/conceptions.py` | **Теги:** conceptions, suppliers

### POST /conceptions/sync

**Авторизация:** Да

Синхронизировать концепции из iiko Server API.

**Response** (`SyncConceptionsResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `synced` | int | Количество синхронизированных |

---

### GET /conceptions

**Авторизация:** Да

Получить список всех концепций.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `is_active` | bool | Нет | Фильтр по активности |

**Response** (`ConceptionListResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `conceptions` | array | Список концепций |
| `total` | int | Общее количество |

Каждая концепция:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | Внутренний ID |
| `iiko_id` | string | iiko UUID |
| `name` | string | Название |
| `code` | string \| null | Код |
| `comment` | string \| null | Комментарий |

---

### POST /suppliers/sync

**Авторизация:** Да

Синхронизировать поставщиков из iiko Server API.

**Response** (`SyncSuppliersResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `synced` | int | Количество синхронизированных |

---

### GET /suppliers

**Авторизация:** Да

Получить список всех поставщиков.

**Response** (`SupplierListResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `suppliers` | array | Список поставщиков |
| `total` | int | Общее количество |

Каждый поставщик:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | Внутренний ID |
| `iiko_id` | string | iiko UUID |
| `name` | string | Название |
| `code` | string \| null | Код |
| `comment` | string \| null | Комментарий |

---

## 19. Департаменты

**Файл:** `routers/departments/departments.py` | **Теги:** departments

### POST /departments/sync

**Авторизация:** Да

Синхронизировать департаменты из iiko API. Получает все департаменты (type=DEPARTMENT) и сохраняет/обновляет в БД.

**Response** (`SyncDepartmentsResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `created` | int | Создано |
| `updated` | int | Обновлено |
| `total` | int | Всего |

---

### GET /departments

**Авторизация:** Да

Получить список всех департаментов.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `is_active` | bool | Нет | Фильтр по активности |

**Response** (`DepartmentListResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `departments` | array | Список департаментов |
| `total` | int | Общее количество |

Каждый департамент (`DepartmentResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | Внутренний ID |
| `iiko_id` | string | iiko UUID |
| `parent_id` | string \| null | ID родительского департамента |
| `code` | string \| null | Код |
| `name` | string | Название |
| `taxpayer_id_number` | string \| null | ИНН |
| `is_active` | bool | Активен |
| `created_at` | datetime | Дата создания |
| `updated_at` | datetime | Дата обновления |

---

### GET /departments/{department_id}

**Авторизация:** Да

Получить департамент по внутреннему ID.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `department_id` | int | **Внутренний** ID департамента |

**Response** (`DepartmentResponse`): См. выше.

**Возможные ошибки:** 404 — Департамент не найден

---

### GET /departments/iiko/{iiko_id}

**Авторизация:** Да

Получить департамент по iiko ID.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `iiko_id` | string | **iiko UUID** департамента |

**Response** (`DepartmentResponse`): См. выше.

**Возможные ошибки:** 404 — Департамент не найден

---

## 20. Документы

**Файл:** `routers/documents/documents.py` | **Префикс:** `/documents` | **Теги:** documents

### POST /documents/writeoff

**Авторизация:** Да

Создать акт списания в iiko.

**Request Body** (`SimpleWriteoffDocumentRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `storeId` | int | Нет | **Внутренний** ID склада (Store.id) |
| `conceptionId` | int | Нет | **Внутренний** ID концепции |
| `account_id` | int | Да | **Внутренний** ID счёта (Account.id) |
| `date` | string | Да | Дата |
| `comment` | string | Нет | Комментарий |
| `items` | array | Да | Позиции (min 1) |

Каждая позиция (`SimpleWriteoffItemRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `id` | int | Да | **Внутренний** ID товара (Item.id) |
| `amount` | float | Да | Количество (> 0) |
| `price` | float | Нет | Цена (>= 0) |
| `sum` | float | Нет | Сумма (>= 0) |

**Response** (`CreateWriteoffDocumentResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `iiko_id` | string \| null | UUID документа в iiko |
| `document_id` | int \| null | Внутренний ID |

**Заметки по ID:** `storeId`, `account_id`, `items[].id` — все внутренние ID. Система конвертирует в iiko UUID.

---

### POST /documents/incoming-invoice

**Авторизация:** Да

Создать приходную накладную.

**Request Body** (`SimpleIncomingInvoiceRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `storeId` | int | Нет | **Внутренний** ID склада |
| `conceptionId` | int | Нет | **Внутренний** ID концепции |
| `dateIncoming` | string | Да | Дата поступления |
| `comment` | string | Нет | Комментарий |
| `supplier` | string | Нет | **iiko UUID** поставщика |
| `invoice` | string | Нет | Номер накладной |
| `items` | array | Да | Позиции (min 1) |

Каждая позиция (`SimpleInvoiceItemRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `id` | int | Да | **Внутренний** ID товара (Item.id) |
| `amount` | float | Да | Количество (> 0) |
| `price` | float | Да | Цена (>= 0) |
| `sum` | float | Да | Сумма (>= 0) |

**Response** (`CreateWarehouseDocumentResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `document_id` | int \| null | Внутренний ID |
| `iiko_id` | string \| null | iiko UUID |

**Заметки по ID:** `items[].id` — **внутренний** Item.id, но `supplier` — это **iiko UUID** (строка).

---

### POST /documents/outgoing-invoice

**Авторизация:** Да

Создать расходную накладную.

**Request Body** (`SimpleOutgoingInvoiceRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `storeId` | int | Нет | **Внутренний** ID склада |
| `conceptionId` | int | Нет | **Внутренний** ID концепции |
| `dateIncoming` | string | Да | Дата |
| `comment` | string | Нет | Комментарий |
| `accountToCode` | string | Нет | Код счёта назначения |
| `supplier` | string | Нет | **iiko UUID** поставщика/контрагента |
| `items` | array | Да | Позиции (min 1) |

Формат позиций аналогичен `SimpleInvoiceItemRequest`.

**Response** (`CreateWarehouseDocumentResponse`): Аналогично incoming-invoice.

---

### GET /documents/accounts

**Авторизация:** Да

Получить список всех счетов (accounts).

**Response** (`AccountsListResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `accounts` | array | Список счетов |

Каждый счёт (`AccountResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int | Внутренний ID |
| `iiko_id` | string | iiko UUID |
| `name` | string | Название |
| `code` | string | Код |
| `type` | string | Тип |
| `system` | bool | Системный ли |

---

### POST /documents/inventory

**Авторизация:** Да

Создать инвентаризацию.

**Request Body** (`SimpleInventoryRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `storeId` | int | Нет | **Внутренний** ID склада |
| `dateIncoming` | string | Да | Дата |
| `comment` | string | Нет | Комментарий |
| `accountSurplusCode` | string | Нет | Код счёта излишков (default: "5.10") |
| `accountShortageCode` | string | Нет | Код счёта недостачи (default: "5.09") |
| `items` | array | Да | Позиции (min 1) |

Каждая позиция (`SimpleInventoryItemRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `id` | int | Да | **Внутренний** ID товара |
| `amount` | float | Да | Фактическое количество (> 0) |
| `price` | float | Нет | Цена (>= 0) |
| `sum` | float | Нет | Сумма (>= 0) |
| `containerId` | string | Нет | ID контейнера |
| `comment` | string | Нет | Комментарий |

**Response** (`CreateWarehouseDocumentResponse`): Аналогично другим документам.

---

### POST /documents/pay-out-types/sync

**Авторизация:** Да

Синхронизировать типы изъятий/внесений из iiko API в локальную БД.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `include_deleted` | bool | Нет | Включать удалённые (default=false) |

**Response** (`SyncPayOutTypesResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `synced` | int | Количество |

---

### GET /documents/pay-out-types

**Авторизация:** Да

Получить типы изъятий/внесений из локальной БД. Требуется предварительная синхронизация через `POST /documents/pay-out-types/sync`.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `include_deleted` | bool | Нет | Включать удалённые (default=false) |

**Response** (`List[PayOutTypeResponse]`):

Каждый тип:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | string | UUID из iiko |
| `account_name` | string | Название счёта |
| `chief_account_name` | string | Название главного счёта |
| `transactionType` | string | Тип транзакции |
| `counteragentType` | string | Тип контрагента |
| `comment` | string | Комментарий |

---

### GET /documents/payrolls

**Авторизация:** Да

Получить список платёжных ведомостей из iiko API.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date_from` | string | Да | Начало периода (**YYYY-MM-DD**) |
| `date_to` | string | Да | Конец периода (**YYYY-MM-DD**) |
| `department` | string | Нет | **UUID** торгового предприятия |
| `include_deleted` | bool | Нет | Включать удалённые (default=false) |

> **Внимание:** Формат дат — YYYY-MM-DD.

**Response** (`List[PayrollResponse]`):

Каждая ведомость:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | string | UUID |
| `dateFrom` | string | Начало периода |
| `dateTo` | string | Конец периода |
| `department` | string | Департамент UUID |
| `documentNumber` | string | Номер документа |
| `status` | string | Статус |
| `comment` | string | Комментарий |

---

### POST /documents/pay-out

**Авторизация:** Да

Создать изъятие из кассы в iiko API.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Request Body** (`CreatePayOutRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `payOutTypeId` | string | Да | **UUID** типа изъятия (из iiko) |
| `payOutDate` | string | Да | Дата (**YYYY-MM-DD**) |
| `chiefAccount` | string | Нет | Главный счёт |
| `counteragent` | string | Нет | **UUID** контрагента |
| `departmentSumMap` | object | Да | Map: `{department_uuid: сумма}` — суммы по департаментам (все > 0) |
| `payrollId` | string | Нет | UUID платёжной ведомости |
| `comment` | string | Нет | Комментарий |

**Response** (`CreatePayOutResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `result` | string | Результат от iiko |
| `errors` | array | Ошибки от iiko |
| `payOutSettings` | object | Настройки изъятия |
| `pay_out_id` | int | Внутренний ID |

**Заметки по ID:** `payOutTypeId`, `counteragent`, ключи `departmentSumMap` — все UUID из iiko. Только `organization_id` — внутренний.

---

## 21. Склад

**Файл:** `routers/warehouse/warehouse.py` | **Префикс:** `/warehouse` | **Теги:** warehouse

> **Примечание:** Эндпоинты CRUD для складских документов (`/warehouse/documents/*`) помечены `include_in_schema=False` и не отображаются в Swagger.

### POST /warehouse/documents *(скрыт из схемы)*

**Авторизация:** Да

Создать новый складской документ (поступление, списание, приходная или расходная накладная).

**Request Body** (`CreateWarehouseDocumentRequest`): Сложная схема с множеством полей. Типы документов: `RECEIPT`, `WRITEOFF`, `INCOMING_INVOICE`, `OUTGOING_INVOICE`.

---

### GET /warehouse/documents *(скрыт из схемы)*

**Авторизация:** Да

Получить список складских документов с фильтрацией.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | int | Нет | **Внутренний** ID организации |
| `document_type` | string | Нет | Тип: RECEIPT, WRITEOFF, INCOMING_INVOICE, OUTGOING_INVOICE, INVENTORY |
| `from_date` | string | Нет | Начало (DD.MM.YYYY) |
| `to_date` | string | Нет | Конец (DD.MM.YYYY) |
| `limit` | int | Нет | Лимит (default=100) |
| `offset` | int | Нет | Смещение (default=0) |

**Response** (`WarehouseDocumentsListResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `documents` | array | Документы |
| `total` | int | Общее количество |

---

### GET /warehouse/documents/{document_id} *(скрыт из схемы)*

**Авторизация:** Да

Получить детали складского документа по ID.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `document_id` | int | **Внутренний** ID документа |

---

### PUT /warehouse/documents/{document_id} *(скрыт из схемы)*

**Авторизация:** Да

Обновить складской документ.

---

### DELETE /warehouse/documents/{document_id} *(скрыт из схемы)*

**Авторизация:** Да

Удалить складской документ.

---

### POST /warehouse/sync

**Авторизация:** Да

Синхронизировать складские документы из iiko. Синхронизация через транзакции (фильтрация по полю Document).

**Request Body** (`SyncWarehouseDocumentsRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `from_date` | string | Нет | Начало периода |
| `to_date` | string | Нет | Конец периода |
| `organization_id` | int | Нет | ID организации |

**Response** (`SyncWarehouseDocumentsResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `created` | int | Создано |
| `updated` | int | Обновлено |
| `errors` | int | Ошибок |

---

### POST /warehouse/writeoff-documents *(скрыт из схемы)*

**Авторизация:** Да

Создать акт списания (расширенная версия с полным набором полей).

**Request Body** (`CreateWriteoffDocumentRequest`): Расширенная схема. Ключевые поля:

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `date_incoming` | string | Да | Дата |
| `store_id` | int | Да | **Внутренний** ID склада (Store.id) |
| `account_id` | int | Да | **Внутренний** ID счёта (Account.id) |
| `organization_id` | int | Да | **Внутренний** ID организации |
| `items` | array | Да | Позиции |

Каждая позиция (`CreateWriteoffItemRequest`):

| Поле | Тип | Обяз. | Описание |
|------|-----|-------|----------|
| `item_id` | int | Нет | **Внутренний** ID товара (Item.id) |
| `product_id` | string | Нет | **iiko UUID** товара (Item.iiko_id) |
| `amount` | float | Да | Количество (> 0) |

> Нужно указать либо `item_id`, либо `product_id`.

---

### GET /warehouse/balance

**Авторизация:** Да

Получить остатки товаров по складам.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `timestamp` | string | Нет | Дата/время ISO (напр. 2025-12-27T12:20:00, default=сейчас) |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response** (`BalanceStoresResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `data` | array | Склады с остатками |

Каждый склад:

| Поле | Тип | Описание |
|------|-----|----------|
| `store` | string | Название склада |
| `sum` | float | Общая сумма |
| `products` | array | Товары: `item` (название), `amount` (количество), `sum` (сумма) |

---

### GET /warehouse/stores

**Авторизация:** Да

Получить список всех складов из iiko Server API.

**Response** (`StoresListResponse`):

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `data` | array | Склады: `id` (UUID), `name`, `code` |

---

## 22. Кэш

**Файл:** `routers/cache/cache.py` | **Префикс:** `/cache` | **Теги:** cache

### GET /cache/stats

**Авторизация:** Да

Получить статистику по кэшу.

**Response:**

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `data` | object | `total_keys`, `valid_keys`, `expired_keys` |

---

### POST /cache/clear

**Авторизация:** Да

Очистить кэш. Поддерживает паттерны (напр. "goods", "reports").

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `pattern` | string | Нет | Паттерн для очистки (default="", очищает всё) |

**Response:**

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |

---

## 23. DB индексы

**Файл:** `routers/db_indexes.py` | **Префикс:** `/db` | **Теги:** database

> **Примечание:** Эндпоинты не требуют JWT авторизации.

### POST /db/indexes/create

Создать все индексы для оптимизации запросов.

**Response:**

| Поле | Тип | Описание |
|------|-----|----------|
| `success` | bool | Результат |
| `message` | string | Описание |
| `data` | object | Детали создания |

---

### POST /db/indexes/drop

Удалить все индексы (используется для пересоздания).

**Response:** Аналогично `/db/indexes/create`.

---

### POST /db/indexes/recreate

Пересоздать все индексы (удалить и создать заново).

**Response:** Аналогично `/db/indexes/create`.

---

### POST /db/indexes/optimize

Оптимизировать индексы (ANALYZE/VACUUM).

**Response:** Аналогично `/db/indexes/create`.

---

## 24. iiko Sync (админ)

**Файл:** `routers/iiko/sync.py` | **Префикс:** `/sync` (задаётся в main.py) | **Теги:** iiko-sync

> Все эндпоинты предназначены для крон-задач и администраторов. Не требуют стандартной JWT авторизации (кроме `/sync/cron/*`, которые используют `apikey`).

### POST /sync/organizations

Синхронизация организаций с iiko API.

**Response:** `{success, message, data}`

---

### POST /sync/organizations/cloud-ids

Синхронизация `iiko_id_cloud` для организаций.

**Response:** `{success, message, data}`

---

### POST /sync/employees

Синхронизация сотрудников с iiko API.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | string | Нет | iiko UUID организации |

**Response:** `{success, message, data}`

---

### POST /sync/terminal-groups

Синхронизация групп терминалов.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | string | Нет | iiko UUID организации |

**Response:** `{success, message, data}`

---

### POST /sync/terminals

Синхронизация терминалов.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | string | Нет | iiko UUID организации |

**Response:** `{success, message, data}`

---

### POST /sync/roles

Синхронизация ролей с iiko API.

**Response:** `{success, message, data}`

---

### POST /sync/restaurant-sections

Синхронизация секций ресторана.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | string | Нет | iiko UUID организации |

**Response:** `{success, message, data}`

---

### POST /sync/tables

Синхронизация столов.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | string | Нет | iiko UUID организации |

**Response:** `{success, message, data}`

---

### POST /sync/accounts

Синхронизация счетов (Server API).

**Response:** `{success, message, data}`

---

### POST /sync/salaries

Синхронизация окладов сотрудников (Server API).

**Response:** `{success, message, data}`

---

### POST /sync/shifts

Синхронизация смен сотрудников (Server API).

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `date_from` | string | Нет | Начало (**YYYY-MM-DD**) |
| `date_to` | string | Нет | Конец (**YYYY-MM-DD**) |

**Response:** `{success, message, data}`

---

### POST /sync/menu

Синхронизация меню.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | string | Нет | iiko UUID организации |

**Response:** `{success, message, data}`

---

### POST /sync/all

Полная синхронизация всех данных с iiko API.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | string | Нет | iiko UUID организации |

**Response:** `{success, message, data}`

---

### POST /sync/organizations-employees-terminals

Синхронизация организаций, сотрудников и терминалов (пакетная).

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `organization_id` | string | Нет | iiko UUID организации |

**Response:** `{success, message, data: {results, summary}}`

---

### POST /sync/transactions

Синхронизация транзакций по дням (последовательная обработка).

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `from_date` | string | Нет | Начало (**YYYY-MM-DD**) |
| `to_date` | string | Нет | Конец (**YYYY-MM-DD**) |

**Response:** `{success, message, data}`

---

### POST /sync/sales

Синхронизация продаж по дням (последовательная обработка).

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `from_date` | string | Нет | Начало (**YYYY-MM-DD**) |
| `to_date` | string | Нет | Конец (**YYYY-MM-DD**) |

**Response:** `{success, message, data}`

---

### POST /sync/cron/sync

Автоматическая синхронизация через cron. Выполняет: sync accounts, sync по дате изменения, sync shifts, пересчёт метрик сотрудников.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `apikey` | string | Да | API ключ для аутентификации |

**Response:** `{success, message, data: {accounts, modification_sync, shifts, employee_metrics}}`

---

### POST /sync/by-modification-date

Синхронизация по дате изменения транзакций (по DateSecondary).

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `from_date` | string | Нет | Начало (**YYYY-MM-DD**) |
| `to_date` | string | Нет | Конец (**YYYY-MM-DD**) |

**Response:** `{success, message, data}`

---

### POST /sync/items/cloud

Синхронизация товаров из Cloud API для всех организаций.

**Response:** `{success, message, data}`

---

### POST /sync/items/cloud/{organization_id}

Синхронизация товаров из Cloud API для конкретной организации.

**Path Parameters:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `organization_id` | int | **Внутренний** ID организации |

**Response:** `{success, message, data}`

---

### POST /sync/items/server

Синхронизация товаров из Server API.

**Response:** `{success, message, data}`

---

### POST /sync/recalculate-daily-metrics

Пересчитать дневные метрики (таблица `daily_analytics`) за период.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `from_date` | string | Нет | Начало |
| `to_date` | string | Нет | Конец |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response:** `{success, message, data: {dates_processed, total_dates, errors}}`

---

### POST /sync/recalculate-employee-metrics

Пересчитать метрики по сотрудникам (таблица `daily_employee_analytics`) за период.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `from_date` | string | Нет | Начало |
| `to_date` | string | Нет | Конец |
| `organization_id` | int | Нет | **Внутренний** ID организации |

**Response:** `{success, message, data: {dates_processed, total_dates, total_employees_processed, errors}}`

---

### POST /sync/writeoff-documents

Синхронизация актов списания с iiko API.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `from_date` | string | Нет | Начало (**YYYY-MM-DD**) |
| `to_date` | string | Нет | Конец (**YYYY-MM-DD**) |
| `status` | string | Нет | Фильтр по статусу |

**Response:** `{success, message, data}`

---

### POST /sync/incoming-invoices

Синхронизация приходных накладных.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `from_date` | string | Нет | Начало (**YYYY-MM-DD**) |
| `to_date` | string | Нет | Конец (**YYYY-MM-DD**) |

**Response:** `{success, message, data}`

---

### POST /sync/outgoing-invoices

Синхронизация расходных накладных.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `from_date` | string | Нет | Начало (**YYYY-MM-DD**) |
| `to_date` | string | Нет | Конец (**YYYY-MM-DD**) |

**Response:** `{success, message, data}`

---

### POST /sync/all-documents

Синхронизация всех типов документов (акты списания, приходные, расходные накладные).

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `from_date` | string | Нет | Начало (**YYYY-MM-DD**) |
| `to_date` | string | Нет | Конец (**YYYY-MM-DD**) |
| `status` | string | Нет | Фильтр по статусу |

**Response:** `{success, message, data}`

---

### POST /sync/conceptions

Синхронизация концепций с iiko API.

**Response:** `{success, message, data}`

---

### POST /sync/suppliers

Синхронизация поставщиков с iiko API.

**Response:** `{success, message, data}`

---

### POST /sync/stores

Синхронизация складов с iiko API.

**Response:** `{success, message, data}`

---

### POST /sync/cron/daily-sync

Ежедневная синхронизация справочников и документов. Запускается в 4:00 по Астане (UTC+6).

Включает: организации, cloud org IDs, роли, товары (cloud), группы терминалов, терминалы, секции ресторана, столы, концепции, поставщики, склады, оклады, документы.

**Query Parameters:**

| Параметр | Тип | Обяз. | Описание |
|----------|-----|-------|----------|
| `apikey` | string | Да | API ключ для аутентификации |

**Response:** `{success, message, data: {organizations, cloud_org_ids, roles, items_cloud, terminal_groups, terminals, restaurant_sections, tables, conceptions, suppliers, stores, salaries, documents}}`
