from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional
from utils.cache import cached
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
    get_bank_commission_total
)
from models.transaction import Transaction


# @cached(ttl_seconds=300, key_prefix="reports_orders")  # Кэш на 5 минут - ВРЕМЕННО ОТКЛЮЧЕН
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
    # Парсим дату и определяем период
    target_date = parse_date(date)
    start_date, end_date, previous_start, previous_end = get_period_dates(target_date, period)
    
    # Получаем заказы за текущий и предыдущий период
    orders = get_orders_for_period(db, start_date, end_date, organization_id)
    previous_orders = get_orders_for_period(db, previous_start, previous_end, organization_id)
    
    # Считаем средний чек
    current_avg_check = calculate_average_check(orders, use_discount=False)
    previous_avg_check = calculate_average_check(previous_orders, use_discount=False)
    
    # Получаем возвраты из Sales
    returns_sum = get_returns_sum_from_sales(db, start_date, end_date, organization_id)
    
    # Считаем среднее количество блюд в заказе
    avg_items_per_order = get_average_items_per_order(db, start_date, end_date, organization_id)
    
    # Получаем популярные и непопулярные блюда
    popular_dishes_list = get_popular_dishes(db, start_date, end_date, organization_id, limit=1)
    unpopular_dishes_list = get_unpopular_dishes(db, start_date, end_date, organization_id, limit=1)
    
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
    # Парсим дату и определяем период
    target_date = parse_date(date)
    start_date, end_date, _, _ = get_period_dates(target_date, period)
    
    # Получаем стоимость блюд по себестоимости
    dishes_data = get_dishes_with_cost(db, start_date, end_date, organization_id)
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
    
    # Получаем реальные данные о списаниях из Sales
    writeoffs_sum = get_writeoffs_sum_from_sales(db, start_date, end_date, organization_id)
    writeoffs_details = get_writeoffs_details_from_sales(db, start_date, end_date, organization_id)
    
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
    
    # Получаем реальные данные о расходах из транзакций
    expenses_result = get_expenses_from_transactions(db, start_date, end_date, organization_id)
    expenses_data = [
        ExpenseItem(
            id=idx,
            reason=expense_group["transaction_name"],
            amount=expense_group["transaction_amount"],
            date=date
        )
        for idx, expense_group in enumerate(expenses_result["data"], start=1)
    ]
    
    # Получаем комиссию банка (из d_order.bank_commission) и добавляем в расходы
    bank_commission = get_bank_commission_total(db, start_date, end_date, organization_id)
    if bank_commission > 0:
        expenses_data.append(
            ExpenseItem(
                id=len(expenses_data) + 1,
                reason="Комиссия банков (в)",
                amount=bank_commission,
                date=date
            )
        )
    
    # Получаем детализированные данные о доходах по категориям меню и типам оплаты
    revenue_by_category_payment = get_revenue_by_menu_category_and_payment(db, start_date, end_date, organization_id)
    
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
    
    # Дополнительная выручка
    # Суммируем отдельно sum_incoming и sum_outgoing
    sum_incoming = db.query(func.sum(Transaction.sum_incoming)).filter(
        and_(
            Transaction.contr_account_name == 'Торговая выручка',
            Transaction.date_typed >= start_date.date(),
            Transaction.date_typed <= end_date.date()
        )
    )
    if organization_id:
        sum_incoming = sum_incoming.filter(Transaction.organization_id == organization_id)
    sum_incoming = float(sum_incoming.scalar() or 0)
    
    sum_outgoing = db.query(func.sum(Transaction.sum_outgoing)).filter(
        and_(
            Transaction.contr_account_name == 'Торговая выручка',
            Transaction.date_typed >= start_date.date(),
            Transaction.date_typed <= end_date.date()
        )
    )
    if organization_id:
        sum_outgoing = sum_outgoing.filter(Transaction.organization_id == organization_id)
    sum_outgoing = float(sum_outgoing.scalar() or 0)
    
    # Итогово = sum_incoming - sum_outgoing
    additional_revenue = round(sum_incoming - sum_outgoing, 2)
    
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
def get_sales_dynamics(
    db: Session,
    date: str,
    days: int = 7,
    organization_id: Optional[int] = None,
) -> SalesDynamicsResponse:
    """
    Получить динамику продаж за последние N дней
    
    Args:
        db: сессия БД
        days: количество дней для анализа (по умолчанию 7)
        organization_id: ID организации (фильтр)
    
    Returns:
        Динамика продаж с разбивкой по дням
    """
    from datetime import datetime, timedelta
    from models.sales import Sales
    
    # Определяем период: сегодня минус N дней
    end_date = datetime.now().date()
    if date:
        end_date = parse_date(date).date()
    start_date = end_date - timedelta(days=days - 1)  # -1 чтобы включить сегодня
    
    daily_data = []
    total_revenue = 0
    total_checks = 0
    
    # Проходим по каждому дню
    for i in range(days):
        current_date = start_date + timedelta(days=i)
        
        # Получаем данные за текущий день из Sales
        query = db.query(
            func.sum(Sales.dish_discount_sum_int).label("revenue"),
            func.count(func.distinct(Sales.order_id)).label("checks_count")
        ).filter(
            and_(
                Sales.open_date_typed == current_date,
                Sales.cashier != 'Удаление позиций',
                Sales.order_deleted != 'DELETED',
                Sales.dish_discount_sum_int.isnot(None),
                Sales.dish_discount_sum_int > 0
            )
        )
        
        if organization_id:
            query = query.filter(Sales.organization_id == organization_id)
        
        result = query.first()
        
        day_revenue = float(result.revenue or 0)
        day_checks = int(result.checks_count or 0)
        day_average_check = day_revenue / day_checks if day_checks > 0 else 0
        
        daily_data.append(
            DailySalesData(
                date=current_date.strftime("%d.%m.%Y"),
                revenue=day_revenue,
                checks_count=day_checks,
                average_check=day_average_check
            )
        )
        
        total_revenue += day_revenue
        total_checks += day_checks
    
    # Дополнительная выручка за весь период
    # Суммируем отдельно sum_incoming и sum_outgoing
    sum_incoming = db.query(func.sum(Transaction.sum_incoming)).filter(
        and_(
            Transaction.contr_account_name == 'Торговая выручка',
            Transaction.date_typed >= start_date.date(),
            Transaction.date_typed <= end_date.date()
        )
    )
    if organization_id:
        sum_incoming = sum_incoming.filter(Transaction.organization_id == organization_id)
    sum_incoming = float(sum_incoming.scalar() or 0)
    
    sum_outgoing = db.query(func.sum(Transaction.sum_outgoing)).filter(
        and_(
            Transaction.contr_account_name == 'Торговая выручка',
            Transaction.date_typed >= start_date.date(),
            Transaction.date_typed <= end_date.date()
        )
    )
    if organization_id:
        sum_outgoing = sum_outgoing.filter(Transaction.organization_id == organization_id)
    sum_outgoing = float(sum_outgoing.scalar() or 0)
    
    # Итогово = sum_incoming - sum_outgoing
    additional_revenue = round(sum_incoming - sum_outgoing, 2)
    
    total_revenue += additional_revenue
    
    overall_average_check = total_revenue / total_checks if total_checks > 0 else 0
    
    return SalesDynamicsResponse(
        success=True,
        message=f"Динамика продаж за последние {days} дней",
        total_revenue=total_revenue,
        total_checks=total_checks,
        overall_average_check=overall_average_check,
        daily_data=daily_data
    )

