from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user
from database.database import get_db
from services.popular_dishes import get_popular_dishes_report
from schemas.popular_dishes import PopularDishesResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/popular-dishes", response_model=PopularDishesResponse)
def get_popular_dishes_endpoint(
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY"),
    period: Optional[str] = Query(default="day", description="Период: day, week, month"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    limit: int = Query(default=10, ge=1, le=100, description="Количество блюд в топе"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить отчет о популярных и непопулярных блюдах
    
    **Query Parameters:**
    - `date` (optional): Дата в формате "DD.MM.YYYY" - дата для отчета
    - `period` (optional): Период отчета ("day" | "week" | "month")
    - `organization_id` (optional): ID организации для фильтрации
    - `limit` (optional): Количество блюд в топе (от 1 до 100, по умолчанию 10)
    
    **Response:**
    - `popular_dishes`: Топ самых популярных блюд
      - Каждое блюдо содержит: название, количество проданных порций, выручку, среднюю цену
    - `unpopular_dishes`: Топ самых непопулярных блюд
      - С той же структурой данных
    - `total_dishes_sold`: Общее количество проданных блюд
    - `total_revenue`: Общая выручка от блюд
    
    **Критерии популярности:**
    - Блюда сортируются по количеству проданных порций (`dish_amount_int`)
    - Учитываются только активные продажи (не удаленные)
    - Фильтруются записи где `cashier != 'Удаление позиций'` и `order_deleted != 'DELETED'`
    - Данные берутся из таблицы `Sales` (реальные продажи)
    
    **Примеры использования:**
    - Топ-10 популярных блюд за день: `/reports/popular-dishes?date=03.11.2025&period=day&limit=10`
    - Топ-5 популярных блюд за неделю: `/reports/popular-dishes?period=week&limit=5`
    - Топ-20 популярных блюд за месяц для организации: `/reports/popular-dishes?period=month&organization_id=1&limit=20`
    """
    try:
        report = get_popular_dishes_report(
            db=db,
            date=date,
            period=period,
            organization_id=organization_id,
            limit=limit
        )
        return report
    except Exception as e:
        logger.error(f"Error generating popular dishes report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

