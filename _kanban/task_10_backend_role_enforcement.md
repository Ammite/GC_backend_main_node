# Task 10 — Role enforcement на бэке (на всех endpoints)

**Статус:** todo
**Заведено:** 2026-05-24

## От @baa21v
> Надо бы сделать чтобы были проверки ролей везде. Фронт итак фильтрует, но беку надо тоже.

## Контекст
- После [[made_task_1_users_access_audit]] и миграции 2026-05-24 у юзеров есть `app_role`:
  - «Владелец» (3) — Акжан, Амир, legacy admin
  - «Менеджер» (32) — управление, бухгалтерия, шефы
  - «Официант» (221) — все остальные (включая поваров, барменов, тех.персонал)
- Сейчас **бэк НЕ проверяет роль** на endpoints — единственное исключение `PUT /auth/change-password` (после фикса 2026-05-21).
- Фронт фильтрует UI по `app_role`, но защита **только клиентская** — официант с curl/postman может вызвать менеджерские endpoints без блокировки.

## Цель
Каждый endpoint должен сам решать, кто к нему может ходить. Минимум — три «полки»:
- **public** (логин, регистрация — но `/register` под вопросом, см. S1)
- **waiter+** (Официант / Менеджер / Владелец) — экраны официанта, свои заказы, своя зарплата
- **manager+** (Менеджер / Владелец) — управление, отчёты, чужие данные, расходы, накладные
- **owner-only** (Владелец) — критическое: смена паролей, удаление, доступы

## Подход
Создать FastAPI-зависимости в `utils/security.py`:

```python
ROLE_ORDER = {"Официант": 1, "Менеджер": 2, "Владелец": 3}

def require_role(min_role: str):
    """Dependency factory: возвращает зависимость, которая 403-ит
    если у юзера роль ниже min_role."""
    def _check(user=Depends(get_current_user)):
        if ROLE_ORDER.get(user.app_role or "", 0) < ROLE_ORDER[min_role]:
            raise HTTPException(403, "Недостаточно прав")
        return user
    return _check

require_waiter = require_role("Официант")
require_manager = require_role("Менеджер")
require_owner = require_role("Владелец")
```

Использование:
```python
@router.get("/expenses")
def list_expenses(user=Depends(require_manager), db=Depends(get_db)):
    ...
```

## Что нужно сделать
1. Добавить `require_role` / `require_waiter` / `require_manager` / `require_owner` в `utils/security.py`.
2. Пройти по всем routers/ и проставить нужный уровень. Это **~50 endpoints**.
3. **Owner-only:** все эндпоинты, которые меняют пароли, создают/удаляют юзеров, дёргают синки.
4. **Manager+:** управление меню, организациями, расходы, накладные, отчёты по другим сотрудникам, payment_types modify (если есть), employees CRUD.
5. **Waiter+:** свои заказы, своё расписание, своя зарплата, своя профиль, GET /menu / /tables / /payment-types (только посмотреть).
6. **Объектный уровень:** официант может смотреть СВОЁ — нужна проверка `order.user_id == current_user.id` и т.п. где relevant. Это поверх role-check.

## Риски
- Без актуального контракта с фронтом легко закрыть endpoint, который реально нужен фронту (тогда у юзера будет 403). Перед каждым endpoint смотреть `frontend_api_audit.md` — какие роли его дёргают.
- Объектный уровень (waiter видит только свои заказы) — отдельная задача после ролей.

## Связи
- [[made_task_1_users_access_audit]] — миграция ролей
- [[questions_for_client_call]] — S1 (публичный /register), #9 (расширение app_role)
- [[frontend_api_audit]] — какие endpoints дёргает фронт под какой ролью
