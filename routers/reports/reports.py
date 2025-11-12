from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user
from database.database import get_db
from services.reports.reports_service import get_order_reports, get_moneyflow_reports, get_sales_dynamics
from schemas.reports import OrderReportsResponse, MoneyFlowResponse, SalesDynamicsResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/orders", response_model=OrderReportsResponse)
async def get_order_reports_endpoint(
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
        reports = await get_order_reports(
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
async def get_moneyflow_reports_endpoint(
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
        reports = await get_moneyflow_reports(
            db=db,
            date=date,
            period=period,
            organization_id=organization_id
        )
        return reports
    except Exception as e:
        logger.error(f"Error getting moneyflow reports: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/sales-dynamics", response_model=SalesDynamicsResponse)
async def get_sales_dynamics_endpoint(
    days: Optional[int] = Query(default=7, description="Количество дней для анализа (по умолчанию 7)"),
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить динамику продаж за последние N дней
    
    **Query Parameters:**
    - `days` (optional): Количество дней для анализа (по умолчанию 7)
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - `total_revenue`: Общая выручка за период
    - `total_checks`: Общее количество чеков за период
    - `overall_average_check`: Общий средний чек за период
    - `daily_data`: Массив данных по каждому дню с выручкой, количеством чеков и средним чеком
    
    **Примеры использования:**
    - `/reports/sales-dynamics` - динамика за последние 7 дней
    - `/reports/sales-dynamics?days=14` - динамика за последние 14 дней
    - `/reports/sales-dynamics?days=7&organization_id=1` - динамика за последние 7 дней по организации
    
    **Данные берутся из таблицы Sales:**
    - Фильтруются записи где `cashier != 'Удаление позиций'` и `order_deleted != 'DELETED'`
    - Выручка считается из поля `dish_discount_sum_int`
    - Количество чеков считается по уникальным `order_id`
    """
    try:
        report = await get_sales_dynamics(
            db=db,
            days=days,
            date=date,
            organization_id=organization_id
        )
        return report
    except Exception as e:
        logger.error(f"Error getting sales dynamics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

