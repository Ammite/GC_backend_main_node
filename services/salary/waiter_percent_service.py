"""Хелперы для персональных процентов официантов с продаж."""
from datetime import date as date_cls
from typing import FrozenSet
from sqlalchemy.orm import Session
from sqlalchemy import or_

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
