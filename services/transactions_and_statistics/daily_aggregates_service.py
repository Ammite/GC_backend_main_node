"""
Сервис для работы с дневными агрегированными метриками.

Задачи:
- Пересчёт дневных метрик при синхронизации sales/transactions.
- Чтение предагрегированных значений для statistics_service и других сервисов.
"""

from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, distinct

from models import Sales, Transaction, Account, BankCommission, DOrder, WarehouseDocument, WarehouseDocumentItem, Expense, Employees
from models.daily_analytics import DailyAnalytics
from models.daily_employee_analytics import DailyEmployeeAnalytics
from utils.performance_logger import log_execution_time

logger = logging.getLogger(__name__)


# ==================== УТИЛИТЫ ====================

def _normalize_date(value: datetime | date) -> date:
    """Привести datetime/date к дате без времени."""
    if isinstance(value, datetime):
        return value.date()
    return value


def _upsert_daily_metric(
    db: Session,
    metric_date: date,
    metric_key: str,
    value: float,
    organization_id: Optional[int] = None,
    metric_subkey: Optional[str] = None,
) -> None:
    """
    Обновить или вставить дневную метрику.
    """
    metric = (
        db.query(DailyAnalytics)
        .filter(
            DailyAnalytics.date == metric_date,
            DailyAnalytics.organization_id == organization_id,
            DailyAnalytics.metric_key == metric_key,
            DailyAnalytics.metric_subkey == metric_subkey,
        )
        .first()
    )

    if metric:
        metric.value = round(float(value or 0), 2)
        metric.updated_at = datetime.now()
    else:
        metric = DailyAnalytics(
            date=metric_date,
            organization_id=organization_id,
            metric_key=metric_key,
            metric_subkey=metric_subkey,
            value=round(float(value or 0), 2),
        )
        db.add(metric)


# ==================== ПЕРЕСЧЁТ МЕТРИК ====================

def recalculate_daily_metrics_for_date(
    db: Session,
    metric_date: date | datetime,
    organization_id: Optional[int] = None,
) -> Dict[str, float]:
    """
    Пересчитать дневные метрики за конкретную дату.

    Вызывает агрегирующие запросы к сырым таблицам и сохраняет результат в daily_analytics.
    Возвращает словарь с основными метриками для отладки.
    """
    metric_date = _normalize_date(metric_date)
    next_date = metric_date + timedelta(days=1)

    results: Dict[str, float] = {}

    # --- Базовые фильтры по датам ---
    sales_date_filter = and_(
        Sales.open_date_typed >= metric_date,
        Sales.open_date_typed < next_date,
        Sales.cashier != "Удаление позиций",
        Sales.order_deleted != "DELETED",
    )

    trx_date_filter = and_(
        Transaction.date_typed >= metric_date,
        Transaction.date_typed < next_date,
        Transaction.is_active == True,  # noqa: E712
    )

    # Фильтр по организации для Sales/Transaction/DOrder/BankCommission
    def _with_org_sales(query):
        if organization_id:
            return query.filter(Sales.organization_id == organization_id)
        return query

    def _with_org_trx(query):
        if organization_id:
            return query.filter(Transaction.organization_id == organization_id)
        return query

    def _with_org_dorder(query):
        if organization_id:
            return query.filter(DOrder.organization_id == organization_id)
        return query

    def _with_org_bank_commission(query):
        if organization_id:
            return query.filter(BankCommission.organization_id == organization_id)
        return query

    def _with_org_warehouse(query):
        if organization_id:
            return query.filter(WarehouseDocument.organization_id == organization_id)
        return query

    def _with_org_expense(query):
        if organization_id:
            return query.filter(Expense.organization_id == organization_id)
        return query

    # ---------- 1. Возвраты из Sales ----------
    returns_query = _with_org_sales(
        db.query(func.sum(Sales.dish_sum_int))
        .filter(
            Sales.deleted_with_writeoff == "DELETED_WITHOUT_WRITEOFF",
            Sales.cashier != "Удаление позиций",
            Sales.order_deleted != "DELETED",
            Sales.open_date_typed >= metric_date,
            Sales.open_date_typed < next_date,
        )
    )
    returns_sum = float(returns_query.scalar() or 0)
    results["returns_sum"] = round(returns_sum, 2)
    _upsert_daily_metric(db, metric_date, "returns_sum", returns_sum, organization_id)

    # ---------- 2. Списания из Sales ----------
    writeoffs_query = _with_org_sales(
        db.query(func.sum(Sales.dish_discount_sum_int)).filter(
            Sales.deleted_with_writeoff == "DELETED_WITH_WRITEOFF",
            Sales.cashier != "Удаление позиций",
            Sales.open_date_typed >= metric_date,
            Sales.open_date_typed < next_date,
        )
    )
    writeoffs_sum = float(writeoffs_query.scalar() or 0)
    results["writeoffs_sum"] = round(writeoffs_sum, 2)
    _upsert_daily_metric(db, metric_date, "writeoffs_sum", writeoffs_sum, organization_id)

    # ---------- 3. Себестоимость проданных товаров (по категориям) ----------
    # Берём ВСЕ аккаунты с типом COST_OF_GOODS_SOLD (включая Дегустацию, Бракераж, Инвентаризацию и т.д.)
    cost_accounts = (
        db.query(Account)
        .filter(
            and_(
                Account.type == "COST_OF_GOODS_SOLD",
                Account.deleted == False,  # noqa: E712
            )
        )
        .all()
    )
    account_ids = [a.iiko_id for a in cost_accounts if a.iiko_id]
    if account_ids:
        cost_query = db.query(
            Transaction.account_hierarchy_second,
            func.sum(func.coalesce(Transaction.sum_resigned, 0)).label("total_cost"),
        ).filter(
            and_(
                Transaction.account_id.in_(account_ids),
                Transaction.date_typed >= metric_date,
                Transaction.date_typed < next_date,
                Transaction.is_active == True,  # noqa: E712
                Transaction.sum_resigned.isnot(None),
            )
        )
        cost_query = _with_org_trx(cost_query)
        cost_rows = cost_query.group_by(Transaction.account_hierarchy_second).all()

        total_cost = 0.0
        for row in cost_rows:
            category = row.account_hierarchy_second or "Без категории"
            amount = float(row.total_cost or 0)
            total_cost += amount
            _upsert_daily_metric(
                db,
                metric_date,
                "cost_goods_category",
                amount,
                organization_id,
                metric_subkey=category,
            )

        results["cost_goods_total"] = round(total_cost, 2)
        _upsert_daily_metric(
            db, metric_date, "cost_goods_total", total_cost, organization_id
        )
    else:
        results["cost_goods_total"] = 0.0
        _upsert_daily_metric(
            db, metric_date, "cost_goods_total", 0.0, organization_id
        )

    # ---------- 4. Выручка фабрики (по organization_id фабрики) ----------
    factory_org_ids = [1, 21]  # ID организаций-фабрик
    factory_query = db.query(func.sum(Transaction.sum_resigned)).filter(
        and_(
            Transaction.organization_id.in_(factory_org_ids),
            Transaction.date_typed >= metric_date,
            Transaction.date_typed < next_date,
            Transaction.sum_resigned != 0,
            Transaction.is_active == True,  # noqa: E712
        )
    )
    factory_revenue = float(factory_query.scalar() or 0)
    results["factory_revenue"] = round(factory_revenue, 2)
    _upsert_daily_metric(
        db, metric_date, "factory_revenue", factory_revenue, organization_id
    )

    # ---------- 5. Выручка по категориям (кухня / бар / прочее) ----------
    base_filter = sales_date_filter

    # Кухня
    kitchen_query = db.query(
        func.sum(Sales.dish_sum_int).label("sum_base"),
        func.sum(Sales.discount_sum).label("sum_discount"),
        func.sum(Sales.increase_sum).label("sum_increase"),
    ).filter(
        and_(
            base_filter,
            func.lower(Sales.cooking_place_type).contains("кухня"),
            Sales.dish_sum_int.isnot(None),
        )
    )
    kitchen_query = _with_org_sales(kitchen_query)
    kitchen_data = kitchen_query.first()
    kitchen_base = float(kitchen_data.sum_base or 0)
    kitchen_discount = float(kitchen_data.sum_discount or 0)
    kitchen_increase = float(kitchen_data.sum_increase or 0)
    kitchen_revenue = kitchen_base - kitchen_discount + kitchen_increase

    _upsert_daily_metric(
        db, metric_date, "revenue_kitchen", kitchen_base, organization_id
    )

    # Бар
    bar_query = db.query(
        func.sum(Sales.dish_sum_int).label("sum_base"),
        func.sum(Sales.discount_sum).label("sum_discount"),
        func.sum(Sales.increase_sum).label("sum_increase"),
    ).filter(
        and_(
            base_filter,
            func.lower(Sales.cooking_place_type).not_like("%кухня%"),
            Sales.cooking_place_type.isnot(None),
            Sales.dish_sum_int.isnot(None),
        )
    )
    bar_query = _with_org_sales(bar_query)
    bar_data = bar_query.first()
    bar_base = float(bar_data.sum_base or 0)
    bar_discount = float(bar_data.sum_discount or 0)
    bar_increase = float(bar_data.sum_increase or 0)
    bar_revenue = bar_base - bar_discount + bar_increase

    _upsert_daily_metric(db, metric_date, "revenue_bar", bar_base, organization_id)

    # Прочее (без категории)
    other_query = db.query(
        func.sum(Sales.dish_sum_int).label("sum_base"),
        func.sum(Sales.discount_sum).label("sum_discount"),
        func.sum(Sales.increase_sum).label("sum_increase"),
    ).filter(
        and_(
            base_filter,
            Sales.cooking_place_type.is_(None),
            Sales.dish_sum_int.isnot(None),
        )
    )
    other_query = _with_org_sales(other_query)
    other_data = other_query.first()
    other_base = float(other_data.sum_base or 0)
    other_discount = float(other_data.sum_discount or 0)
    other_increase = float(other_data.sum_increase or 0)
    other_revenue = other_base - other_discount + other_increase

    _upsert_daily_metric(
        db, metric_date, "revenue_other", other_revenue, organization_id
    )

    total_increase = kitchen_increase + bar_increase + other_increase
    _upsert_daily_metric(
        db, metric_date, "revenue_increase_total", total_increase, organization_id
    )

    # Общая выручка по sales (dish_discount_sum_int)
    overall_query = db.query(
        func.sum(Sales.dish_discount_sum_int).label("sum_total")
    ).filter(base_filter)
    overall_query = _with_org_sales(overall_query)
    overall_data = overall_query.first()
    overall_revenue = float(overall_data.sum_total or 0)

    # Дополнительная выручка (Торговая выручка)
    sum_incoming_q = db.query(func.sum(Transaction.sum_incoming)).filter(
        and_(
            Transaction.contr_account_name == "Торговая выручка",
            Transaction.date_typed >= metric_date,
            Transaction.date_typed < next_date,
        )
    )
    sum_incoming_q = _with_org_trx(sum_incoming_q)
    sum_incoming = float(sum_incoming_q.scalar() or 0)

    sum_outgoing_q = db.query(func.sum(Transaction.sum_outgoing)).filter(
        and_(
            Transaction.contr_account_name == "Торговая выручка",
            Transaction.date_typed >= metric_date,
            Transaction.date_typed < next_date,
        )
    )
    sum_outgoing_q = _with_org_trx(sum_outgoing_q)
    sum_outgoing = float(sum_outgoing_q.scalar() or 0)
    additional_revenue = sum_incoming - sum_outgoing
    _upsert_daily_metric(
        db, metric_date, "revenue_additional", additional_revenue, organization_id
    )

    # Дополнительные доходы (OTHER_INCOME)
    other_income_accounts = (
        db.query(Account)
        .filter(
            and_(
                Account.type == "OTHER_INCOME",
                Account.deleted == False,  # noqa: E712
            )
        )
        .all()
    )
    other_income_ids = [a.iiko_id for a in other_income_accounts if a.iiko_id]
    total_other_income = 0.0

    if other_income_ids:
        other_income_query = db.query(
            Transaction.account_name,
            func.sum(func.coalesce(Transaction.sum_resigned, 0)).label("total_income"),
        ).filter(
            and_(
                Transaction.account_id.in_(other_income_ids),
                Transaction.date_typed >= metric_date,
                Transaction.date_typed < next_date,
                Transaction.is_active == True,  # noqa: E712
            )
        )
        other_income_query = _with_org_trx(other_income_query)
        income_rows = other_income_query.group_by(Transaction.account_name).all()

        for row in income_rows:
            account_name = row.account_name or "Прочие доходы"
            income = float(row.total_income or 0)
            total_other_income += income if income != 0 else 0
            _upsert_daily_metric(
                db,
                metric_date,
                "revenue_other_income",
                income,
                organization_id,
                metric_subkey=account_name,
            )

    _upsert_daily_metric(
        db,
        metric_date,
        "revenue_other_income_total",
        total_other_income,
        organization_id,
    )

    # Итоговая выручка (без фабрики и без прочих доходов — они показываются отдельно)
    total_revenue = overall_revenue + additional_revenue
    results["revenue_total"] = round(total_revenue, 2)
    _upsert_daily_metric(
        db, metric_date, "revenue_total", total_revenue, organization_id
    )

    # ---------- 6. Банковская комиссия ----------
    commission_query = db.query(func.sum(BankCommission.bank_commission)).filter(
        and_(
            BankCommission.time_transaction >= datetime.combine(
                metric_date, datetime.min.time()
            ),
            BankCommission.time_transaction < datetime.combine(
                next_date, datetime.min.time()
            ),
            BankCommission.bank_commission.isnot(None),
        )
    )
    commission_query = _with_org_bank_commission(commission_query)
    commission_value = float(commission_query.scalar() or 0)
    commission_value = abs(commission_value)
    results["bank_commission_total"] = round(commission_value, 2)
    _upsert_daily_metric(
        db, metric_date, "bank_commission_total", commission_value, organization_id
    )

    # ---------- 7. Скидки из DOrder ----------
    discount_query = db.query(func.sum(DOrder.discount)).filter(
        and_(
            DOrder.time_order >= datetime.combine(metric_date, datetime.min.time()),
            DOrder.time_order < datetime.combine(next_date, datetime.min.time()),
            DOrder.deleted == False,  # noqa: E712
        )
    )
    discount_query = _with_org_dorder(discount_query)
    total_discount = float(discount_query.scalar() or 0)
    results["discount_total"] = round(total_discount, 2)
    _upsert_daily_metric(
        db, metric_date, "discount_total", total_discount, organization_id
    )

    # ---------- 7.1. Количество чеков (из Sales по уникальным order_id) ----------
    orders_count_query = db.query(func.count(func.distinct(Sales.order_id))).filter(
        and_(
            sales_date_filter,
            Sales.order_id.isnot(None),
        )
    )
    orders_count_query = _with_org_sales(orders_count_query)
    orders_count = int(orders_count_query.scalar() or 0)
    results["orders_count"] = orders_count
    _upsert_daily_metric(
        db, metric_date, "orders_count", float(orders_count), organization_id
    )

    # ---------- 7.2. Средний чек (из revenue_total / orders_count) ----------
    # Средний чек рассчитывается как общая выручка (revenue_total) деленная на количество уникальных чеков (orders_count)
    # revenue_total включает выручку из Sales + дополнительную выручку + прочие доходы (без фабрики)
    average_check = round(total_revenue / orders_count, 2) if orders_count > 0 else 0.0
    results["average_check"] = average_check
    _upsert_daily_metric(
        db, metric_date, "average_check", average_check, organization_id
    )

    # ---------- 8. Расходы из Transaction ----------
    accounts_expense = (
        db.query(Account)
        .filter(
            Account.type.in_(["EXPENSES"]),
            Account.deleted == False,  # noqa: E712
        )
        .all()
    )
    expense_account_ids = [a.iiko_id for a in accounts_expense if a.name != "Зарплата"]
    total_expenses = 0.0

    if expense_account_ids:
        trx_q = db.query(Transaction).filter(
            Transaction.account_id.in_(expense_account_ids),
            trx_date_filter,
        )
        trx_q = _with_org_trx(trx_q)
        transactions = trx_q.all()

        salary_q = db.query(Transaction).filter(
            Transaction.account_id == "13000ead-41f0-d569-d85c-704242cc91f5",
            Transaction.date_typed >= metric_date,
            Transaction.date_typed < next_date,
            Transaction.contr_account_name == "Зарплата",
        )
        salary_q = _with_org_trx(salary_q)
        salary_transactions = salary_q.all()
        transactions.extend(salary_transactions)

        total_salary = abs(
            sum(float(t.sum_resigned or 0) for t in salary_transactions)
        )

        total_expenses = abs(
            sum(
                float(t.sum_resigned or 0)
                for t in transactions
                if t.contr_account_name != "Зарплата"
                and t.account_id != "e0c6f1d8-4483-a946-0734-2585ed233bc4"
            )
        )
        total_expenses += total_salary

    # ---------- 8b. Прочие расходы (OTHER_EXPENSES) ----------
    other_expense_accounts = (
        db.query(Account)
        .filter(
            Account.type == "OTHER_EXPENSES",
            Account.deleted == False,  # noqa: E712
        )
        .all()
    )
    other_expense_ids = [a.iiko_id for a in other_expense_accounts if a.iiko_id]
    other_expenses_total = 0.0

    if other_expense_ids:
        other_exp_q = db.query(
            func.sum(func.abs(Transaction.sum_resigned))
        ).filter(
            and_(
                Transaction.account_id.in_(other_expense_ids),
                trx_date_filter,
            )
        )
        other_exp_q = _with_org_trx(other_exp_q)
        other_expenses_total = float(other_exp_q.scalar() or 0)

    total_expenses += other_expenses_total

    results["other_expenses_total"] = round(other_expenses_total, 2)
    _upsert_daily_metric(
        db, metric_date, "other_expenses_total", other_expenses_total, organization_id
    )

    results["expenses_total"] = round(total_expenses, 2)
    _upsert_daily_metric(
        db, metric_date, "expenses_total", total_expenses, organization_id
    )

    # ---------- Складские документы: Поступления ----------
    warehouse_receipts_date_filter = and_(
        WarehouseDocument.date >= metric_date,
        WarehouseDocument.date < next_date,
        WarehouseDocument.document_type == "RECEIPT",
    )
    
    # Суммируем суммы позиций документов поступлений
    receipts_query = (
        db.query(func.sum(WarehouseDocumentItem.amount))
        .join(WarehouseDocument, WarehouseDocumentItem.document_id == WarehouseDocument.id)
        .filter(warehouse_receipts_date_filter)
    )
    if organization_id:
        receipts_query = receipts_query.filter(WarehouseDocument.organization_id == organization_id)
    
    receipts_total = float(receipts_query.scalar() or 0)
    
    results["warehouse_receipts_total"] = round(receipts_total, 2)
    _upsert_daily_metric(
        db, metric_date, "warehouse_receipts_total", receipts_total, organization_id
    )

    # ---------- Складские документы: Списания ----------
    warehouse_writeoffs_date_filter = and_(
        WarehouseDocument.date >= metric_date,
        WarehouseDocument.date < next_date,
        WarehouseDocument.document_type == "WRITEOFF",
    )
    
    # Суммируем суммы позиций документов списаний
    writeoffs_query = (
        db.query(func.sum(WarehouseDocumentItem.amount))
        .join(WarehouseDocument, WarehouseDocumentItem.document_id == WarehouseDocument.id)
        .filter(warehouse_writeoffs_date_filter)
    )
    if organization_id:
        writeoffs_query = writeoffs_query.filter(WarehouseDocument.organization_id == organization_id)
    
    writeoffs_total = float(writeoffs_query.scalar() or 0)
    
    results["warehouse_writeoffs_total"] = round(writeoffs_total, 2)
    _upsert_daily_metric(
        db, metric_date, "warehouse_writeoffs_total", writeoffs_total, organization_id
    )

    # ---------- Расходы из модели Expense ----------
    # НЕ добавляем к expenses_total — эти суммы уже учтены через транзакции
    # (Expense модель хранит WRITEOFF/OUTGOING_INVOICE, которые дублируют данные из Transaction)
    expense_date_filter = and_(
        Expense.date >= metric_date,
        Expense.date < next_date,
    )

    expense_total_query = _with_org_expense(
        db.query(func.sum(Expense.amount)).filter(expense_date_filter)
    )
    expense_total = float(expense_total_query.scalar() or 0)

    # Сохраняем отдельную метрику для расходов из Expense (для справки)
    results["expense_model_total"] = round(expense_total, 2)
    _upsert_daily_metric(
        db, metric_date, "expense_model_total", expense_total, organization_id
    )

    db.commit()
    return results


# ==================== ЧТЕНИЕ МЕТРИК ====================

@log_execution_time
def get_daily_metric_sum(
    db: Session,
    metric_key: str,
    start_date: datetime | date,
    end_date: datetime | date,
    organization_id: Optional[int] = None,
) -> float:
    """
    Получить сумму значения метрики за период по ключу.
    """
    start = _normalize_date(start_date)
    end = _normalize_date(end_date)

    logger.debug(f"[PERF] get_daily_metric_sum -> querying metric_key={metric_key}, start={start}, end={end}, org_id={organization_id}")
    query = db.query(func.sum(DailyAnalytics.value)).filter(
        DailyAnalytics.metric_key == metric_key,
        DailyAnalytics.date >= start,
        DailyAnalytics.date <= end,
    )
    if organization_id:
        query = query.filter(DailyAnalytics.organization_id == organization_id)

    result = query.scalar()
    return round(float(result or 0), 2)


def get_daily_metric_by_subkey(
    db: Session,
    metric_key: str,
    start_date: datetime | date,
    end_date: datetime | date,
    organization_id: Optional[int] = None,
) -> Dict[str, float]:
    """
    Получить значения метрик по под-ключу (например, по категориям) за период.
    """
    start = _normalize_date(start_date)
    end = _normalize_date(end_date)

    query = db.query(
        DailyAnalytics.metric_subkey,
        func.sum(DailyAnalytics.value).label("total_value"),
    ).filter(
        DailyAnalytics.metric_key == metric_key,
        DailyAnalytics.date >= start,
        DailyAnalytics.date <= end,
    )
    if organization_id:
        query = query.filter(DailyAnalytics.organization_id == organization_id)

    query = query.group_by(DailyAnalytics.metric_subkey)
    rows = query.all()

    result: Dict[str, float] = {}
    for row in rows:
        key = row.metric_subkey or "Без категории"
        result[key] = round(float(row.total_value or 0), 2)
    return result


# ==================== АГРЕГАЦИЯ ДАННЫХ ПО СОТРУДНИКАМ ====================

def _upsert_daily_employee_metric(
    db: Session,
    metric_date: date,
    employee_id: int,
    revenue: float,
    checks_count: int,
    returns_count: int,
    average_check: float,
    organization_id: Optional[int] = None,
) -> None:
    """
    Обновить или вставить дневную метрику по сотруднику.
    """
    metric = (
        db.query(DailyEmployeeAnalytics)
        .filter(
            DailyEmployeeAnalytics.date == metric_date,
            DailyEmployeeAnalytics.employee_id == employee_id,
            DailyEmployeeAnalytics.organization_id == organization_id,
        )
        .first()
    )

    if metric:
        metric.revenue = round(float(revenue or 0), 2)
        metric.checks_count = int(checks_count or 0)
        metric.returns_count = int(returns_count or 0)
        metric.average_check = round(float(average_check or 0), 2)
        metric.updated_at = datetime.now()
    else:
        metric = DailyEmployeeAnalytics(
            date=metric_date,
            employee_id=employee_id,
            organization_id=organization_id,
            revenue=round(float(revenue or 0), 2),
            checks_count=int(checks_count or 0),
            returns_count=int(returns_count or 0),
            average_check=round(float(average_check or 0), 2),
        )
        db.add(metric)


@log_execution_time
def recalculate_daily_employee_metrics_for_date(
    db: Session,
    metric_date: date | datetime,
    organization_id: Optional[int] = None,
) -> Dict[str, int]:
    """
    Пересчитать дневные метрики по сотрудникам за конкретную дату.

    Агрегирует данные из таблицы Sales и сохраняет результат в daily_employee_analytics.
    Возвращает словарь с количеством обработанных сотрудников.
    """
    metric_date = _normalize_date(metric_date)
    next_date = metric_date + timedelta(days=1)

    # Базовые фильтры по датам
    base_filter = and_(
        Sales.open_date_typed >= metric_date,
        Sales.open_date_typed < next_date,
        Sales.cashier != "Удаление позиций",
        Sales.order_deleted != "DELETED",
        Sales.order_id.isnot(None),
        Sales.order_waiter_id.isnot(None),
    )

    # Фильтр по организации
    if organization_id:
        base_filter = and_(base_filter, Sales.organization_id == organization_id)

    # Получаем данные по каждому сотруднику: выручка и количество чеков
    employee_stats_query = (
        db.query(
            Employees.id.label("employee_id"),
            Employees.iiko_id.label("employee_iiko_id"),
            func.sum(Sales.dish_discount_sum_int).label("revenue"),
            func.count(distinct(Sales.order_id)).label("checks_count"),
        )
        .join(Employees, Sales.order_waiter_id == Employees.iiko_id)
        .filter(base_filter)
        .group_by(Employees.id, Employees.iiko_id)
    )

    employee_stats = employee_stats_query.all()

    # Для каждого сотрудника получаем количество возвратов
    processed_count = 0
    for stat in employee_stats:
        employee_id = stat.employee_id
        revenue = float(stat.revenue or 0)
        checks_count = int(stat.checks_count or 0)

        # Подсчет возвратов для этого сотрудника
        returns_query = (
            db.query(func.count(distinct(Sales.order_id)).label("returns_count"))
            .join(Employees, Sales.order_waiter_id == Employees.iiko_id)
            .filter(
                and_(
                    base_filter,
                    Employees.id == employee_id,
                    Sales.deleted_with_writeoff == 'DELETED_WITHOUT_WRITEOFF'
                )
            )
        )
        returns_count = int(returns_query.scalar() or 0)

        # Расчет среднего чека
        average_check = round(revenue / checks_count, 2) if checks_count > 0 else 0.0

        # Сохраняем метрику
        _upsert_daily_employee_metric(
            db=db,
            metric_date=metric_date,
            employee_id=employee_id,
            revenue=revenue,
            checks_count=checks_count,
            returns_count=returns_count,
            average_check=average_check,
            organization_id=organization_id,
        )
        processed_count += 1

    db.commit()
    return {"processed_employees": processed_count}


@log_execution_time
def get_employee_analytics_sum(
    db: Session,
    start_date: datetime | date,
    end_date: datetime | date,
    organization_id: Optional[int] = None,
    limit: int = 10,
) -> List[Tuple[str, str, int, float, int, int, float]]:
    """
    Получить агрегированные данные по сотрудникам за период из daily_employee_analytics.

    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        limit: количество результатов

    Returns:
        Список кортежей (имя, iiko_id, employee_id, выручка, количество_чеков, количество_возвратов, средний_чек)
    """
    start = _normalize_date(start_date)
    end = _normalize_date(end_date)

    logger.debug(
        f"[PERF] get_employee_analytics_sum -> querying start={start}, end={end}, org_id={organization_id}"
    )

    # Агрегируем данные из daily_employee_analytics
    query = (
        db.query(
            Employees.name.label("waiter_name"),
            Employees.iiko_id.label("waiter_id"),
            Employees.id.label("employee_id"),
            func.sum(DailyEmployeeAnalytics.revenue).label("total_revenue"),
            func.sum(DailyEmployeeAnalytics.checks_count).label("total_checks_count"),
            func.sum(DailyEmployeeAnalytics.returns_count).label("total_returns_count"),
        )
        .join(Employees, DailyEmployeeAnalytics.employee_id == Employees.id)
        .filter(
            DailyEmployeeAnalytics.date >= start,
            DailyEmployeeAnalytics.date <= end,
        )
    )

    if organization_id:
        query = query.filter(DailyEmployeeAnalytics.organization_id == organization_id)

    results = (
        query.group_by(Employees.name, Employees.iiko_id, Employees.id)
        .order_by(func.sum(DailyEmployeeAnalytics.revenue).desc())
        .limit(limit)
        .all()
    )

    # Формируем результат с расчетом среднего чека
    result_list = []
    for row in results:
        revenue = round(float(row.total_revenue or 0), 2)
        checks_count = int(row.total_checks_count or 0)
        returns_count = int(row.total_returns_count or 0)
        avg_check = round(revenue / checks_count, 2) if checks_count > 0 else 0.0

        result_list.append((
            row.waiter_name or "Неизвестно",
            row.waiter_id or "",
            row.employee_id,
            revenue,
            checks_count,
            returns_count,
            avg_check,
        ))

    return result_list


