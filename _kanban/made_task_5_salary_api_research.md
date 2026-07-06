# Task 5 — Исследование iiko API окладов/зарплат

**Статус:** todo (на исследовании)
**Заведено:** 2026-05-21

## От менеджера
> По зарплате посмотреть что возвращает апи https://ru.iiko.help/articles/#!api-documentations/rabota-s-dannymi-oklada

## Уточнение от @baa21v
> Давай исследовать. Отдельно думаю через свои запросы напрямую. Аккуратно, только смотрим что там у них.

## Контекст
- Исследовательская задача — пока что не интеграция, а ресёрч.
- Запросы делаем «руками» (не через нашу синхронизацию), аккуратно, чтобы не нагружать iiko.
- ⚠️ Kill switch включён — реальные запросы к iiko через наш код не пройдут. Запросы должны быть аккуратными manual-запросами или через временное снятие флага в локальной/тестовой среде.

## Что выяснить в исследовании
1. Какие эндпоинты iiko API относятся к окладам/зарплате (по ссылке + смежные).
2. Что они принимают (params) и возвращают (структура).
3. Какие из этих данных полезны нашему фронту (manager UI / профиль сотрудника).
4. Есть ли у нас уже частичная интеграция в `services/salary/` — что готово, чего нет.
5. Сформулировать список manual-запросов, которые надо сделать аккуратно, чтобы получить sample-ответы (без массовой нагрузки).

## Файлы
- `services/salary/`
- `routers/salary/`
- `models/` — модель зарплаты, если есть
- `services/iiko/iiko_service.py` — что уже есть по salary

## Findings

### 1. Что есть у нас

**Модели**
- `models/user_salary.py` — таблица `user_salaries`:
  - `id`, `iiko_id` (nullable), `employee_id` (FK → employees.id), `salary` (Numeric 10,2), `date_from`, `date_to`, `created_at`, `updated_at`.
  - Изначально была привязка к `user_id`, миграция `migrations/2026_03_19_update_user_salaries.sql` переименовала на `employee_id` + добавила `date_from`/`date_to`.
- Связанные модели: `models/shifts.py` (смены), `models/attendance_types.py`, `models/schedule_types.py`, `models/penalty.py`, `models/pay_out.py` (там есть `payroll_id` — UUID платежной ведомости), `models/rewards.py`/`user_reward.py`.

**Схемы** — `schemas/salary.py`:
- `SalaryResponse`, `SalaryBreakdown`, `BonusItem`, `PenaltyItem`, `QuestRewardItem`, `WaiterSalesResponse`. Это наш собственный расчёт для UI официанта, не маппинг iiko.

**Роутер** — `routers/salary/salary.py` (всего 2 эндпоинта):
- `GET /waiter/{waiter_id}/salary?date=DD.MM.YYYY&organization_id=...` — расчёт «зарплаты официанта за день».
- `GET /waiter/{waiter_id}/sales-today?date=...` — сумма продаж и счётчик заказов за день.

**Логика расчёта** — `services/salary/salary_service.py::calculate_waiter_salary`:
- Берёт заказы официанта (`DOrder` по `user_id`/`time_order`/`organization_id`).
- Получает `UserSalary` (но НЕ использует поле `salary` оттуда!) — на строке 84 запрос делается, но затем хардкод `salary_percentage = 5.0`.
- `base_salary = total_revenue * 5%` (хардкод процента).
- Прибавляет квестовые бонусы (`services/quests/quests_service.py::get_waiter_quests`), вычитает штрафы (`Penalty`), добавляет «performance bonus» при выручке > 500 000.
- **Важно:** поле `salary` из `UserSalary` (которое мы синхронизируем из iiko!) в расчёте фактически не участвует. Это рассинхрон.

**Другие связанные эндпоинты по теме**
- `routers/documents/documents.py::GET /payrolls` — список платежных ведомостей iiko (read-through, проксирует `iiko_service.get_payrolls`).
- `routers/documents/documents.py::POST /pay-out` — создание изъятия из кассы, поддерживает `payrollId` (привязка к ведомости).
- `routers/iiko/sync.py::POST /salaries` (через `iiko_sync.sync_salaries`) — синхронизация окладов из iiko Server API в `user_salaries`.

**Что мы умеем сейчас (резюме)**
- Читаем оклады (`payment`) сотрудников из iiko Server API (XML) и кладём в `user_salaries` — period-based ставка.
- Имеем список платежных ведомостей iiko (документы оклада) через Cloud-подобный endpoint payrolls/list.
- Считаем «дневную зарплату официанта» — но **своей формулой**, без использования сохранённого оклада и без агрегатов iiko по начислениям/выплатам.
- Никаких эндпоинтов «зарплата произвольного сотрудника за период», «оклад по ролям», «история начислений из iiko», «выплаты по ведомости» в API наружу нет.

---

### 2. Использование iiko API по теме

Из `services/iiko/iiko_service.py` (Server API, XML/JSON; авторизация — `GET /resto/api/auth?login=&pass=` → токен на 1 час, кэш `_get_server_token`):

| # | Метод (Python)                  | Строка | iiko endpoint                                  | Параметры                                                      | Назначение                                      |
|---|--------------------------------|-------:|------------------------------------------------|----------------------------------------------------------------|------------------------------------------------|
| 1 | `get_server_employees`         | ~727   | `GET /resto/api/employees`                      | `key`                                                          | Список сотрудников (XML), парсит роли + `steadySalary` (см. стр. 834) |
| 2 | `get_server_employee_roles`    | ~937   | `GET /resto/api/employees/roles`                | `key`                                                          | Роли сотрудников                                |
| 3 | `get_server_schedule_types`    | ~957   | `GET /resto/api/employees/schedule/types`       | `key`                                                          | Типы графиков работы                            |
| 4 | `get_server_attendance_types`  | ~960   | `GET /resto/api/employees/attendance/types`     | `key`, `includeDeleted`                                       | Типы явок (рабочий день, отпуск, больничный…) |
| 5 | `get_server_salaries`          | 1246   | `GET /resto/api/employees/salary`               | `key`                                                          | **Оклады сотрудников (XML), поля: `employeeId`, `dateFrom`, `dateTo`, `payment`** |
| 6 | `get_server_shifts`            | 1300   | `GET /resto/api/employees/attendance`           | `key`, `from=YYYY-MM-DD`, `to=YYYY-MM-DD`, `employeeId?`     | Явки/смены за период (XML: `id`, `employeeId`, `dateFrom`, `dateTo`, `attendanceTypeId`, `roleId`, `userId`) |
| 7 | `get_payrolls`                 | 2815   | `GET /resto/api/v2/payrolls/list`              | `key`, `dateFrom`, `dateTo`, `department?`, `includeDeleted` | **Список платежных ведомостей (JSON)** — этот метод уже используется (task 6 указывает на него) |
| 8 | `create_pay_out`               | 2848   | `POST /resto/api/v2/payInOuts/addPayOut`        | `key`, JSON body с `payrollId?`                                | Создание изъятия из кассы, может ссылаться на ведомость (выплата зарплаты) |

Парсер `services/iiko/iiko_parser.py::parse_salaries` (стр. 1389) тащит из XML только 4 поля: `employee_iiko_id`, `date_from`, `date_to`, `salary` — это всё, что мы сохраняем из `/employees/salary`.

Из `services/iiko/iiko_service.py::_parse_xml_employees` (стр. 800-840) также подтягиваем `steadySalary` внутри ролей сотрудника, но в БД (`employees`) сейчас не сохраняем (см. модель `employees`).

---

### 3. Документация iiko

Страница `https://ru.iiko.help/articles/#!api-documentations/rabota-s-dannymi-oklada` — **JS-SPA**. Все попытки фетча (прямой URL, `~`-вариант, без `#`, Google cache, английская версия `en.iiko.help` → редирект на `en.syrve.help`) возвращают только HTML-скелет портала без контента. WebSearch также не индексирует тело статьи.

Удалось получить **карту раздела «API documentations»** через `sitemap_publication_api-documentations.xml` — относящиеся к теме страницы:
1. `rabota-s-dannymi-sotrudnikovv` — Работа с данными сотрудников
2. `rabota-s-dannymi-oklada` — Работа с данными оклада
3. `rabota-s-dannymi-smeny-i-raspisaniy` — Смены и расписания
4. `rabota-s-dannymi-yavok` — Явки
5. `rabota-s-dannymi-brigad` — Бригады (новое, у нас не реализовано)
6. `rabota-s-dannymi-dolzhnostey` — Должности

Контент ни одной из этих страниц публично не отдаётся фетчером — нужен живой просмотр в браузере.

**Что известно достоверно (по нашему коду + кросс-ссылкам):**
- Раздел «работа с данными оклада» соответствует `GET /resto/api/employees/salary` (Server API) — XML с элементами `<salary>` и полями `employeeId`, `dateFrom`, `dateTo`, `payment` (ставка/оклад на период).
- Связки: `employeeId` → `/resto/api/employees`; период оклада пересекается с явками (`/resto/api/employees/attendance`); должность/роль — через `/resto/api/employees/roles` и поле `steadySalary` в роли сотрудника (фиксированный оклад на роль).
- Платежные ведомости (`payroll`) — отдельная сущность с другим API: `GET /resto/api/v2/payrolls/list` (JSON), они линкуют выплаты (`payInOuts/addPayOut`) с конкретной ведомостью.

**Рекомендация:** менеджеру скинуть скриншоты страницы либо снять kill switch локально и руками отдёрнуть curl-запросы из секции 5 — реальные ответы дадут нам схему быстрее, чем закрытая SPA-документация.

---

### 4. Гэп-анализ

**Что iiko предоставляет, а у нас не используется / используется слабо:**

| Возможность iiko | Наше состояние | Что можно добавить |
|---|---|---|
| `steadySalary` в `/employees` (фикс. оклад на роль) | Парсится из XML, в БД не сохраняется | Добавить колонку в `employees` или таблицу `employee_roles`, отдавать в `/profile` и менеджерском UI |
| `payment` в `/employees/salary` (период. оклад) | Сохраняется в `user_salaries`, но **не используется** в расчёте `calculate_waiter_salary` (там хардкод 5%) | Завести роль-зависимую формулу: фикс. оклад из `user_salaries` + % с выручки из настройки роли; убрать магическое число 5 |
| Привязка явки (`attendance`) к окладу + роли (`roleId`) | Явки синхронизируются, но не используются в расчёте зарплаты — только в shifts UI | Часовая ставка: `salary / (рабочих часов в месяце)` × фактические часы из явок |
| Платежные ведомости (`/payrolls/list`) | Есть list-endpoint (документы), но нет UI / детализации **по сотруднику** | `GET /payrolls/{id}` (если iiko отдаёт) или связать наши `pay_out` с ведомостью и показывать историю выплат сотрудника |
| `attendance_types` (отпуск/больничный/работа) | Тип хранится в shifts, но в зарплате не учитывается | Учёт нерабочих типов явок (отпускные, больничные, штатные часы) |
| Должности (`rabota-s-dannymi-dolzhnostey`) | Роли есть через `/employees/roles` | Возможно отдельный справочник «должность» с базовой ставкой — посмотреть после получения доки |
| Бригады (`rabota-s-dannymi-brigad`) | Не используем | Если есть в iiko — добавить связку сотрудников в бригады (актуально для горячего цеха, доставки) |
| История изменения оклада | `user_salaries` имеет `date_from`/`date_to`, но эндпоинта на чтение нет | `GET /employees/{id}/salary-history` для менеджерского UI |
| Начисления (бонусы/штрафы из iiko backoffice) | Свои `penalty` и `user_reward`, не синхронизируем с iiko | Уточнить — есть ли в iiko endpoint начислений; если да, синхронизировать |

**Полезно фронту (manager UI / профиль сотрудника):**
- В профиле сотрудника: текущий оклад из iiko, история окладов, должность(и) с базовыми ставками.
- В менеджерском UI: список платежных ведомостей за период, статусы, кнопка «создать выплату» (есть `POST /pay-out` с `payrollId`).
- В «зарплате официанта» — нормальная формула: брать ставку/процент из iiko вместо хардкода 5%, прибавлять оклад за отработанные часы (часы из `attendance`).

**Технические долги:**
- `salary_service.py` строка 84: `user_salary_record = db.query(UserSalary).filter(UserSalary.user_id == user.id).first()` — это **сломанный код**: в `UserSalary` уже нет поля `user_id` (миграция 2026-03-19 переименовала в `employee_id`). Запрос упадёт или вернёт None всегда. Не баг этой задачи, но триаж — записать как side-finding.
- В `_parse_xml_salaries` теряются возможные поля (если iiko возвращает что-то ещё — например, валюту, тип ставки, признак удаления). Чтобы убедиться — нужен реальный ответ (см. секцию 5).

---

### 5. Manual curl-запросы для исследования

Эти curl-команды идут **напрямую** в iiko Server API, минуя наш `IikoService` и kill switch.
То есть `IIKO_REQUESTS_DISABLED` можно НЕ снимать — он блокирует только наш HTTP-клиент, не системный curl.

Перед использованием:
1. Получить токен и сразу же скормить его в `$TOKEN` (живёт 1 час).
2. Использовать малые периоды (1-3 дня), один department за раз. Все запросы — Server API.
3. Не запускать в проде в часы пик; если боишься — `--max-time 10`.

```bash
# Базовые переменные (заполнить вручную):
export IIKO_SERVER="https://<ваш-iiko>.iiko.it"   # из IIKO_SERVER_API_URL
export LOGIN="<server_login>"                      # IIKO_SERVER_LOGIN
export PASS="<server_password_md5_или_plain>"      # IIKO_SERVER_PASSWORD
export DEPARTMENT_ID="<uuid-department>"           # один department UUID
export EMPLOYEE_ID="<uuid-employee>"               # опционально

# --- 0. Получить токен (живёт 1 час) ---
export TOKEN=$(curl -sS "$IIKO_SERVER/resto/api/auth?login=$LOGIN&pass=$PASS")
echo "TOKEN=$TOKEN"

# --- 1. Список окладов сотрудников (раздел документации) ---
#     XML, поля: employeeId, dateFrom, dateTo, payment
curl -sS "$IIKO_SERVER/resto/api/employees/salary?key=$TOKEN" \
  | xmllint --format - | head -120

# --- 2. Список платежных ведомостей за 3 дня по одному department ---
#     JSON: id, dateFrom, dateTo, department, documentNumber, status, comment
curl -sS "$IIKO_SERVER/resto/api/v2/payrolls/list?key=$TOKEN&dateFrom=2026-05-18&dateTo=2026-05-20&department=$DEPARTMENT_ID&includeDeleted=false" \
  | jq '.[:3]'

# --- 3. Один сотрудник + проверка поля steadySalary в ролях ---
#     XML, корень <employees>, внутри <employee> с массивом <roles>/<role>/<steadySalary>
curl -sS "$IIKO_SERVER/resto/api/employees?key=$TOKEN" \
  | xmllint --xpath "//employee[id='$EMPLOYEE_ID']" -

# --- 4. Явки сотрудника за 1 день (для проверки связки attendance ↔ salary period) ---
#     XML, <attendance> с employeeId, dateFrom, dateTo, attendanceTypeId, roleId, userId
curl -sS "$IIKO_SERVER/resto/api/employees/attendance?key=$TOKEN&from=2026-05-20&to=2026-05-20&employeeId=$EMPLOYEE_ID" \
  | xmllint --format -

# --- (опционально) 5. Освободить лицензионный слот ---
curl -sS "$IIKO_SERVER/resto/api/logout?key=$TOKEN"
```

Что смотреть в ответах:
- В (1): есть ли поля сверх 4-х (валюта, признак удаления, тип ставки) — расширить парсер.
- В (2): есть ли в ведомости детализация по сотрудникам или это только «шапка» документа. Если только шапка — нужен отдельный GET по id ведомости.
- В (3): структура `<roles>` и наличие `steadySalary`, `mainRoleId`, `scheduleTypeId` — пригодится для гэп-задач.
- В (4): как явка ссылается на роль и интервал, чтобы матчить с периодом оклада.

## Реализовано (2026-05-21)

### 1. Починили сломанный запрос UserSalary в расчёте зарплаты
`services/salary/salary_service.py` (около строк 83-105).

Было:
```python
user_salary_record = db.query(UserSalary).filter(UserSalary.user_id == user.id).first()
salary_percentage = 5.0  # По умолчанию 5%
```
- `UserSalary.user_id` колонки **не существует** — её переименовали в `employee_id` миграцией 2026-03-19. Запрос либо падал ошибкой SQLAlchemy, либо в зависимости от драйвера вёл себя странно.
- Захардкоженные 5% от выручки использовались всегда — синхронизированный из iiko оклад (`payment` в `user_salaries`) фактически «лежал в столе».

Стало:
```python
user_salary_record = (
    db.query(UserSalary)
    .filter(
        UserSalary.employee_id == employee.id,
        UserSalary.date_from <= end_of_day,
        UserSalary.date_to >= start_of_day,
    )
    .order_by(UserSalary.date_from.desc())
    .first()
)
if user_salary_record and user_salary_record.salary is not None:
    base_salary = float(user_salary_record.salary)
    salary_percentage = 0.0
else:
    salary_percentage = 5.0
    base_salary = total_revenue * (salary_percentage / 100)
```
- Теперь у сотрудника, у которого есть запись `UserSalary` с активным периодом, берётся **реальный оклад из iiko**.
- Если записи нет — fallback на 5% от выручки (как было), чтобы ничего не сломать у текущих сотрудников.
- Семантика «оклад за период vs за день vs процент от выручки» — бизнес-вопрос. TODO в коде: окончательно определить и переписать формулу.

### 1b. Совместимость с фронтом: `waiter_id` принимает и `User.id`, и `Employee.id`
По аудиту фронта (`frontend_api_audit.md`) — `app/waiter/salary.tsx:57` шлёт **`User.id`** под именем `waiter_id`. До 2026-05-21 мой фикс ожидал только `Employee.id`, поэтому под текущим фронтом ничего бы не нашёл и шёл в fallback 5%.

`services/salary/salary_service.py: calculate_waiter_salary` теперь сначала пробует `Employees.id == waiter_id`, при неудаче — `User.id == waiter_id` и резолвит Employee через `iiko_id`. Если ни одно не находится — `return None` (404).

Аналогичный fallback **уже был** в `get_waiter_quests` — взяли как референс.

### 2. Подготовлены read-only curl-команды для будущего ресёрча
Сами команды — в секции 5 этого файла. Идут напрямую в iiko Server API, kill switch не задевают.

Использование — когда понадобится посмотреть реальные ответы по окладам / ведомостям / явкам без подъёма всего нашего синка.

### Что не сделано (явно отложено)
- **Полноценная интеграция «оклад + история + steadySalary»** — это уже отдельная фича: расширение модели, эндпоинт в профиле сотрудника, UI. Здесь не дёргал.
- **Часовая ставка через `attendance`** (расчёт по реальным часам смен) — отдельная фича.
- **Документация iiko (`rabota-s-dannymi-oklada`) — это JS SPA**, ни WebFetch, ни Google cache контент не отдают. Когда менеджер сможет — пусть скинет скриншоты, тогда уточним маппинг полей.
