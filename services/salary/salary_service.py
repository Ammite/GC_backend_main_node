from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from models.employees import Employees
from models.user import User
from models.d_order import DOrder
from models.shifts import Shift
from services.salary.waiter_percent_service import get_active_percent
from schemas.salary import (
    SalaryResponse,
    SalaryBreakdown,
    BonusItem,
    PenaltyItem,
    QuestRewardItem,
)
from schemas.quests import QuestResponse
from services.quests.quests_service import get_waiter_quests
from services.employees.employees_service import get_employee_summary

SHIFT_FLAT_RATE = 3000.0  # фикс за смену


def _resolve_employee_user(db: Session, waiter_id: int):
    """waiter_id может быть Employee.id или User.id (фронт шлёт User.id)."""
    employee = db.query(Employees).filter(Employees.id == waiter_id).first()
    if employee:
        user = db.query(User).filter(User.iiko_id == employee.iiko_id).first()
        return employee, user
    user = db.query(User).filter(User.id == waiter_id).first()
    if not user or not user.iiko_id:
        return None, None
    employee = db.query(Employees).filter(Employees.iiko_id == user.iiko_id).first()
    return employee, user


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


def get_waiter_daily_sales(
    db: Session,
    waiter_id: int,
    date: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Получить сумму продаж официанта за день и количество чеков.

    Переиспользует логику get_employee_summary, чтобы данные совпадали
    с остальными отчетами по сотрудникам.
    """
    try:
        summary = get_employee_summary(
            db=db,
            employee_id=waiter_id,
            date=date,
            organization_id=organization_id,
        )
    except ValueError:
        return None

    return {
        "date": date or datetime.now().strftime("%d.%m.%Y"),
        "totalAmount": summary.get("totalAmount", 0.0),
        "ordersCount": summary.get("ordersCount", 0),
    }

