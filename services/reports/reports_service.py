from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional
from datetime import datetime, timedelta
from models.d_order import DOrder
from models.t_order import TOrder
from models.item import Item
from schemas.reports import (
    OrderReportsResponse,
    MoneyFlowResponse,
    CheckMetric,
    ReturnMetric,
    AverageMetric,
    DishesMetric,
    WriteoffsMetric,
    ExpensesMetric,
    IncomesMetric,
    DishCost,
    WriteoffItem,
    ExpenseItem,
    IncomeItem
)
from schemas.analytics import ChangeMetric


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


def get_order_reports(
    db: Session,
    date: str,
    period: Optional[str] = "day",
    organization_id: Optional[int] = None,
) -> OrderReportsResponse:
    """
    Получить отчеты по заказам
    
    Args:
        db: сессия БД
        date: дата в формате "DD.MM.YYYY"
        period: период ("day" | "week" | "month")
        organization_id: ID организации (фильтр)
    
    Returns:
        Отчеты по заказам
    """
    # Парсим дату
    try:
        target_date = datetime.strptime(date, "%d.%m.%Y")
    except ValueError:
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
    
    # Получаем заказы за предыдущий период
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
    
    # Считаем средний чек
    current_revenue = sum(float(order.sum_order or 0) for order in orders)
    current_checks = len(orders)
    current_avg_check = current_revenue / current_checks if current_checks > 0 else 0
    
    previous_revenue = sum(float(order.sum_order or 0) for order in previous_orders)
    previous_checks = len(previous_orders)
    previous_avg_check = previous_revenue / previous_checks if previous_checks > 0 else 0
    
    # Считаем возвраты
    returns_sum = sum(float(order.sum_order or 0) for order in orders if order.state_order == "cancelled")
    
    # Считаем среднее количество блюд в заказе
    total_items = db.query(func.sum(TOrder.count_order)).join(
        DOrder, DOrder.id == TOrder.order_id
    ).filter(
        and_(
            DOrder.time_order >= start_date,
            DOrder.time_order <= end_date,
            DOrder.deleted == False
        )
    )
    
    if organization_id:
        total_items = total_items.filter(DOrder.organization_id == organization_id)
    
    total_items_count = total_items.scalar() or 0
    avg_items_per_order = total_items_count / current_checks if current_checks > 0 else 0
    
    # Получаем популярные блюда
    popular_dishes = db.query(
        Item.name,
        func.sum(TOrder.count_order).label("total_count"),
        func.sum(TOrder.count_order * Item.price).label("total_amount")
    ).join(
        TOrder, TOrder.item_id == Item.id
    ).join(
        DOrder, DOrder.id == TOrder.order_id
    ).filter(
        and_(
            DOrder.time_order >= start_date,
            DOrder.time_order <= end_date,
            DOrder.deleted == False
        )
    )
    
    if organization_id:
        popular_dishes = popular_dishes.filter(DOrder.organization_id == organization_id)
    
    popular_dishes = popular_dishes.group_by(Item.name).order_by(
        func.sum(TOrder.count_order).desc()
    ).first()
    
    # Получаем непопулярные блюда
    unpopular_dishes = db.query(
        Item.name,
        func.sum(TOrder.count_order).label("total_count"),
        func.sum(TOrder.count_order * Item.price).label("total_amount")
    ).join(
        TOrder, TOrder.item_id == Item.id
    ).join(
        DOrder, DOrder.id == TOrder.order_id
    ).filter(
        and_(
            DOrder.time_order >= start_date,
            DOrder.time_order <= end_date,
            DOrder.deleted == False
        )
    )
    
    if organization_id:
        unpopular_dishes = unpopular_dishes.filter(DOrder.organization_id == organization_id)
    
    unpopular_dishes = unpopular_dishes.group_by(Item.name).order_by(
        func.sum(TOrder.count_order).asc()
    ).first()
    
    # Формируем ответ
    checks_metric = CheckMetric(
        id=12332,
        label="Средний чек",
        value=format_currency(current_avg_check)
    )
    
    returns_metric = ReturnMetric(
        id=31341,
        label="Сумма возвратов",
        value=f"-{format_currency(returns_sum)}",
        type="negative" if returns_sum > 0 else None
    )
    
    averages = [
        AverageMetric(
            id=1,
            label="Среднее количество",
            value=f"{int(avg_items_per_order)} блюда"
        )
    ]
    
    if popular_dishes:
        dish_name, dish_count, dish_amount = popular_dishes
        averages.append(
            AverageMetric(
                id=2,
                label="Популярные блюда",
                value=f"{dish_name} ({int(dish_count)} шт, {format_currency(float(dish_amount))})",
                change=ChangeMetric(value="+23%", trend="up")
            )
        )
    
    if unpopular_dishes:
        dish_name, dish_count, dish_amount = unpopular_dishes
        averages.append(
            AverageMetric(
                id=3,
                label="Непопулярные блюда",
                value=f"{dish_name} ({int(dish_count)} шт, {format_currency(float(dish_amount))})",
                change=ChangeMetric(value="-15%", trend="down")
            )
        )
    
    return OrderReportsResponse(
        checks=checks_metric,
        returns=returns_metric,
        averages=averages
    )


def get_moneyflow_reports(
    db: Session,
    date: str,
    period: Optional[str] = "day",
    organization_id: Optional[int] = None,
) -> MoneyFlowResponse:
    """
    Получить денежные отчеты
    
    Args:
        db: сессия БД
        date: дата в формате "DD.MM.YYYY"
        period: период ("day" | "week" | "month")
        organization_id: ID организации (фильтр)
    
    Returns:
        Денежные потоки
    """
    # Парсим дату
    try:
        target_date = datetime.strptime(date, "%d.%m.%Y")
    except ValueError:
        target_date = datetime.now()
    
    # Определяем период
    if period == "week":
        start_date = target_date - timedelta(days=7)
    elif period == "month":
        start_date = target_date - timedelta(days=30)
    else:  # day
        start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Получаем стоимость блюд по себестоимости
    dishes_data = db.query(
        Item.name,
        func.sum(TOrder.count_order).label("quantity"),
        func.sum(TOrder.count_order * Item.price * 0.3).label("cost_amount")  # Примерно 30% себестоимость
    ).join(
        TOrder, TOrder.item_id == Item.id
    ).join(
        DOrder, DOrder.id == TOrder.order_id
    ).filter(
        and_(
            DOrder.time_order >= start_date,
            DOrder.time_order <= end_date,
            DOrder.deleted == False
        )
    )
    
    if organization_id:
        dishes_data = dishes_data.filter(DOrder.organization_id == organization_id)
    
    dishes_data = dishes_data.group_by(Item.name).all()
    
    total_cost = sum(float(cost) for _, _, cost in dishes_data)
    
    dish_costs = [
        DishCost(
            id=idx,
            name=name,
            amount=float(cost),
            quantity=int(quantity)
        )
        for idx, (name, quantity, cost) in enumerate(dishes_data, start=1)
    ]
    
    # TODO: Добавить реальные данные о списаниях
    writeoffs_data = [
        WriteoffItem(
            id=1,
            item="Молоко",
            quantity=5,
            reason="Истек срок годности"
        )
    ]
    
    # TODO: Добавить реальные данные о расходах
    expenses_data = [
        ExpenseItem(
            id=1,
            reason="Аренда помещения",
            amount=500000.0,
            date=date
        )
    ]
    
    # TODO: Добавить реальные данные о доходах
    incomes_data = [
        IncomeItem(
            id=1,
            source="Продажи",
            amount=total_cost / 0.3,  # Обратный расчет от себестоимости
            date=date
        )
    ]
    
    return MoneyFlowResponse(
        dishes=DishesMetric(
            id=1,
            label="Сумма всех проданных блюд по себестоимости",
            value=format_currency(total_cost),
            data=dish_costs
        ),
        writeoffs=WriteoffsMetric(
            id=2,
            label="Списания",
            value=format_currency(sum(w.quantity * 100 for w in writeoffs_data)),  # Примерная стоимость
            data=writeoffs_data
        ),
        expenses=ExpensesMetric(
            id=3,
            label="Расходы",
            value=format_currency(sum(e.amount for e in expenses_data)),
            type="negative",
            data=expenses_data
        ),
        incomes=IncomesMetric(
            id=4,
            label="Доходы",
            value=format_currency(sum(i.amount for i in incomes_data)),
            type="positive",
            data=incomes_data
        )
    )

