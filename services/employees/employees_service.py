from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from datetime import datetime
from models.employees import Employees
from models.shifts import Shift
from models.roles import Roles
from schemas.employees import EmployeeResponse, EmployeeWithShiftsResponse


def get_employees(
    db: Session,
    name: Optional[str] = None,
    login: Optional[str] = None,
    organization_id: Optional[int] = None,
    role_code: Optional[str] = None,
    deleted: Optional[bool] = None,
    status: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[EmployeeWithShiftsResponse]:
    """
    
    array of objects:
        {
            id: "1",
            name: "Аслан Аманов",
            role: "Оффицант",
            avatarUrl:
                "https://api.builder.io/api/v1/image/assets/TEMP/3a1a0f795dd6cebc375ac2f7fbeab6a0d791efc8?width=80",
            totalAmount: "56 897 тг",
            shiftTime: "00:56:25",
            isActive: true,
        }
    """
    query = db.query(Employees)
    
    # Фильтрация по статусу (active = сотрудники с открытой сменой)
    # TODO Пока что не используем
    if status == "active":
        # Находим сотрудников с открытыми сменами (end_time is None или end_time > now)
        now = datetime.now()
        active_shift_query = db.query(Shift.employee_id).filter(
            or_(
                Shift.end_time.is_(None),
                Shift.end_time > now
            )
        ).distinct()
        active_employee_ids = [row[0] for row in active_shift_query.all() if row[0] is not None]
        if active_employee_ids:
            query = query.filter(Employees.id.in_(active_employee_ids))
        else:
            # Если нет активных смен, возвращаем пустой список
            query = query.filter(Employees.id == -1)  # Невозможный ID
    
    # Фильтрация по дате (сотрудники со сменой на указанную дату)
    if date:
        try:
            target_date = datetime.strptime(date, "%d.%m.%Y")
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # Находим сотрудников со сменами на эту дату
            shifts_on_date_query = db.query(Shift.employee_id).filter(
                and_(
                    Shift.start_time >= start_of_day,
                    Shift.start_time <= end_of_day
                )
            ).distinct()
            employee_ids_on_date = [row[0] for row in shifts_on_date_query.all() if row[0] is not None]
            
            if employee_ids_on_date:
                query = query.filter(Employees.id.in_(employee_ids_on_date))
            else:
                # Если нет смен на эту дату, возвращаем пустой список
                query = query.filter(Employees.id == -1)  # Невозможный ID
        except ValueError:
            # Если дата некорректная, игнорируем фильтр
            pass
    
    if name:
        query = query.filter(Employees.name.ilike(f"%{name}%"))
    if login:
        query = query.filter(Employees.login.ilike(f"%{login}%"))
    if organization_id is not None:
        query = query.filter(Employees.preferred_organization_id == organization_id)
    if role_code:
        query = query.filter(Employees.main_role_code == role_code)
    
    # По умолчанию показываем только неудаленных сотрудников, если не указано иное
    if deleted is not None:
        query = query.filter(Employees.deleted == deleted)
    else:
        query = query.filter(Employees.deleted == False)

    # Применяем offset
    query = query.offset(offset)
    
    # Если limit=0, возвращаем все записи без ограничения
    if limit > 0:
        query = query.limit(limit)
    
    employees = query.all()
    
    # Определяем дату для проверки активных смен
    if date:
        try:
            target_date = datetime.strptime(date, "%d.%m.%Y")
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            target_date = datetime.now()
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        target_date = datetime.now()
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    now = datetime.now()
    
    result = []
    for e in employees:
        # Получаем название роли по коду
        role_name = None
        if e.main_role_code:
            role = db.query(Roles).filter(
                Roles.code == e.main_role_code,
                Roles.deleted == False
            ).first()
            if role:
                role_name = role.name
        
        # Проверяем, есть ли активная смена у сотрудника на указанную дату
        is_active = False
        active_shift = db.query(Shift).filter(
            and_(
                Shift.employee_id == e.id,
                Shift.start_time >= start_of_day,
                Shift.start_time <= end_of_day,
                or_(
                    Shift.end_time.is_(None),
                    Shift.end_time > now
                )
            )
        ).first()
        
        if active_shift:
            is_active = True
        
        result.append(
            EmployeeWithShiftsResponse(
                id=e.id,
                name=e.name,
                deleted=e.deleted,
                role=role_name or e.main_role_code,  # Если название не найдено, возвращаем код
                avatarUrl="",  # Пустое пока что будет
                totalAmount="",  # Пустое пока что будет
                shiftTime="",  # От начала смена сколько времени прошло
                isActive=is_active,
            )
        )
    
    return result

def get_employees_with_shifts(
    db: Session,
    organization_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[EmployeeWithShiftsResponse]:
    """
    """
    employees = db.query(Employees).offset(offset).limit(limit).all()


    return [
        EmployeeWithShiftsResponse(
            id=e.id,
            name=e.name,
            deleted=e.deleted,
            role="", # TODO: get role with employee_id
            avatarUrl="",
            totalAmount="", # TODO: get total amount with employee_id
            shiftTime="", # TODO: get shift time with employee_id
            isActive=False, # TODO: get is active with employee_id
        )
        for e in employees
    ]