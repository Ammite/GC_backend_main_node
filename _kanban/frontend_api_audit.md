# Frontend API Audit — что фронт реально шлёт в бэк

Проект фронта: `/srv/project/gcapp_front` (React Native / Expo Router).
Все ссылки `file:line` — абсолютные на этот проект.

## Базовый URL и auth

- Базовый URL берётся из `Constants.expoConfig.extra.EXPO_PUBLIC_API_URL` или `process.env.EXPO_PUBLIC_API_URL`. См. `src/server/api.ts:8-10`.
- В `.env` сейчас стоит `EXPO_PUBLIC_API_URL=https://tsolution.kz/` (`.env:4`).
- Axios инстанс с timeout 30s: `src/server/api.ts:12-15`.
- Auth — **только** `Authorization: Bearer <token>` (token из storage по ключу `access_token`). Никаких `?token=` query. См. `src/server/api.ts:18-31`.
- 401 → автоматически удаляется `access_token` из storage. Логика перенаправления на логин не реализована (`src/server/api.ts:67-73`).
- Сохранённый `user` в storage — это объект `{ id, email, role, organization_id }` (см. `src/contexts/AuthContext.tsx:13-18`). `id` ← `response.user_id` из `POST /login` (см. `app/auth/index.tsx:102`). То есть это **`User.id`**, а не `Employee.id`.

## 1. Auth (task 1)

### `POST /login`
- file: `src/server/auth.ts:37`.
- Payload: `{ login, password }`. Из формы логина: `formData.email` маппится в поле `login`, `formData.password` — в `password` (`app/auth/index.tsx:95-98`).
- Ответ ожидается: `{ access_token, user, success, user_id, role, name }`. `user_id` сохраняется как `user.id` в AuthContext.

### `PUT /change-password`
- file: `src/server/general/employees.ts:24` (функция `changeEmployeePassword`).
- Payload: `{ employee_id, new_password }`.
- Источник `employee_id`: **из списка сотрудников** (`GET /employees`), а это уже `Employee.id`. Выбор сотрудника через модалку в `app/manager/profile/changePassword.tsx:75-89` (передаётся `selectedEmployee.id`).
- В `app/ceo/profile/changePassword.tsx:71-89` функция реально **не вызывается** — там TODO заглушка (`handleSubmit` просто `alert("Пароль успешно изменён")`).

### `POST /employees/create-users`
- **Не используется** на фронте. `grep` по `create-users / create_users` — пусто.

### `POST /register`
- file: `src/server/auth.ts:13` (функция `register`).
- Вызывается только в `app/auth/registration.tsx:17` (экран `/auth/registration`).
- ВАЖНО: эндпоинт уже **удалён на бэке**, но во фронте код остался. Экран регистрации не закрыт.

## 2. Расходы (task 2)

### `POST /documents/writeoff`
- file: `src/server/general/warehouse.ts:43`.
- Payload (формируется в `app/manager/storage/item.tsx:101-115`):
  ```
  {
    account_id,
    items,
    // опционально: date, invoice, supplier, comment
  }
  ```
- **Нет** `storeId`, **нет** `conceptionId`, **нет** `organization_id`.

### `POST /documents/incoming-invoice`
- file: `src/server/general/warehouse.ts:58`.
- Payload (`app/manager/storage/item.tsx:85-100`):
  ```
  {
    dateIncoming,
    items,
    // опционально: comment, invoice, supplier
  }
  ```
- **Нет** `storeId`, **нет** `conceptionId`, **нет** `organization_id`.

### `POST /documents/inventory`
- file: `src/server/general/warehouse.ts:50`. Payload: `{ dateIncoming, items, comment? }` (`app/manager/storage/item.tsx:116-131`).

### `POST /documents/outgoing-invoice`
- **Не используется** на фронте. UI-вкладка "Расходная накладная" есть (`app/manager/storage/index.tsx:42`), но POST-вызова нет. Хелпера `createWarehouseDocumentOutgoingInvoice` в `src/server/general/warehouse.ts` нет.

### `POST /expenses`
- file: `src/server/general/expenses.ts:17` (функция `addExpenses`).
- Caller: `app/manager/expenses/expense.tsx:165-181`.
- Payload:
  ```
  {
    organization_id,   // обязателен (валидация ниже: "Пожалуйста, выберите организацию")
    expense_type,
    amount,
    date,
    comment,
    account_id?,
    counteragent_id?
  }
  ```
- `organization_id` **всегда передаётся** — есть валидация на форме (`app/manager/expenses/expense.tsx:160-163`).
- Тип в `src/server/types/expenses.ts:30-38` помечает `organization_id` как required.

### `POST /warehouse/documents` (legacy)
- **Не используется**. `GET /warehouse/documents` есть (`src/server/general/warehouse.ts:14`), POST на этот URL — нигде.

### `PUT /documents/{document_id}`
- file: `src/server/general/warehouse.ts:35`. Используется через `updateWarehouseDocumentWrapper` (`src/contexts/StorageProvider.tsx:105`).

## 3. Заказы (task 3, task 8)

### `POST /orders`
- file: `src/server/waiter/general.ts:68` (функция `createOrder`).
- Тип payload — `CreateOrdersInputType` (`src/server/types/waiter.ts:165-171`):
  ```
  { organizationId?, tableId?, waiterId?, guests?, items: [{productId, amount, price, sum, comment?}] }
  ```
- Caller: `app/waiter/newOrder.tsx:276-290`:
  ```
  organizationId: selectedLocation,
  tableId: Number(selectedTable?.id),
  waiterId: user?.id === 10 ? 322256 : user?.id,
  guests: 2,                       // ВСЕГДА 2, захардкожено
  items: selectedDishes.map(...)
  ```
- **`waiterId` = `user.id` (User.id из AuthContext)**, не Employee.id. Хардкод-маппинг `10 → 322256` (особый случай для тестового юзера id=10).
- `items.comment` приходит из выбора блюд в меню.
- **Модификаторов нет** в payload.

### `PUT /orders/{order_id}`
- file: `src/server/waiter/general.ts:94` (`updateOrder`).
- Тип `UpdateOrdersInputType` (`src/server/types/waiter.ts:172-179`): все поля опциональны (`organizationId?, tableId?, waiterId?, guests?, items?, comment?`).
- Реальный caller — единственный: `app/waiter/editOrderMenu.tsx:347-355`.
  - **Шлёт только** `{ items: [...] }`. Ничего больше.
  - Сценарий: редактирование позиций (добавить/удалить/изменить количество). Смена `tableId`, `waiterId`, `guests` не передаётся.
  - На входе экрана позиции seeded из `orderItems` (`editOrderMenu.tsx:212-228`).
- **Обработки предупреждения "не уехало в iiko" нет**. На любой error — `Alert.alert("Ошибка", "Не удалось сохранить изменения")` (`editOrderMenu.tsx:364-366`). Никаких warnings из ответа не читается.

### `POST /orders/{order_id}/pay`
- file: `src/server/waiter/general.ts:76` (`payOrder`).
- Caller: `app/waiter/payment.tsx:66-69`:
  ```
  const input: Record<string, any> = {};
  if (selectedPaymentMethod) input.paymentType = selectedPaymentMethod.id;
  await payOrderWrapper(order_id, input);
  ```
- Формат: **одиночный `paymentType: <int>`** — это **наш id из таблицы payment_types** (`selectedPaymentMethod.id` берётся из ответа `GET /payment-types`).
- **Массив `paymentTypes` НЕ шлётся.** Поля `iiko_id`, `payment_type_kind` фронт не отправляет.
- `tipAmount` / чаевые — закомментировано (`payment.tsx:172-195`).
- Никакого split-cheque.
- Никакой обработки warning'а от бэка про "не уехало в iiko".

### `POST /orders/{order_id}/cancel`
- file: `src/server/waiter/general.ts:83` (`cancelOrder`).
- Caller: `app/waiter/cancel.tsx:51`. Payload: `{ reason: <строка> }`.
- Возможные `reason`: один из строк ("Долгое ожидание", "Изменились планы", "Ошиблись при заказе", "Нет в наличии") — `app/waiter/cancel.tsx:20-25`.
- **`removalTypeId` НЕ шлётся**, только текстовая `reason`.

### `GET /orders`
- file: `src/server/waiter/general.ts:60`, `src/server/general/generalOrders.ts:7`.
- Params: `{ organization_id?, user_id?, state?, date?, limit?, offset? }`. Фильтрует список заказов на стороне бэка по `user_id` (= User.id из AuthContext, см. `app/waiter/newOrder.tsx:295`, `payment.tsx:71`, `cancel.tsx:53`, `editOrderMenu.tsx:357-360`).

## 4. Виды оплаты (task 4)

### `GET /payment-types`
- file: `src/server/waiter/general.ts:102` (`getPaymentTypes`).
- Params: `{ organization_id? }`. В `app/waiter/payment.tsx:43-45`: передаётся `selectedLocation` из AuthContext (может быть `undefined` при null).
- `checkFilters` (`src/utils/serverUtils.ts:14`) выкинет `organization_id`, если он `null/undefined`/пустая строка — то есть если выбранной локации нет, бэк получит запрос **без** `organization_id` и должен будет вернуть все виды оплаты.
- Локальной фильтрации по точкам нет — используется как пришло (`payment.tsx:46-48`).

## 5. Зарплата (task 5)

### `GET /waiter/{waiter_id}/salary`
- file: `src/server/waiter/general.ts:42` (`getWaiterSalary`).
- Caller: `app/waiter/salary.tsx:57,67`:
  ```
  const waiter_id = user.id;          // User.id из AuthContext
  await fetchSalary(waiter_id, { date, organization_id? });
  ```
- **`{waiter_id}` в URL — это `User.id`, НЕ `Employee.id`**. КРИТИЧНО: бэк ждёт `Employees.id`.
- Хардкод-маппинга (как в newOrder.tsx) здесь нет — отправляется `user.id` как есть.

### `GET /waiter/{waiter_id}/sales-today`
- **Не используется** на фронте. Поиск по `sales-today` / `salesToday` / `sales_today` — пусто.

## 6. Мотивация (task 7)

### `GET /tasks`
- file: `src/server/ceo/generals.ts:74` (`getTasks`).
- Params: `{ user_id?, date?, organization_id? }`.
- Callers:
  - Waiter: `app/waiter/motivation/index.tsx:47-51`, `app/waiter/motivation/[id].tsx:62-66` — шлёт `user_id: Number(user.id)` (= User.id из AuthContext).
  - CEO/Manager: `app/ceo/motivation/index.tsx:98-100`, `app/manager/motivation/index.tsx:98-100` — шлёт только `{ date }`.

### `POST /tasks`
- file: `src/server/ceo/generals.ts:62` (`createTask`).
- Тип `TaskInputsType` (`src/server/types/ceo.ts:14-21`): `{ title, description, user_id?, employee_id?, organization_id, due_date }`.
- Caller: `app/ceo/motivation/index.tsx:199-205`, `app/manager/motivation/index.tsx:199-205`:
  ```
  createTaskWrapper({
    title, description,
    employee_id: data.user_id,    // <-- здесь data.user_id это уже Employee.id
    organization_id, due_date
  })
  ```
- `data.user_id` приходит из модалки `AddQuestModal.tsx:320-323`: значение = `Number(taskSelectedEmployee.id)` (с хардкод-маппингом `322256 → 10`). Поскольку список сотрудников загружается через `GET /employees` (`src/server/general/employees.ts:8`), то `selectedEmployee.id` = **`Employee.id`**, что соответствует ожиданию бэка. **Тут совпадение.** Имя поля `user_id` в модалке вводит в заблуждение, но фактически это Employee.id.

### `POST /tasks/{id}/complete`
- file: `src/server/ceo/generals.ts:80` (`completeTask`).
- Caller: `app/waiter/motivation/[id].tsx:56`.
- Body пустой, только `task_id` в URL.

### `GET /quests/active`
- file: `src/server/ceo/generals.ts:46` (`getQuests`).
- Params (declared): `{ data?: string, organization_id? }`. ⚠️ **Опечатка** — `data` вместо `date` в `src/server/ceo/generals.ts:41`. Фронт передаёт `date` в реальности (`app/ceo/motivation/index.tsx:94-96`) → попадает в params как `date`. Бэк должен принимать `date`, поле `data` мёртвое.
- `date_from`, `date_to` — **не шлются**.

### `GET /waiter/{waiter_id}/quests`
- file: `src/server/waiter/general.ts:33` (`getWaiterQuests`).
- Caller: `app/waiter/motivation/index.tsx:52`, `app/waiter/index.tsx:95`:
  ```
  fetchQuest(user.id, { date, ...organization_id? })   // waiter_id = User.id из AuthContext
  ```
- **КРИТИЧНО: `{waiter_id}` = `User.id`, НЕ `Employee.id`**. Аналогично `salary`.

### `POST /quests`
- file: `src/server/ceo/generals.ts:54` (`createQuest`).
- Тип `QuestInputsType` (`src/server/types/ceo.ts:8-12`) формально лишь `{ date?, employee_id?, organization_id? }`, но реальный caller в `app/ceo/motivation/index.tsx:169-180`:
  ```
  {
    title, description, reward, target, unit,
    totalEmployees, completedEmployees: 0, employeeNames: [],
    date: selectedDate,
    durationDate: data.durationDate
  }
  ```
- В payload **много полей не из типа**: `title, description, reward, target, unit, totalEmployees, completedEmployees, employeeNames, durationDate`. Это похоже на старую/мок-схему.
- Поля `employee_id` / `organization_id` (из типа) фактически не передаются.

### `PUT /quests/{id}` и `DELETE /quests/{id}`
- **Не используются** на фронте. `grep` по `updateQuest / deleteQuest / put.*quests / delete.*quests` — пусто.

## 7. Меню

### `GET /menu`
- file: `src/server/general/menu.ts:7` (`getMenu`).
- Тип параметров `MenuInputsType` (`src/server/types/menu.ts:1-7`): `{ organization_id?, category_id?, name?, limit?, offset? }`.
- Callers все передают только `{ limit: 0 }`:
  - `app/waiter/menu.tsx:100`
  - `app/waiter/editOrderMenu.tsx:108`
  - `src/client/components/form/MenuPicker.tsx:67`
- **`organization_id` НЕ передаётся** — фронт всегда получает меню "общее".
- **Попыток слать модификаторы нигде нет** (поиск по `modifier`/`modifiers` — пусто). В `CreateOrderItem` (`src/server/types/waiter.ts:157-163`) полей модификаторов тоже нет.

## 8. Профиль

### `GET /profile`
- **Не вызывается** ни в одной форме. Поиск по `/profile` (как axios path) — пусто.

### `GET /me`
- Декларирован в `src/server/auth.ts:59` (`getMe`), но **нигде не вызывается** (grep по `getMe(` — только определение).

### Экран профиля
- `app/waiter/profile.tsx:68-97`, `app/ceo/profile/index.tsx:80-99`, `app/manager/profile/index.tsx:80-99` — все используют **mock-данные**. Реальный HTTP-вызов профиля закомментирован (например `app/waiter/profile.tsx:74`).
- Данные `name`/`role` для отображения берутся из `user` объекта в AuthContext (что положили при login).

## Дополнительно

### Authorization header
- Только `Authorization: Bearer <jwt>` (`src/server/api.ts:22`). Никакого `?token=` query.

### Попытки слать поля, которые бэк не принимает
- **Модификаторы (`modifiers`)** — НЕ шлёт нигде.
- **`tipAmount` (чаевые)** — есть UI, но он закомментирован (`app/waiter/payment.tsx:172-195`).
- **Split cheque** — нигде.
- **`removalTypeId`** — нигде. В `POST /orders/{id}/cancel` шлётся только `reason: <ru-строка>`.
- **`paymentTypes: []` массив** — нигде. Шлётся одиночный `paymentType: <int>`.
- В `POST /quests` фронт шлёт пачку доп. полей (`title`, `description`, `reward`, `target`, `unit`, `totalEmployees`, `completedEmployees`, `employeeNames`, `durationDate`), которых нет в `QuestInputsType` — но в бэк-схему может попадать как лишний JSON.

### Обработка ответов с warning "не уехало в iiko"
- **Нет.** `updateOrder`, `payOrder` возвращают `res.data`, верхний слой просто игнорирует поля кроме error/exception. См. `WaiterProvider.tsx:282-309`, `app/waiter/editOrderMenu.tsx:341-378`, `app/waiter/payment.tsx:61-89`. Никаких проверок поля типа `iiko_synced` / `warning` / `message` нет.

### Вызовы `POST /register` (удалённый эндпоинт)
- Да. `src/server/auth.ts:13` + экран `app/auth/registration.tsx` (вся форма с тремя инпутами). Кнопка регистрации жмёт `register({ login, password })` → `POST /register`. **После удаления эндпоинта этот экран будет отдавать 404.** Сам экран `/auth/registration` есть как роут Expo Router, но в основном `/auth/index.tsx` ссылку на регистрацию убрали — однако роут открываем напрямую.

---

## ⚠️ Несовпадения backend ↔ frontend (главное)

1. **`/waiter/{waiter_id}/salary`** — фронт шлёт `User.id` вместо `Employee.id`. Caller `app/waiter/salary.tsx:57`. **Backend ждёт `Employees.id`.** → 404/нули будут массово.

2. **`/waiter/{waiter_id}/quests`** — то же самое. Caller `app/waiter/motivation/index.tsx:30,52` (и `app/waiter/index.tsx:95`). **Backend ждёт `Employees.id`.**

3. **`POST /orders` — поле `waiterId`** — фронт шлёт `user?.id` (User.id) с хардкод-патчем `10 → 322256`. Caller `app/waiter/newOrder.tsx:281`. Тут зависит от бэка: если ожидается `User.id` для последующего маппинга в `Employees.iiko_id` через `User.iiko_id` — может ОК; если ожидается напрямую `Employees.id` или iiko-uuid официанта — не совпадёт. Магическое число `322256` похоже на iiko-id конкретного сотрудника, что говорит о попытке "руками" привести User.id к iiko-id.

4. **`POST /orders/{id}/pay`** — фронт шлёт `{ paymentType: <int> }` (наш id из `GET /payment-types`). Если бэк теперь ждёт массив `paymentTypes: [{iiko_id, payment_type_kind}]` (новая семантика task 4/8) — **несовпадение**. Caller `app/waiter/payment.tsx:66-69`.

5. **`POST /orders/{id}/cancel`** — фронт шлёт `{ reason: <ru-строка> }`. Если бэк теперь требует `removalTypeId` — **несовпадение**. Caller `app/waiter/cancel.tsx:48-51`.

6. **`PUT /orders/{id}` — обработка warning'а** — фронт **не читает** новые поля ответа про "изменения не уехали в iiko". Любой не-2xx → generic alert. Caller `app/waiter/editOrderMenu.tsx:341-378`.

7. **`POST /register`** — эндпоинт удалён на бэке, фронт его всё ещё дёргает с экрана `app/auth/registration.tsx`. Код в `src/server/auth.ts:13` нужно убрать.

8. **`POST /employees/create-users`** — фронт **никогда не дёргает**. Если задача — кнопка "создать пользователей всем сотрудникам", её на фронте просто нет (надо добавить).

9. **`POST /documents/writeoff` и `POST /documents/incoming-invoice`** — фронт **не шлёт** `storeId`, `conceptionId`, `organization_id`. Бэку, если они теперь обязательны/нужны для маршрутизации в нужную точку — будет нечем заполнить.

10. **`GET /payment-types`** — `organization_id` может быть `undefined/null` (тогда `checkFilters` его выкинет). Если бэк теперь ОБЯЗАТЕЛЬНО требует `organization_id` — упадёт.

11. **`GET /menu`** — фронт всегда шлёт только `{ limit: 0 }`, без `organization_id`. Если меню разное между точками — официант получит "что-то усреднённое" / весь список.

12. **`POST /tasks`** — формально совпадает (фронт шлёт `employee_id: <Employee.id>` под полем `employee_id`), несмотря на странное имя `data.user_id` внутри handler'а в `app/ceo/motivation/index.tsx:199-205`. ✅ Это работает.

13. **`POST /quests`** — фронт шлёт нестандартный набор полей (см. раздел 6). Если pydantic-схема бэка строгая — упадёт; если разрешает extra — лишнее проигнорируется, но `date` / `organization_id` / `employee_id` могут не дойти, потому что фронт их не кладёт.

14. **`PUT /change-password`** — фронт шлёт `employee_id` из `GET /employees` → правильно (Employee.id), но у CEO экран — TODO-заглушка (`app/ceo/profile/changePassword.tsx:82-89`), реально функция не вызывается. У Manager — работает (`app/manager/profile/changePassword.tsx:85-89`).

15. **`GET /profile` / `GET /me`** — НИ ОДИН экран не дёргает. Все профильные данные — mock + storage. Новый функционал `employee_id` в `/profile` (что был задеплоен бэком) фронт пока никак не использует.
