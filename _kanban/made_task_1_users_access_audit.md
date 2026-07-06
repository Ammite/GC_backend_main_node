# Task 1 — Аудит юзеров, ролей и паролей

**Статус:** todo (на исследовании)
**Заведено:** 2026-05-21

## От менеджера
> Проверить чтобы все юзеры правильные доступа имели и могли нормально авторизоваться

## Уточнение от @baa21v
> Надо убедиться что всем сотрудникам создан user и правильные роли стоят у всех везде, и правильные пароли.

## Контекст
- Юзеры связаны с Employee через `iiko_id`.
- Пароли — sha256 hex (`utils/security.py: hash_password`).
- 2026-02-24 уже сделали `POST /employees/create-users` (массовое создание юзеров из сотрудников) и `PUT /auth/change-password`.

## Что выяснить в исследовании
1. У всех ли активных сотрудников (Employee) есть User? Кто пропущен и почему — нет `iiko_id`, нет логина, не подходит роль?
2. Как сейчас выставляется `roles_id` при создании юзера через `create_users_for_all_employees`? Корректно ли?
3. Есть ли сотрудники с юзером, но без пароля / с дефолтным паролем?
4. Какие сейчас роли есть в системе и какие маппинги на `main_role_code` из Employee?
5. Логика логина — корректно ли проходит сравнение пароля, нет ли утечек, кейс-сенс и т.п.?
6. Сценарии «не пускает» — что в логах за последние недели?

## Файлы, куда смотреть
- `models/users.py`, `models/employees.py`, `models/roles.py` (или аналог)
- `services/employees/employees_service.py` — `create_users_for_all_employees`
- `routers/auth/`, `routers/users/`, `routers/employees/`
- `utils/security.py`
- `logs/` — последние записи об ошибках авторизации

## Findings

Исследование от 2026-05-21. Все цифры получены SELECT-запросами к проду через `venv/bin/python` + SQLAlchemy. Никаких изменений в коде/БД не делалось.

### 1. Модели

**`models/user.py` (таблица `users`)**
- `id` (PK, autoincrement)
- `iiko_id` (String 50, unique, **nullable**)
- `name` (String 100, nullable) — обычно пустое
- `login` (String 100, unique, NOT NULL, indexed)
- `password` (String 255, NOT NULL) — sha256 hex
- `roles_id` (FK -> `roles.id`, nullable)
- `app_role` (String 50, nullable) — строка вида "Владелец" / "Менеджер" / "Официант"

**`models/employees.py` (таблица `employees`)** — поля связанные с правами:
- `iiko_id` (String 50, unique, **NOT NULL**)
- `login`, `password` — нативные поля Employee (приходят из iiko), отдельно от User
- `main_role_id` (FK -> `roles.id`), `main_role_code` (String) — основная роль
- `roles_id` (`ARRAY(Integer)`), `role_codes` (`ARRAY(String)`) — все роли сотрудника
- `deleted` (Boolean) — флаг увольнения

**`models/roles.py` (таблица `roles`)**
- `id`, `iiko_id` (unique, NOT NULL), `code`, `name`, `payment_per_hour`, `steady_salary`, `schedule_type`, `deleted`.

Связь User <-> Employee только через `iiko_id` (string match). Связь Employee -> Roles реализована и как FK (`main_role_id`), и как массив (`roles_id`), и как строковые коды.

В БД сейчас **82 роли**, синхронизируются из iiko (`services/iiko/iiko_sync.py: sync_roles`). Есть искусственная локальная роль `OWNER` (`iiko_id='owner-role-local'`, id=82, name='Владелец'). Дублирующиеся `code` (e.g. `HR` x2, `BR1` vs `БАРМЕ`, кириллица вперемешку с латиницей) — мусор из iiko, но это не блокирует логин.

Никаких енамов/констант для `app_role` в коде **нет**. Комментарий в `models/user.py` упоминает три значения `"Владелец"`, `"Менеджер"`, `"Официант"`, и они захардкожены только в миграции `migrations/2026_03_26_add_app_role_to_users.sql`.

### 2. Логика ролей

**`create_users_for_all_employees(db)`** (`services/employees/employees_service.py:1051`):
- проходит по `Employees.deleted == False`,
- пропускает того, чей `iiko_id` уже есть в `users.iiko_id`,
- генерирует `login = transliterate(employee.name)` + при коллизии добавляет суффикс,
- генерирует `plain_password` = 8 случайных букв/цифр (`secrets.choice`),
- создаёт `User(login=..., password=hash_password(plain_password), iiko_id=employee.iiko_id)`.
- **`roles_id` и `app_role` НЕ выставляются вообще** — оба остаются NULL.

**`recreate_all_credentials(db)`** и `regenerate_user_logins(db)` — тоже не трогают `roles_id` / `app_role`.

Маппинга `Employee.main_role_code` -> `User.roles_id` в коде **нет нигде**. Единственное, что роль в коде где-то реально проставляется — миграция от 2026-03-26, которая руками выставила `app_role` для login = 'admin' / 'manager' / 'ofik'.

Дефолт для `app_role` и `roles_id` в `User` — `NULL`.

### 3. Логика логина

`routers/auth/auth.py: POST /login` (mount без префикса — endpoint `/login`):
- читает `LoginRequest { login: str, password: str }` (`schemas/auth.py`),
- `db.query(User).filter(User.login == request.login).first()` — **case-sensitive** (Postgres `=`, без `ilike`),
- `verify_password(request.password, user.password)` -> `hashlib.sha256(password.encode()).hexdigest() == hashed_password` (`utils/security.py:20`),
- если не сходится — возвращает `200 OK { success: false, message: "Invalid credentials" }` (НЕ 401),
- иначе создаёт JWT (`HS*`, секрет в `config.JWT_SECRET_KEY`, expires 5 дней), кладёт в payload `sub = user.login`,
- ответ включает `role: user.app_role` (просто строка) и `name` сотрудника.

`POST /register` (`routers/auth/auth.py:88`) — **публичный, без авторизации**, создаёт User без `iiko_id`, без `roles_id`, без `app_role`. Это лазейка: любой может зарегистрировать себе аккаунт без привязки к сотруднику; JWT он получит, но дальнейшие зависимости `get_current_user` пройдут (проверяется только наличие user.login).

`PUT /change-password` (`routers/auth/auth.py:123`) — требует `Depends(get_current_user)`, но **никакой проверки роли нет** (комментарий «требуется manager или owner» неправда). Любой авторизованный пользователь, включая того, кто только что сам себя зарегистрировал через `/register`, может сменить пароль любому сотруднику по `employee_id`.

Никаких ограничений на пустой / слабый пароль ни в `/register`, ни в `/change-password`, ни в `/login` нет. `request.password` — обычная строка из Pydantic, пустую строку Pydantic примет.

Авторизация только по `login`. Альтернативных путей (email / phone) нет.

`OAuth2PasswordBearer(tokenUrl="/login")` в `utils/security.py:30` — это просто URL для Swagger, фактический логин — JSON-body, а не form-urlencoded.

### 4. Состояние БД

Запросы выполнены 2026-05-21 через `venv/bin/python`.

**Employees:**
- Всего: **259**
- Не удалённых (`deleted=false`): **183**
- Удалённых: **76**
- Без `iiko_id`: **0** (поле NOT NULL по схеме)
- С заполненным `main_role_code`: **257**
- С пустым `main_role_code`: **2** — оба тестовые: `Manager` (id=1851), `Test Employee` (id=1297)
- Все `main_role_code` ссылаются на существующие `roles.code` — **нет несоответствий**.
- Distribution `main_role_code` среди живых: `WR1`=43 (Официант), `PoV`=38 (повар), `BR1`=16 (Бармен), `ADM`=13, `MN1`=11 (Менеджер), `Sous chef`=9, и т.д.

**Users:**
- Всего: **256**
- Без `iiko_id`: **0**
- С `iiko_id`, у которого нет соответствующего Employee: **0**
- С NULL/пустым паролем: **0**
- С паролем длины != 64: **0**
- С паролем не-hex: **0**
- Дубликатов паролей: **нет**
- Дубликатов login (case-insensitive): **нет**
- Совпавших с распространёнными дефолтами (admin, qwerty, 12345, 123456, password, iiko, restoresto, etc.) — **0**
- С `roles_id IS NULL`: **253 из 256** (99%!). Заполнено только у admin (id=1), manager (id=1250), ofik (id=10).
- С `roles_id` указывающим на несуществующую роль: **0**
- С `app_role IS NULL`: **253 из 256**. Заполнено только у admin/manager/ofik (миграцией от 2026-03-26).

**Employee <-> User линковка:**
- Живых Employees с привязанным User: **183 / 183** (100% покрытие)
- **Живых Employees без User: 0** — массовое создание было сделано.
- Удалённых Employees, у которых User всё ещё активен: **73 из 76** — User-записи не помечаются и не блокируются при увольнении сотрудника. Технически любой уволенный с известным логином/паролем по-прежнему может войти.

### 5. Логи ошибок

В `/srv/project/backend_main_node/logs/` лежат только `sync_cron.log` и `daily_sync_cron.log` — это вывод cron-скриптов синхронизации с iiko. **Application/uvicorn логов нет вообще** — `find` по диску ничего не нашёл; auth-события (`/login`, неудачные пароли) **никуда не пишутся** на диск.

Logger в `routers/auth/auth.py` есть и пишет `logger.info` при `change-password`, но для `/login` нет ни warn, ни info-сообщения. Соответственно опереться на «частые ошибки» нельзя — это отдельная проблема: ноль аудита аутентификации.

### 6. Список рисков

В порядке приоритета:

1. **253 из 256 юзеров не имеют ни `roles_id`, ни `app_role`.** Логин для них формально работает, но API отдаёт `role: null`. Любая фича, которая в фронте смотрит на `role`, по факту даёт «никакую роль». **Это главное «не правильные роли стоят»** из задачи. `create_users_for_all_employees` не маппит `Employee.main_role_code` на `User.roles_id` и не выставляет `app_role`.
2. **Открытый `POST /register` без префикса и без авторизации.** Кто угодно может создать себе валидного юзера + JWT, а потом через `/change-password` (там нет проверки роли!) сменить пароль ЛЮБОМУ сотруднику по `employee_id`. Это критическая security-проблема.
3. **`/change-password` не проверяет роль вызывающего**, хотя docstring это обещает. Любой залогиненный — может сменить любому пароль.
4. **73 уволенных сотрудника (`deleted=true`) сохранили активные User**: login + пароль работают. Логика «увольнение -> отключение User» отсутствует.
5. **Нет валидации пустого / слабого пароля** ни в `/register`, ни в `/change-password`. Pydantic примет `""`.
6. **Нет логирования попыток логина** (ни успешных, ни неудачных) — невозможно диагностировать «не пускает».
7. **Сравнение пароля простым `==`**: не timing-safe, но при sha256 это лишь теоретическая проблема. Хеш — простой sha256 без соли, без bcrypt/argon2 — устаревшая схема.
8. **2 «технических» Employee (`Manager` id=1851, `Test Employee` id=1297)** без `main_role_code` — мусорные сущности, оставшиеся от тестов; их юзеры (manager/admin) — единственные с проставленными `roles_id`/`app_role`.
9. Сейчас в БД нет дефолтных/слабых паролей (`recreate_all_credentials` выдал каждому случайные 8 символов), но **открытые `/register` + `/change-password` сводят это на нет** — атакующий может перезаписать любой пароль.

**TL;DR для менеджера:** все живые сотрудники имеют User и пароль выглядит «нормальным» (sha256, рандом). Но 99% юзеров не имеют выставленных ролей в БД (`roles_id`/`app_role` = NULL), и есть открытые `/register` + не защищённый по ролям `/change-password` — это позволяет любому захватить аккаунт.

## Реализовано (2026-05-21)

### 1. Удалён публичный `POST /register` ⚠️ откачен позже того же дня
`routers/auth/auth.py` — эндпоинт сначала был убран целиком. **Возвращён 2026-05-21 (тот же день) под совместимость с фронтом** (аудит `frontend_api_audit.md`): экран `app/auth/registration.tsx` активно использует `POST /register` через `src/server/auth.ts:13`. Без него регистрация на фронте → 404.

Текущее состояние:
- `POST /register` снова есть, работает как раньше (создаёт User без `iiko_id`/`roles_id`/`app_role`).
- В docstring помечен как «временный, для совместимости с фронтом, см. вопрос S1».
- Долгосрочное решение — в `questions_for_client_call.md → S1` (на созвон): убрать экран с фронта **или** защитить эндпоинт ролью владельца.

Альтернативные пути создания юзеров остаются:
- Массово — `POST /employees/create-users`.
- Смена пароля — `PUT /change-password` (теперь под менеджером, см. ниже).

### 2. `PUT /change-password` теперь требует роль
`routers/auth/auth.py: change_password`: проверка `current_user.app_role IN {"Владелец", "Менеджер"}`, иначе 403. Неудачные попытки логируются (`logger.warning`).

### 3. Блокировка логина уволенных сотрудников
`routers/auth/auth.py: login`: после нахождения юзера ищем связанного `Employee` по `iiko_id` и, если `deleted=True`, отказываем (`success: false, message: "Account disabled"`). 73 ранее активных «уволенных» юзера теперь не зайдут.

### 4. Аудит-логи аутентификации
`routers/auth/auth.py: login` теперь пишет:
- `logger.warning` на неудачную попытку (с указанием логина);
- `logger.warning` на блокировку уволенного;
- `logger.info` на успешный вход.

⚠️ Логи сейчас уходят только в stdout — отдельная задача поставить файловый/journald-логгер для долгого аудита (см. findings task 2 — там это упомянуто отдельно).

### 5. `create_users_for_all_employees` теперь проставляет роль
`services/employees/employees_service.py`:
- При создании User выставляются `roles_id = employee.main_role_id` и `app_role` через маппинг `_map_role_code_to_app_role`.
- Маппинг (по распределению из findings):
  - `ADM`, `MN0`, `MN1`, `TekhD`, `GBuh` → `"Менеджер"`
  - `WR1` → `"Официант"`
  - всё остальное → `"Сотрудник"`
- Маппинг — heuristic, при необходимости — уточнить бизнес-маппинг и обновить `_MANAGER_CODES`/`_WAITER_CODES`. Та же логика продублирована в SQL-миграции (см. ниже) — синхронизировать оба места.

### 6. Миграция для 253 существующих юзеров
`migrations/2026_05_21_populate_user_roles_and_app_role.sql` — однократный `UPDATE`, который проставит `roles_id` и `app_role` всем юзерам, где они NULL, на основе связанного Employee.
- Идемпотентна (через `COALESCE` + `WHERE ... IS NULL`).
- Логика маппинга совпадает с Python-функцией.
- **Запустить вручную** (через `migrations/run_migration.py` или из psql). Не вшивал в автозапуск — нужно посмотреть результат глазами через контрольные SELECT-ы внизу файла.

### Что не сделано (по этой задаче)
- Логи аудита уходят в stdout — нет файлового логгера. Это пересекается с task 2 («нет HTTP-логов»). Разумнее решить общим конфигом логирования отдельной задачей.
- Кейс-сенситивность логина (`User.login == request.login`) и проверка слабых паролей не трогал — не критично сейчас, поведение «case-sensitive» местами даже желательно. Если потребуется — отдельной задачей.
- `2 «технических»` Employee без `main_role_code` остаются — но они и так помечены не как мусор фронтом, а как просто роль NULL.

## Дополнительная итерация (2026-05-24)

### 7. Финальный маппинг ролей (v2) — миграция применена в проде
Требование @baa21v:
> Сделать чтобы у официантов был доступ только к офикам. У Акжан и у Амира были владельцы + менеджер + официант. У всех остальных доступ только на менеджера + официанта.

Сделано:
- **Только 2 автоматических уровня**: «Менеджер» (директора, бухгалтерия, шефы, HR) и «Официант» (всё остальное). Убран fallback «Сотрудник».
- **Расширен `_MANAGER_CODES`** в `services/employees/employees_service.py:1054` — теперь 16 кодов вместо 5: `ADM, MN0, MN1, MD, GuestM, TekhD, CFO, OpDir, ZFD, GBuh, buh, BUH, HR, BChef, BChefB, менеджер`.
- **Удалён `_WAITER_CODES`** — теперь любой не-Менеджер автоматически Официант.
- **Akzhan (id=1622) и Амир Байжанович (id=1662)** — принудительно «Владелец» + `roles_id=82` (локальная OWNER role) через миграцию.

Миграция: `migrations/2026_05_24_role_mapping_v2.sql` (применена 2026-05-24). Старая v1 (`2026_05_21_populate_user_roles_and_app_role.sql`) **никогда не запускалась** и помечена как DEPRECATED.

Финальное распределение в проде (после применения):
| app_role | юзеров |
|---|---|
| Официант | 221 (148 живых + 73 уволенных) |
| Менеджер | 32 |
| Владелец | 3 (Акжан, Амир, legacy admin) |
| NULL | 0 |

### 8. Открытые задачи, заведённые из этой итерации
- [[task_10_backend_role_enforcement]] — проверки ролей на самих endpoints (фронт фильтрует, бэк нет — потенциальная дыра)
- [[task_11_password_export_verification]] — как проверить выгрузку паролей сотрудникам, когда вспомним откуда выгружали

### 9. Что осталось ждать после восстановления Server API
- Точное соответствие JurPerson UUID (`b60190ad..`, `c2115cb4..`, `945e983c..`) → имена юр.лиц (ИП Шаяхметов / Акжан / Амиржан). Сейчас гипотеза: главный — `b60190ad..` (4 точки, включая ГолОфис), две оставшиеся — Акжан/Амиржан. Подтвердить через `/resto/api/corporation/departments` JURPERSON-узлы.
- Когда подтвердим — можно будет (если потребуется) ограничить «Владелец» по юр.лицу (только для орг. Акжан/Амиржан), но это похоже не нужно — сейчас у Владельцев нет автомата по юр.лицу, только конкретные Akzhan/Амир по emp_id.

