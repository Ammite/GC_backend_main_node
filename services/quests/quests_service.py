from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional
from datetime import datetime, timedelta
from models.rewards import Reward
from models.user_reward import UserReward
from models.item import Item
from models.employees import Employees
from models.user import User
import logging
from schemas.quests import (
    QuestResponse, 
    QuestDetailResponse, 
    EmployeeQuestProgress,
    CreateQuestRequest
)

logger = logging.getLogger(__name__)
def get_waiter_quests(
    db: Session,
    waiter_id: int,
    date: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> List[QuestResponse]:
    """
    Получить квесты официанта на определенную дату
    
    Args:
        db: сессия БД
        waiter_id: ID официанта
        date: дата в формате "DD.MM.YYYY"
        organization_id: ID организации (фильтр)
    
    Returns:
        Список квестов официанта
    """
    # Парсим дату
    logger.info(f"Getting quests for waiter {waiter_id} on date {date}")
    if date:
        try:
            target_date = datetime.strptime(date, "%d.%m.%Y")
        except ValueError:
            target_date = datetime.now()
    else:
        target_date = datetime.now()
    
    # Получаем пользователя по ID сотрудника
    # employee = db.query(Employees).filter(Employees.id == waiter_id).first()
    # if not employee:
    #     return []
    
    # Находим связанного пользователя
    user = db.query(User).filter(User.id == waiter_id).first()
    if not user:
        return []
    
    # Получаем награды (квесты) в диапазоне дат
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    query = db.query(Reward).filter(
        and_(
            Reward.start_date <= end_of_day,
            Reward.end_date >= start_of_day
        )
    )
    
    rewards = query.all()
    
    quests = []
    for reward in rewards:
        # Получаем прогресс пользователя по этому квесту
        user_reward = db.query(UserReward).filter(
            and_(
                UserReward.reward_id == reward.id,
                UserReward.user_id == user.id
            )
        ).first()
        
        current_progress = user_reward.current_progress if user_reward else 0
        progress_percent = (current_progress / reward.end_goal * 100) if reward.end_goal > 0 else 0
        completed = current_progress >= reward.end_goal
        
        # Получаем информацию о блюде
        item = db.query(Item).filter(Item.id == reward.item_id).first()
        unit = item.name if item else "единиц"
        
        quest = QuestResponse(
            id=str(reward.id),
            title="Квест на сегодня",
            description=f"Продай {reward.end_goal} {unit}",
            reward=float(reward.prize_sum),
            current=current_progress,
            target=reward.end_goal,
            unit=unit,
            completed=completed,
            progress=round(progress_percent, 2),
            expiresAt=reward.end_date.isoformat() if reward.end_date else None
        )
        quests.append(quest)
    
    return quests


def get_quest_detail(
    db: Session,
    quest_id: int,
    organization_id: Optional[int] = None,
) -> Optional[QuestDetailResponse]:
    """
    Получить детальную информацию о квесте (для CEO)
    
    Args:
        db: сессия БД
        quest_id: ID квеста
        organization_id: ID организации (фильтр)
    
    Returns:
        Детальная информация о квесте
    """
    reward = db.query(Reward).filter(Reward.id == quest_id).first()
    if not reward:
        return None
    
    # Получаем всех пользователей с прогрессом по этому квесту
    user_rewards = db.query(UserReward).filter(UserReward.reward_id == quest_id).all()
    
    # Получаем информацию о блюде
    item = db.query(Item).filter(Item.id == reward.item_id).first()
    unit = item.name if item else "единиц"
    
    # Считаем общую статистику
    total_employees = len(user_rewards)
    completed_employees = sum(1 for ur in user_rewards if ur.current_progress >= reward.end_goal)
    
    # Формируем список прогресса сотрудников
    employee_progress_list = []
    employee_names = []
    
    for idx, user_reward in enumerate(user_rewards, start=1):
        user = db.query(User).filter(User.id == user_reward.user_id).first()
        if not user:
            continue
        
        employee = db.query(Employees).filter(Employees.iiko_id == user.iiko_id).first()
        if not employee:
            continue
        
        # Фильтр по организации
        if organization_id and employee.preferred_organization_id != organization_id:
            continue
        
        progress_percent = (user_reward.current_progress / reward.end_goal * 100) if reward.end_goal > 0 else 0
        completed = user_reward.current_progress >= reward.end_goal
        
        employee_progress = EmployeeQuestProgress(
            employeeId=str(employee.id),
            employeeName=employee.name or "Неизвестно",
            progress=round(progress_percent, 2),
            completed=completed,
            points=user_reward.current_progress,
            rank=idx
        )
        employee_progress_list.append(employee_progress)
        employee_names.append(employee.name or "Неизвестно")
    
    # Сортируем по прогрессу (по убыванию)
    employee_progress_list.sort(key=lambda x: x.points, reverse=True)
    
    # Обновляем ранги после сортировки
    for idx, ep in enumerate(employee_progress_list, start=1):
        ep.rank = idx
    
    # Средний прогресс всех сотрудников
    avg_progress = sum(ep.progress for ep in employee_progress_list) / len(employee_progress_list) if employee_progress_list else 0
    
    quest_detail = QuestDetailResponse(
        id=str(reward.id),
        title="Квест на сегодня",
        description=f"Продай {reward.end_goal} {unit}",
        reward=float(reward.prize_sum),
        current=int(avg_progress * reward.end_goal / 100),
        target=reward.end_goal,
        unit=unit,
        completed=completed_employees == total_employees,
        progress=round(avg_progress, 2),
        expiresAt=reward.end_date.isoformat() if reward.end_date else None,
        totalEmployees=total_employees,
        completedEmployees=completed_employees,
        employeeNames=employee_names,
        date=reward.start_date.strftime("%d.%m.%Y") if reward.start_date else "",
        employeeProgress=employee_progress_list
    )
    
    return quest_detail


def create_quest(
    db: Session,
    quest_data: CreateQuestRequest
) -> Reward:
    """
    Создать новый квест
    
    Args:
        db: сессия БД
        quest_data: данные для создания квеста
    
    Returns:
        Созданный квест (Reward)
    """
    # Парсим дату
    try:
        target_date = datetime.strptime(quest_data.date, "%d.%m.%Y")
    except ValueError:
        target_date = datetime.now()
    
    start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Находим блюдо по названию (unit)
    item = db.query(Item).filter(Item.name.ilike(f"%{quest_data.unit}%")).first()
    if not item:
        # Если не найдено, создаем временное блюдо или берем первое попавшееся
        item = db.query(Item).first()
    
    # Создаем награду (квест)
    new_reward = Reward(
        create_date=datetime.now(),
        start_date=start_date,
        end_date=end_date,
        item_id=item.id if item else 1,
        end_goal=quest_data.target,
        prize_sum=quest_data.reward
    )
    
    db.add(new_reward)
    db.flush()
    
    # Если указаны конкретные сотрудники, создаем для них UserReward
    if quest_data.employeeIds:
        for employee_id_str in quest_data.employeeIds:
            try:
                employee_id = int(employee_id_str)
                employee = db.query(Employees).filter(Employees.id == employee_id).first()
                if not employee:
                    continue
                
                user = db.query(User).filter(User.iiko_id == employee.iiko_id).first()
                if not user:
                    continue
                
                user_reward = UserReward(
                    reward_id=new_reward.id,
                    user_id=user.id,
                    current_progress=0
                )
                db.add(user_reward)
            except ValueError:
                continue
    else:
        # Если не указаны сотрудники, создаем для всех активных официантов
        employees = db.query(Employees).filter(
            Employees.deleted == False,
            Employees.main_role_code.in_(["waiter", "Waiter", "WAITER", "Официант"])
        )
        
        if quest_data.organization_id:
            employees = employees.filter(Employees.preferred_organization_id == quest_data.organization_id)
        
        for employee in employees.all():
            user = db.query(User).filter(User.iiko_id == employee.iiko_id).first()
            if not user:
                continue
            
            user_reward = UserReward(
                reward_id=new_reward.id,
                user_id=user.id,
                current_progress=0
            )
            db.add(user_reward)
    
    db.commit()
    db.refresh(new_reward)
    
    return new_reward

