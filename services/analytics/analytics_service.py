from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional
import asyncio
from utils.cache import cached
from utils.async_db_executor import gather_db_queries, run_in_thread
from schemas.analytics import (
    AnalyticsResponse,
    ExpensesAnalyticsResponse,
    ExpenseTypeData,
    ExpenseTransactionItem,
    Metric,
    Report,
    OrderMetric,
    FinancialMetric,
    InventoryMetric,
    EmployeeAnalytic,
)
from services.transactions_and_statistics.statistics_service import (
    format_currency,
    calculate_change_percent,
    get_revenue_by_category,
    parse_date,
    get_period_dates,
    get_orders_for_period,
    calculate_revenue_from_orders,
    calculate_average_check,
    get_returns_sum_from_sales,
    get_cost_of_goods_from_sales,
    get_top_employees_by_revenue,
    get_expenses_from_transactions
)
from models.transaction import Transaction


# @cached(ttl_seconds=300, key_prefix="analytics")  # Кэш на 5 минут - ВРЕМЕННО ОТКЛЮЧЕН
async def get_analytics(
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
    # Парсим дату и определяем период
    target_date = parse_date(date)
    start_date, end_date, previous_start, previous_end = get_period_dates(target_date, period)
    
    # Параллельно получаем все данные
    orders, previous_orders, current_revenue_data, previous_revenue_data, expenses_result, returns_sum, cost_of_goods_dict, employee_stats = await gather_db_queries(
        lambda: get_orders_for_period(db, start_date, end_date, organization_id),
        lambda: get_orders_for_period(db, previous_start, previous_end, organization_id),
        lambda: get_revenue_by_category(db, start_date, end_date, organization_id),
        lambda: get_revenue_by_category(db, previous_start, previous_end, organization_id),
        lambda: get_expenses_from_transactions(db, start_date, end_date, organization_id, ['EXPENSES']),
        lambda: get_returns_sum_from_sales(db, start_date, end_date, organization_id),
        lambda: get_cost_of_goods_from_sales(db, start_date, end_date, organization_id),
        lambda: get_top_employees_by_revenue(db, start_date, end_date, organization_id, limit=10)
    )
    
    current_revenue = current_revenue_data["total"]
    previous_revenue = previous_revenue_data["total"]
    
    current_checks = len(orders)
    previous_checks = len(previous_orders)
    
    current_avg_check = calculate_average_check(orders, use_discount=True)
    previous_avg_check = calculate_average_check(previous_orders, use_discount=True)
    
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
    
    total_expenses = expenses_result['expenses_amount']
    
    # Формируем отчеты (расходы)
    reports = [
        Report(
            id=1,
            title="Итого Расходы",
            value=f"-{format_currency(total_expenses)}",  # Реальные расходы из транзакций
            date=target_date.strftime("%d.%m"),
            type="expense"
        )
    ]
    
    # Метрики заказов
    cost_of_goods = cost_of_goods_dict.get("total", 0.0)
    
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
    employees_analytics = []
    for waiter_name, waiter_id, employee_id, total_revenue in employee_stats:
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



# @cached(ttl_seconds=300, key_prefix="analytics_expenses")  # Кэш на 5 минут - ВРЕМЕННО ОТКЛЮЧЕН
async def get_expenses_analytics(
    db: Session,
    date: Optional[str] = None,
    period: Optional[str] = "day",
    organization_id: Optional[int] = None,
) -> ExpensesAnalyticsResponse:
    """
    Получить аналитику расходов
    
    Args:
        db: сессия БД
        date: дата в формате "DD.MM.YYYY"
        period: период аналитики ("day" | "week" | "month")
        organization_id: ID организации (фильтр)
    
    Returns:
        Структурированные данные о расходах с группировкой по типам
    """
    # Парсим дату и определяем период
    target_date = parse_date(date)
    start_date, end_date, _, _ = get_period_dates(target_date, period)
    
    # Получаем расходы из транзакций
    expense_types = ['EXPENSES']
    result = await run_in_thread(lambda: get_expenses_from_transactions(db, start_date, end_date, organization_id, expense_types))
    
    return ExpensesAnalyticsResponse(
        success=True,
        message=f"Получено расходов: {format_currency(result['expenses_amount'])}",
        expenses_amount=result['expenses_amount'],
        data=result['data']
    )