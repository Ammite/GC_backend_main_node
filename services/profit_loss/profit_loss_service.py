from sqlalchemy.orm import Session
from typing import Optional
from schemas.profit_loss import (
    ProfitLossResponse,
    RevenueByCategory,
    ExpenseByType
)
from services.transactions_and_statistics.statistics_service import (
    parse_date,
    get_period_dates,
    get_revenue_by_category,
    get_bank_commission_total,
    get_expenses_from_transactions
)
import logging

logger = logging.getLogger(__name__)


def get_profit_loss_report(
    db: Session,
    date: Optional[str] = None,
    period: Optional[str] = "day",
    organization_id: Optional[int] = None,
) -> ProfitLossResponse:
    """
    Получить отчет о прибылях и убытках (Profit & Loss)
    
    Args:
        db: сессия БД
        date: дата в формате "DD.MM.YYYY"
        period: период аналитики ("day" | "week" | "month")
        organization_id: ID организации (фильтр)
    
    Returns:
        Отчет о прибылях и убытках
    """
    # Парсим дату и определяем период
    target_date = parse_date(date)
    start_date, end_date, _, _ = get_period_dates(target_date, period)
    
    logger.info(f"🔥 Generating P&L report for period {start_date} - {end_date}")
    logger.info(f"   📅 Input date: {date}")
    logger.info(f"   📆 Target date: {target_date}")
    logger.info(f"   ⏱️ Period: {period}")
    logger.info(f"   🏢 Organization ID: {organization_id}")
    
    # 1. Получаем доходы по категориям (из Sales, поле dish_discount_sum_int)
    revenue_data = get_revenue_by_category(db, start_date, end_date, organization_id)
    total_revenue = revenue_data["total"]
    
    revenue_by_category = [
        RevenueByCategory(category=category, amount=amount)
        for category, amount in revenue_data.items()
        if category != "total" and amount > 0
    ]
    
    logger.info(f"Total revenue: {total_revenue}")
    
    # 2. Получаем расходы (из Transactions)
    expense_types = ['EXPENSES', 'EQUITY']
    expenses_result = get_expenses_from_transactions(db, start_date, end_date, organization_id, expense_types)
    total_expenses = expenses_result["expenses_amount"]
    
    expenses_by_type = [
        ExpenseByType(
            transaction_type=expense_group["transaction_type"],
            transaction_name=expense_group["transaction_name"],
            amount=expense_group["transaction_amount"]
        )
        for expense_group in expenses_result["data"]
    ]
    
    logger.info(f"Total expenses: {total_expenses}")
    
    # 3. Получаем комиссии банка (из d_order.bank_commission)
    logger.info(f"📞 Calling get_bank_commission_total with: start={start_date}, end={end_date}, org={organization_id}")
    bank_commission = get_bank_commission_total(db, start_date, end_date, organization_id)
    logger.info(f"💰 Bank commission returned: {bank_commission}")
    
    expenses_by_type.append(
        ExpenseByType(
            transaction_type="EXPENSES",
            transaction_name="Комиссия банков (в)",
            amount=bank_commission
        )
    )
    
    logger.info(f"Bank commission: {bank_commission}")
    
    # 4. Рассчитываем прибыль
    # Прибыль = Доход - Расходы - Комиссия банков
    gross_profit = total_revenue - total_expenses - bank_commission
    
    # Маржа прибыли в процентах
    profit_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    logger.info(f"Gross profit: {gross_profit}, Profit margin: {profit_margin}%")
    
    return ProfitLossResponse(
        success=True,
        message=f"Отчет о прибылях и убытках за период {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
        total_revenue=total_revenue,
        revenue_by_category=revenue_by_category,
        total_expenses=total_expenses,
        expenses_by_type=expenses_by_type,
        bank_commission=bank_commission,
        gross_profit=gross_profit,
        profit_margin=round(profit_margin, 2)
    )

