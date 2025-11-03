"""
Сервис для работы со статистикой и транзакциями
Содержит переиспользуемые функции для аналитики и отчетов
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta
from models.d_order import DOrder
from models.t_order import TOrder
from models.item import Item
from models.sales import Sales
from models.employees import Employees
from models.account import Account
from models.transaction import Transaction
from schemas.analytics import ChangeMetric


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
        return sum(float(order.discount or 0) for order in orders)
    return sum(float(order.sum_order or 0) for order in orders)


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
    return revenue / len(orders)


# ==================== РАБОТА С SALES ====================

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
    return sum(float(sale.dish_sum_int or 0) for sale in sales)


def get_cost_of_goods_from_sales(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None
) -> float:
    """
    Получить себестоимость проданных товаров из таблицы Sales
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        
    Returns:
        Себестоимость товаров
    """
    # Приводим к датам для сравнения с open_date_typed
    start_date_only = start_date.date() if hasattr(start_date, 'date') else start_date
    end_date_only = end_date.date() if hasattr(end_date, 'date') else end_date
    
    # Используем func.sum для агрегации в БД
    result = db.query(
        func.sum(Sales.product_cost_base_product_cost)
    ).filter(
        and_(
            Sales.open_date_typed >= start_date_only,
            Sales.open_date_typed <= end_date_only,
            Sales.cashier != 'Удаление позиций',
            Sales.order_deleted != 'DELETED',
            Sales.dish_amount_int.isnot(None),
            Sales.product_cost_base_product_cost.isnot(None),
            Sales.product_cost_base_product_cost > 0
        )
    )
    
    if organization_id:
        result = result.filter(Sales.organization_id == organization_id)
    
    total = result.scalar()
    return float(total or 0)


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
    sales_query = db.query(Sales).filter(
        Sales.deleted_with_writeoff == 'DELETED_WITH_WRITEOFF',
        Sales.cashier != 'Удаление позиций',
        Sales.open_time >= start_date,
        Sales.open_time <= end_date,
    )
    
    if organization_id:
        sales_query = sales_query.filter(Sales.organization_id == organization_id)
    
    sales = sales_query.all()
    return sum(float(sale.dish_discount_sum_int or 0) for sale in sales)


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
    sales_query = db.query(Sales).filter(
        Sales.deleted_with_writeoff == 'DELETED_WITH_WRITEOFF',
        Sales.cashier != 'Удаление позиций',
        Sales.open_time >= start_date,
        Sales.open_time <= end_date,
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
        reason = sale.deletion_method_type or "Списание"
        
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
        (dish_name, data['quantity'], data['amount'], data['reason'])
        for dish_name, data in writeoffs_dict.items()
    ]


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
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        
    Returns:
        Словарь с доходами по категориям: {"Кухня": amount, "Бар": amount, "Наценка": amount, "total": amount}
    """
    # Базовый фильтр для всех запросов
    base_filter = and_(
        Sales.open_date_typed >= start_date,
        Sales.open_date_typed < end_date,
        Sales.cashier != 'Удаление позиций',
        Sales.order_deleted != 'DELETED'
    )
    
    # Выручка Кухня (с учетом скидок и наценок)
    kitchen_query = db.query(
        func.sum(Sales.dish_sum_int).label('sum_base'),
        func.sum(Sales.discount_sum).label('sum_discount'),
        func.sum(Sales.increase_sum).label('sum_increase')
    ).filter(
        and_(
            base_filter,
            func.lower(Sales.cooking_place_type).contains('кухня'),
            Sales.dish_sum_int.isnot(None)
        )
    )
    
    if organization_id:
        kitchen_query = kitchen_query.filter(Sales.organization_id == organization_id)
    
    kitchen_data = kitchen_query.first()
    kitchen_base = float(kitchen_data.sum_base or 0)
    kitchen_discount = float(kitchen_data.sum_discount or 0)
    kitchen_increase = float(kitchen_data.sum_increase or 0)
    kitchen_revenue = kitchen_base - kitchen_discount + kitchen_increase
    
    # Выручка Бар (не Кухня, с учетом скидок и наценок)
    bar_query = db.query(
        func.sum(Sales.dish_sum_int).label('sum_base'),
        func.sum(Sales.discount_sum).label('sum_discount'),
        func.sum(Sales.increase_sum).label('sum_increase')
    ).filter(
        and_(
            base_filter,
            Sales.cooking_place_type != 'Кухня',
            Sales.cooking_place_type.isnot(None),
            Sales.dish_sum_int.isnot(None)
        )
    )
    
    if organization_id:
        bar_query = bar_query.filter(Sales.organization_id == organization_id)
    
    bar_data = bar_query.first()
    bar_base = float(bar_data.sum_base or 0)
    bar_discount = float(bar_data.sum_discount or 0)
    bar_increase = float(bar_data.sum_increase or 0)
    bar_revenue = bar_base - bar_discount + bar_increase
    
    # Прочие (без категории, с учетом скидок и наценок)
    other_query = db.query(
        func.sum(Sales.dish_sum_int).label('sum_base'),
        func.sum(Sales.discount_sum).label('sum_discount'),
        func.sum(Sales.increase_sum).label('sum_increase')
    ).filter(
        and_(
            base_filter,
            Sales.cooking_place_type.is_(None),
            Sales.dish_sum_int.isnot(None)
        )
    )
    
    if organization_id:
        other_query = other_query.filter(Sales.organization_id == organization_id)
    
    other_data = other_query.first()
    other_base = float(other_data.sum_base or 0)
    other_discount = float(other_data.sum_discount or 0)
    other_increase = float(other_data.sum_increase or 0)
    other_revenue = other_base - other_discount + other_increase
    
    # Общая сумма наценок (отдельная категория)
    total_increase = kitchen_increase + bar_increase + other_increase
    
    # Общая выручка
    total_revenue = kitchen_revenue + bar_revenue + other_revenue
    
    return {
        "Кухня": kitchen_base,
        "Бар": bar_base,
        "Прочее": other_revenue,
        "Наценка (обслуживание)": total_increase,
        "total": total_revenue
    }


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
            float(row.total_amount or 0)
        )
        for row in results
    ]


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
    commission_query = db.query(
        func.sum(DOrder.bank_commission)
    ).filter(
        and_(
            DOrder.time_order >= start_date,
            DOrder.time_order < end_date,
            DOrder.bank_commission.isnot(None),
            DOrder.deleted == False
        )
    )
    
    if organization_id:
        commission_query = commission_query.filter(DOrder.organization_id == organization_id)
    
    return float(commission_query.scalar() or 0)


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
    query = db.query(func.sum(DOrder.discount)).filter(
        and_(
            DOrder.time_order >= start_date,
            DOrder.time_order <= end_date,
            DOrder.deleted == False
        )
    )
    
    if organization_id:
        query = query.filter(DOrder.organization_id == organization_id)
    
    result = query.scalar()
    return float(result or 0)


# ==================== РАБОТА С БЛЮДАМИ ====================

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
    
    return total_items_count / orders_count if orders_count > 0 else 0


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
    
    return results


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
    
    return results


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
    
    return results


# ==================== РАБОТА С СОТРУДНИКАМИ ====================

def get_top_employees_by_revenue(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    organization_id: Optional[int] = None,
    limit: int = 10
) -> List[Tuple[str, str, int, float]]:
    """
    Получить топ сотрудников по выручке
    
    Args:
        db: сессия БД
        start_date: начало периода
        end_date: конец периода
        organization_id: ID организации (фильтр)
        limit: количество результатов
        
    Returns:
        Список кортежей (имя, iiko_id, employee_id, выручка)
    """
    query = db.query(
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
        query = query.filter(Sales.organization_id == organization_id)
    
    results = query.group_by(
        Employees.name, 
        Employees.iiko_id,
        Employees.id
    ).order_by(
        func.sum(Sales.dish_discount_sum_int).desc()
    ).limit(limit).all()
    
    return results


# ==================== РАБОТА С ТРАНЗАКЦИЯМИ И РАСХОДАМИ ====================

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
    if expense_types is None:
        expense_types = ['EXPENSES', 'EQUITY', 'EMPLOYEES_LIABILITY', 'DEBTS_OF_EMPLOYEES']
    
    # Шаг 1: Получаем аккаунты с нужными типами
    accounts = db.query(Account).filter(
        Account.type.in_(expense_types),
        Account.deleted == False
    ).all()
    
    # Шаг 2: Извлекаем iiko_id из аккаунтов
    account_iiko_ids = [account.iiko_id for account in accounts]
    
    if not account_iiko_ids:
        return {
            "expenses_amount": 0.0,
            "data": []
        }
    
    # Шаг 3: Получаем транзакции по этим account_id
    transactions_query = db.query(Transaction).filter(
        Transaction.account_id.in_(account_iiko_ids),
        Transaction.date_time >= start_date,
        Transaction.date_time <= end_date,
        Transaction.is_active == True
    )
    
    # Фильтруем по организации если указана
    if organization_id:
        transactions_query = transactions_query.filter(
            Transaction.organization_id == organization_id
        )
    
    transactions = transactions_query.all()
    
    # Считаем общую сумму расходов
    total_expenses = sum(
        float(abs(transaction.sum_resigned) or 0) 
        for transaction in transactions
    )
    
    # Группируем транзакции по типу счета и названию счета
    # Структура: {account_type: {account_name: [transactions]}}
    grouped_data = {}
    
    for transaction in transactions:
        account_type = transaction.account_type or 'Неизвестно'
        account_name = transaction.account_name or 'Неизвестно'
        
        if account_type not in grouped_data:
            grouped_data[account_type] = {}
        
        if account_name not in grouped_data[account_type]:
            grouped_data[account_type][account_name] = []
        
        grouped_data[account_type][account_name].append(transaction)
    
    # Формируем итоговую структуру данных
    data = []
    
    for account_type, accounts_dict in grouped_data.items():
        for account_name, trans_list in accounts_dict.items():
            # Считаем сумму всех транзакций для этого типа и счета
            account_total = sum(float(abs(t.sum_resigned) or 0) for t in trans_list)
            
            # Формируем список транзакций
            transactions_items = []
            for trans in trans_list:
                transactions_items.append({
                    "transaction_id": trans.id,
                    "transaction_type": account_type,
                    "transaction_name": account_name,
                    "transaction_amount": float(abs(trans.sum_resigned) or 0),
                    "transaction_datetime": trans.date_time.strftime("%Y-%m-%d %H:%M:%S") if trans.date_time else "",
                    "transaction_comment": trans.comment or ""
                })
            
            # Добавляем группу расходов
            data.append({
                "transaction_type": account_type,
                "transaction_name": account_name,
                "transaction_amount": account_total,
                "transactions": transactions_items
            })
    
    return {
        "expenses_amount": total_expenses,
        "data": data
    }

