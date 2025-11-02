from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional
from datetime import datetime, timedelta
from models.d_order import DOrder
from models.sales import Sales
from models.employees import Employees
from models.user import User
from schemas.analytics import (
    AnalyticsResponse,
    ExpensesAnalyticsResponse,
    Metric,
    Report,
    OrderMetric,
    FinancialMetric,
    InventoryMetric,
    EmployeeAnalytic,
    ChangeMetric
)


def format_currency(amount: float) -> str:
    """Форматировать сумму в строку с разделителями"""
    return f"{int(amount):,} тг".replace(",", " ")


def calculate_change_percent(current: float, previous: float) -> Optional[ChangeMetric]:
    """Рассчитать процент изменения"""
    if previous == 0:
        return None
    
    change = ((current - previous) / previous) * 100
    trend = "up" if change > 0 else "down"
    sign = "+" if change > 0 else ""
    
    return ChangeMetric(
        value=f"{sign}{int(change)}%",
        trend=trend
    )


def get_analytics(
    db: Session,
    date: Optional[str] = None,
    period: Optional[str] = "day",
    organization_id: Optional[int] = None,
) -> AnalyticsResponse:
    """
    Получить аналитику для CEO
    
    Args:
        db: сессия БД
        date: дата в формате "DD.MM.YYYY"
        period: период аналитики ("day" | "week" | "month")
        organization_id: ID организации (фильтр)
    
    Returns:
        Аналитические данные
    """
    # Парсим дату
    if date:
        try:
            target_date = datetime.strptime(date, "%d.%m.%Y")
        except ValueError:
            target_date = datetime.now()
    else:
        target_date = datetime.now()
    
    # Определяем период
    if period == "week":
        start_date = target_date - timedelta(days=7)
        previous_start = start_date - timedelta(days=7)
        previous_end = start_date
    elif period == "month":
        start_date = target_date - timedelta(days=30)
        previous_start = start_date - timedelta(days=30)
        previous_end = start_date
    else:  # day
        start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        previous_start = start_date - timedelta(days=1)
        previous_end = start_date
    
    end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Получаем заказы за текущий период
    query = db.query(DOrder).filter(
        and_(
            DOrder.time_order >= start_date,
            DOrder.time_order <= end_date,
            DOrder.deleted == False
        )
    )
    
    if organization_id:
        query = query.filter(DOrder.organization_id == organization_id)
    
    orders = query.all()
    
    # Получаем заказы за предыдущий период (для сравнения)
    previous_query = db.query(DOrder).filter(
        and_(
            DOrder.time_order >= previous_start,
            DOrder.time_order < previous_end,
            DOrder.deleted == False
        )
    )
    
    if organization_id:
        previous_query = previous_query.filter(DOrder.organization_id == organization_id)
    
    previous_orders = previous_query.all()
    
    # Считаем метрики
    current_revenue = sum(float(order.discount or 0) for order in orders)
    previous_revenue = sum(float(order.discount or 0) for order in previous_orders)
    
    current_checks = len(orders)
    previous_checks = len(previous_orders)
    
    current_avg_check = current_revenue / current_checks if current_checks > 0 else 0
    previous_avg_check = previous_revenue / previous_checks if previous_checks > 0 else 0
    
    # Формируем основные метрики
    metrics = [
        Metric(
            id=1,
            label="Выручка",
            value=format_currency(current_revenue),
            change=calculate_change_percent(current_revenue, previous_revenue)
        ),
        Metric(
            id=2,
            label="Чеки",
            value=str(current_checks),
            change=calculate_change_percent(current_checks, previous_checks)
        ),
        Metric(
            id=3,
            label="Средний чек",
            value=format_currency(current_avg_check),
            change=calculate_change_percent(current_avg_check, previous_avg_check)
        )
    ]
    
    # Формируем отчеты (расходы/доходы)
    # TODO: Добавить реальные данные о расходах из соответствующих таблиц
    reports = [
        Report(
            id=1,
            title="Итого Расходы",
            value=f"+{format_currency(current_revenue * 0.7)}",  # Примерно 70% от выручки
            date=target_date.strftime("%d.%m"),
            type="expense"
        )
    ]
    
    # Метрики заказов
    '''
    Нужно брать sales, и фильтровать по deleted_with_writeoff = 'DELETED_WITHOUT_WRITEOFF'
    Потом чтобы было cashier != 'Удаление позиций'
    И order_deleted != 'DELETED'

    И суммируем по dish_sum_int
    '''

    sales_query = db.query(Sales).filter(
        Sales.deleted_with_writeoff == 'DELETED_WITHOUT_WRITEOFF',
        Sales.cashier != 'Удаление позиций',
        Sales.order_deleted != 'DELETED',
        Sales.open_time >= start_date,
        Sales.open_time <= end_date,
    )
    if organization_id:
        sales_query = sales_query.filter(Sales.organization_id == organization_id)
    
    sales = sales_query.all()
    returns_sum = sum(float(sale.dish_sum_int or 0) for sale in sales)

    
    sales_for_cost_of_goods = db.query(Sales).filter(
        Sales.cashier != 'Удаление позиций',
        Sales.order_deleted != 'DELETED',
        Sales.open_time >= start_date,
        Sales.open_time <= end_date,
    )
    if organization_id:
        sales_query = sales_query.filter(Sales.organization_id == organization_id)
    
    sales_for_cost_of_goods = sales_for_cost_of_goods.all()
    cost_of_goods = sum(float(sale.product_cost_base_product_cost or 0) for sale in sales_for_cost_of_goods)
    
    order_metrics = [
        OrderMetric(
            id=1,
            label="Средний чек",
            value=format_currency(current_avg_check)
        ),
        OrderMetric(
            id=2,
            label="Сумма возвратов",
            value=f"{format_currency(returns_sum)}",
            type="negative" if returns_sum > 0 else None
        )
    ]
    
    # Финансовые метрики
    
    financial_metrics = [
        FinancialMetric(
            id=1,
            label="Сумма всех проданных блюд по себестоимости",
            value=format_currency(cost_of_goods)
        )
    ]
    
    # Метрики инвентаря
    # TODO: Добавить реальные данные об инвентаре
    inventory_metrics = [
        InventoryMetric(
            id=1,
            label="Сумма товаров на начало периода",
            value=format_currency(0)
        )
    ]
    
    # Топ сотрудников по выручке
    # Считаем по таблице Sales, группируем по order_waiter_id (официант)
    employee_stats = db.query(
        Employees.name.label("waiter_name"),
        Employees.iiko_id.label("waiter_id"),
        Employees.id.label("employee_id"),
        func.sum(Sales.dish_discount_sum_int).label("total_revenue")
    ).join(
        Employees, Sales.order_waiter_id == Employees.iiko_id
    ).filter(
        and_(
            Sales.open_time >= start_date,
            Sales.open_time <= end_date,
            Sales.cashier != 'Удаление позиций',
            Sales.order_deleted != 'DELETED'
        )
    )
    
    if organization_id:
        employee_stats = employee_stats.filter(Sales.organization_id == organization_id)
    
    employee_stats = employee_stats.group_by(
        Employees.name, 
        Employees.iiko_id,
        Employees.id
    ).order_by(
        func.sum(Sales.dish_discount_sum_int).desc()
    ).limit(10).all()
    
    employees_analytics = []
    for idx, (waiter_name, waiter_id, employee_id, total_revenue) in enumerate(employee_stats, start=1):
        employees_analytics.append(
            EmployeeAnalytic(
                id=employee_id,
                name=waiter_name or "Неизвестно",
                amount=format_currency(float(total_revenue or 0)),
                avatar="https://static.vecteezy.com/system/resources/previews/031/090/019/non_2x/cat-icon-in-flat-trendy-style-isolated-on-transparent-background-cat-silhouette-sign-symbol-mobile-concept-and-web-design-house-animals-symbol-logo-graphics-vector.jpg"
            )
        )
    
    return AnalyticsResponse(
        metrics=metrics,
        reports=reports,
        orders=order_metrics,
        financial=financial_metrics,
        inventory=inventory_metrics,
        employees=employees_analytics
    )



def get_expenses_analytics(
    db: Session,
    date: Optional[str] = None,
    period: Optional[str] = "day",
    organization_id: Optional[int] = None,
) -> ExpensesAnalyticsResponse:
    """
    Получить аналитику расходов
    Типы которые есть в таблице transactions
    "EMPLOYEES_LIABILITY"
    "EQUITY"
    "CLIENTS_LIABILITY"
    "OTHER_INCOME"
    "INVENTORY_ASSETS"
    "OTHER_CURRENT_LIABILITY"
    "DEBTS_OF_EMPLOYEES"
    "OTHER_CURRENT_ASSET"
    "COST_OF_GOODS_SOLD"
    "CASH"
    "INCOME"
    "EXPENSES"
    "ACCOUNTS_PAYABLE"

    Нужно получить id у типов EXPENSES и EQUITY и EMPLOYEES_LIABILITY и DEBTS_OF_EMPLOYEES.
    """
    pass