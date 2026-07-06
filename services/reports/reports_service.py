from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional
import asyncio
import logging
from utils.cache import cached
from utils.async_db_executor import gather_db_queries, run_in_thread
from utils.performance_logger import log_async_execution_time, log_execution
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
    IncomeItem,
    IncomeByCategoryItem,
    IncomeByPaymentItem,
    SalesDynamicsResponse,
    DailySalesData
)
from schemas.analytics import ChangeMetric
from services.transactions_and_statistics.statistics_service import (
    format_currency,
    calculate_change_percent,
    parse_date,
    get_period_dates,
    resolve_date_range,
    get_orders_for_period,
    calculate_revenue_from_orders,
    calculate_average_check,
    get_average_items_per_order,
    get_popular_dishes,
    get_unpopular_dishes,
    get_dishes_with_cost,
    get_returns_sum_from_sales,
    get_writeoffs_sum_from_sales,
    get_writeoffs_details_from_sales,
    get_total_discount_from_orders,
    get_expenses_from_transactions,
    get_revenue_by_menu_category_and_payment,
    get_bank_commission_total,
    get_factory_revenue
)
from services.transactions_and_statistics.daily_aggregates_service import (
    get_daily_metric_sum,
    get_daily_average_check,
)

logger = logging.getLogger(__name__)


# @cached(ttl_seconds=300, key_prefix="reports_orders")  # Кэш на 5 минут - ВРЕМЕННО ОТКЛЮЧЕН
async def get_order_reports(
    db: Session,
    date: Optional[str] = None,
    period: Optional[str] = "day",
    organization_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> OrderReportsResponse:
    """
    Получить отчеты по заказам

    Args:
        db: сессия БД
        date: дата в формате "DD.MM.YYYY"
        period: период ("day" | "week" | "month")
        organization_id: ID организации (фильтр)
        date_from: начало периода DD.MM.YYYY (приоритет над date+period)
        date_to: конец периода DD.MM.YYYY (приоритет над date+period)

    Returns:
        Отчеты по заказам
    """
    # Парсим дату и определяем период
    start_date, end_date, previous_start, previous_end = resolve_date_range(date_from, date_to, date, period)
    
    # Параллельно получаем все данные
    orders, previous_orders, returns_sum, avg_items_per_order, popular_dishes_list, unpopular_dishes_list = await gather_db_queries(
        lambda: get_orders_for_period(db, start_date, end_date, organization_id),
        lambda: get_orders_for_period(db, previous_start, previous_end, organization_id),
        lambda: get_returns_sum_from_sales(db, start_date, end_date, organization_id),
        lambda: get_average_items_per_order(db, start_date, end_date, organization_id),
        lambda: get_popular_dishes(db, start_date, end_date, organization_id, limit=1),
        lambda: get_unpopular_dishes(db, start_date, end_date, organization_id, limit=1)
    )
    
    # Считаем средний чек
    current_avg_check = calculate_average_check(orders, use_discount=False)
    previous_avg_check = calculate_average_check(previous_orders, use_discount=False)
    
    popular_dishes = popular_dishes_list[0] if popular_dishes_list else None
    unpopular_dishes = unpopular_dishes_list[0] if unpopular_dishes_list else None
    
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


# @cached(ttl_seconds=300, key_prefix="reports_moneyflow")  # Кэш на 5 минут - ВРЕМЕННО ОТКЛЮЧЕН
@log_async_execution_time
async def get_moneyflow_reports(
    db: Session,
    date: Optional[str] = None,
    period: Optional[str] = "day",
    organization_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> MoneyFlowResponse:
    """
    Получить денежные отчеты

    Args:
        db: сессия БД
        date: дата в формате "DD.MM.YYYY"
        period: период ("day" | "week" | "month")
        organization_id: ID организации (фильтр)
        date_from: начало периода DD.MM.YYYY (приоритет над date+period)
        date_to: конец периода DD.MM.YYYY (приоритет над date+period)

    Returns:
        Денежные потоки
    """
    logger.debug("[PERF] get_moneyflow_reports -> parsing dates")
    # Парсим дату и определяем период
    start_date, end_date, _, _ = resolve_date_range(date_from, date_to, date, period)
    # Для обратной совместимости: date используется ниже как строка в ExpenseItem
    if not date:
        date = start_date.strftime("%d.%m.%Y")

    # Подготовка запросов для параллельного выполнения
    start_date_only = start_date.date()
    end_date_only = end_date.date()
    
    # Используем агрегированные данные из DailyAnalytics
    def get_additional_revenue():
        logger.debug("[PERF] get_moneyflow_reports -> get_additional_revenue")
        return get_daily_metric_sum(
            db,
            metric_key="revenue_additional",
            start_date=start_date_only,
            end_date=end_date_only,
            organization_id=organization_id
        )
    
    def get_factory_revenue_from_aggregates():
        logger.debug("[PERF] get_moneyflow_reports -> get_factory_revenue_from_aggregates")
        return get_daily_metric_sum(
            db,
            metric_key="factory_revenue",
            start_date=start_date_only,
            end_date=end_date_only,
            organization_id=organization_id
        )
    
    logger.debug("[PERF] get_moneyflow_reports -> starting gather_db_queries")
    # Параллельно получаем все данные
    with log_execution("gather_db_queries for moneyflow"):
        dishes_data, writeoffs_sum, writeoffs_details, expenses_result, bank_commission, revenue_by_category_payment, additional_revenue, factory_revenue = await gather_db_queries(
            lambda: get_dishes_with_cost(db, start_date, end_date, organization_id),
            lambda: get_writeoffs_sum_from_sales(db, start_date, end_date, organization_id),
            lambda: get_writeoffs_details_from_sales(db, start_date, end_date, organization_id),
            lambda: get_expenses_from_transactions(db, start_date, end_date, organization_id),
            lambda: get_bank_commission_total(db, start_date, end_date, organization_id),
            lambda: get_revenue_by_menu_category_and_payment(db, start_date, end_date, organization_id),
            get_additional_revenue,
            get_factory_revenue_from_aggregates
        )
    
    logger.debug("[PERF] get_moneyflow_reports -> processing results")
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
    
    # Формируем детализацию списаний по товарам
    writeoffs_data = [
        WriteoffItem(
            id=idx,
            item=dish_name,
            quantity=quantity,
            reason=reason
        )
        for idx, (dish_name, quantity, amount, reason) in enumerate(writeoffs_details, start=1)
    ]
    
    # Если списаний нет, добавляем заглушку
    if not writeoffs_data:
        writeoffs_data = [
            WriteoffItem(
                id=1,
                item="Нет списаний за период",
                quantity=0,
                reason="-"
            )
        ]
    
    expenses_data = [
        ExpenseItem(
            id=idx,
            reason=expense_group["transaction_name"],
            amount=expense_group["transaction_amount"],
            date=date
        )
        for idx, expense_group in enumerate(expenses_result["data"], start=1)
    ]
    
    # Добавляем комиссию банка в расходы
    if bank_commission > 0:
        expenses_data.append(
            ExpenseItem(
                id=len(expenses_data) + 1,
                reason="Комиссия банков (в)",
                amount=bank_commission,
                date=date
            )
        )
    
    incomes_sum = 0
    
    # Разделяем данные на два словаря: по категориям и по типам оплаты
    category_totals = {}  # {category: total_amount}
    payment_totals = {}   # {payment_type: total_amount}
    
    for category, payment_type, amount in revenue_by_category_payment:
        # Суммируем по категориям
        if category not in category_totals:
            category_totals[category] = 0
        category_totals[category] += amount
        
        # Суммируем по типам оплаты
        if payment_type not in payment_totals:
            payment_totals[payment_type] = 0
        payment_totals[payment_type] += amount
        
        incomes_sum += amount
    
    # Дополнительная выручка (фабрика не включается в доходы — показывается отдельно)
    incomes_sum += additional_revenue
    
    # Формируем массив доходов по категориям
    income_by_category = []
    for idx, (category, amount) in enumerate(sorted(category_totals.items(), key=lambda x: x[1], reverse=True), start=1):
        income_by_category.append(
            IncomeByCategoryItem(
                id=idx,
                category=category,
                amount=amount
            )
        )
    
    # Формируем массив доходов по типам оплаты
    income_by_pay_type = []
    for idx, (payment_type, amount) in enumerate(sorted(payment_totals.items(), key=lambda x: x[1], reverse=True), start=1):
        income_by_pay_type.append(
            IncomeByPaymentItem(
                id=idx,
                payment_type=payment_type,
                amount=amount
            )
        )
    
    # Если данных нет, добавляем заглушки
    if not income_by_category:
        income_by_category = [
            IncomeByCategoryItem(
                id=1,
                category="Нет данных",
                amount=0
            )
        ]
    
    if not income_by_pay_type:
        income_by_pay_type = [
            IncomeByPaymentItem(
                id=1,
                payment_type="Нет данных",
                amount=0
            )
        ]
    
    # Пересчитываем общую сумму расходов с учетом комиссии банка
    total_expenses_with_commission = expenses_result["expenses_amount"] + bank_commission
    
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
            value=format_currency(writeoffs_sum),
            data=writeoffs_data
        ),
        expenses=ExpensesMetric(
            id=3,
            label="Расходы",
            value=format_currency(total_expenses_with_commission),
            type="negative",
            data=expenses_data
        ),
        incomes=IncomesMetric(
            id=4,
            label="Доходы (выручка)",
            value=format_currency(incomes_sum),
            type="positive",
            income_by_category=income_by_category,
            income_by_pay_type=income_by_pay_type
        )
    )


# @cached(ttl_seconds=300, key_prefix="reports_sales_dynamics")  # Кэш на 5 минут - ВРЕМЕННО ОТКЛЮЧЕН
@log_async_execution_time
async def get_sales_dynamics(
    db: Session,
    date: Optional[str] = None,
    days: int = 7,
    organization_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> SalesDynamicsResponse:
    """
    Получить динамику продаж за последние N дней

    Args:
        db: сессия БД
        days: количество дней для анализа (по умолчанию 7)
        organization_id: ID организации (фильтр)
        date_from: начало периода DD.MM.YYYY (приоритет над date+days)
        date_to: конец периода DD.MM.YYYY (приоритет над date+days)

    Returns:
        Динамика продаж с разбивкой по дням
    """
    from datetime import datetime, timedelta

    logger.debug("[PERF] get_sales_dynamics -> determining period")
    if date_from and date_to:
        start_date = datetime.strptime(date_from, "%d.%m.%Y").date()
        end_date = datetime.strptime(date_to, "%d.%m.%Y").date()
    else:
        # Определяем период: сегодня минус N дней
        end_date = datetime.now().date()
        if date:
            end_date = parse_date(date).date()
        start_date = end_date - timedelta(days=days - 1)  # -1 чтобы включить сегодня
    
    # Функции для получения данных по каждому дню из агрегированных данных (для параллельного выполнения)
    def get_day_data(current_date):
        logger.debug(f"[PERF] get_sales_dynamics -> get_day_data for {current_date}")
        # Используем агрегированные данные из DailyAnalytics
        with log_execution(f"get_day_data({current_date})"):
            day_revenue = get_daily_metric_sum(
                db,
                metric_key="revenue_total",
                start_date=current_date,
                end_date=current_date,
                organization_id=organization_id
            )
            
            day_checks = int(get_daily_metric_sum(
                db,
                metric_key="orders_count",
                start_date=current_date,
                end_date=current_date,
                organization_id=organization_id
            ))
            
            day_average_check = get_daily_average_check(
                db,
                start_date=current_date,
                end_date=current_date,
                organization_id=organization_id,
            )
        
            return DailySalesData(
                date=current_date.strftime("%d.%m.%Y"),
                revenue=day_revenue,
                checks_count=day_checks,
                average_check=day_average_check
            )
    
    logger.debug("[PERF] get_sales_dynamics -> starting parallel day data collection")
    # Параллельно получаем данные по всем дням
    def create_day_task(i):
        current_date = start_date + timedelta(days=i)
        return run_in_thread(lambda: get_day_data(current_date))
    
    with log_execution(f"gather day data for {days} days"):
        day_tasks = [create_day_task(i) for i in range(days)]
        daily_data = await asyncio.gather(*day_tasks)
    
    logger.debug("[PERF] get_sales_dynamics -> calculating totals")
    # Общая выручка (revenue_total не включает фабрику — фабрика показывается отдельно)
    total_revenue = sum(day.revenue for day in daily_data)
    total_checks = sum(day.checks_count for day in daily_data)
    
    # Средний чек вычисляем из общей выручки и количества чеков
    overall_average_check = total_revenue / total_checks if total_checks > 0 else 0
    
    return SalesDynamicsResponse(
        success=True,
        message=f"Динамика продаж за последние {days} дней",
        total_revenue=total_revenue,
        total_checks=total_checks,
        overall_average_check=overall_average_check,
        daily_data=daily_data
    )

