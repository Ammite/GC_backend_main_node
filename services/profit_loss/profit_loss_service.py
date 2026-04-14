from sqlalchemy.orm import Session
from typing import Optional, Dict
import asyncio
from utils.async_db_executor import gather_db_queries
from schemas.profit_loss import (
    ProfitLossResponse,
    RevenueByCategory,
    ExpenseByType,
    ProfitLossDetailResponse,
    ProfitLossDetailByOrg,
)
from services.transactions_and_statistics.statistics_service import (
    parse_date,
    get_period_dates,
    resolve_date_range,
    get_revenue_by_category,
    get_bank_commission_total,
    get_expenses_from_transactions,
    get_cost_of_goods_from_sales
)
from services.transactions_and_statistics.daily_aggregates_service import (
    get_daily_metric_sum,
    get_daily_metric_by_subkey,
)
from models.organization import Organization
from models import Transaction, Account
from sqlalchemy import func, and_
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Маппинг: название категории дохода -> metric_key для DailyAggregate
REVENUE_CATEGORY_TO_METRIC_KEY = {
    "Кухня": "revenue_kitchen",
    "Бар": "revenue_bar",
    "Прочее": "revenue_other",
    "Наценка (обслуживание)": "revenue_increase_total",
    "Дополнительная выручка": "revenue_additional",
    "Фабрика": "factory_revenue",
}


async def get_profit_loss_report(
    db: Session,
    date: Optional[str] = None,
    period: Optional[str] = "day",
    organization_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> ProfitLossResponse:
    """
    Получить отчет о прибылях и убытках (Profit & Loss)

    Args:
        db: сессия БД
        date: дата в формате "DD.MM.YYYY"
        period: период аналитики ("day" | "week" | "month")
        organization_id: ID организации (фильтр)
        date_from: начало периода DD.MM.YYYY (приоритет над date+period)
        date_to: конец периода DD.MM.YYYY (приоритет над date+period)

    Returns:
        Отчет о прибылях и убытках
    """
    # Парсим дату и определяем период
    start_date, end_date, _, _ = resolve_date_range(date_from, date_to, date, period)
    
    logger.info(f"🔥 Generating P&L report for period {start_date} - {end_date}")
    logger.info(f"   📅 Input date: {date}")
    logger.info(f"   📆 Period: {start_date} - {end_date}")
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
    
    revenue_by_category = []
    for category, amount in revenue_data.items():
        if category in ("total", "Фабрика") or amount <= 0:
            continue
        metric_key = REVENUE_CATEGORY_TO_METRIC_KEY.get(category)
        if metric_key is None:
            # Динамические категории из OTHER_INCOME
            metric_key = f"revenue_other_income:{category}"
        revenue_by_category.append(
            RevenueByCategory(id=metric_key, category=category, amount=amount)
        )
    
    logger.info(f"Total revenue: {total_revenue}")
    
    total_expenses = expenses_result["expenses_amount"]
    
    expenses_by_type = [
        ExpenseByType(
            id=f"expense_account:{expense_group['transaction_name']}",
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
            id="cost_goods_total",
            transaction_type="EXPENSES",
            transaction_name="Итого себестоимость",
            amount=cost_of_goods
        )
    )
    for category, amount in cost_of_goods_dict.items():
        if category != "total":
            expenses_by_type.append(
                ExpenseByType(
                    id=f"cost_goods_category:{category}",
                    transaction_type="EXPENSES",
                    transaction_name=f"Себестоимость: {category}",
                    amount=amount
                )
            )
    
    logger.info(f"📞 Calling get_bank_commission_total with: start={start_date}, end={end_date}, org={organization_id}")
    logger.info(f"💰 Bank commission returned: {bank_commission}")
    
    expenses_by_type.append(
        ExpenseByType(
            id="bank_commission",
            transaction_type="EXPENSES",
            transaction_name="Комиссия банков (в)",
            amount=bank_commission
        )
    )
    
    logger.info(f"Bank commission: {bank_commission}")
    
    # 5. Прочие доходы (OTHER_INCOME) — не входят в выручку, но участвуют в чистой прибыли
    start_date_only = start_date.date() if hasattr(start_date, 'date') else start_date
    end_date_only = end_date.date() if hasattr(end_date, 'date') else end_date
    other_income = get_daily_metric_sum(db, "revenue_other_income_total", start_date_only, end_date_only, organization_id)

    # 6. Рассчитываем прибыль
    # Чистая прибыль = Выручка - Себестоимость - Расходы (вкл. прочие расходы) + Прочие доходы
    gross_profit = total_revenue - total_expenses - cost_of_goods + other_income

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


def get_profit_loss_detail(
    db: Session,
    item_id: str,
    item_type: str,
    date_from: str,
    date_to: str,
) -> ProfitLossDetailResponse:
    """
    Детализация статьи P&L по организациям (точкам).

    Args:
        item_id: ID статьи из profit-loss (например "revenue_kitchen", "expense_account:Аренда")
        item_type: "revenue" или "expense"
        date_from: начало периода DD.MM.YYYY
        date_to: конец периода DD.MM.YYYY
    """
    start_date = datetime.strptime(date_from, "%d.%m.%Y").date()
    end_date = datetime.strptime(date_to, "%d.%m.%Y").date()

    organizations = (
        db.query(Organization)
        .filter(Organization.is_active == True)  # noqa: E712
        .all()
    )

    by_organization = []
    total = 0.0
    item_name = item_id

    if item_type == "revenue":
        # Определяем metric_key и имя
        if item_id.startswith("revenue_other_income:"):
            # Динамическая категория OTHER_INCOME
            account_name = item_id.split(":", 1)[1]
            item_name = account_name
            for org in organizations:
                subkeys = get_daily_metric_by_subkey(
                    db, "revenue_other_income", start_date, end_date, org.id
                )
                amount = round(float(subkeys.get(account_name, 0)), 2)
                if amount != 0:
                    by_organization.append(
                        ProfitLossDetailByOrg(
                            organization_id=org.id,
                            organization_name=org.name,
                            amount=amount,
                        )
                    )
                    total += amount
        else:
            # Стандартные категории дохода
            reverse_map = {v: k for k, v in REVENUE_CATEGORY_TO_METRIC_KEY.items()}
            item_name = reverse_map.get(item_id, item_id)
            for org in organizations:
                amount = get_daily_metric_sum(
                    db, item_id, start_date, end_date, org.id
                )
                if amount != 0:
                    by_organization.append(
                        ProfitLossDetailByOrg(
                            organization_id=org.id,
                            organization_name=org.name,
                            amount=amount,
                        )
                    )
                    total += amount

    elif item_type == "expense":
        if item_id == "bank_commission":
            item_name = "Комиссия банков (в)"
            for org in organizations:
                amount = get_daily_metric_sum(
                    db, "bank_commission_total", start_date, end_date, org.id
                )
                if amount != 0:
                    by_organization.append(
                        ProfitLossDetailByOrg(
                            organization_id=org.id,
                            organization_name=org.name,
                            amount=amount,
                        )
                    )
                    total += amount

        elif item_id == "cost_goods_total":
            item_name = "Итого себестоимость"
            for org in organizations:
                amount = get_daily_metric_sum(
                    db, "cost_goods_total", start_date, end_date, org.id
                )
                if amount != 0:
                    by_organization.append(
                        ProfitLossDetailByOrg(
                            organization_id=org.id,
                            organization_name=org.name,
                            amount=amount,
                        )
                    )
                    total += amount

        elif item_id.startswith("cost_goods_category:"):
            category = item_id.split(":", 1)[1]
            item_name = f"Себестоимость: {category}"
            for org in organizations:
                subkeys = get_daily_metric_by_subkey(
                    db, "cost_goods_category", start_date, end_date, org.id
                )
                amount = round(float(subkeys.get(category, 0)), 2)
                if amount != 0:
                    by_organization.append(
                        ProfitLossDetailByOrg(
                            organization_id=org.id,
                            organization_name=org.name,
                            amount=amount,
                        )
                    )
                    total += amount

        elif item_id.startswith("expense_account:"):
            account_name = item_id.split(":", 1)[1]
            item_name = account_name
            # Запрос транзакций по account_name с группировкой по organization_id
            rows = (
                db.query(
                    Transaction.organization_id,
                    func.sum(func.abs(func.coalesce(Transaction.sum_resigned, 0))).label("total"),
                )
                .filter(
                    Transaction.account_name == account_name,
                    Transaction.date_typed >= start_date,
                    Transaction.date_typed <= end_date,
                    Transaction.is_active == True,  # noqa: E712
                )
                .group_by(Transaction.organization_id)
                .all()
            )
            org_map = {org.id: org.name for org in organizations}
            for row in rows:
                amount = round(float(row.total or 0), 2)
                if amount != 0:
                    by_organization.append(
                        ProfitLossDetailByOrg(
                            organization_id=row.organization_id,
                            organization_name=org_map.get(row.organization_id, "Неизвестно"),
                            amount=amount,
                        )
                    )
                    total += amount

    total = round(total, 2)

    return ProfitLossDetailResponse(
        success=True,
        item_id=item_id,
        item_type=item_type,
        item_name=item_name,
        total=total,
        by_organization=by_organization,
    )

