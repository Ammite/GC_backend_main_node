from sqlalchemy.orm import Session
from typing import Optional
from utils.cache import cached
from schemas.popular_dishes import (
    PopularDishesResponse,
    DishItem
)
from services.transactions_and_statistics.statistics_service import (
    parse_date,
    get_period_dates,
    get_popular_dishes,
    get_unpopular_dishes
)
import logging

logger = logging.getLogger(__name__)


@cached(ttl_seconds=300, key_prefix="popular_dishes")  # Кэш на 5 минут
def get_popular_dishes_report(
    db: Session,
    date: Optional[str] = None,
    period: Optional[str] = "day",
    organization_id: Optional[int] = None,
    limit: int = 10
) -> PopularDishesResponse:
    """
    Получить отчет о популярных и непопулярных блюдах
    
    Args:
        db: сессия БД
        date: дата в формате "DD.MM.YYYY"
        period: период аналитики ("day" | "week" | "month")
        organization_id: ID организации (фильтр)
        limit: количество блюд в топе (по умолчанию 10)
    
    Returns:
        Отчет с популярными и непопулярными блюдами
    """
    # Парсим дату и определяем период
    target_date = parse_date(date)
    start_date, end_date, _, _ = get_period_dates(target_date, period)
    
    logger.info(f"Generating popular dishes report for period {start_date} - {end_date}")
    
    # Получаем топ популярных блюд
    popular_list = get_popular_dishes(db, start_date, end_date, organization_id, limit=limit)
    
    popular_dishes = []
    total_popular_quantity = 0
    total_popular_revenue = 0
    
    for idx, (dish_name, quantity, revenue) in enumerate(popular_list, start=1):
        quantity = int(quantity)
        revenue = float(revenue)
        average_price = revenue / quantity if quantity > 0 else 0
        
        popular_dishes.append(
            DishItem(
                id=idx,
                name=dish_name,
                quantity=quantity,
                revenue=revenue,
                average_price=round(average_price, 2)
            )
        )
        
        total_popular_quantity += quantity
        total_popular_revenue += revenue
    
    # Получаем топ непопулярных блюд
    unpopular_list = get_unpopular_dishes(db, start_date, end_date, organization_id, limit=limit)
    
    unpopular_dishes = []
    total_unpopular_quantity = 0
    total_unpopular_revenue = 0
    
    for idx, (dish_name, quantity, revenue) in enumerate(unpopular_list, start=1):
        quantity = int(quantity)
        revenue = float(revenue)
        average_price = revenue / quantity if quantity > 0 else 0
        
        unpopular_dishes.append(
            DishItem(
                id=idx,
                name=dish_name,
                quantity=quantity,
                revenue=revenue,
                average_price=round(average_price, 2)
            )
        )
        
        total_unpopular_quantity += quantity
        total_unpopular_revenue += revenue
    
    # Общая статистика
    total_dishes_sold = total_popular_quantity + total_unpopular_quantity
    total_revenue = total_popular_revenue + total_unpopular_revenue
    
    logger.info(f"Popular dishes: {len(popular_dishes)}, Unpopular dishes: {len(unpopular_dishes)}")
    logger.info(f"Total dishes sold: {total_dishes_sold}, Total revenue: {total_revenue}")
    
    return PopularDishesResponse(
        success=True,
        message=f"Отчет о популярных блюдах за период {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}",
        popular_dishes=popular_dishes,
        unpopular_dishes=unpopular_dishes,
        total_dishes_sold=total_dishes_sold,
        total_revenue=round(total_revenue, 2)
    )

