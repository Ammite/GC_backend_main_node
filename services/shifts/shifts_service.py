from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional
from datetime import datetime, timedelta
from models.shifts import Shift
from models.employees import Employees
from models.user import User
from models.d_order import DOrder
from models.penalty import Penalty
from models.rewards import Reward
from models.user_reward import UserReward
from schemas.shifts import ShiftResponse, ShiftStatusResponse


def calculate_elapsed_time(start_time: datetime, end_time: Optional[datetime] = None) -> str:
    """Рассчитать прошедшее время в формате HH:mm:ss"""
    if end_time is None:
        end_time = datetime.now()
    
    elapsed = end_time - start_time
    hours = int(elapsed.total_seconds() // 3600)
    minutes = int((elapsed.total_seconds() % 3600) // 60)
    seconds = int(elapsed.total_seconds() % 60)
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_shifts(
    db: Session,
    date: Optional[str] = None,
    employee_id: Optional[int] = None,
    organization_id: Optional[int] = None,
) -> ShiftResponse:
    """
    Получить информацию о смене
    
    Args:
        db: сессия БД
        date: дата в формате "DD.MM.YYYY" (по умолчанию сегодня)
        employee_id: ID сотрудника (фильтр)
        organization_id: ID организации (фильтр)
    
    Returns:
        Информация о смене
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
    
    # Получаем смены за день
    query = db.query(Shift).filter(
        and_(
            Shift.start_time >= start_of_day,
            Shift.start_time <= end_of_day
        )
    )
    
    if employee_id:
        query = query.filter(Shift.employee_id == employee_id)
    
    shifts = query.all()
    
    # Считаем количество активных сотрудников
    open_employees = len(set(shift.employee_id for shift in shifts if shift.end_time is None or shift.end_time > datetime.now()))
    
    # Получаем общую выручку за день
    orders_query = db.query(DOrder).filter(
        and_(
            DOrder.time_order >= start_of_day,
            DOrder.time_order <= end_of_day,
            DOrder.deleted == False
        )
    )
    
    if organization_id:
        orders_query = orders_query.filter(DOrder.organization_id == organization_id)
    
    orders = orders_query.all()
    total_amount = sum(float(order.sum_order or 0) for order in orders)
    
    # Считаем штрафы
    penalties_query = db.query(Penalty)
    penalties = penalties_query.all()
    fines_count = len(penalties)
    
    # Считаем квесты
    rewards_query = db.query(Reward).filter(
        and_(
            Reward.start_date <= end_of_day,
            Reward.end_date >= start_of_day
        )
    )
    rewards = rewards_query.all()
    quests_count = len(rewards)
    motivation_count = quests_count
    
    # Определяем статус смены
    if shifts:
        first_shift = min(shifts, key=lambda s: s.start_time)
        last_shift = max(shifts, key=lambda s: s.end_time if s.end_time else datetime.now())
        
        start_time = first_shift.start_time
        end_time = last_shift.end_time if last_shift.end_time and last_shift.end_time < datetime.now() else None
        
        if end_time:
            status = "completed"
            elapsed_time = calculate_elapsed_time(start_time, end_time)
        else:
            status = "active"
            elapsed_time = calculate_elapsed_time(start_time)
    else:
        # Если нет смен, создаем дефолтные значения
        start_time = start_of_day.replace(hour=9, minute=0)
        end_time = None
        status = "active"
        elapsed_time = "00:00:00"
    
    shift_id = f"shift-{target_date.strftime('%Y-%m-%d')}"
    
    return ShiftResponse(
        id=shift_id,
        date=target_date.strftime("%d.%m.%Y"),
        startTime=start_time.strftime("%H:%M"),
        endTime=end_time.strftime("%H:%M") if end_time else None,
        elapsedTime=elapsed_time,
        openEmployees=open_employees,
        totalAmount=total_amount,
        finesCount=fines_count,
        motivationCount=motivation_count,
        questsCount=quests_count,
        status=status
    )


def get_waiter_shift_status(
    db: Session,
    waiter_id: int,
    organization_id: Optional[int] = None,
) -> ShiftStatusResponse:
    """
    Проверить активность смены официанта
    
    Args:
        db: сессия БД
        waiter_id: ID официанта
        organization_id: ID организации (фильтр)
    
    Returns:
        Статус смены официанта
    """
    # Получаем сотрудника
    employee = db.query(Employees).filter(Employees.id == waiter_id).first()
    if not employee:
        return ShiftStatusResponse(isActive=False)
    
    # Получаем текущую смену
    now = datetime.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    shift = db.query(Shift).filter(
        and_(
            Shift.employee_id == waiter_id,
            Shift.start_time >= start_of_day,
            Shift.start_time <= now
        )
    ).order_by(Shift.start_time.desc()).first()
    
    if not shift:
        return ShiftStatusResponse(isActive=False)
    
    # Проверяем, активна ли смена
    is_active = shift.end_time is None or shift.end_time > now
    
    if is_active:
        elapsed_time = calculate_elapsed_time(shift.start_time)
        return ShiftStatusResponse(
            isActive=True,
            shiftId=str(shift.id),
            startTime=shift.start_time.strftime("%H:%M"),
            elapsedTime=elapsed_time
        )
    else:
        return ShiftStatusResponse(isActive=False)

