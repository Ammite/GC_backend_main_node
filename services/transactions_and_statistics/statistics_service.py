"""
Сервис для работы со статистикой и транзакциями
Содержит переиспользуемые функции для аналитики и отчетов
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, distinct, case
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta
from models.d_order import DOrder
from models.bank_commission import BankCommission
from models.t_order import TOrder
from models.item import Item
from models.sales import Sales
from models.employees import Employees
from models.account import Account
from models.transaction import Transaction
from schemas.analytics import ChangeMetric
from utils.file_cache import file_cached
from utils.performance_logger import log_execution_time
from services.transactions_and_statistics.daily_aggregates_service import (
    get_daily_metric_sum,
    get_daily_metric_by_subkey,
)

import logging
logger = logging.getLogger(__name__)

# ==================== УТИЛИТЫ ====================

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


def parse_date(date: Optional[str] = None) -> datetime:
    """
    Распарсить дату из строки
    
    Args:
        date: дата в формате "DD.MM.YYYY" или None
        
    Returns:
        datetime объект
    """
    if date:
        try:
            return datetime.strptime(date, "%d.%m.%Y")
        except ValueError:
            return datetime.now()
    return datetime.now()


def get_period_dates(
    target_date: datetime,
    period: str = "day"
) -> Tuple[datetime, datetime, datetime, datetime]:
    """
    Получить даты начала и конца периода + предыдущего периода
    
    Args:
        target_date: целевая дата
        period: период ("day" | "week" | "month")
        
    Returns:
        (start_date, end_date, previous_start, previous_end)
    """
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
    
    return start_date, end_date, previous_start, previous_end


def resolve_date_range(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    date: Optional[str] = None,
    period: Optional[str] = "day",
) -> Tuple[datetime, datetime, datetime, datetime]:
    """
    Универсальный резолвер диапазона дат.

    Приоритет: если переданы date_from/date_to (DD.MM.YYYY) — используются они.
    Иначе — старая логика date + period.

    Returns:
        (start_date, end_date, previous_start, previous_end)
    """
    if date_from and date_to:
        start = datetime.strptime(date_from, "%d.%m.%Y").replace(hour=0, minute=0, second=0, microsecond=0)
        end = datetime.strptime(date_to, "%d.%m.%Y").replace(hour=23, minute=59, second=59, microsecond=999999)
        delta = end - start
        prev_end = start
        prev_start = start - delta - timedelta(seconds=1)
        prev_start = prev_start.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, end, prev_start, prev_end
    target_date = parse_date(date)
    return get_period_dates(target_date, period)


# ==================== РАБОТА С ЗАКАЗАМИ ====================

def get_orders_for_period(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None
) -> List[DOrder]:
    """
    Получить заказы за указанный период
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        
    Returns:
        Список заказов
    """
    query = db.query(DOrder).filter(
        and_(
            DOrder.time_order >= start_date,
            DOrder.time_order <= end_date,
            DOrder.deleted == False
        )
    )
    
    if organization_id:
        query = query.filter(DOrder.organization_id == organization_id)
    
    return query.all()


def calculate_revenue_from_orders(orders: List[DOrder], use_discount: bool = False) -> float:
    """
    Рассчитать выручку из списка заказов
    
    Args:
        orders: список заказов
        use_discount: использовать поле discount вместо sum_order
        
    Returns:
        Общая сумма выручки
    """
    if use_discount:
        return round(sum(float(order.discount or 0) for order in orders), 2)
    return round(sum(float(order.sum_order or 0) for order in orders), 2)


def calculate_average_check(orders: List[DOrder], use_discount: bool = False) -> float:
    """
    Рассчитать средний чек из списка заказов
    
    Args:
        orders: список заказов
        use_discount: использовать поле discount вместо sum_order
        
    Returns:
        Средний чек
    """
    if not orders:
        return 0.0
    
    revenue = calculate_revenue_from_orders(orders, use_discount)
    return round(revenue / len(orders), 2)


# ==================== РАБОТА С SALES ====================

@file_cached(ttl_seconds=600, key_prefix="returns")
def get_returns_sum_from_sales(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None
) -> float:
    """
    Получить сумму возвратов из таблицы Sales
    Фильтрует по deleted_with_writeoff = 'DELETED_WITHOUT_WRITEOFF'
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        
    Returns:
        Сумма возвратов
    """
    # Используем предагрегированную дневную метрику returns_sum
    return get_daily_metric_sum(
        db,
        metric_key="returns_sum",
        start_date=start_date,
        end_date=end_date,
        organization_id=organization_id,
    )


@file_cached(ttl_seconds=600, key_prefix="cost_goods")
def get_cost_of_goods_from_sales(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None
) -> Dict[str, float]:
    """
    Получить себестоимость проданных товаров из таблицы Transactions
    Группирует по категориям на основе account_hierarchy_top
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        
    Returns:
        Словарь с себестоимостью по категориям: {"category": amount, "total": amount}
    """
    # Используем предагрегированные дневные метрики cost_goods_category и cost_goods_total
    start_date_only = start_date.date() if hasattr(start_date, "date") else start_date
    end_date_only = end_date.date() if hasattr(end_date, "date") else end_date

    cost_by_category = get_daily_metric_by_subkey(
        db,
        metric_key="cost_goods_category",
        start_date=start_date_only,
        end_date=end_date_only,
        organization_id=organization_id,
    )
    total_cost = get_daily_metric_sum(
        db,
        metric_key="cost_goods_total",
        start_date=start_date_only,
        end_date=end_date_only,
        organization_id=organization_id,
    )

    if not cost_by_category:
        return {"total": total_cost}

    cost_by_category["total"] = total_cost
    return cost_by_category


@file_cached(ttl_seconds=600, key_prefix="writeoffs_sum")
@log_execution_time
def get_writeoffs_sum_from_sales(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None
) -> float:
    """
    Получить сумму списаний из таблицы Sales
    Суммирует sales.dish_discount_sum_int с фильтром deleted_with_writeoff = 'DELETED_WITH_WRITEOFF'
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        
    Returns:
        Сумма списаний
    """
    logger.debug("[PERF] get_writeoffs_sum_from_sales -> calling get_daily_metric_sum")
    # Используем предагрегированную дневную метрику writeoffs_sum
    return get_daily_metric_sum(
        db,
        metric_key="writeoffs_sum",
        start_date=start_date,
        end_date=end_date,
        organization_id=organization_id,
    )


@log_execution_time
def get_writeoffs_details_from_sales(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None
) -> List[Tuple[str, int, float, str]]:
    """
    Получить детализированные данные о списаниях из таблицы Sales
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        
    Returns:
        Список кортежей (название блюда, количество, сумма, причина)
    """
    logger.debug("[PERF] get_writeoffs_details_from_sales -> querying Sales table")
    sales_query = db.query(Sales).filter(
        Sales.deleted_with_writeoff == 'DELETED_WITH_WRITEOFF',
        Sales.cashier != 'Удаление позиций',
        Sales.open_date_typed >= start_date.date() if isinstance(start_date, datetime) else start_date,
        Sales.open_date_typed <= end_date.date() if isinstance(end_date, datetime) else end_date,
    )
    
    if organization_id:
        sales_query = sales_query.filter(Sales.organization_id == organization_id)
    
    sales = sales_query.all()
    
    # Группируем списания по блюдам
    writeoffs_dict = {}
    for sale in sales:
        dish_name = sale.dish_name or "Неизвестное блюдо"
        amount = float(sale.dish_discount_sum_int or 0)
        quantity = int(sale.dish_amount_int or 0)
        reason = sale.writeoff_reason or "Списание"
        
        if dish_name not in writeoffs_dict:
            writeoffs_dict[dish_name] = {
                'quantity': 0,
                'amount': 0.0,
                'reason': reason
            }
        
        writeoffs_dict[dish_name]['quantity'] += quantity
        writeoffs_dict[dish_name]['amount'] += amount
    
    # Преобразуем в список кортежей
    return [
        (dish_name, data['quantity'], round(data['amount'], 2), data['reason'])
        for dish_name, data in writeoffs_dict.items()
    ]


@file_cached(ttl_seconds=600, key_prefix="factory_revenue")
def get_factory_revenue(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None
) -> float:
    """
    Получить выручку с фабрики из таблицы transactions
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        
    Returns:
        Сумма выручки с фабрики
    """
    # Используем предагрегированную дневную метрику factory_revenue
    start_date_only = start_date.date() if hasattr(start_date, "date") else start_date
    end_date_only = end_date.date() if hasattr(end_date, "date") else end_date
    return get_daily_metric_sum(
        db,
        metric_key="factory_revenue",
        start_date=start_date_only,
        end_date=end_date_only,
        organization_id=organization_id,
    )


@file_cached(ttl_seconds=600, key_prefix="revenue_category")
def get_revenue_by_category(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None
) -> Dict[str, float]:
    """
    Получить доходы по категориям (Кухня, Бар) из таблицы Sales
    Учитывает: dish_sum_int (базовая цена), discount_sum (скидки), increase_sum (наценки/обслуживание)
    Формула: Выручка = dish_sum_int - discount_sum + increase_sum
    Также включает выручку с фабрики из таблицы transactions
    Включает дополнительные доходы из accounts_list с типом OTHER_INCOME, группированные по названию счета
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        
    Returns:
        Словарь с доходами по категориям: {"Кухня": amount, "Бар": amount, "Наценка": amount, "Фабрика": amount, "Название счета OTHER_INCOME": amount, "total": amount}
    """
    # Используем предагрегированные дневные метрики по выручке
    start_date_only = start_date.date() if hasattr(start_date, "date") else start_date
    end_date_only = end_date.date() if hasattr(end_date, "date") else end_date

    kitchen_base = get_daily_metric_sum(
        db,
        metric_key="revenue_kitchen",
        start_date=start_date_only,
        end_date=end_date_only,
        organization_id=organization_id,
    )
    bar_base = get_daily_metric_sum(
        db,
        metric_key="revenue_bar",
        start_date=start_date_only,
        end_date=end_date_only,
        organization_id=organization_id,
    )
    other_revenue = get_daily_metric_sum(
        db,
        metric_key="revenue_other",
        start_date=start_date_only,
        end_date=end_date_only,
        organization_id=organization_id,
    )
    total_increase = get_daily_metric_sum(
        db,
        metric_key="revenue_increase_total",
        start_date=start_date_only,
        end_date=end_date_only,
        organization_id=organization_id,
    )
    additional_revenue = get_daily_metric_sum(
        db,
        metric_key="revenue_additional",
        start_date=start_date_only,
        end_date=end_date_only,
        organization_id=organization_id,
    )
    factory_revenue = get_daily_metric_sum(
        db,
        metric_key="factory_revenue",
        start_date=start_date_only,
        end_date=end_date_only,
        organization_id=organization_id,
    )
    other_income_revenue = get_daily_metric_by_subkey(
        db,
        metric_key="revenue_other_income",
        start_date=start_date_only,
        end_date=end_date_only,
        organization_id=organization_id,
    )
    total_revenue = get_daily_metric_sum(
        db,
        metric_key="revenue_total",
        start_date=start_date_only,
        end_date=end_date_only,
        organization_id=organization_id,
    )

    result = {
        "Кухня": round(kitchen_base, 2),
        "Бар": round(bar_base, 2),
        "Прочее": round(other_revenue, 2),
        "Наценка (обслуживание)": round(total_increase, 2),
        "Дополнительная выручка": round(additional_revenue, 2),
        "Фабрика": round(factory_revenue, 2),
    }

    # Добавляем дополнительные доходы как категории
    for account_name, income in other_income_revenue.items():
        result[account_name] = round(float(income or 0), 2)

    result["total"] = round(total_revenue, 2)
    return result


@log_execution_time
@file_cached(ttl_seconds=600, key_prefix="revenue_menu_payment")
def get_revenue_by_menu_category_and_payment(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None
) -> List[Tuple[str, str, float]]:
    """
    Получить выручку по категориям меню и типам оплаты из таблицы Sales
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        
    Returns:
        Список кортежей (категория, тип оплаты, сумма)
    """
    logger.debug("[PERF] get_revenue_by_menu_category_and_payment -> querying Sales table")
    query = db.query(
        Sales.dish_category,
        Sales.card_type_name,
        func.sum(Sales.dish_discount_sum_int).label('total_amount')
    ).filter(
        and_(
            Sales.open_date_typed >= start_date,
            Sales.open_date_typed < end_date,
            Sales.cashier != 'Удаление позиций',
            Sales.order_deleted != 'DELETED',
            Sales.dish_discount_sum_int.isnot(None)
        )
    )
    
    if organization_id:
        query = query.filter(Sales.organization_id == organization_id)
    
    # Группируем по категории и типу оплаты
    results = query.group_by(
        Sales.dish_category,
        Sales.card_type_name
    ).all()
    
    # Преобразуем в список кортежей с обработкой NULL значений
    return [
        (
            row.dish_category or "Без категории",
            row.card_type_name or "Без типа оплаты",
            round(float(row.total_amount or 0), 2)
        )
        for row in results
    ]


@log_execution_time
@file_cached(ttl_seconds=600, key_prefix="bank_commission")
def get_bank_commission_total(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None
) -> float:
    """
    Получить общую сумму комиссий банка из таблицы d_order
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        
    Returns:
        Сумма комиссий банка
    """
    import logging

    logger = logging.getLogger(__name__)

    logger.info("🔍 get_bank_commission_total called with:")
    logger.info(f"   start_date: {start_date}")
    logger.info(f"   end_date: {end_date}")
    logger.info(f"   organization_id: {organization_id}")

    start_date_only = start_date.date() if hasattr(start_date, "date") else start_date
    end_date_only = end_date.date() if hasattr(end_date, "date") else end_date

    result = get_daily_metric_sum(
        db,
        metric_key="bank_commission_total",
        start_date=start_date_only,
        end_date=end_date_only,
        organization_id=organization_id,
    )

    logger.info(f"   💰 Total commission (from daily_analytics): {result}")
    return result


def get_total_discount_from_orders(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None
) -> float:
    """
    Получить общую сумму скидок из таблицы d_order
    Суммирует d_order.discount
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        
    Returns:
        Сумма скидок
    """
    start_date_only = start_date.date() if hasattr(start_date, "date") else start_date
    end_date_only = end_date.date() if hasattr(end_date, "date") else end_date

    return get_daily_metric_sum(
        db,
        metric_key="discount_total",
        start_date=start_date_only,
        end_date=end_date_only,
        organization_id=organization_id,
    )


# ==================== РАБОТА С БЛЮДАМИ ====================

@file_cached(ttl_seconds=600, key_prefix="avg_items_per_order")
def get_average_items_per_order(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None
) -> float:
    """
    Получить среднее количество блюд в заказе из таблицы Sales
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        
    Returns:
        Среднее количество блюд
    """
    # Получаем общее количество блюд
    total_items_query = db.query(func.sum(Sales.dish_amount_int)).filter(
        and_(
            Sales.open_date_typed >= start_date,
            Sales.open_date_typed < end_date,
            Sales.cashier != 'Удаление позиций',
            Sales.order_deleted != 'DELETED',
            Sales.dish_amount_int.isnot(None)
        )
    )
    
    if organization_id:
        total_items_query = total_items_query.filter(Sales.organization_id == organization_id)
    
    total_items_count = total_items_query.scalar() or 0
    
    # Получаем количество уникальных заказов
    orders_count_query = db.query(func.count(func.distinct(Sales.order_id))).filter(
        and_(
            Sales.open_date_typed >= start_date,
            Sales.open_date_typed < end_date,
            Sales.cashier != 'Удаление позиций',
            Sales.order_deleted != 'DELETED',
            Sales.order_id.isnot(None)
        )
    )
    
    if organization_id:
        orders_count_query = orders_count_query.filter(Sales.organization_id == organization_id)
    
    orders_count = orders_count_query.scalar() or 0
    
    return round(total_items_count / orders_count, 2) if orders_count > 0 else 0.0


@file_cached(ttl_seconds=600, key_prefix="popular_dishes")
def get_popular_dishes(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None,
    limit: int = 1
) -> List[Tuple[str, int, float]]:
    """
    Получить популярные блюда из таблицы Sales
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        limit: количество результатов
        
    Returns:
        Список кортежей (название, количество, сумма)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Приводим к датам для сравнения с open_date_typed (который может быть типа Date)
    start_date_only = start_date.date() if hasattr(start_date, 'date') else start_date
    end_date_only = end_date.date() if hasattr(end_date, 'date') else end_date
    
    logger.info(f"Getting popular dishes from {start_date_only} to {end_date_only}")
    
    query = db.query(
        Sales.dish_name,
        func.sum(Sales.dish_amount_int).label("total_count"),
        func.sum(Sales.dish_discount_sum_int).label("total_amount")
    ).filter(
        and_(
            Sales.open_date_typed >= start_date_only,
            Sales.open_date_typed <= end_date_only,
            Sales.cashier != 'Удаление позиций',
            Sales.order_deleted != 'DELETED',
            Sales.dish_name.isnot(None),
            Sales.dish_amount_int.isnot(None),
            Sales.dish_amount_int > 0,
            Sales.dish_discount_sum_int.isnot(None),
            Sales.dish_discount_sum_int > 0
        )
    )
    
    if organization_id:
        query = query.filter(Sales.organization_id == organization_id)
    
    results = query.group_by(Sales.dish_name).order_by(
        func.sum(Sales.dish_amount_int).desc()
    ).limit(limit).all()
    
    logger.info(f"Found {len(results)} unique dishes (popular)")
    
    # Округляем суммы до 2 знаков после запятой
    return [
        (dish_name, total_count, round(float(total_amount or 0), 2))
        for dish_name, total_count, total_amount in results
    ]


@file_cached(ttl_seconds=600, key_prefix="unpopular_dishes")
def get_unpopular_dishes(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None,
    limit: int = 1
) -> List[Tuple[str, int, float]]:
    """
    Получить непопулярные блюда из таблицы Sales
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        limit: количество результатов
        
    Returns:
        Список кортежей (название, количество, сумма)
    """
    # Приводим к датам для сравнения с open_date_typed
    start_date_only = start_date.date() if hasattr(start_date, 'date') else start_date
    end_date_only = end_date.date() if hasattr(end_date, 'date') else end_date
    
    query = db.query(
        Sales.dish_name,
        func.sum(Sales.dish_amount_int).label("total_count"),
        func.sum(Sales.dish_discount_sum_int).label("total_amount")
    ).filter(
        and_(
            Sales.open_date_typed >= start_date_only,
            Sales.open_date_typed <= end_date_only,
            Sales.cashier != 'Удаление позиций',
            Sales.order_deleted != 'DELETED',
            Sales.dish_name.isnot(None),
            Sales.dish_amount_int.isnot(None),
            Sales.dish_amount_int > 0,
            Sales.dish_discount_sum_int.isnot(None),
            Sales.dish_discount_sum_int > 0
        )
    )
    
    if organization_id:
        query = query.filter(Sales.organization_id == organization_id)
    
    results = query.group_by(Sales.dish_name).order_by(
        func.sum(Sales.dish_amount_int).asc()
    ).limit(limit).all()
    
    # Округляем суммы до 2 знаков после запятой
    return [
        (dish_name, total_count, round(float(total_amount or 0), 2))
        for dish_name, total_count, total_amount in results
    ]


@log_execution_time
@file_cached(ttl_seconds=600, key_prefix="dishes_with_cost")
def get_dishes_with_cost(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None
) -> List[Tuple[str, int, float]]:
    """
    Получить все блюда с себестоимостью за период из таблицы Sales
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        
    Returns:
        Список кортежей (название, количество, себестоимость)
    """
    logger.debug("[PERF] get_dishes_with_cost -> querying Sales table")
    # Приводим к датам для сравнения с open_date_typed
    start_date_only = start_date.date() if hasattr(start_date, 'date') else start_date
    end_date_only = end_date.date() if hasattr(end_date, 'date') else end_date
    
    query = db.query(
        Sales.dish_name,
        func.sum(Sales.dish_amount_int).label("quantity"),
        func.sum(Sales.product_cost_base_product_cost).label("cost_amount")
    ).filter(
        and_(
            Sales.open_date_typed >= start_date_only,
            Sales.open_date_typed <= end_date_only,
            Sales.cashier != 'Удаление позиций',
            Sales.order_deleted != 'DELETED',
            Sales.dish_name.isnot(None),
            Sales.dish_amount_int.isnot(None),
            Sales.product_cost_base_product_cost.isnot(None),
            Sales.product_cost_base_product_cost > 0
        )
    )
    
    if organization_id:
        query = query.filter(Sales.organization_id == organization_id)
    
    results = query.group_by(Sales.dish_name).all()
    
    # Округляем суммы до 2 знаков после запятой
    return [
        (dish_name, quantity, round(float(cost_amount or 0), 2))
        for dish_name, quantity, cost_amount in results
    ]


# ==================== РАБОТА С СОТРУДНИКАМИ ====================

@file_cached(ttl_seconds=600, key_prefix="top_employees_revenue")
def get_top_employees_by_revenue(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None,
    limit: int = 10
) -> List[Tuple[str, str, int, float, int, int, float]]:
    """
    Получить топ сотрудников по выручке с расширенными метриками
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        limit: количество результатов
        
    Returns:
        Список кортежей (имя, iiko_id, employee_id, выручка, количество_чеков, количество_возвратов, средний_чек)
    """
    start_date_only = start_date.date() if isinstance(start_date, datetime) else start_date
    end_date_only = end_date.date() if isinstance(end_date, datetime) else end_date
    
    # Базовые фильтры
    base_filter = and_(
        Sales.open_date_typed >= start_date_only,
        Sales.open_date_typed <= end_date_only,
        Sales.cashier != 'Удаление позиций',
        Sales.order_deleted != 'DELETED',
        Sales.order_id.isnot(None)
    )
    
    if organization_id:
        base_filter = and_(base_filter, Sales.organization_id == organization_id)
    
    # Основной запрос с выручкой и количеством чеков
    query = db.query(
        Employees.name.label("waiter_name"),
        Employees.iiko_id.label("waiter_id"),
        Employees.id.label("employee_id"),
        func.sum(Sales.dish_discount_sum_int).label("total_revenue"),
        func.count(distinct(Sales.order_id)).label("checks_count")
    ).join(
        Employees, Sales.order_waiter_id == Employees.iiko_id
    ).filter(base_filter)
    
    results = query.group_by(
        Employees.name, 
        Employees.iiko_id,
        Employees.id
    ).order_by(
        func.sum(Sales.dish_discount_sum_int).desc()
    ).limit(limit).all()
    
    # Для каждого сотрудника получаем количество возвратов
    employee_returns = {}
    for waiter_name, waiter_id, employee_id, total_revenue, checks_count in results:
        returns_query = db.query(
            func.count(distinct(Sales.order_id)).label("returns_count")
        ).join(
            Employees, Sales.order_waiter_id == Employees.iiko_id
        ).filter(
            and_(
                base_filter,
                Employees.id == employee_id,
                Sales.deleted_with_writeoff == 'DELETED_WITHOUT_WRITEOFF'
            )
        ).scalar()
        
        employee_returns[employee_id] = int(returns_query or 0)
    
    # Формируем результат с расчетом среднего чека
    result_list = []
    for waiter_name, waiter_id, employee_id, total_revenue, checks_count in results:
        revenue = round(float(total_revenue or 0), 2)
        checks = int(checks_count or 0)
        returns = employee_returns.get(employee_id, 0)
        avg_check = round(revenue / checks, 2) if checks > 0 else 0.0
        
        result_list.append((
            waiter_name,
            waiter_id,
            employee_id,
            revenue,
            checks,
            returns,
            avg_check
        ))
    
    return result_list


# ==================== РАБОТА С ТРАНЗАКЦИЯМИ И РАСХОДАМИ ====================

@file_cached(ttl_seconds=600, key_prefix="expenses")
@log_execution_time
def get_expenses_from_transactions(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None,
    expense_types: Optional[List[str]] = None
) -> Dict:
    """
    Получить расходы из таблицы транзакций
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        expense_types: список типов расходов (по умолчанию EXPENSES, EQUITY, EMPLOYEES_LIABILITY, DEBTS_OF_EMPLOYEES)
        
    Returns:
        Словарь с структурированными данными о расходах
    """
    logger.debug("[PERF] get_expenses_from_transactions -> getting total expenses from aggregates")
    # Используем предагрегированную дневную метрику expenses_total для общей суммы
    start_date_only = start_date.date() if hasattr(start_date, "date") else start_date
    end_date_only = end_date.date() if hasattr(end_date, "date") else end_date

    total_expenses = get_daily_metric_sum(
        db,
        metric_key="expenses_total",
        start_date=start_date_only,
        end_date=end_date_only,
        organization_id=organization_id,
    )

    # Детализацию по транзакциям получаем из сырых данных (как раньше, но без пересчёта total)
    if expense_types is None:
        expense_types = ["EXPENSES", "OTHER_EXPENSES"]

    accounts = (
        db.query(Account)
        .filter(
            Account.type.in_(expense_types),
            Account.deleted == False,  # noqa: E712
        )
        .all()
    )

    account_iiko_ids = [account.iiko_id for account in accounts if account.name != "Зарплата"]

    if not account_iiko_ids:
        return {
            "expenses_amount": total_expenses,
            "data": [],
        }

    # Оптимизация: делаем агрегацию в БД, затем загружаем только нужные транзакции для детализации
    logger.debug("[PERF] get_expenses_from_transactions -> aggregating in DB")
    
    # Базовый запрос для обычных транзакций - получаем только ID и суммы для группировки
    base_query = db.query(
        Transaction.account_type,
        Transaction.account_name,
        Transaction.id
    ).filter(
        Transaction.account_id.in_(account_iiko_ids),
        Transaction.date_typed >= start_date_only,
        Transaction.date_typed <= end_date_only,
        Transaction.is_active == True,  # noqa: E712
    )
    
    if organization_id:
        base_query = base_query.filter(Transaction.organization_id == organization_id)
    
    base_transactions = base_query.all()
    
    # Запрос для зарплаты
    salary_query = db.query(
        Transaction.account_type,
        Transaction.account_name,
        Transaction.id
    ).filter(
        Transaction.account_id == "13000ead-41f0-d569-d85c-704242cc91f5",
        Transaction.date_typed >= start_date_only,
        Transaction.date_typed <= end_date_only,
        Transaction.contr_account_name == "Зарплата",
    )
    
    if organization_id:
        salary_query = salary_query.filter(Transaction.organization_id == organization_id)
    
    salary_transactions = salary_query.all()
    
    # Объединяем и группируем по (account_type, account_name)
    grouped_data = {}
    all_transaction_ids = []
    
    for trans in base_transactions + salary_transactions:
        account_type = trans.account_type or "Неизвестно"
        account_name = trans.account_name or "Неизвестно"
        key = (account_type, account_name)
        
        if key not in grouped_data:
            grouped_data[key] = []
        grouped_data[key].append(trans.id)
        all_transaction_ids.append(trans.id)
    
    # Загружаем полные данные транзакций одним запросом
    logger.debug("[PERF] get_expenses_from_transactions -> loading transaction details")
    transactions_dict = {}
    if all_transaction_ids:
        transactions = db.query(Transaction).filter(
            Transaction.id.in_(all_transaction_ids)
        ).all()
        transactions_dict = {t.id: t for t in transactions}
    
    # Формируем результат
    data = []
    for (account_type, account_name), trans_ids in grouped_data.items():
        transactions_items = []
        account_total = 0.0
        
        for trans_id in trans_ids:
            trans = transactions_dict.get(trans_id)
            if trans:
                amount = round(float(abs(trans.sum_resigned or 0)), 2)
                account_total += amount
                transactions_items.append(
                    {
                        "transaction_id": trans.id,
                        "transaction_type": account_type,
                        "transaction_name": account_name,
                        "transaction_amount": amount,
                        "transaction_datetime": trans.date_time.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        if trans.date_time
                        else "",
                        "transaction_comment": trans.comment or "",
                    }
                )
        
        data.append(
            {
                "transaction_type": account_type,
                "transaction_name": account_name,
                "transaction_amount": round(account_total, 2),
                "transactions": transactions_items,
            }
        )

    return {
        "expenses_amount": total_expenses,
        "data": data,
    }

