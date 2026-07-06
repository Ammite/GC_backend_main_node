# Task 7 — Раздел «Мотивация»: фильтры, кнопки, табы

**Статус:** todo (на исследовании)
**Заведено:** 2026-05-21

## От менеджера (Khamzinho)

### 18 мая 2026 г., 00:33
> Сделать фильтр как в анал[итике]

### 18 мая 2026 г., 00:32
> Добавить фильтр по дате как в аналитике и по умолчанию отображать последние 7 дней

### 18 мая 2026 г., 00:32
> Сделать чтобы фильтр по дате был как в аналитике

### 16 апр. 2026 г., 22:35
> http://85.198.88.117/manager
> Тут в разделе мотивации сейчас есть только кнопка добавить.
> Нужно сделать две кнопки:
> - Добавить (открывается модалка создания)
> - Посмотреть квесты (открывается форма всех квестов)
>
> В форме отображения квестов таски и квесты поделить по табам

## Уточнение от @baa21v
> Давай просмотрим.

## Контекст
- В этом репозитории — бэкенд. UI находится в другом репозитории.
- Здесь интересует **бэкенд-поддержка**: какие эндпоинты есть, чего не хватает, чтобы фронт это собрал.
- Связано с `routers/quests/` и `routers/tasks/`.

## Что выяснить в исследовании
1. Какой бэкенд сейчас есть под мотивацию: листинг квестов, листинг тасков, создание, обновление, удаление, агрегаты?
2. Поддерживают ли эти эндпоинты `date_from/date_to`? Если да — по какому полю фильтруют? Если нет — где надо допилить?
3. Какой формат фильтрации **по дате в аналитике** (`routers/analytics/`) — взять его как референс, чтобы фронт работал единообразно.
4. По умолчанию «последние 7 дней» — это вычисляется на фронте или на бэке? Что предпочтительнее в нашей текущей архитектуре?
5. Что нужно для «формы всех квестов с табами» — какой API ждёт фронт, есть ли единый эндпоинт листинга или нужны два (quests, tasks)?

## Файлы
- `routers/quests/`, `services/quests/`
- `routers/tasks/`, `services/tasks/`
- `routers/analytics/` — паттерн фильтрации по дате как референс

## Findings

### 1. Quests endpoints

Файл: `routers/quests/quests.py`. Префикс пустой (`""`), тег `quests`. Все защищены `get_current_user`.

| Метод  | Путь                              | Описание                                                          | Параметры                                                                                                          |
|--------|-----------------------------------|-------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| GET    | `/waiter/{waiter_id}/quests`      | Квесты конкретного официанта на дату                              | path: `waiter_id`; query: `date` (DD.MM.YYYY, default — сегодня), `organization_id`                                |
| POST   | `/quests`                         | Создать квест (CEO)                                               | body: `CreateQuestRequest` — `title`, `description`, `reward`, `target`, `unit`, `date` (DD.MM.YYYY), `employeeIds?`, `organization_id?` |
| GET    | `/quests/active`                  | Список активных квестов на дату                                   | query: `date` (DD.MM.YYYY, default — сегодня), `organization_id`                                                   |
| GET    | `/quests/{quest_id}`              | Детали квеста (прогресс всех сотрудников)                         | path: `quest_id`; query: `organization_id`                                                                          |
| GET    | `/quests/{quest_id}/progress`     | То же самое, что и предыдущий (дубль, вызывает `get_quest_detail`) | path: `quest_id`; query: `organization_id`                                                                          |
| PUT    | `/quests/{quest_id}`              | Обновить квест                                                    | path + body: `UpdateQuestRequest` — все поля опциональны                                                            |
| DELETE | `/quests/{quest_id}`              | Удалить квест                                                     | path: `quest_id`                                                                                                    |

**Важное:** общего листинга `GET /quests` с фильтром `date_from`/`date_to` нет. `GET /quests/active` принимает **только одну дату** (`date=DD.MM.YYYY`), а внутри сервиса (`get_active_quests`) выбирает квесты, у которых `start_date <= end_of_day AND end_date >= start_of_day` — то есть пересечение с одним днём, а не интервал. Истории прошлых квестов через этот эндпоинт получить нельзя.

### 2. Tasks endpoints

Файл: `routers/tasks/tasks.py`. Префикс пустой, тег `tasks`. Защищены `get_current_user`.

| Метод | Путь                          | Описание                                          | Параметры                                                                                            |
|-------|-------------------------------|---------------------------------------------------|------------------------------------------------------------------------------------------------------|
| GET   | `/tasks`                      | Список задач                                      | query: `organization_id`, `employee_id`, `date` (DD.MM.YYYY — `due_date >= date`), `due_date` (точная дата) |
| POST  | `/tasks`                      | Создать задачу                                    | body: `CreateTaskRequest` — `title?`, `description`, `employee_id`, `organization_id?`, `due_date?` (DD.MM.YYYY) |
| POST  | `/tasks/{task_id}/complete`   | Переключить статус выполнения (toggle)            | path: `task_id`                                                                                       |

**Важное:** PUT/PATCH/DELETE для tasks отсутствуют. Параметра `date_to` нет, есть только нижняя граница `date` или точное `due_date`. Интервальный фильтр (`date_from/date_to`) не реализован.

### 3. Модели

**`models/rewards.py` (Reward — квест):**
- `id`, `iiko_id`
- `create_date` (TIMESTAMP, server default `now()`)
- `start_date` (TIMESTAMP, обяз.) — начало действия квеста
- `end_date` (TIMESTAMP, обяз.) — истечение квеста
- `item_id`, `end_goal`, `prize_sum`
- `created_at`, `updated_at` (есть оба набора timestamps)

Связь: `models/user_reward.py` (UserReward) — `reward_id`, `user_id`, `employee_id`, `current_progress`.

**`models/task.py` (Task):**
- `id`, `title?`, `description`
- `employee_id`, `organization_id?`
- `is_completed`
- `due_date` (DateTime, nullable) — дедлайн
- `created_at`, `updated_at` (UTC+5)

**Логика для фильтра по дате:**
- Для **квестов** — фильтровать пересечение интервала `[date_from, date_to]` с `[Reward.start_date, Reward.end_date]` (т.е. `start_date <= date_to AND end_date >= date_from`). Можно ещё по `create_date` если нужна «дата создания», но по смыслу мотивации логичнее «активность квеста в окне».
- Для **тасков** — `due_date` (дедлайн в окне) ИЛИ `created_at` (когда создана). По смыслу мотивации/раздела «посмотреть» лучше `due_date BETWEEN date_from AND date_to`, как уже частично сделано в `get_tasks` (но только нижняя граница).

### 4. Сервисы

**`services/quests/quests_service.py`:**
- `get_waiter_quests(db, waiter_id, date, organization_id)` — фильтр по `target_date` (одиночная дата).
- `get_active_quests(db, date, organization_id)` — фильтр по `target_date`, `func.date(Reward.end_date) >= today_date`. Дата на входе одна. Параметр `organization_id` фильтрует не сами `Reward`, а только список `user_rewards` для расчёта среднего прогресса.
- `get_quest_detail(db, quest_id, organization_id)` — без дат, по id.
- `create_quest`, `update_quest`, `delete_quest` — управление.
- `update_quest_progress_for_order(db, order)` — инкремент прогресса при оплате заказа.

Никакого фильтра по диапазону дат в сервисах квестов нет — есть только «одна дата». Чтобы получить список квестов за «последние 7 дней» нужно добавить аналог `resolve_date_range`.

**`services/tasks/tasks_service.py`:**
- `get_tasks(db, organization_id, employee_id, date, due_date)` — `date` фильтрует `Task.due_date >= date`, `due_date` фильтрует точное `due_date == that_day`. **Нет** верхней границы.
- `create_task`, `complete_task` (тоггл).

### 5. Паттерн фильтра в аналитике

Файл роутера: `routers/analytics/analytics.py`. Эндпоинт `GET /analytics` принимает (все Query, all optional):
- `date: str` — `DD.MM.YYYY`
- `period: str` — `"day" | "week" | "month"` (default `"day"`)
- `date_from: str` — `DD.MM.YYYY` (приоритет над `date+period`)
- `date_to: str` — `DD.MM.YYYY` (приоритет над `date+period`)
- `organization_id: int`

Резолвер диапазона — `resolve_date_range` в `services/transactions_and_statistics/statistics_service.py:100`. Сигнатура: `resolve_date_range(date_from, date_to, date, period) -> (start_date, end_date, previous_start, previous_end)`. Возвращает 4 datetime'а: основной интервал + предыдущий такой же длительности (для сравнения).

Логика:
- Если переданы оба `date_from`/`date_to` — используется явный интервал.
- Иначе — `get_period_dates(target_date, period)`:
  - `day`: один день (start = 00:00, end = 23:59:59);
  - `week`: 7 дней назад от target_date;
  - `month`: 30 дней назад от target_date.
- **Дефолта «последние 7 дней» сейчас нет**: дефолт у аналитики — `period="day"` для одной (сегодняшней) даты, если ничего не передано.

Дополнительный эндпоинт-референс — `POST /recalculate-employee-metrics` принимает `from_date`/`to_date` в двух форматах (`DD.MM.YYYY` или `YYYY-MM-DD`), с парсером `_parse_flex_date`. Это пример «гибкой» валидации, который можно скопировать, но в `/analytics` используется только `DD.MM.YYYY`.

### 6. Чего не хватает

**6.1. Эндпоинты, которые нужно добавить/допилить:**

1. **`GET /quests` (общий листинг с интервалом)** — сейчас нет. Нужен новый или расширить `/quests/active`:
   - query: `date_from`, `date_to` (DD.MM.YYYY), `organization_id`, опц. `status` (active/completed/expired);
   - возвращать все квесты, у которых `[start_date, end_date]` пересекается с `[date_from, date_to]`;
   - переиспользовать `resolve_date_range` из `statistics_service.py`.
2. **`GET /tasks` — добавить `date_from`/`date_to`** к существующим query-параметрам. Дёшево: дописать в `get_tasks` фильтр `Task.due_date BETWEEN date_from AND date_to` (или по `created_at`, если такое нужно — стоит уточнить с менеджером по какому полю фильтровать; рекомендую `due_date`, потому что задачи «к выполнению на 7 дней» именно по нему).
3. **(желательно) Унифицировать формат**: тот же `DD.MM.YYYY`, как в `/analytics`, чтобы фронт использовал один и тот же date-picker компонент.
4. **Дубль `/quests/{id}` и `/quests/{id}/progress`** — это технический долг, оба вызывают `get_quest_detail`. Не блокирует задачу, но можно почистить.

**6.2. Где выставлять дефолт «последние 7 дней»:**

Рекомендация — **на бэке**, причины:
- В аналитике дефолт уже на бэке (`period="day"`), консистентно расширить «если ничего не передано — берём `date_to = today, date_from = today - 6 days`».
- Единое место — меньше расхождений с разными фронтами (есть UI ваитера, менеджер-UI).
- Технически: если `date_from is None and date_to is None and date is None and period is None` → подставить семидневное окно. **Не ломать** при этом обратную совместимость с одиночной `date` (нужно для текущих фронтов, которые передают только `date`).

Альтернатива — на фронте. Если фронт уже дублирует логику аналитики, тоже допустимо, но тогда бэкенд должен корректно работать с явным `date_from/date_to` (это сейчас не реализовано для quests/tasks).

**6.3. Единый эндпоинт «таски + квесты» или два разных:**

Сейчас это два разных вызова (`GET /tasks`, `GET /quests/active`). Для UI с табами **два разных вызова достаточно и предпочтительнее**:
- разные структуры данных (Task vs Reward+UserReward+aggregates);
- разные query-параметры (квестам не нужен `employee_id`, таскам не нужен расчёт прогресса);
- независимая пагинация в будущем;
- ленивая загрузка по активному табу — экономия трафика.

Единый эндпоинт не нужен.

**6.4. Эндпоинты для бейджей-счётчиков:**

Сейчас нет ни `GET /quests/count`, ни `GET /tasks/count`. Если в UI на табах нужны бейджи с количеством — фронт может извлекать `len(items)` из основных листингов, что в большинстве случаев приемлемо. Отдельные `/count` эндпоинты стоит добавлять только если:
- листинги обрастут пагинацией (тогда `total` лучше отдать прямо в response — `{items, total}`);
- бейджи нужно показывать **до** перехода на таб (например, на главном экране мотивации).

Пока — не блокер, добавлять не обязательно.

**6.5. Прочие наблюдения:**
- В `get_active_quests` `organization_id` фильтрует не сами `Reward`, а только список юзеров для расчёта прогресса. Это значит, что квест из другой организации всё равно появится в списке (с прогрессом 0). Если фронту нужен честный фильтр по орг — нужно либо привязать `organization_id` к `Reward` (нет такого поля в модели), либо отфильтровывать квесты, у которых после фильтра `user_rewards` оказался пустым.
- В модели `Reward` нет `organization_id` — это потенциальная архитектурная проблема для мульти-организационного фильтра. Сейчас «организация квеста» определяется через сотрудников из `UserReward`. Стоит зафиксировать как риск.

## Реализовано (2026-05-21)

### 1. `GET /tasks` — добавлены `date_from`/`date_to` + дефолт «последние 7 дней»
`routers/tasks/tasks.py: get_tasks_endpoint` + `services/tasks/tasks_service.py: get_tasks`:
- Новые query-параметры `date_from`/`date_to` (DD.MM.YYYY) — фильтр по `Task.due_date`.
- Если фронт ничего не передал из дат (`date`, `due_date`, `date_from`, `date_to`) — на бэке выставляется дефолт `date_to=сегодня`, `date_from=сегодня − 7 дней`.
- Legacy-параметры `date` и `due_date` оставлены для обратной совместимости, при `date_from/date_to` игнорируются.

### 2. `GET /quests/active` — то же
`routers/quests/quests.py: get_active_quests_endpoint` + `services/quests/quests_service.py: get_active_quests`:
- Новые query-параметры `date_from`/`date_to` (DD.MM.YYYY) + `include_expired: bool`.
- Логика окна: квест возвращается, если `[start_date, end_date]` пересекает заданный интервал.
- Если фронт ничего не передал — дефолт «последние 7 дней» + `include_expired=true` (чтобы в «истории» были и истёкшие).
- При явной передаче `include_expired=true` — листинг работает как «история квестов» (нужно для формы «Посмотреть квесты»).

### Что не сделано (отложено)
- **Кнопки «Добавить» / «Посмотреть квесты»** и табы «Таски / Квесты» — это **frontend** в другом репозитории, бэкенд для них теперь готов.
- **Отдельный `GET /quests` без `/active`** — не делал, чтобы не плодить эндпоинты. Текущий `/quests/active` с `include_expired=true` решает кейс «вся история».
- **`organization_id` на сам `Reward`** — архитектурный риск, отложил (как в findings).
- **`/count` эндпоинты для бейджей** — не делал, фронт может брать `len(items)` из листинга.
- **Маппинг периода «activity quest vs created_at»** — сейчас фильтр идёт по `[start_date, end_date]` (период действия). Если бизнесу нужно «по дате создания» — добавим параметр `filter_field=period|created`.
