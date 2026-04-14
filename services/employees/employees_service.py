import secrets
import string

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, distinct
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from models.employees import Employees
from models.shifts import Shift
from models.roles import Roles
from models.user import User
from models.d_order import DOrder
from models.sales import Sales
from models.tables import Table
from models.restaurant_sections import RestaurantSection
from schemas.employees import EmployeeResponse, EmployeeWithShiftsResponse
from utils.security import hash_password


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


def get_employees_summary(
    db: Session,
    date: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Получить сводку по сотрудникам - количество сотрудников с открытой смены и их сумма чеков
    
    Args:
        db: сессия БД
        date: Дата в формате DD.MM.YYYY (по умолчанию сегодня)
        organization_id: ID организации для фильтрации
        
    Returns:
        Словарь с:
        - activeEmployeesCount: количество сотрудников с открытой сменой
        - totalAmount: общая сумма чеков активных сотрудников
        - employees: массив с id, name, amount для каждого
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
    
    # Находим сотрудников с открытыми сменами
    active_shifts_query = db.query(Shift).filter(
        and_(
            Shift.start_time >= start_of_day,
            Shift.start_time <= end_of_day,
            or_(
                Shift.end_time.is_(None),
                Shift.end_time > now
            )
        )
    )
    
    if organization_id is not None:
        # Фильтруем по организации через Employees
        active_shifts_query = active_shifts_query.join(
            Employees, Shift.employee_id == Employees.id
        ).filter(Employees.preferred_organization_id == organization_id)
    
    active_shifts = active_shifts_query.all()
    active_employee_ids = list(set([shift.employee_id for shift in active_shifts if shift.employee_id]))
    
    active_employees_count = len(active_employee_ids)
    total_amount = 0.0
    employees_data = []
    
    # Для каждого активного сотрудника считаем сумму чеков
    for employee_id in active_employee_ids:
        employee = db.query(Employees).filter(Employees.id == employee_id).first()
        if not employee:
            continue
        
        # Получаем User по iiko_id
        user = None
        if employee.iiko_id:
            user = db.query(User).filter(User.iiko_id == employee.iiko_id).first()
        
        employee_amount = 0.0
        
        # Считаем сумму чеков из DOrder
        if user:
            orders_query = db.query(func.sum(DOrder.sum_order)).filter(
                and_(
                    DOrder.user_id == user.id,
                    DOrder.time_order >= start_of_day,
                    DOrder.time_order <= end_of_day,
                    DOrder.deleted == False
                )
            )
            
            if organization_id is not None:
                orders_query = orders_query.filter(DOrder.organization_id == organization_id)
            
            order_sum = orders_query.scalar()
            if order_sum:
                employee_amount = float(order_sum)
        
        # Если нет данных из DOrder, пробуем получить из Sales
        if employee_amount == 0 and employee.iiko_id:
            sales_query = db.query(func.sum(Sales.dish_discount_sum_int)).filter(
                and_(
                    Sales.waiter_name_id == employee.iiko_id,
                    Sales.open_date_typed >= start_of_day.date(),
                    Sales.open_date_typed <= end_of_day.date(),
                    Sales.cashier != "Удаление позиций",
                    Sales.order_deleted != "DELETED"
                )
            )
            
            if organization_id is not None:
                sales_query = sales_query.filter(Sales.organization_id == organization_id)
            
            sales_sum = sales_query.scalar()
            if sales_sum:
                employee_amount = float(sales_sum)
        
        total_amount += employee_amount
        
        employees_data.append({
            "id": employee.id,
            "name": employee.name or "",
            "amount": round(employee_amount, 2)
        })
    
    return {
        "activeEmployeesCount": active_employees_count,
        "totalAmount": round(total_amount, 2),
        "employees": employees_data
    }


def get_employee_summary(
    db: Session,
    employee_id: int,
    date: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Получить сводку по конкретному сотруднику - имя фамилия сотрудника, длительность смены и сумма
    
    Args:
        db: сессия БД
        employee_id: ID сотрудника
        date: Дата в формате DD.MM.YYYY (по умолчанию сегодня)
        organization_id: ID организации для фильтрации
        
    Returns:
        Словарь с:
        - id, firstName, lastName, name
        - shiftDuration: длительность смены
        - totalAmount: сумма чеков
        - ordersCount: количество чеков
    """
    # Получаем сотрудника
    employee = db.query(Employees).filter(Employees.id == employee_id).first()
    if not employee:
        raise ValueError(f"Employee with id {employee_id} not found")
    
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
    
    # Получаем имя и фамилию
    name_parts = (employee.name or "").split(" ", 1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    
    # Получаем User по iiko_id
    user = None
    if employee.iiko_id:
        user = db.query(User).filter(User.iiko_id == employee.iiko_id).first()
    
    # Считаем сумму чеков и количество чеков
    total_amount = 0.0
    orders_count = 0
    
    # Из DOrder
    if user:
        orders_query = db.query(
            func.sum(DOrder.sum_order).label("total"),
            func.count(DOrder.id).label("count")
        ).filter(
            and_(
                DOrder.user_id == user.id,
                DOrder.time_order >= start_of_day,
                DOrder.time_order <= end_of_day,
                DOrder.deleted == False
            )
        )
        
        if organization_id is not None:
            orders_query = orders_query.filter(DOrder.organization_id == organization_id)
        
        orders_result = orders_query.first()
        if orders_result:
            total_amount = float(orders_result.total or 0)
            orders_count = int(orders_result.count or 0)
    
    # Если нет данных из DOrder, пробуем получить из Sales
    if orders_count == 0 and employee.iiko_id:
        sales_query = db.query(
            func.sum(Sales.dish_discount_sum_int).label("total"),
            func.count(distinct(Sales.order_id)).label("count")
        ).filter(
            and_(
                Sales.waiter_name_id == employee.iiko_id,
                Sales.open_date_typed >= start_of_day.date(),
                Sales.open_date_typed <= end_of_day.date(),
                Sales.cashier != "Удаление позиций",
                Sales.order_deleted != "DELETED",
                Sales.order_id.isnot(None)
            )
        )
        
        if organization_id is not None:
            sales_query = sales_query.filter(Sales.organization_id == organization_id)
        
        sales_result = sales_query.first()
        if sales_result:
            total_amount = float(sales_result.total or 0)
            orders_count = int(sales_result.count or 0)
    
    # Считаем длительность смены за день
    shift = db.query(Shift).filter(
        and_(
            Shift.employee_id == employee_id,
            Shift.start_time >= start_of_day,
            Shift.start_time <= end_of_day
        )
    ).order_by(Shift.start_time.desc()).first()
    
    shift_duration = "00:00:00"
    if shift:
        if shift.end_time:
            duration_seconds = (shift.end_time - shift.start_time).total_seconds()
        else:
            # Если смена не закрыта, считаем до текущего момента
            duration_seconds = (datetime.now() - shift.start_time).total_seconds()
        
        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        seconds = int(duration_seconds % 60)
        shift_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    return {
        "id": employee.id,
        "firstName": first_name,
        "lastName": last_name,
        "name": employee.name or "",
        "shiftDuration": shift_duration,
        "totalAmount": round(total_amount, 2),
        "ordersCount": orders_count
    }


def get_employee_details(
    db: Session,
    employee_id: int,
    table_id: Optional[int] = None,
    date: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Получить детали по одному сотруднику - длительность смены, сумма чеков и столы на которых открыты чеки
    
    Args:
        db: сессия БД
        employee_id: ID сотрудника
        table_id: ID стола для фильтрации (опционально)
        date: Дата в формате DD.MM.YYYY (по умолчанию сегодня)
        organization_id: ID организации для фильтрации
        
    Returns:
        Словарь с:
        - shiftDuration: длительность смены
        - totalAmount: сумма чеков
        - ordersCount: количество чеков
        - tables: массив столов с id, number, roomName, orderId, amount
    """
    # Получаем сотрудника
    employee = db.query(Employees).filter(Employees.id == employee_id).first()
    if not employee:
        raise ValueError(f"Employee with id {employee_id} not found")
    
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
    
    # Получаем User по iiko_id
    user = None
    if employee.iiko_id:
        user = db.query(User).filter(User.iiko_id == employee.iiko_id).first()
    
    # Считаем сумму чеков и количество чеков
    total_amount = 0.0
    orders_count = 0
    
    # Из DOrder
    if user:
        orders_query = db.query(
            func.sum(DOrder.sum_order).label("total"),
            func.count(DOrder.id).label("count")
        ).filter(
            and_(
                DOrder.user_id == user.id,
                DOrder.time_order >= start_of_day,
                DOrder.time_order <= end_of_day,
                DOrder.deleted == False
            )
        )
        
        if organization_id is not None:
            orders_query = orders_query.filter(DOrder.organization_id == organization_id)
        
        orders_result = orders_query.first()
        if orders_result:
            total_amount = float(orders_result.total or 0)
            orders_count = int(orders_result.count or 0)
    
    # Если нет данных из DOrder, пробуем получить из Sales
    if orders_count == 0 and employee.iiko_id:
        sales_query = db.query(
            func.sum(Sales.dish_discount_sum_int).label("total"),
            func.count(distinct(Sales.order_id)).label("count")
        ).filter(
            and_(
                Sales.waiter_name_id == employee.iiko_id,
                Sales.open_date_typed >= start_of_day.date(),
                Sales.open_date_typed <= end_of_day.date(),
                Sales.cashier != "Удаление позиций",
                Sales.order_deleted != "DELETED",
                Sales.order_id.isnot(None)
            )
        )
        
        if organization_id is not None:
            sales_query = sales_query.filter(Sales.organization_id == organization_id)
        
        sales_result = sales_query.first()
        if sales_result:
            total_amount = float(sales_result.total or 0)
            orders_count = int(sales_result.count or 0)
    
    # Считаем длительность смены
    shift = db.query(Shift).filter(
        and_(
            Shift.employee_id == employee_id,
            Shift.start_time >= start_of_day,
            Shift.start_time <= end_of_day
        )
    ).order_by(Shift.start_time.desc()).first()
    
    shift_duration = "00:00:00"
    if shift:
        if shift.end_time:
            duration_seconds = (shift.end_time - shift.start_time).total_seconds()
        else:
            duration_seconds = (now - shift.start_time).total_seconds()
        
        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        seconds = int(duration_seconds % 60)
        shift_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    # Получаем столы с открытыми чеками
    tables_data = []
    
    # Получаем открытые заказы сотрудника
    if user:
        open_orders_query = db.query(DOrder).filter(
            and_(
                DOrder.user_id == user.id,
                DOrder.time_order >= start_of_day,
                DOrder.time_order <= end_of_day,
                DOrder.deleted == False,
                DOrder.state_order != "CLOSED"  # Только открытые заказы
            )
        )
        
        if organization_id is not None:
            open_orders_query = open_orders_query.filter(DOrder.organization_id == organization_id)
        
        if table_id is not None:
            # Фильтруем по столу через tab_name
            table = db.query(Table).filter(Table.id == table_id).first()
            if table:
                open_orders_query = open_orders_query.filter(DOrder.tab_name == str(table.number))
        
        open_orders = open_orders_query.all()
        
        # Группируем по столам
        tables_dict = {}
        for order in open_orders:
            table_num = order.tab_name
            if not table_num:
                continue
            
            # Находим стол по номеру
            table = db.query(Table).filter(Table.number == int(table_num)).first()
            if not table:
                continue
            
            # Получаем секцию (помещение)
            section = db.query(RestaurantSection).filter(
                RestaurantSection.id == table.section_id
            ).first()
            
            table_key = str(table.id)
            if table_key not in tables_dict:
                tables_dict[table_key] = {
                    "id": table.id,
                    "number": str(table.number),
                    "roomName": section.name if section else None,
                    "orderId": order.iiko_id or str(order.id),
                    "amount": 0.0
                }
            
            tables_dict[table_key]["amount"] += float(order.sum_order or 0)
        
        tables_data = list(tables_dict.values())
    
    # Если нет данных из DOrder, пробуем получить из Sales
    if not tables_data and employee.iiko_id:
        sales_query = db.query(
            Sales.table_num,
            Sales.order_id,
            func.sum(Sales.dish_discount_sum_int).label("amount")
        ).filter(
            and_(
                Sales.waiter_name_id == employee.iiko_id,
                Sales.open_date_typed >= start_of_day.date(),
                Sales.open_date_typed <= end_of_day.date(),
                Sales.cashier != "Удаление позиций",
                Sales.order_deleted != "DELETED",
                Sales.order_id.isnot(None),
                Sales.table_num.isnot(None)
            )
        )
        
        if organization_id is not None:
            sales_query = sales_query.filter(Sales.organization_id == organization_id)
        
        if table_id is not None:
            table = db.query(Table).filter(Table.id == table_id).first()
            if table:
                sales_query = sales_query.filter(Sales.table_num == table.number)
        
        sales_results = sales_query.group_by(Sales.table_num, Sales.order_id).all()
        
        tables_dict = {}
        for result in sales_results:
            table_num = result.table_num
            if not table_num:
                continue
            
            # Находим стол по номеру
            table = db.query(Table).filter(Table.number == int(table_num)).first()
            if not table:
                continue
            
            # Получаем секцию (помещение)
            section = db.query(RestaurantSection).filter(
                RestaurantSection.id == table.section_id
            ).first()
            
            table_key = str(table.id)
            if table_key not in tables_dict:
                tables_dict[table_key] = {
                    "id": table.id,
                    "number": str(table.number),
                    "roomName": section.name if section else None,
                    "orderId": result.order_id,
                    "amount": 0.0
                }
            
            tables_dict[table_key]["amount"] += float(result.amount or 0)
        
        tables_data = list(tables_dict.values())
    
    return {
        "shiftDuration": shift_duration,
        "totalAmount": round(total_amount, 2),
        "ordersCount": orders_count,
        "tables": tables_data
    }


def get_employee_open_check(
    db: Session,
    employee_id: int,
    date_time: str,
    organization_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Получить детали открытого счета сотрудника - содержимое чека
    
    Args:
        db: сессия БД
        employee_id: ID сотрудника
        date_time: Дата и время в формате ISO (YYYY-MM-DDTHH:mm:ssZ или YYYY-MM-DDTHH:mm:ss)
        organization_id: ID организации для фильтрации
        
    Returns:
        Словарь с:
        - orderId: ID заказа
        - tableId, tableNumber, roomName: информация о столе
        - items: массив блюд с name, quantity, price, total
        - totalAmount: общая сумма
        - status: статус заказа
    """
    from models.restaurant_sections import RestaurantSection
    
    # Получаем сотрудника
    employee = db.query(Employees).filter(Employees.id == employee_id).first()
    if not employee:
        raise ValueError(f"Employee with id {employee_id} not found")
    
    # Парсим dateTime
    try:
        # Пробуем разные форматы ISO
        if 'Z' in date_time:
            target_datetime = datetime.fromisoformat(date_time.replace('Z', '+00:00'))
        elif '+' in date_time or '-' in date_time[-6:]:
            target_datetime = datetime.fromisoformat(date_time)
        else:
            target_datetime = datetime.fromisoformat(date_time)
    except ValueError:
        raise ValueError(f"Invalid dateTime format: {date_time}. Use ISO format (YYYY-MM-DDTHH:mm:ssZ)")
    
    # Получаем User по iiko_id
    user = None
    if employee.iiko_id:
        user = db.query(User).filter(User.iiko_id == employee.iiko_id).first()
    
    if not user:
        raise ValueError(f"User not found for employee {employee_id}")
    
    # Ищем заказ по user_id и времени (с допуском ±5 минут)
    time_tolerance = timedelta(minutes=5)
    start_time = target_datetime - time_tolerance
    end_time = target_datetime + time_tolerance
    
    order = db.query(DOrder).filter(
        and_(
            DOrder.user_id == user.id,
            DOrder.time_order >= start_time,
            DOrder.time_order <= end_time,
            DOrder.deleted == False
        )
    )
    
    if organization_id is not None:
        order = order.filter(DOrder.organization_id == organization_id)
    
    order = order.order_by(DOrder.time_order.desc()).first()
    
    if not order:
        raise ValueError(f"Order not found for employee {employee_id} at {date_time}")
    
    # Получаем информацию о столе
    table_id = None
    table_number = None
    room_name = None
    
    if order.tab_name:
        try:
            table_num = int(order.tab_name)
            table = db.query(Table).filter(Table.number == table_num).first()
            if table:
                table_id = table.id
                table_number = str(table.number)
                
                # Получаем секцию (помещение)
                section = db.query(RestaurantSection).filter(
                    RestaurantSection.id == table.section_id
                ).first()
                if section:
                    room_name = section.name
        except (ValueError, TypeError):
            pass
    
    # Получаем items из Sales
    items = []
    if order.iiko_id:
        sales_items = db.query(Sales).filter(
            and_(
                Sales.order_id == order.iiko_id,
                Sales.deleted_with_writeoff == 'NOT_DELETED',
                Sales.dish_discount_sum_int > 0
            )
        ).all()
        
        for sale in sales_items:
            items.append({
                "name": sale.dish_name or "",
                "quantity": sale.dish_amount_int or 0,
                "price": float(sale.dish_discount_sum_int or 0) / (sale.dish_amount_int or 1) if sale.dish_amount_int else 0.0,
                "total": float(sale.dish_discount_sum_int or 0)
            })
    
    # Если нет items из Sales, пробуем получить из JSON поля items в DOrder
    if not items and order.items:
        if isinstance(order.items, list):
            for item in order.items:
                if isinstance(item, dict):
                    items.append({
                        "name": item.get("name", ""),
                        "quantity": item.get("amount", 0),
                        "price": float(item.get("price", 0)),
                        "total": float(item.get("sum", 0))
                    })
    
    total_amount = float(order.sum_order or 0)
    
    return {
        "orderId": order.iiko_id or str(order.id),
        "tableId": table_id,
        "tableNumber": table_number,
        "roomName": room_name,
        "items": items,
        "totalAmount": round(total_amount, 2),
        "status": order.state_order or "OPEN"
    }


def get_employee_closed_tables_history(
    db: Session,
    employee_id: int,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Получить историю закрытых столиков сотрудника - список чеков закрытых сотрудником и суммы
    
    Args:
        db: сессия БД
        employee_id: ID сотрудника
        from_date: Дата начала периода в формате DD.MM.YYYY
        to_date: Дата конца периода в формате DD.MM.YYYY
        organization_id: ID организации для фильтрации
        
    Returns:
        Массив закрытых чеков с:
        - orderId, tableId, tableNumber, roomName
        - closedAt: дата/время закрытия
        - totalAmount: сумма чека
        - itemsCount: количество позиций
    """
    from models.restaurant_sections import RestaurantSection
    
    # Получаем сотрудника
    employee = db.query(Employees).filter(Employees.id == employee_id).first()
    if not employee:
        raise ValueError(f"Employee with id {employee_id} not found")
    
    # Парсим даты
    if from_date:
        try:
            start_date = datetime.strptime(from_date, "%d.%m.%Y").replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    else:
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    
    if to_date:
        try:
            end_date = datetime.strptime(to_date, "%d.%m.%Y").replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Получаем User по iiko_id
    user = None
    if employee.iiko_id:
        user = db.query(User).filter(User.iiko_id == employee.iiko_id).first()
    
    result = []
    
    # Получаем закрытые заказы из DOrder
    if user:
        closed_orders_query = db.query(DOrder).filter(
            and_(
                DOrder.user_id == user.id,
                DOrder.time_order >= start_date,
                DOrder.time_order <= end_date,
                DOrder.deleted == False,
                DOrder.state_order == "CLOSED"  # Только закрытые заказы
            )
        )
        
        if organization_id is not None:
            closed_orders_query = closed_orders_query.filter(DOrder.organization_id == organization_id)
        
        closed_orders = closed_orders_query.order_by(DOrder.time_order.desc()).all()
        
        for order in closed_orders:
            # Получаем информацию о столе
            table_id = None
            table_number = None
            room_name = None
            
            if order.tab_name:
                try:
                    table_num = int(order.tab_name)
                    table = db.query(Table).filter(Table.number == table_num).first()
                    if table:
                        table_id = table.id
                        table_number = str(table.number)
                        
                        # Получаем секцию (помещение)
                        section = db.query(RestaurantSection).filter(
                            RestaurantSection.id == table.section_id
                        ).first()
                        if section:
                            room_name = section.name
                except (ValueError, TypeError):
                    pass
            
            # Считаем количество позиций
            items_count = 0
            if order.iiko_id:
                items_count = db.query(func.count(Sales.id)).filter(
                    and_(
                        Sales.order_id == order.iiko_id,
                        Sales.deleted_with_writeoff == 'NOT_DELETED'
                    )
                ).scalar() or 0
            
            result.append({
                "orderId": order.iiko_id or str(order.id),
                "tableId": table_id,
                "tableNumber": table_number,
                "roomName": room_name,
                "closedAt": order.time_order.isoformat() if order.time_order else None,
                "totalAmount": round(float(order.sum_order or 0), 2),
                "itemsCount": items_count
            })
    
    # Если нет данных из DOrder, пробуем получить из Sales
    if not result and employee.iiko_id:
        closed_sales_query = db.query(
            Sales.order_id,
            Sales.table_num,
            Sales.close_time,
            func.sum(Sales.dish_discount_sum_int).label("total"),
            func.count(Sales.id).label("items_count")
        ).filter(
            and_(
                Sales.waiter_name_id == employee.iiko_id,
                Sales.open_date_typed >= start_date.date(),
                Sales.open_date_typed <= end_date.date(),
                Sales.cashier != "Удаление позиций",
                Sales.order_deleted == "CLOSED",  # Закрытые заказы
                Sales.order_id.isnot(None)
            )
        )
        
        if organization_id is not None:
            closed_sales_query = closed_sales_query.filter(Sales.organization_id == organization_id)
        
        closed_sales = closed_sales_query.group_by(
            Sales.order_id, Sales.table_num, Sales.close_time
        ).all()
        
        for sale_result in closed_sales:
            table_id = None
            table_number = None
            room_name = None
            
            if sale_result.table_num:
                table = db.query(Table).filter(Table.number == int(sale_result.table_num)).first()
                if table:
                    table_id = table.id
                    table_number = str(table.number)
                    
                    section = db.query(RestaurantSection).filter(
                        RestaurantSection.id == table.section_id
                    ).first()
                    if section:
                        room_name = section.name
            
            result.append({
                "orderId": sale_result.order_id,
                "tableId": table_id,
                "tableNumber": table_number,
                "roomName": room_name,
                "closedAt": sale_result.close_time.isoformat() if sale_result.close_time else None,
                "totalAmount": round(float(sale_result.total or 0), 2),
                "itemsCount": int(sale_result.items_count or 0)
            })

    return result


_PASSWORD_ALPHABET = string.ascii_letters + string.digits

# Таблица транслитерации кириллица -> латиница
_TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
    'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
    'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
    'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch',
    'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
    'қ': 'q', 'Қ': 'Q', 'ң': 'ng', 'Ң': 'Ng', 'ү': 'u', 'Ү': 'U',
    'ұ': 'u', 'Ұ': 'U', 'һ': 'h', 'Һ': 'H', 'ә': 'a', 'Ә': 'A',
    'і': 'i', 'І': 'I', 'ғ': 'gh', 'Ғ': 'Gh', 'ө': 'o', 'Ө': 'O',
}


def transliterate(name: str) -> str:
    """Транслитерация кириллицы в латиницу. Пробелы -> точки, lowercase."""
    result = []
    for ch in name:
        if ch in _TRANSLIT_MAP:
            result.append(_TRANSLIT_MAP[ch])
        elif ch == ' ':
            result.append('.')
        else:
            result.append(ch)
    return "".join(result).lower()


def _generate_unique_login(base_login: str, existing_logins: set) -> str:
    """Генерирует уникальный логин, добавляя суффикс при коллизии."""
    login = base_login
    counter = 2
    while login in existing_logins:
        login = f"{base_login}{counter}"
        counter += 1
    return login


def create_users_for_all_employees(db: Session) -> List[Dict[str, Any]]:
    """
    Создать пользователей для всех сотрудников, у которых нет связанного User.

    Для каждого Employee без User (совпадение по iiko_id):
    - Логин = транслитерация Employee.name (латиница, lowercase, пробелы -> точки)
    - Пароль — случайные 8 символов (буквы + цифры), возвращается в открытом виде

    Returns:
        Список словарей: [{"employee_id", "login", "plain_password"}]
    """
    employees = db.query(Employees).filter(Employees.deleted == False).all()  # noqa: E712

    existing_iiko_ids = {
        u.iiko_id
        for u in db.query(User.iiko_id).filter(User.iiko_id.isnot(None)).all()
        if u.iiko_id
    }
    existing_logins = {
        u.login
        for u in db.query(User.login).all()
        if u.login
    }

    created = []
    for employee in employees:
        if employee.iiko_id and employee.iiko_id in existing_iiko_ids:
            continue

        if not employee.name:
            continue

        base_login = transliterate(employee.name)
        if not base_login:
            continue

        login = _generate_unique_login(base_login, existing_logins)

        plain_password = "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(8))
        new_user = User(
            login=login,
            password=hash_password(plain_password),
            iiko_id=employee.iiko_id,
        )
        db.add(new_user)
        existing_logins.add(login)
        if employee.iiko_id:
            existing_iiko_ids.add(employee.iiko_id)

        created.append({
            "employee_id": employee.id,
            "login": login,
            "plain_password": plain_password,
        })

    db.commit()
    return created


EXCLUDED_LOGINS = {"admin", "ofik", "integrator"}


def regenerate_user_logins(db: Session) -> List[Dict[str, Any]]:
    """
    Перегенерировать логины всех пользователей (кроме admin, ofik, integrator) на латиницу.

    Для каждого User (кроме исключённых):
    - Находим связанного Employee по iiko_id
    - Новый логин = транслитерация Employee.name
    - Пароль НЕ меняется

    Returns:
        Список словарей: [{"user_id", "old_login", "new_login"}]
    """

    users = db.query(User).all()

    # Собираем логины которые уже заняты (исключённые останутся)
    existing_logins = set(EXCLUDED_LOGINS)

    updated = []
    for user in users:
        if user.login in EXCLUDED_LOGINS:
            existing_logins.add(user.login)
            continue

        # Находим Employee по iiko_id
        employee = None
        if user.iiko_id:
            employee = db.query(Employees).filter(Employees.iiko_id == user.iiko_id).first()

        if not employee or not employee.name:
            existing_logins.add(user.login)
            continue

        base_login = transliterate(employee.name)
        if not base_login:
            existing_logins.add(user.login)
            continue

        new_login = _generate_unique_login(base_login, existing_logins)

        old_login = user.login
        if old_login == new_login:
            existing_logins.add(new_login)
            continue

        user.login = new_login
        existing_logins.add(new_login)

        updated.append({
            "user_id": user.id,
            "old_login": old_login,
            "new_login": new_login,
        })

    db.commit()
    return updated


def recreate_all_credentials(db: Session) -> List[Dict[str, Any]]:
    """
    Пересоздать логины и пароли для всех сотрудников.

    Для каждого не-удалённого Employee:
    - Если User с таким iiko_id существует — обновить login и password
    - Если не существует — создать нового User
    - Исключения: admin, ofik, integrator — не трогаем

    Returns:
        Список словарей: [{"employee_id", "employee_name", "login", "password"}]
    """
    employees = db.query(Employees).filter(Employees.deleted == False).all()  # noqa: E712

    # Загружаем всех существующих пользователей и маппим по iiko_id
    all_users = db.query(User).all()
    users_by_iiko_id = {}
    for u in all_users:
        if u.iiko_id:
            users_by_iiko_id[u.iiko_id] = u

    # iiko_id сотрудников, которых мы будем перегенерировать —
    # их текущие логины будут переписаны и могут быть переиспользованы
    employee_iiko_ids = {e.iiko_id for e in employees if e.iiko_id}

    # Собираем занятые логины: все пользователи, КРОМЕ тех, чей логин
    # будет перезаписан в этом прогоне (их iiko_id совпадает с employee.iiko_id
    # и логин не в EXCLUDED_LOGINS).
    existing_logins = set(EXCLUDED_LOGINS)
    for u in all_users:
        if u.login in EXCLUDED_LOGINS:
            existing_logins.add(u.login)
            continue
        if u.iiko_id and u.iiko_id in employee_iiko_ids:
            # Логин этого юзера будет перезаписан — слот освобождается
            continue
        existing_logins.add(u.login)

    result = []
    for employee in employees:
        if not employee.name or not employee.iiko_id:
            continue

        # Проверяем, не является ли связанный User исключённым
        existing_user = users_by_iiko_id.get(employee.iiko_id)
        if existing_user and existing_user.login in EXCLUDED_LOGINS:
            continue

        base_login = transliterate(employee.name)
        if not base_login:
            continue

        login = _generate_unique_login(base_login, existing_logins)
        plain_password = "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(8))
        hashed = hash_password(plain_password)

        if existing_user:
            existing_user.login = login
            existing_user.password = hashed
        else:
            new_user = User(
                login=login,
                password=hashed,
                iiko_id=employee.iiko_id,
            )
            db.add(new_user)

        existing_logins.add(login)

        result.append({
            "employee_id": employee.id,
            "employee_name": employee.name,
            "login": login,
            "password": plain_password,
        })

    db.commit()
    return result