# Waiter Comment + Percent-Based Salary — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Подставлять имя официанта в комментарий заказа iiko и переключить расчёт зарплаты на модель «3000 ₸ за смену + персональный % от продаж смены», атрибутируемую на дату открытия смены.

**Architecture:** Три независимых блока. (1) Чистый хелпер сборки комментария в `orders_services.py`. (2) Новая таблица `waiter_sales_percent` с периодами + сервис-хелперы (нормализация имён, активный %) + ручной скрипт-импортёр из xlsx. (3) Переписанный `calculate_waiter_salary`: смены матчатся по дате открытия, продажи берутся в окне смены, % из новой таблицы.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy (sync ORM), PostgreSQL (prod) / SQLite (тесты), pytest, psycopg2, openpyxl.

**Спека:** `docs/superpowers/specs/2026-06-07-waiter-comment-and-percent-salary-design.md`

**Тестовые заметки:**
- Запуск тестов: `source venv/bin/activate && pytest <path> -v`
- Фикстуры в `tests/conftest.py`: `test_db` (Session), `sample_employee`, `test_user`, `test_attendance_type`, `test_organization`. ARRAY-колонки патчатся на JSON для SQLite автоматически.
- `_resolve_employee_user` требует, чтобы у `User.iiko_id == Employees.iiko_id`. В юнит-тестах зарплаты создаём связанную пару руками.

---

## Task 1: Хелпер сборки комментария заказа

**Files:**
- Modify: `services/orders/orders_services.py` (добавить функцию + использовать в `create_order_in_iiko`, ~строки 603–621)
- Test: `tests/test_order_comment.py` (создать)

- [ ] **Step 1: Написать падающий тест**

Создать `tests/test_order_comment.py`:

```python
"""Тесты сборки комментария заказа для iiko (имя официанта)."""
from services.orders.orders_services import build_order_comment


def test_comment_with_name_and_user_comment():
    assert build_order_comment("Асылбек Мейрамов", "без лука") == \
        "Асылбек Мейрамов оформил с приложения. без лука"


def test_comment_with_name_only():
    assert build_order_comment("Асылбек Мейрамов", None) == \
        "Асылбек Мейрамов оформил с приложения"


def test_comment_with_name_and_empty_user_comment():
    assert build_order_comment("Асылбек Мейрамов", "   ") == \
        "Асылбек Мейрамов оформил с приложения"


def test_comment_without_name_falls_back_to_user_comment():
    assert build_order_comment(None, "без лука") == "без лука"
    assert build_order_comment("", "без лука") == "без лука"


def test_comment_without_name_and_without_user_comment():
    assert build_order_comment(None, None) == ""
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `source venv/bin/activate && pytest tests/test_order_comment.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_order_comment'`

- [ ] **Step 3: Реализовать хелпер**

В `services/orders/orders_services.py` после строки `logger = logging.getLogger(__name__)` (около строки 29) добавить:

```python
def build_order_comment(waiter_name: Optional[str], user_comment: Optional[str]) -> str:
    """
    Собирает comment для iiko-заказа.

    Официанта нельзя передать по Cloud API штатно, поэтому пишем его в комментарий:
      «{ФИО} оформил с приложения[. {пользовательский комментарий}]».
    Если имя официанта неизвестно — возвращаем пользовательский комментарий как есть.
    """
    name = (waiter_name or "").strip()
    user_part = (user_comment or "").strip()
    if not name:
        return user_part
    prefix = f"{name} оформил с приложения"
    if user_part:
        return f"{prefix}. {user_part}"
    return prefix
```

- [ ] **Step 4: Запустить тест — убедиться, что проходит**

Run: `source venv/bin/activate && pytest tests/test_order_comment.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Подключить хелпер в `create_order_in_iiko`**

В `services/orders/orders_services.py`, внутри `create_order_in_iiko`, найти блок (около строк 603–616):

```python
        ext = order.external_data or {}
        table_iiko_id = ext.get("tableIikoId")
        waiter_iiko_id = ext.get("waiterIikoId")

        order_body: Dict[str, Any] = {
            "externalNumber": str(order.id),
            "phone": None,
            "comment": comment or "",
```

Заменить на:

```python
        ext = order.external_data or {}
        table_iiko_id = ext.get("tableIikoId")
        waiter_iiko_id = ext.get("waiterIikoId")

        # Имя официанта для комментария: официанта нельзя передать штатно по API,
        # поэтому пишем «{ФИО} оформил с приложения» в comment.
        waiter_name = None
        if waiter_iiko_id:
            waiter_emp = (
                db.query(Employees)
                .filter(Employees.iiko_id == str(waiter_iiko_id))
                .first()
            )
            if waiter_emp:
                waiter_name = waiter_emp.name

        order_body: Dict[str, Any] = {
            "externalNumber": str(order.id),
            "phone": None,
            "comment": build_order_comment(waiter_name, comment),
```

(`Employees` уже импортирован в этом файле — строка 13.)

- [ ] **Step 6: Запустить тесты заказов целиком — нет регрессий**

Run: `source venv/bin/activate && pytest tests/test_orders.py tests/test_order_comment.py -v`
Expected: PASS (без новых падений)

- [ ] **Step 7: Commit**

```bash
git add services/orders/orders_services.py tests/test_order_comment.py
git commit -m "feat(orders): имя официанта в комментарии заказа iiko"
```

---

## Task 2: Модель `WaiterSalesPercent`

**Files:**
- Create: `models/waiter_sales_percent.py`
- Modify: `models/__init__.py`
- Test: `tests/test_waiter_percent.py` (создать)

- [ ] **Step 1: Написать падающий тест**

Создать `tests/test_waiter_percent.py`:

```python
"""Тесты модели и сервиса персональных процентов официантов."""
from datetime import date
from models.waiter_sales_percent import WaiterSalesPercent


def test_create_waiter_sales_percent(test_db, sample_employee):
    rec = WaiterSalesPercent(
        employee_id=sample_employee.id,
        percent=7.0,
        date_from=date(2026, 5, 1),
        date_to=None,
    )
    test_db.add(rec)
    test_db.commit()
    test_db.refresh(rec)
    assert rec.id is not None
    assert float(rec.percent) == 7.0
    assert rec.date_to is None
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `source venv/bin/activate && pytest tests/test_waiter_percent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.waiter_sales_percent'`

- [ ] **Step 3: Создать модель**

Создать `models/waiter_sales_percent.py`:

```python
from sqlalchemy import Column, Integer, ForeignKey, Numeric, Date, DateTime
from sqlalchemy.orm import relationship
from database.database import Base
from datetime import datetime


class WaiterSalesPercent(Base):
    """
    Персональный процент официанта с продаж, с периодом действия.
    Активная запись на дату X: date_from <= X AND (date_to IS NULL OR date_to >= X).
    """
    __tablename__ = "waiter_sales_percent"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    percent = Column(Numeric(5, 2), nullable=False)
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    employee = relationship("Employees", foreign_keys=[employee_id])
```

- [ ] **Step 4: Зарегистрировать модель в `models/__init__.py`**

В `models/__init__.py` добавить импорт рядом с остальными (после строки `from .payment_type import PaymentType`):

```python
from .waiter_sales_percent import WaiterSalesPercent
```

И добавить `"WaiterSalesPercent",` в список `__all__`.

- [ ] **Step 5: Зарегистрировать модель в тестовом conftest**

В `tests/conftest.py` в блоке `from models import (...)` (около строк 14–22) добавить `WaiterSalesPercent` в список импортируемых имён, чтобы таблица создавалась в тестовой БД через `Base.metadata.create_all`.

- [ ] **Step 6: Запустить тест — убедиться, что проходит**

Run: `source venv/bin/activate && pytest tests/test_waiter_percent.py -v`
Expected: PASS (1 passed)

- [ ] **Step 7: Commit**

```bash
git add models/waiter_sales_percent.py models/__init__.py tests/conftest.py tests/test_waiter_percent.py
git commit -m "feat(salary): модель waiter_sales_percent (процент официанта с периодами)"
```

---

## Task 3: Миграция таблицы `waiter_sales_percent`

**Files:**
- Create: `migrations/2026_06_07_add_waiter_sales_percent.sql`
- Create: `migrations/2026_06_07_add_waiter_sales_percent.py`

- [ ] **Step 1: Написать SQL миграции**

Создать `migrations/2026_06_07_add_waiter_sales_percent.sql`:

```sql
-- Миграция: таблица персональных процентов официантов с продаж
-- Дата: 2026-06-07

CREATE TABLE IF NOT EXISTS waiter_sales_percent (
    id          SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(id),
    percent     NUMERIC(5, 2) NOT NULL,
    date_from   DATE NOT NULL,
    date_to     DATE,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_waiter_sales_percent_employee_id
    ON waiter_sales_percent (employee_id);
```

- [ ] **Step 2: Написать Python-раннер миграции**

Создать `migrations/2026_06_07_add_waiter_sales_percent.py` (по образцу `migrations/2026_02_24_add_geo_to_organizations.py`):

```python
#!/usr/bin/env python3
"""
Миграция: таблица waiter_sales_percent (персональный % официанта с продаж)
Дата: 2026-06-07
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
import config


def run_migration():
    database_url = config.DATABASE_URL
    if not database_url.startswith("postgresql"):
        print("Поддерживается только PostgreSQL")
        return False

    raw_url = database_url.split("://", 1)[1]
    url_parts = raw_url.split("/")
    if len(url_parts) < 2:
        print("Неверный формат DATABASE_URL")
        return False

    auth_part = url_parts[0]
    database = url_parts[1]
    if "@" in auth_part:
        user_pass, host_port = auth_part.split("@")
        user, password = user_pass.split(":") if ":" in user_pass else (user_pass, None)
        host, port = host_port.split(":") if ":" in host_port else (host_port, "5432")
    else:
        user, password, host, port = auth_part, None, "localhost", "5432"

    conn = psycopg2.connect(host=host, port=port, database=database, user=user, password=password)
    conn.autocommit = True
    cursor = conn.cursor()
    print("Подключение к базе данных установлено")

    migration_file = os.path.join(
        os.path.dirname(__file__), "2026_06_07_add_waiter_sales_percent.sql"
    )
    with open(migration_file, "r", encoding="utf-8") as f:
        migration_sql = f.read()

    print("Выполнение миграции...")
    try:
        cursor.execute(migration_sql)
        print("Миграция успешно выполнена!")
        return True
    except Exception as e:
        print(f"Ошибка при выполнении миграции: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
```

- [ ] **Step 3: Проверить синтаксис раннера (без подключения к БД)**

Run: `source venv/bin/activate && python -c "import ast; ast.parse(open('migrations/2026_06_07_add_waiter_sales_percent.py').read()); print('OK')"`
Expected: `OK`

> Примечание: реальный запуск `python migrations/2026_06_07_add_waiter_sales_percent.py` выполняется вручную против БД при деплое — это не часть автотестов.

- [ ] **Step 4: Commit**

```bash
git add migrations/2026_06_07_add_waiter_sales_percent.sql migrations/2026_06_07_add_waiter_sales_percent.py
git commit -m "feat(salary): миграция таблицы waiter_sales_percent"
```

---

## Task 4: Сервис процентов — нормализация имени и активный %

**Files:**
- Create: `services/salary/waiter_percent_service.py`
- Test: `tests/test_waiter_percent.py` (дополнить)

- [ ] **Step 1: Написать падающие тесты**

Дополнить `tests/test_waiter_percent.py` (добавить в конец файла):

```python
from datetime import date
from services.salary.waiter_percent_service import (
    normalize_name_tokens,
    get_active_percent,
)


def test_normalize_tokens_order_independent():
    # Порядок слов не важен
    assert normalize_name_tokens("Азаткызы Бота") == normalize_name_tokens("Бота Азаткызы")


def test_normalize_tokens_kazakh_letters():
    # Каз. буквы сводятся к базовым: «Орак Акерке» == «Ақерке Орақ»
    assert normalize_name_tokens("Орак Акерке") == normalize_name_tokens("Ақерке Орақ")


def test_normalize_tokens_whitespace_and_case():
    assert normalize_name_tokens("  Асылбек   Мейрамов ") == normalize_name_tokens("асылбек мейрамов")


def test_get_active_percent_within_period(test_db, sample_employee):
    test_db.add(WaiterSalesPercent(
        employee_id=sample_employee.id, percent=7.0,
        date_from=date(2026, 5, 1), date_to=None,
    ))
    test_db.commit()
    assert get_active_percent(test_db, sample_employee.id, date(2026, 6, 7)) == 7.0


def test_get_active_percent_before_period_returns_zero(test_db, sample_employee):
    test_db.add(WaiterSalesPercent(
        employee_id=sample_employee.id, percent=7.0,
        date_from=date(2026, 5, 1), date_to=None,
    ))
    test_db.commit()
    assert get_active_percent(test_db, sample_employee.id, date(2026, 4, 1)) == 0.0


def test_get_active_percent_no_record_returns_zero(test_db, sample_employee):
    assert get_active_percent(test_db, sample_employee.id, date(2026, 6, 7)) == 0.0


def test_get_active_percent_picks_latest_period(test_db, sample_employee):
    test_db.add(WaiterSalesPercent(
        employee_id=sample_employee.id, percent=5.0,
        date_from=date(2026, 5, 1), date_to=date(2026, 5, 31),
    ))
    test_db.add(WaiterSalesPercent(
        employee_id=sample_employee.id, percent=8.0,
        date_from=date(2026, 6, 1), date_to=None,
    ))
    test_db.commit()
    assert get_active_percent(test_db, sample_employee.id, date(2026, 6, 7)) == 8.0
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `source venv/bin/activate && pytest tests/test_waiter_percent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.salary.waiter_percent_service'`

- [ ] **Step 3: Реализовать сервис**

Создать `services/salary/waiter_percent_service.py`:

```python
"""Хелперы для персональных процентов официантов с продаж."""
from datetime import date as date_cls
from typing import FrozenSet
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models.waiter_sales_percent import WaiterSalesPercent

# Свод казахских букв к базовым кириллическим — имена в xlsx и в БД
# различаются написанием (қ/к, ә/а и т.д.).
_KAZAKH_FOLD = str.maketrans({
    "қ": "к", "Қ": "к",
    "ә": "а", "Ә": "а",
    "ө": "о", "Ө": "о",
    "ұ": "у", "Ұ": "у",
    "ү": "у", "Ү": "у",
    "і": "и", "І": "и",
    "ң": "н", "Ң": "н",
    "ғ": "г", "Ғ": "г",
    "һ": "х", "Һ": "х",
})


def normalize_name_tokens(name: str) -> FrozenSet[str]:
    """
    Нормализует имя в множество токенов, не зависящее от порядка слов,
    регистра, лишних пробелов и казахских букв.
    «Азаткызы Бота» и «Бота Азаткызы» → одинаковое множество.
    """
    if not name:
        return frozenset()
    folded = name.translate(_KAZAKH_FOLD).lower()
    tokens = [t for t in folded.split() if t]
    return frozenset(tokens)


def get_active_percent(db: Session, employee_id: int, target_date: date_cls) -> float:
    """
    Возвращает активный процент официанта на дату target_date.
    Активная запись: date_from <= target_date AND (date_to IS NULL OR date_to >= target_date).
    При нескольких — берём свежайшую по date_from. Нет записи → 0.0.
    """
    record = (
        db.query(WaiterSalesPercent)
        .filter(
            WaiterSalesPercent.employee_id == employee_id,
            WaiterSalesPercent.date_from <= target_date,
            or_(
                WaiterSalesPercent.date_to.is_(None),
                WaiterSalesPercent.date_to >= target_date,
            ),
        )
        .order_by(WaiterSalesPercent.date_from.desc())
        .first()
    )
    if record is None:
        return 0.0
    return float(record.percent)
```

(`and_` импортирован для единообразия; если линтер ругается на неиспользуемый импорт — убрать его из строки `from sqlalchemy import and_, or_`, оставив `or_`.)

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `source venv/bin/activate && pytest tests/test_waiter_percent.py -v`
Expected: PASS (все тесты файла)

- [ ] **Step 5: Commit**

```bash
git add services/salary/waiter_percent_service.py tests/test_waiter_percent.py
git commit -m "feat(salary): сервис нормализации имён и активного процента официанта"
```

---

## Task 5: Скрипт-импортёр процентов из xlsx

**Files:**
- Create: `migrations/import_waiter_percents.py`

- [ ] **Step 1: Реализовать скрипт-импортёр**

Создать `migrations/import_waiter_percents.py`:

```python
#!/usr/bin/env python3
"""
Ручной импорт персональных процентов официантов из ofik_percent_salary.xlsx
в таблицу waiter_sales_percent.

Запуск: source venv/bin/activate && python migrations/import_waiter_percents.py

Матчинг имени xlsx → employees.name токен-множеством (порядок слов и
казахские буквы расходятся). Несопоставленные/неоднозначные строки печатаются
для ручного занесения. Идемпотентно по (employee_id, date_from).
"""
import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl
from database.database import SessionLocal
from models.employees import Employees
from models.waiter_sales_percent import WaiterSalesPercent
from services.salary.waiter_percent_service import normalize_name_tokens

XLSX_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ofik_percent_salary.xlsx",
)
DATE_FROM = date(2026, 5, 1)


def _parse_rows(path):
    """Возвращает список (name, percent) из листа, пропуская заголовки/пустые."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Лист1"]
    rows = []
    for row in ws.iter_rows(values_only=True):
        # Колонки: A=№, B=Имя в системе, C=%, D=группа
        if len(row) < 3:
            continue
        name, percent_raw = row[1], row[2]
        if not name or percent_raw is None:
            continue
        name = str(name).strip()
        if not name or name == "Имя в системе":
            continue
        try:
            percent = float(percent_raw)
        except (TypeError, ValueError):
            print(f"  ! Не распознан процент для «{name}»: {percent_raw!r}")
            continue
        rows.append((name, percent))
    return rows


def run_import():
    db = SessionLocal()
    try:
        rows = _parse_rows(XLSX_PATH)
        print(f"Строк с именем и процентом в xlsx: {len(rows)}")

        # Индекс сотрудников по токен-множеству имени.
        employees = db.query(Employees).filter(Employees.deleted == False).all()  # noqa: E712
        by_tokens = {}
        for emp in employees:
            key = normalize_name_tokens(emp.name or "")
            if not key:
                continue
            by_tokens.setdefault(key, []).append(emp)

        matched, ambiguous, unmatched = 0, [], []
        for name, percent in rows:
            key = normalize_name_tokens(name)
            candidates = by_tokens.get(key, [])
            if len(candidates) == 1:
                emp = candidates[0]
                exists = (
                    db.query(WaiterSalesPercent)
                    .filter(
                        WaiterSalesPercent.employee_id == emp.id,
                        WaiterSalesPercent.date_from == DATE_FROM,
                    )
                    .first()
                )
                if exists:
                    print(f"  = уже есть: {name} → {emp.name} ({emp.id})")
                else:
                    db.add(WaiterSalesPercent(
                        employee_id=emp.id, percent=percent,
                        date_from=DATE_FROM, date_to=None,
                    ))
                    matched += 1
            elif len(candidates) > 1:
                ambiguous.append((name, percent, [e.name for e in candidates]))
            else:
                unmatched.append((name, percent))

        db.commit()

        print(f"\nСопоставлено и вставлено: {matched}")
        print(f"Неоднозначных (>1 кандидата): {len(ambiguous)}")
        for name, percent, cands in ambiguous:
            print(f"  ? «{name}» ({percent}%) → кандидаты: {cands}")
        print(f"Не сопоставлено: {len(unmatched)}")
        for name, percent in unmatched:
            print(f"  - «{name}» ({percent}%)")
        return True
    except Exception as e:
        db.rollback()
        print(f"Ошибка импорта: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    ok = run_import()
    sys.exit(0 if ok else 1)
```

- [ ] **Step 2: Проверить, что скрипт парсит xlsx (без записи в БД)**

Проверяем только парсер строк — он не трогает БД:

Run:
```bash
source venv/bin/activate && python -c "
from migrations.import_waiter_percents import _parse_rows, XLSX_PATH
rows = _parse_rows(XLSX_PATH)
print('rows:', len(rows))
print('sample:', rows[:3])
assert len(rows) > 30
assert all(isinstance(p, float) for _, p in rows)
print('OK')
"
```
Expected: `rows:` ~46, `sample:` список кортежей `(имя, процент)`, затем `OK`

> Примечание: реальный импорт (`python migrations/import_waiter_percents.py`) запускается вручную против прод-БД после Task 3. Отчёт по несопоставленным именам заносится вручную отдельными INSERT'ами.

- [ ] **Step 3: Commit**

```bash
git add migrations/import_waiter_percents.py
git commit -m "feat(salary): скрипт импорта процентов официантов из xlsx"
```

---

## Task 6: Поле `percentAmount` в схеме `SalaryBreakdown`

**Files:**
- Modify: `schemas/salary.py`
- Test: `tests/test_salary_schema.py` (создать)

- [ ] **Step 1: Написать падающий тест**

Создать `tests/test_salary_schema.py`:

```python
"""Тест схемы зарплаты — новое поле percentAmount."""
from schemas.salary import SalaryBreakdown


def test_breakdown_has_percent_amount():
    b = SalaryBreakdown(
        baseSalary=6000.0,
        percentage=7.0,
        percentAmount=1400.0,
        bonuses=[],
        penalties=[],
        questRewards=[],
    )
    assert b.percentAmount == 1400.0
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `source venv/bin/activate && pytest tests/test_salary_schema.py -v`
Expected: FAIL — `ValidationError` (unexpected keyword `percentAmount`) или `TypeError`

- [ ] **Step 3: Добавить поле в схему**

В `schemas/salary.py`, в классе `SalaryBreakdown`, добавить поле `percentAmount` после `percentage`:

```python
class SalaryBreakdown(BaseModel):
    """Детализация зарплаты"""
    baseSalary: float
    percentage: float
    percentAmount: float = 0.0  # сумма, начисленная с процента от продаж
    bonuses: List[BonusItem]
    penalties: List[PenaltyItem]
    questRewards: List[QuestRewardItem]
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `source venv/bin/activate && pytest tests/test_salary_schema.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add schemas/salary.py tests/test_salary_schema.py
git commit -m "feat(salary): поле percentAmount в SalaryBreakdown"
```

---

## Task 7: Переписать `calculate_waiter_salary` (3000/смена + % по дате открытия)

**Files:**
- Modify: `services/salary/salary_service.py` (функция `calculate_waiter_salary`, строки 35–178)
- Test: `tests/test_salary_calc.py` (создать)

- [ ] **Step 1: Написать падающие тесты**

Создать `tests/test_salary_calc.py`:

```python
"""Юнит-тесты нового расчёта зарплаты официанта."""
from datetime import datetime, date, timedelta
import pytest

from models.user import User
from models.employees import Employees
from models.shifts import Shift
from models.d_order import DOrder
from models.waiter_sales_percent import WaiterSalesPercent
from utils.security import hash_password
from services.salary.salary_service import calculate_waiter_salary


@pytest.fixture
def linked(test_db, test_organization, test_role):
    """Связанная пара employee+user (через общий iiko_id)."""
    iiko_id = "calc_iiko_1"
    emp = Employees(
        iiko_id=iiko_id, name="Тест Официант", login="calc_emp",
        main_role_id=test_role.id, main_role_code="WR1",
        preferred_organization_id=test_organization.id,
    )
    test_db.add(emp)
    test_db.commit()
    test_db.refresh(emp)
    user = User(login="calc_user", password=hash_password("x"),
                name="Тест Официант", iiko_id=iiko_id)
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return emp, user


def _add_shift(db, emp, start, end):
    s = Shift(start_time=start, end_time=end, employee_id=emp.id)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _add_order(db, user, org, when, total):
    o = DOrder(
        organization_id=org.id, user_id=user.id, sum_order=total,
        time_order=when, state_order="PAID", deleted=False,
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


def test_base_3000_per_shift(test_db, linked, test_organization):
    emp, user = linked
    # Одна закрытая смена 03.06 09:00–17:00, без процента.
    _add_shift(test_db, emp, datetime(2026, 6, 3, 9), datetime(2026, 6, 3, 17))
    res = calculate_waiter_salary(test_db, emp.id, "03.06.2026")
    assert res is not None
    assert res.breakdown.baseSalary == 3000.0
    assert res.salary == 3000.0  # нет продаж, нет процента


def test_two_shifts_same_day_double_base(test_db, linked, test_organization):
    emp, user = linked
    _add_shift(test_db, emp, datetime(2026, 6, 3, 8), datetime(2026, 6, 3, 12))
    _add_shift(test_db, emp, datetime(2026, 6, 3, 14), datetime(2026, 6, 3, 18))
    res = calculate_waiter_salary(test_db, emp.id, "03.06.2026")
    assert res.breakdown.baseSalary == 6000.0


def test_percent_of_sales_within_shift(test_db, linked, test_organization):
    emp, user = linked
    _add_shift(test_db, emp, datetime(2026, 6, 3, 9), datetime(2026, 6, 3, 17))
    _add_order(test_db, user, test_organization, datetime(2026, 6, 3, 12), 10000.0)
    test_db.add(WaiterSalesPercent(
        employee_id=emp.id, percent=7.0, date_from=date(2026, 5, 1), date_to=None,
    ))
    test_db.commit()
    res = calculate_waiter_salary(test_db, emp.id, "03.06.2026")
    assert res.totalRevenue == 10000.0
    assert res.breakdown.percentage == 7.0
    assert res.breakdown.percentAmount == 700.0
    assert res.salary == 3700.0  # 3000 + 700


def test_overnight_shift_attributed_to_open_date(test_db, linked, test_organization):
    emp, user = linked
    # Смена открыта 04.06 20:00, закрыта 05.06 02:00.
    _add_shift(test_db, emp, datetime(2026, 6, 4, 20), datetime(2026, 6, 5, 2))
    # Заказ в 23:00 04.06 и заказ в 01:00 05.06 — оба внутри окна смены.
    _add_order(test_db, user, test_organization, datetime(2026, 6, 4, 23), 5000.0)
    _add_order(test_db, user, test_organization, datetime(2026, 6, 5, 1), 3000.0)
    test_db.add(WaiterSalesPercent(
        employee_id=emp.id, percent=10.0, date_from=date(2026, 5, 1), date_to=None,
    ))
    test_db.commit()

    # На дату открытия (04.06) смена видна со всем итогом.
    res4 = calculate_waiter_salary(test_db, emp.id, "04.06.2026")
    assert res4.breakdown.baseSalary == 3000.0
    assert res4.totalRevenue == 8000.0
    assert res4.breakdown.percentAmount == 800.0
    assert res4.salary == 3800.0

    # На дату закрытия (05.06) этой смены нет.
    res5 = calculate_waiter_salary(test_db, emp.id, "05.06.2026")
    assert res5.breakdown.baseSalary == 0.0
    assert res5.salary == 0.0


def test_no_shift_returns_zero_salary(test_db, linked, test_organization):
    emp, user = linked
    res = calculate_waiter_salary(test_db, emp.id, "03.06.2026")
    assert res is not None
    assert res.breakdown.baseSalary == 0.0
    assert res.salary == 0.0
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `source venv/bin/activate && pytest tests/test_salary_calc.py -v`
Expected: FAIL — текущая реализация считает почасовую ставку, ассерты на `baseSalary == 3000` не проходят.

- [ ] **Step 3: Переписать `calculate_waiter_salary`**

В `services/salary/salary_service.py`:

(a) В шапке заменить импорт `UserSalary` на новый сервис. Удалить строку `from models.user_salary import UserSalary` и добавить:

```python
from services.salary.waiter_percent_service import get_active_percent
```

(b) Добавить модульную константу после импортов:

```python
SHIFT_FLAT_RATE = 3000.0  # фикс за смену
```

(c) Заменить тело функции `calculate_waiter_salary` (строки ~35–178) на:

```python
def calculate_waiter_salary(
    db: Session,
    waiter_id: int,
    date: str,
    organization_id: Optional[int] = None,
) -> Optional[SalaryResponse]:
    try:
        target_date = datetime.strptime(date, "%d.%m.%Y")
    except ValueError:
        return None

    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    employee, user = _resolve_employee_user(db, waiter_id)
    if not employee or not user:
        return None

    now = datetime.now()

    # --- Смены, ОТКРЫТЫЕ в target_date (атрибуция по дате открытия) ---
    # Закрытая смена засчитывается, если открыта в этот день.
    # Открытая (end_time IS NULL) — только если открыта не в будущем и не
    # старше 48ч (защита от забытых смен), см. salary_open_shift_window.
    candidate_shifts = (
        db.query(Shift)
        .filter(
            Shift.employee_id == employee.id,
            Shift.start_time >= start_of_day,
            Shift.start_time <= end_of_day,
        )
        .all()
    )
    shifts_today = []
    for s in candidate_shifts:
        if s.end_time is None:
            if s.start_time > now:
                continue
            if (now - s.start_time) > timedelta(hours=48):
                continue
        shifts_today.append(s)

    base_salary = round(SHIFT_FLAT_RATE * len(shifts_today), 2)
    worked = len(shifts_today) > 0

    # --- Продажи внутри окна каждой смены ---
    total_revenue = 0.0
    tables_completed = 0
    for s in shifts_today:
        seg_start = s.start_time
        seg_end = s.end_time if s.end_time is not None else now
        if seg_end <= seg_start:
            continue
        orders_query = db.query(DOrder).filter(
            and_(
                DOrder.user_id == user.id,
                DOrder.time_order >= seg_start,
                DOrder.time_order <= seg_end,
                DOrder.deleted == False,  # noqa: E712
            )
        )
        if organization_id:
            orders_query = orders_query.filter(DOrder.organization_id == organization_id)
        shift_orders = orders_query.all()
        tables_completed += len(shift_orders)
        total_revenue += sum(float(o.sum_order or 0) for o in shift_orders)

    # --- Персональный процент с продаж ---
    salary_percentage = 0.0
    percent_amount = 0.0
    if worked:
        salary_percentage = get_active_percent(db, employee.id, target_date.date())
        percent_amount = round(total_revenue * salary_percentage / 100.0, 2)

    salary = round(base_salary + percent_amount, 2)

    # --- Квесты (без изменений) ---
    quests = get_waiter_quests(
        db=db, waiter_id=waiter_id, date=date, organization_id=organization_id
    )
    quest_bonus = 0.0
    quest_rewards_list = []
    quest_description = ""
    for quest in quests:
        if quest.completed:
            quest_bonus += quest.reward
            quest_rewards_list.append(
                QuestRewardItem(
                    questId=quest.id,
                    questName=quest.description,
                    reward=quest.reward,
                )
            )
            if not quest_description:
                quest_description = f"Бонус за выполнение квеста: {quest.description}"

    total_earnings = round(salary + quest_bonus, 2)

    breakdown = SalaryBreakdown(
        baseSalary=base_salary,
        percentage=salary_percentage,
        percentAmount=percent_amount,
        bonuses=[],
        penalties=[],
        questRewards=quest_rewards_list,
    )

    return SalaryResponse(
        date=date,
        tablesCompleted=tables_completed,
        totalRevenue=total_revenue,
        salary=salary,
        salaryPercentage=salary_percentage,
        bonuses=0.0,
        questBonus=quest_bonus,
        questDescription=quest_description,
        penalties=0.0,
        totalEarnings=total_earnings,
        breakdown=breakdown,
        quests=quests,
    )
```

- [ ] **Step 4: Запустить новые тесты — убедиться, что проходят**

Run: `source venv/bin/activate && pytest tests/test_salary_calc.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Запустить существующие тесты зарплаты — нет регрессий**

Run: `source venv/bin/activate && pytest tests/test_salary.py -v`
Expected: PASS (эндпоинт-тесты допускают 200/404/500, контракт ответа не сломан)

- [ ] **Step 6: Commit**

```bash
git add services/salary/salary_service.py tests/test_salary_calc.py
git commit -m "feat(salary): расчёт 3000/смена + % от продаж по дате открытия смены"
```

---

## Task 8: Финальная проверка всего набора

**Files:** (нет правок — только прогон)

- [ ] **Step 1: Прогнать все затронутые тесты**

Run:
```bash
source venv/bin/activate && pytest tests/test_order_comment.py tests/test_waiter_percent.py \
    tests/test_salary_schema.py tests/test_salary_calc.py tests/test_salary.py tests/test_orders.py -v
```
Expected: всё PASS.

- [ ] **Step 2: Прогнать полный набор на регрессии**

Run: `source venv/bin/activate && pytest -q`
Expected: нет НОВЫХ падений по сравнению с baseline до начала работ (если в репозитории были заранее красные тесты — зафиксировать, что они не связаны с этими изменениями).

- [ ] **Step 3: (вручную, на деплое) применить миграцию и импорт**

```bash
source venv/bin/activate && python migrations/2026_06_07_add_waiter_sales_percent.py
source venv/bin/activate && python migrations/import_waiter_percents.py
```
Разобрать отчёт импортёра: несопоставленные/неоднозначные имена занести вручную.

---

## Self-Review (выполнено автором плана)

**Покрытие спеки:**
- Фича 1 (комментарий) → Task 1. ✓
- Фича 2 (таблица + сервис + импорт) → Tasks 2, 3, 4, 5. ✓
- Фича 3 (расчёт зарплаты) → Tasks 6, 7. ✓
- Матчинг имён (порядок слов + каз. буквы) → Task 4 (`normalize_name_tokens`) + Task 5. ✓
- `date_from=2026-05-01`, нет % → 0 → Task 4/5. ✓
- Удаление `UserSalary`/почасовой логики → Task 7. ✓
- `percentAmount` в breakdown → Task 6 + Task 7. ✓

**Согласованность типов:** `normalize_name_tokens`, `get_active_percent`, `build_order_comment`, `WaiterSalesPercent`, `SHIFT_FLAT_RATE`, `percentAmount` используются согласованно между задачами.

**Плейсхолдеров нет:** весь код приведён целиком.
