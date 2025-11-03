from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import Optional
from datetime import datetime
from models.employees import Employees
from models.user import User
from models.d_order import DOrder
from models.penalty import Penalty
from models.user_salary import UserSalary
from models.user_reward import UserReward
from models.rewards import Reward
from models.item import Item
from schemas.salary import (
    SalaryResponse,
    SalaryBreakdown,
    BonusItem,
    PenaltyItem,
    QuestRewardItem
)
from schemas.quests import QuestResponse
from services.quests.quests_service import get_waiter_quests


def calculate_waiter_salary(
    db: Session,
    waiter_id: int,
    date: str,
    organization_id: Optional[int] = None,
) -> Optional[SalaryResponse]:
    """
    Рассчитать зарплату официанта за день
    
    Args:
        db: сессия БД
        waiter_id: ID официанта (employee_id)
        date: дата в формате "DD.MM.YYYY"
        organization_id: ID организации (фильтр)
    
    Returns:
        Информация о зарплате официанта
    """
    # Парсим дату
    try:
        target_date = datetime.strptime(date, "%d.%m.%Y")
    except ValueError:
        return None
    
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Получаем сотрудника
    employee = db.query(Employees).filter(Employees.id == waiter_id).first()
    if not employee:
        return None
    
    # Получаем пользователя
    user = db.query(User).filter(User.iiko_id == employee.iiko_id).first()
    if not user:
        return None
    
    # Получаем заказы официанта за день
    query = db.query(DOrder).filter(
        and_(
            DOrder.user_id == user.id,
            DOrder.time_order >= start_of_day,
            DOrder.time_order <= end_of_day,
            DOrder.deleted == False
        )
    )
    
    if organization_id:
        query = query.filter(DOrder.organization_id == organization_id)
    
    orders = query.all()
    
    # Считаем количество завершенных столов (уникальных заказов)
    tables_completed = len(orders)
    
    # Считаем общую выручку
    total_revenue = sum(float(order.sum_order or 0) for order in orders)
    
    # Получаем процент зарплаты (из UserSalary или по умолчанию 5%)
    user_salary_record = db.query(UserSalary).filter(UserSalary.user_id == user.id).first()
    salary_percentage = 5.0  # По умолчанию 5%
    
    # Рассчитываем базовую зарплату (процент от выручки)
    base_salary = total_revenue * (salary_percentage / 100)
    
    # Получаем штрафы за день (по user_id или employee_id)
    penalties_query = db.query(Penalty).filter(
        or_(
            Penalty.user_id == user.id,
            Penalty.employee_id == waiter_id
        )
    )
    penalties = penalties_query.all()
    
    total_penalties = sum(float(penalty.penalty_sum or 0) for penalty in penalties)
    
    penalties_list = [
        PenaltyItem(
            reason=penalty.description or "Штраф",
            amount=float(penalty.penalty_sum or 0),
            date=date
        )
        for penalty in penalties
    ]
    
    # Получаем квесты и награды за день
    quests = get_waiter_quests(db=db, waiter_id=waiter_id, date=date, organization_id=organization_id)
    
    # Считаем бонусы за квесты
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
                    reward=quest.reward
                )
            )
            if not quest_description:
                quest_description = f"Бонус за выполнение квеста: {quest.description}"
    
    if not quest_description:
        quest_description = "Бонус определенный сумма"
    
    # Дополнительные бонусы (можно расширить логику)
    additional_bonuses = 0.0
    bonuses_list = []
    
    # Пример: бонус за отличную работу (если выручка больше определенной суммы)
    if total_revenue > 500000:
        performance_bonus = total_revenue * 0.01  # 1% от выручки
        additional_bonuses += performance_bonus
        bonuses_list.append(
            BonusItem(
                type="performance",
                amount=performance_bonus,
                description="Бонус за отличную работу"
            )
        )
    
    total_bonuses = additional_bonuses
    
    # Итоговая зарплата
    total_earnings = base_salary + total_bonuses + quest_bonus - total_penalties
    
    # Формируем детализацию
    breakdown = SalaryBreakdown(
        baseSalary=base_salary,
        percentage=salary_percentage,
        bonuses=bonuses_list,
        penalties=penalties_list,
        questRewards=quest_rewards_list
    )
    
    salary_response = SalaryResponse(
        date=date,
        tablesCompleted=tables_completed,
        totalRevenue=total_revenue,
        salary=base_salary,
        salaryPercentage=salary_percentage,
        bonuses=total_bonuses,
        questBonus=quest_bonus,
        questDescription=quest_description,
        penalties=total_penalties,
        totalEarnings=total_earnings,
        breakdown=breakdown,
        quests=quests
    )
    
    return salary_response

