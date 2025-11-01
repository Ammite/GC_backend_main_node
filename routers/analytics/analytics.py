from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user
from database.database import get_db
from services.analytics.analytics_service import get_analytics
from schemas.analytics import AnalyticsResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics_endpoint(
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY"),
    period: Optional[str] = Query(default="day", description="Период: day, week, month"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить аналитику (для CEO)
    
    **Query Parameters:**
    - `date` (optional): Дата в формате "DD.MM.YYYY" - дата для аналитики
    - `period` (optional): Период аналитики ("day" | "week" | "month")
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - Метрики: выручка, чеки, средний чек
    - Отчеты: расходы и доходы
    - Заказы: статистика по заказам
    - Финансы: себестоимость и прибыль
    - Инвентарь: остатки товаров
    - Сотрудники: топ по выручке
    """
    try:
        analytics = get_analytics(
            db=db,
            date=date,
            period=period,
            organization_id=organization_id
        )
        return analytics
    except Exception as e:
        logger.error(f"Error getting analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

