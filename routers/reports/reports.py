from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user, require_role
from database.database import get_db
from services.reports.reports_service import get_order_reports, get_moneyflow_reports, get_sales_dynamics
from services.reports.personnel_service import get_personnel_report
from schemas.reports import OrderReportsResponse, MoneyFlowResponse, SalesDynamicsResponse, PersonnelReportResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/orders", response_model=OrderReportsResponse)
async def get_order_reports_endpoint(
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY"),
    period: Optional[str] = Query(default="day", description="Период: day, week, month"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    date_from: Optional[str] = Query(default=None, description="Начало периода DD.MM.YYYY (приоритет над date+period)"),
    date_to: Optional[str] = Query(default=None, description="Конец периода DD.MM.YYYY (приоритет над date+period)"),
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Получить отчеты по заказам

    **Query Parameters:**
    - `date` (optional): Дата в формате "DD.MM.YYYY"
    - `period` (optional): Период ("day" | "week" | "month")
    - `date_from` (optional): Начало периода DD.MM.YYYY (приоритет над date+period)
    - `date_to` (optional): Конец периода DD.MM.YYYY (приоритет над date+period)
    - `organization_id` (optional): ID организации для фильтрации
    """
    try:
        reports = await get_order_reports(
            db=db,
            date=date,
            period=period,
            organization_id=organization_id,
            date_from=date_from,
            date_to=date_to,
        )
        return reports
    except Exception as e:
        logger.error(f"Error getting order reports: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/moneyflow", response_model=MoneyFlowResponse)
async def get_moneyflow_reports_endpoint(
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY"),
    period: Optional[str] = Query(default="day", description="Период: day, week, month"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    date_from: Optional[str] = Query(default=None, description="Начало периода DD.MM.YYYY (приоритет над date+period)"),
    date_to: Optional[str] = Query(default=None, description="Конец периода DD.MM.YYYY (приоритет над date+period)"),
    db: Session = Depends(get_db),
    user = Depends(require_role("Владелец")),
):
    """
    Получить денежные отчеты

    **Query Parameters:**
    - `date` (optional): Дата в формате "DD.MM.YYYY"
    - `period` (optional): Период ("day" | "week" | "month")
    - `date_from` (optional): Начало периода DD.MM.YYYY (приоритет над date+period)
    - `date_to` (optional): Конец периода DD.MM.YYYY (приоритет над date+period)
    - `organization_id` (optional): ID организации для фильтрации
    """
    try:
        reports = await get_moneyflow_reports(
            db=db,
            date=date,
            period=period,
            organization_id=organization_id,
            date_from=date_from,
            date_to=date_to,
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
    date_from: Optional[str] = Query(default=None, description="Начало периода DD.MM.YYYY (приоритет над date+days)"),
    date_to: Optional[str] = Query(default=None, description="Конец периода DD.MM.YYYY (приоритет над date+days)"),
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Получить динамику продаж за последние N дней

    **Query Parameters:**
    - `days` (optional): Количество дней для анализа (по умолчанию 7)
    - `date` (optional): Дата в формате DD.MM.YYYY
    - `date_from` (optional): Начало периода DD.MM.YYYY (приоритет над date+days)
    - `date_to` (optional): Конец периода DD.MM.YYYY (приоритет над date+days)
    - `organization_id` (optional): ID организации для фильтрации
    """
    try:
        report = await get_sales_dynamics(
            db=db,
            days=days,
            date=date,
            organization_id=organization_id,
            date_from=date_from,
            date_to=date_to,
        )
        return report
    except Exception as e:
        logger.error(f"Error getting sales dynamics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/personnel", response_model=PersonnelReportResponse)
async def get_personnel_report_endpoint(
    from_date: Optional[str] = Query(default=None, description="Дата начала периода в формате DD.MM.YYYY"),
    to_date: Optional[str] = Query(default=None, description="Дата конца периода в формате DD.MM.YYYY"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Получить отчет по персоналу за период
    
    **Query Parameters:**
    - `from_date` (optional): Дата начала периода в формате "DD.MM.YYYY". Если не указана, используется 30 дней назад.
    - `to_date` (optional): Дата конца периода в формате "DD.MM.YYYY". Если не указана, используется сегодня.
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - Список сотрудников с:
      - id, name, role
      - totalAmount (сумма чеков за период)
      - ordersCount (количество чеков за период)
      - shiftDuration (общая длительность смен за период в формате HH:mm:ss)
    """
    try:
        report = get_personnel_report(
            db=db,
            from_date=from_date,
            to_date=to_date,
            organization_id=organization_id
        )
        return report
    except Exception as e:
        logger.error(f"Error getting personnel report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

