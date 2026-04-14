from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from models.shifts import Shift
from models.attendance_types import AttendanceType
from models.employees import Employees
from models.user import User
from models.d_order import DOrder
from models.penalty import Penalty
from models.rewards import Reward
from models.user_reward import UserReward
from models.organization import Organization
from schemas.shifts import ShiftResponse, ShiftStatusResponse
from services.iiko.iiko_service import IikoService, IikoApiType
import logging

logger = logging.getLogger(__name__)

iiko_service = IikoService()

# Дефолтная организация для явок, если не указана и нет preferred_organization_id
DEFAULT_ORGANIZATION_ID = 1  # Фабрика


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
    
    # Ищем активную смену (end_time is NULL) для данного официанта
    # Не фильтруем по времени start_time, потому что смена могла быть создана
    # только что или даже вчера и всё ещё быть активной
    shift = db.query(Shift).filter(
        and_(
            Shift.employee_id == waiter_id,
            Shift.end_time.is_(None),  # Активная смена = end_time is NULL
        )
    ).order_by(Shift.start_time.desc()).first()
    
    if not shift:
        return ShiftStatusResponse(isActive=False)
    
    # Смена активна (end_time is NULL)
    elapsed_time = calculate_elapsed_time(shift.start_time)
    return ShiftStatusResponse(
        isActive=True,
        shiftId=str(shift.id),
        startTime=shift.start_time.strftime("%H:%M"),
        elapsedTime=elapsed_time
    )


def start_shift(
    db: Session,
    waiter_id: int,
    organization_id: Optional[int] = None,  # noqa: ARG001 - на будущее, сейчас не используется
) -> Shift:
    """
    Запустить смену официанта.

    - Если активная смена уже есть, просто возвращаем её.
    - Если нет — создаём новую смену с текущим временем.
    """
    # Проверяем, что сотрудник существует
    employee = db.query(Employees).filter(Employees.id == waiter_id).first()
    if not employee:
        raise ValueError(f"Employee with id {waiter_id} not found")

    now = datetime.now()

    # Проверяем, есть ли уже активная смена (end_time is NULL или в будущем)
    active_shift = (
        db.query(Shift)
        .filter(
            and_(
                Shift.employee_id == waiter_id,
                Shift.end_time.is_(None),
            )
        )
        .order_by(Shift.start_time.desc())
        .first()
    )

    if active_shift:
        return active_shift

    # Находим тип явки "Р" (Работа)
    attendance_type = db.query(AttendanceType).filter(AttendanceType.code == "Р").first()

    # Создаём новую смену
    new_shift = Shift(
        employee_id=waiter_id,
        start_time=now,
        end_time=None,
        user_id=None,
        attendance_type_id=attendance_type.id if attendance_type else None,
    )

    db.add(new_shift)
    db.commit()
    db.refresh(new_shift)

    return new_shift


def end_shift(
    db: Session,
    waiter_id: int,
    organization_id: Optional[int] = None,  # noqa: ARG001 - на будущее, сейчас не используется
) -> Shift:
    """
    Завершить активную смену официанта.

    - Находит активную смену (end_time is NULL).
    - Устанавливает end_time = текущее время.
    """
    # Проверяем, что сотрудник существует
    employee = db.query(Employees).filter(Employees.id == waiter_id).first()
    if not employee:
        raise ValueError(f"Employee with id {waiter_id} not found")

    now = datetime.now()

    # Находим активную смену
    active_shift = (
        db.query(Shift)
        .filter(
            and_(
                Shift.employee_id == waiter_id,
                Shift.end_time.is_(None),
            )
        )
        .order_by(Shift.start_time.desc())
        .first()
    )

    if not active_shift:
        raise ValueError(f"No active shift found for waiter {waiter_id}")

    # Завершаем смену
    active_shift.end_time = now

    db.commit()
    db.refresh(active_shift)

    logger.info(f"Shift {active_shift.id} ended for waiter {waiter_id}")

    return active_shift


def _get_department_info(db: Session, employee_id: int, organization_id: Optional[int] = None) -> Optional[Dict[str, str]]:
    """Определить iiko_id и name подразделения (department) для явки."""
    from models.department import Department

    employee = db.query(Employees).filter(Employees.id == employee_id).first()
    org_id = organization_id or (employee.preferred_organization_id if employee else None) or DEFAULT_ORGANIZATION_ID

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org and org.department_id:
        dept = db.query(Department).filter(Department.id == org.department_id).first()
        if dept:
            return {"iiko_id": dept.iiko_id, "name": dept.name}

    # Фолбэк — Фабрика department
    dept = db.query(Department).filter(Department.name == "ФАБРИКА").first()
    if dept:
        return {"iiko_id": dept.iiko_id, "name": dept.name}
    return None


def _build_attendance_xml(
    employee_iiko_id: str,
    department_iiko_id: str,
    department_name: str,
    attendance_type_code: Optional[str] = None,
    role_iiko_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    attendance_id: Optional[str] = None,
) -> str:
    """Собрать XML для создания явки в iiko Server API."""
    # iiko принимает формат: 2017-10-08T10:00:00+05:00
    # Сервер работает в UTC, конвертируем в Астану (+05:00)
    from zoneinfo import ZoneInfo

    tz_almaty = ZoneInfo("Asia/Almaty")

    def fmt_dt(dt: datetime) -> str:
        # Считаем что dt в UTC (naive) → конвертируем в Астану
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz_almaty)
        else:
            dt = dt.astimezone(tz_almaty)
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + "+05:00"

    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    parts.append("<attendance>")
    if attendance_id:
        parts.append(f"  <id>{attendance_id}</id>")
    else:
        parts.append("  <id/>")
    parts.append(f"  <employeeId>{employee_iiko_id}</employeeId>")
    if role_iiko_id:
        parts.append(f"  <roleId>{role_iiko_id}</roleId>")
    if attendance_type_code:
        parts.append(f"  <attendanceType>{attendance_type_code}</attendanceType>")
    if date_from:
        parts.append(f"  <dateFrom>{fmt_dt(date_from)}</dateFrom>")
    if date_to:
        parts.append(f"  <dateTo>{fmt_dt(date_to)}</dateTo>")
    parts.append(f"  <departmentId>{department_iiko_id}</departmentId>")
    parts.append(f"  <departmentName>{department_name}</departmentName>")
    parts.append("</attendance>")
    return "\n".join(parts)


async def clockin_employee_in_iiko(
    db: Session,
    employee_id: int,
    organization_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Заглушка — при открытии смены не отправляем в iiko. Явка создаётся при закрытии."""
    return {}


async def clockout_employee_in_iiko(
    db: Session,
    employee_id: int,
    organization_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Закрыть явку в iiko Server API — создаём явку с dateFrom + dateTo одним запросом."""
    import httpx

    try:
        employee = db.query(Employees).filter(Employees.id == employee_id).first()
        if not employee or not employee.iiko_id:
            logger.warning(f"Employee {employee_id} не найден или не имеет iiko_id")
            return {}

        dept_info = _get_department_info(db, employee_id, organization_id)
        if not dept_info:
            logger.warning(f"Не удалось определить department для employee {employee_id}")
            return {}

        # Находим только что завершённую смену (end_time уже установлен в end_shift)
        last_shift = (
            db.query(Shift)
            .filter(Shift.employee_id == employee_id, Shift.end_time.isnot(None))
            .order_by(Shift.start_time.desc())
            .first()
        )

        if not last_shift:
            logger.warning(f"Не найдена завершённая смена для employee {employee_id}")
            return {}

        # Тип явки "Р"
        attendance_type = db.query(AttendanceType).filter(AttendanceType.code == "Р").first()

        # Роль сотрудника
        role_iiko_id = None
        if employee.main_role_id:
            from models.roles import Roles
            role = db.query(Roles).filter(Roles.id == employee.main_role_id).first()
            if role:
                role_iiko_id = role.iiko_id

        xml_body = _build_attendance_xml(
            employee_iiko_id=employee.iiko_id,
            department_iiko_id=dept_info["iiko_id"],
            department_name=dept_info["name"],
            attendance_type_code=attendance_type.code if attendance_type else "Р",
            role_iiko_id=role_iiko_id,
            date_from=last_shift.start_time,
            date_to=last_shift.end_time,
        )

        token = await iiko_service._get_server_token()
        if not token:
            logger.warning("Не удалось получить токен Server API")
            return {}

        url = f"{iiko_service.server_base_url}/resto/api/employees/attendance/create"
        logger.info(f"Clockout (create attendance) employee {employee_id}: XML:\n{xml_body}")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                params={"key": token},
                content=xml_body.encode("utf-8"),
                headers={"Content-Type": "application/xml; charset=UTF-8"},
            )

        logger.info(f"Clockout response: {response.status_code} - {response.text[:500]}")

        # Сохраняем iiko_id явки в смену
        if response.status_code == 200:
            try:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                attendance_id = root.findtext("id")
                if attendance_id:
                    last_shift.iiko_id = attendance_id
                    db.commit()
                    logger.info(f"Сохранён iiko_id явки {attendance_id} в shift {last_shift.id}")
            except Exception as e:
                logger.warning(f"Не удалось распарсить iiko_id явки: {e}")

        return {"status": response.status_code, "response": response.text}
    except Exception as e:
        logger.error(f"Ошибка при clockout employee {employee_id} в iiko: {e}", exc_info=True)
        return {}

