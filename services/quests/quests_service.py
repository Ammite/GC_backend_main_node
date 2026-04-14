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
from typing import Dict, Any

logger = logging.getLogger(__name__)


def update_quest_progress_for_order(db: Session, order):
    """
    Обновляет прогресс квестов при оплате заказа.
    Для каждой позиции заказа проверяет, есть ли активный квест на этот товар,
    и инкрементирует current_progress у соответствующего UserReward.

    Официант определяется из external_data['waiterId'] (employee_id),
    затем находится связанный user через iiko_id.
    """
    from models.t_order import TOrder

    # Определяем официанта из external_data
    # waiterId в external_data — это User.id, нужно найти Employee через iiko_id
    waiter_user_id = None
    if order.external_data and isinstance(order.external_data, dict):
        waiter_user_id = order.external_data.get("waiterId")

    if not waiter_user_id:
        logger.warning(f"Quest progress skip: order {order.id} has no waiterId in external_data")
        return

    # Находим User, затем Employee по iiko_id
    from models.user import User
    user = db.query(User).filter(User.id == waiter_user_id).first()
    if not user or not user.iiko_id:
        logger.warning(f"Quest progress skip: user {waiter_user_id} not found or has no iiko_id")
        return

    employee = db.query(Employees).filter(Employees.iiko_id == user.iiko_id).first()
    if not employee:
        logger.warning(f"Quest progress skip: employee with iiko_id {user.iiko_id} not found (user_id={waiter_user_id})")
        return

    now = datetime.now()

    waiter_employee_id = employee.id
    logger.info(f"Quest progress: processing order {order.id}, waiter_employee={waiter_employee_id}, user_id={waiter_user_id}")

    # Получаем позиции заказа
    t_orders = db.query(TOrder).filter(TOrder.order_id == order.id).all()
    if not t_orders:
        logger.warning(f"Quest progress skip: no t_orders for order {order.id}")
        return

    # Собираем item_id → count
    item_counts = {}
    for t in t_orders:
        if t.item_id is not None:
            item_counts[t.item_id] = item_counts.get(t.item_id, 0) + (t.count_order or 0)

    if not item_counts:
        logger.warning(f"Quest progress skip: no items with item_id in order {order.id}")
        return

    logger.info(f"Quest progress: order {order.id} items: {item_counts}")

    # Находим активные квесты на эти товары
    active_rewards = db.query(Reward).filter(
        and_(
            Reward.item_id.in_(list(item_counts.keys())),
            Reward.start_date <= now,
            Reward.end_date >= now,
        )
    ).all()

    if not active_rewards:
        # Проверяем, есть ли вообще активные квесты (для диагностики)
        all_active = db.query(Reward).filter(
            and_(Reward.start_date <= now, Reward.end_date >= now)
        ).all()
        logger.warning(
            f"Quest progress skip: no active rewards for items {list(item_counts.keys())}. "
            f"Total active rewards: {len(all_active)}, their item_ids: {[r.item_id for r in all_active]}"
        )
        return

    for reward in active_rewards:
        count = item_counts.get(reward.item_id, 0)
        if count <= 0:
            continue

        # Находим UserReward для официанта (по employee_id или user_id)
        user_reward = db.query(UserReward).filter(
            and_(
                UserReward.reward_id == reward.id,
                UserReward.employee_id == waiter_employee_id,
            )
        ).first()

        # Фолбэк: ищем по user_id (user уже найден выше)
        if not user_reward and user:
            user_reward = db.query(UserReward).filter(
                and_(
                    UserReward.reward_id == reward.id,
                    UserReward.user_id == user.id,
                )
            ).first()

        if user_reward:
            user_reward.current_progress += count
            logger.info(
                f"Quest progress updated: employee={waiter_employee_id}, "
                f"reward={reward.id}, item={reward.item_id}, "
                f"+{count} → {user_reward.current_progress}/{reward.end_goal}"
            )
        else:
            logger.warning(
                f"Quest progress skip: no UserReward for employee={waiter_employee_id}, reward={reward.id}"
            )


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
    
    # waiter_id может быть как Employee.id, так и User.id
    # Пробуем найти UserReward по employee_id, с фолбэком на user_id
    employee = db.query(Employees).filter(Employees.id == waiter_id).first()
    user = db.query(User).filter(User.id == waiter_id).first()

    if not employee and not user:
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
        # Ищем прогресс по employee_id, затем по user_id
        user_reward = None
        if employee:
            user_reward = db.query(UserReward).filter(
                and_(
                    UserReward.reward_id == reward.id,
                    UserReward.employee_id == employee.id
                )
            ).first()
        if not user_reward and user:
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

                # User опционален — квест работает через employee_id
                user = db.query(User).filter(User.iiko_id == employee.iiko_id).first() if employee.iiko_id else None

                user_reward = UserReward(
                    reward_id=new_reward.id,
                    user_id=user.id if user else None,
                    employee_id=employee.id,
                    current_progress=0
                )
                db.add(user_reward)
            except ValueError:
                continue
    else:
        # Если не указаны сотрудники, создаем для всех активных сотрудников
        employees = db.query(Employees).filter(
            Employees.deleted == False,
        )

        if quest_data.organization_id:
            employees = employees.filter(Employees.preferred_organization_id == quest_data.organization_id)

        for employee in employees.all():
            # User опционален — квест работает через employee_id
            user = db.query(User).filter(User.iiko_id == employee.iiko_id).first() if employee.iiko_id else None

            user_reward = UserReward(
                reward_id=new_reward.id,
                user_id=user.id if user else None,
                employee_id=employee.id,
                current_progress=0
            )
            db.add(user_reward)
    
    db.commit()
    db.refresh(new_reward)
    
    return new_reward


def get_active_quests(
    db: Session,
    date: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> List[QuestResponse]:
    """
    Получить список активных квестов
    
    Args:
        db: сессия БД
        date: Дата в формате DD.MM.YYYY (по умолчанию сегодня)
        organization_id: ID организации (фильтр)
    
    Returns:
        Список активных квестов
    """
    # Парсим дату
    if date:
        try:
            target_date = datetime.strptime(date, "%d.%m.%Y")
        except ValueError:
            target_date = datetime.now()
    else:
        target_date = datetime.now()
    
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    now = datetime.now()
    # Сравниваем только даты (без времени) для проверки истечения
    today_date = now.date()
    
    # Получаем активные квесты (которые еще не истекли)
    # Квест активен, если его expire_date (end_date) >= сегодняшней даты
    query = db.query(Reward).filter(
        and_(
            Reward.start_date <= end_of_day,
            Reward.end_date >= start_of_day,
            func.date(Reward.end_date) >= today_date  # Еще не истекли (сравниваем только даты)
        )
    )
    
    rewards = query.all()
    
    quests = []
    for reward in rewards:
        # Получаем информацию о блюде
        item = db.query(Item).filter(Item.id == reward.item_id).first()
        unit = item.name if item else "единиц"
        
        # Считаем средний прогресс всех сотрудников
        user_rewards = db.query(UserReward).filter(UserReward.reward_id == reward.id).all()
        
        if organization_id:
            # Фильтруем по организации
            filtered_user_rewards = []
            for ur in user_rewards:
                user = db.query(User).filter(User.id == ur.user_id).first()
                if not user:
                    continue
                employee = db.query(Employees).filter(Employees.iiko_id == user.iiko_id).first()
                if employee and employee.preferred_organization_id == organization_id:
                    filtered_user_rewards.append(ur)
            user_rewards = filtered_user_rewards
        
        if user_rewards:
            avg_progress = sum(ur.current_progress for ur in user_rewards) / len(user_rewards)
            progress_percent = (avg_progress / reward.end_goal * 100) if reward.end_goal > 0 else 0
            completed = avg_progress >= reward.end_goal
        else:
            avg_progress = 0
            progress_percent = 0
            completed = False
        
        quest = QuestResponse(
            id=str(reward.id),
            title="Квест на сегодня",
            description=f"Продай {reward.end_goal} {unit}",
            reward=float(reward.prize_sum),
            current=int(avg_progress),
            target=reward.end_goal,
            unit=unit,
            completed=completed,
            progress=round(progress_percent, 2),
            expiresAt=reward.end_date.isoformat() if reward.end_date else None
        )
        quests.append(quest)
    
    return quests


def update_quest(
    db: Session,
    quest_id: int,
    quest_data: CreateQuestRequest
) -> Reward:
    """
    Изменить квест
    
    Args:
        db: сессия БД
        quest_id: ID квеста
        quest_data: данные для обновления квеста
    
    Returns:
        Обновленный квест (Reward)
    """
    reward = db.query(Reward).filter(Reward.id == quest_id).first()
    if not reward:
        raise ValueError(f"Quest with id {quest_id} not found")
    
    # Обновляем поля
    if quest_data.date:
        try:
            target_date = datetime.strptime(quest_data.date, "%d.%m.%Y")
            start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            reward.start_date = start_date
            reward.end_date = end_date
        except ValueError:
            pass
    
    if quest_data.target:
        reward.end_goal = quest_data.target
    
    if quest_data.reward:
        reward.prize_sum = quest_data.reward
    
    if quest_data.unit:
        # Находим блюдо по названию
        item = db.query(Item).filter(Item.name.ilike(f"%{quest_data.unit}%")).first()
        if item:
            reward.item_id = item.id
    
    # Обновляем сотрудников, если указаны
    if quest_data.employeeIds is not None:
        # Удаляем старые UserReward
        db.query(UserReward).filter(UserReward.reward_id == quest_id).delete()
        
        # Создаем новые UserReward
        for employee_id_str in quest_data.employeeIds:
            try:
                employee_id = int(employee_id_str)
                employee = db.query(Employees).filter(Employees.id == employee_id).first()
                if not employee:
                    continue

                user = db.query(User).filter(User.iiko_id == employee.iiko_id).first() if employee.iiko_id else None

                user_reward = UserReward(
                    reward_id=quest_id,
                    user_id=user.id if user else None,
                    employee_id=employee.id,
                    current_progress=0
                )
                db.add(user_reward)
            except ValueError:
                continue
    
    db.commit()
    db.refresh(reward)
    
    return reward


def delete_quest(
    db: Session,
    quest_id: int,
) -> Dict[str, Any]:
    """
    Удалить квест
    
    Args:
        db: сессия БД
        quest_id: ID квеста
    
    Returns:
        Словарь с результатом удаления
    """
    reward = db.query(Reward).filter(Reward.id == quest_id).first()
    if not reward:
        raise ValueError(f"Quest with id {quest_id} not found")
    
    # Удаляем связанные UserReward
    db.query(UserReward).filter(UserReward.reward_id == quest_id).delete()
    
    # Удаляем квест
    db.delete(reward)
    db.commit()
    
    return {
        "success": True,
        "message": "Quest deleted successfully"
    }

