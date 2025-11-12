from sqlalchemy.orm import Session
from typing import Optional
import asyncio
from utils.async_db_executor import gather_db_queries
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
    get_expenses_from_transactions,
    get_cost_of_goods_from_sales
)
import logging

logger = logging.getLogger(__name__)


async def get_profit_loss_report(
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
    
    # Параллельно получаем все данные
    revenue_data, expenses_result, cost_of_goods_dict, bank_commission = await gather_db_queries(
        lambda: get_revenue_by_category(db, start_date, end_date, organization_id),
        lambda: get_expenses_from_transactions(db, start_date, end_date, organization_id, ['EXPENSES']),
        lambda: get_cost_of_goods_from_sales(db, start_date, end_date, organization_id),
        lambda: get_bank_commission_total(db, start_date, end_date, organization_id)
    )
    
    total_revenue = revenue_data["total"]
    
    revenue_by_category = [
        RevenueByCategory(category=category, amount=amount)
        for category, amount in revenue_data.items()
        if category != "total" and amount > 0
    ]
    
    logger.info(f"Total revenue: {total_revenue}")
    
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
    
    cost_of_goods = cost_of_goods_dict.get("total", 0.0)
    logger.info(f"📦 Cost of goods: {cost_of_goods} (by categories: {cost_of_goods_dict})")
    
    expenses_by_type.append(
        ExpenseByType(
            transaction_type="EXPENSES",
            transaction_name="Итого себестоимость",
            amount=cost_of_goods
        )
    )
    for category, amount in cost_of_goods_dict.items():
        if category != "total":
            expenses_by_type.append(
                ExpenseByType(
                    transaction_type="EXPENSES",
                    transaction_name=f"Себестоимость: {category}",
                    amount=amount
                )
            )
    
    logger.info(f"📞 Calling get_bank_commission_total with: start={start_date}, end={end_date}, org={organization_id}")
    logger.info(f"💰 Bank commission returned: {bank_commission}")
    
    expenses_by_type.append(
        ExpenseByType(
            transaction_type="EXPENSES",
            transaction_name="Комиссия банков (в)",
            amount=bank_commission
        )
    )
    
    logger.info(f"Bank commission: {bank_commission}")
    
    # 5. Рассчитываем прибыль
    # Прибыль = Доход - Расходы - Себестоимость - Комиссия банков
    gross_profit = total_revenue - total_expenses - cost_of_goods
    
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

