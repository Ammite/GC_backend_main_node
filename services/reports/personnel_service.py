"""
Сервис для отчетов по персоналу
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, distinct
from typing import List, Optional
from datetime import datetime, timedelta
from models.employees import Employees
from models.shifts import Shift
from models.d_order import DOrder
from models.sales import Sales
from models.user import User
from models.roles import Roles
from schemas.reports import PersonnelReportResponse, PersonnelEmployeeItem


def get_personnel_report(
    db: Session,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> PersonnelReportResponse:
    """
    Получить отчет по персоналу за период
    
    Args:
        db: сессия БД
        from_date: Дата начала периода в формате DD.MM.YYYY
        to_date: Дата конца периода в формате DD.MM.YYYY
        organization_id: ID организации для фильтрации
        
    Returns:
        Отчет по персоналу с суммами чеков, количеством чеков и длительностью смен
    """
    # Парсим даты
    if from_date:
        try:
            start_date = datetime.strptime(from_date, "%d.%m.%Y").replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        # Если не указана начальная дата, берем 30 дней назад
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
    
    if to_date:
        try:
            end_date = datetime.strptime(to_date, "%d.%m.%Y").replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Получаем всех сотрудников
    employees_query = db.query(Employees).filter(Employees.deleted == False)
    
    if organization_id is not None:
        employees_query = employees_query.filter(Employees.preferred_organization_id == organization_id)
    
    employees = employees_query.all()
    
    result = []
    
    for employee in employees:
        # Получаем User по iiko_id
        user = None
        if employee.iiko_id:
            user = db.query(User).filter(User.iiko_id == employee.iiko_id).first()
        
        # Получаем название роли
        role_name = None
        if employee.main_role_code:
            role = db.query(Roles).filter(
                Roles.code == employee.main_role_code,
                Roles.deleted == False
            ).first()
            if role:
                role_name = role.name
        
        # Считаем сумму чеков и количество чеков из DOrder (если есть user_id)
        total_amount = 0.0
        orders_count = 0
        
        if user:
            # Сумма чеков из DOrder
            orders_query = db.query(
                func.sum(DOrder.sum_order).label("total"),
                func.count(DOrder.id).label("count")
            ).filter(
                and_(
                    DOrder.user_id == user.id,
                    DOrder.time_order >= start_date,
                    DOrder.time_order <= end_date,
                    DOrder.deleted == False
                )
            )
            
            if organization_id is not None:
                orders_query = orders_query.filter(DOrder.organization_id == organization_id)
            
            orders_result = orders_query.first()
            if orders_result:
                total_amount = float(orders_result.total or 0)
                orders_count = int(orders_result.count or 0)
        
        # Если нет данных из DOrder, пробуем получить из Sales по waiter_name_id
        if orders_count == 0 and employee.iiko_id:
            sales_query = db.query(
                func.sum(Sales.dish_discount_sum_int).label("total"),
                func.count(distinct(Sales.order_id)).label("count")
            ).filter(
                and_(
                    Sales.waiter_name_id == employee.iiko_id,
                    Sales.open_date_typed >= start_date.date(),
                    Sales.open_date_typed <= end_date.date(),
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
        
        # Считаем общую длительность смен за период
        shifts_query = db.query(Shift).filter(
            and_(
                Shift.employee_id == employee.id,
                Shift.start_time >= start_date,
                Shift.start_time <= end_date
            )
        )
        
        shifts = shifts_query.all()
        
        total_shift_duration_seconds = 0
        for shift in shifts:
            if shift.end_time:
                duration = (shift.end_time - shift.start_time).total_seconds()
            else:
                # Если смена не закрыта, считаем до текущего момента
                duration = (datetime.now() - shift.start_time).total_seconds()
            total_shift_duration_seconds += duration
        
        # Преобразуем секунды в формат HH:mm:ss
        hours = int(total_shift_duration_seconds // 3600)
        minutes = int((total_shift_duration_seconds % 3600) // 60)
        seconds = int(total_shift_duration_seconds % 60)
        shift_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        result.append(
            PersonnelEmployeeItem(
                id=employee.id,
                name=employee.name or "",
                role=role_name or employee.main_role_code or "",
                totalAmount=round(total_amount, 2),
                ordersCount=orders_count,
                shiftDuration=shift_duration
            )
        )
    
    return PersonnelReportResponse(
        success=True,
        message=f"Отчет по персоналу за период с {from_date or 'начало'} по {to_date or 'конец'}",
        employees=result
    )

