from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user
from database.database import get_db
from services.reports.reports_service import get_order_reports, get_moneyflow_reports
from schemas.reports import OrderReportsResponse, MoneyFlowResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/orders", response_model=OrderReportsResponse)
def get_order_reports_endpoint(
    date: str = Query(..., description="Дата в формате DD.MM.YYYY"),
    period: Optional[str] = Query(default="day", description="Период: day, week, month"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить отчеты по заказам
    
    **Query Parameters:**
    - `date` (required): Дата в формате "DD.MM.YYYY"
    - `period` (optional): Период ("day" | "week" | "month")
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - Средний чек
    - Сумма возвратов
    - Среднее количество блюд
    - Популярные и непопулярные блюда
    """
    try:
        reports = get_order_reports(
            db=db,
            date=date,
            period=period,
            organization_id=organization_id
        )
        return reports
    except Exception as e:
        logger.error(f"Error getting order reports: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/moneyflow", response_model=MoneyFlowResponse)
def get_moneyflow_reports_endpoint(
    date: str = Query(..., description="Дата в формате DD.MM.YYYY"),
    period: Optional[str] = Query(default="day", description="Период: day, week, month"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить денежные отчеты
    
    **Query Parameters:**
    - `date` (required): Дата в формате "DD.MM.YYYY"
    - `period` (optional): Период ("day" | "week" | "month")
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - Стоимость блюд по себестоимости
    - Списания
    - Расходы
    - Доходы
    """
    try:
        reports = get_moneyflow_reports(
            db=db,
            date=date,
            period=period,
            organization_id=organization_id
        )
        return reports
    except Exception as e:
        logger.error(f"Error getting moneyflow reports: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

