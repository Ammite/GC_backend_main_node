from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user, require_self_or_role
from database.database import get_db
from services.salary.salary_service import calculate_waiter_salary, get_waiter_daily_sales
from schemas.salary import SalaryResponse, WaiterSalesResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["salary"])


@router.get("/waiter/{waiter_id}/salary", response_model=SalaryResponse)
def get_waiter_salary(
    waiter_id: int = Path(..., description="ID официанта"),
    date: str = Query(..., description="Дата в формате DD.MM.YYYY"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user=Depends(require_self_or_role("waiter_id", "Менеджер")),
):
    """
    Получить зарплату официанта за день
    
    **Query Parameters:**
    - `date` (required): Дата в формате "DD.MM.YYYY" - дата для расчета зарплаты
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - Детальная информация о зарплате официанта за указанный день
    - Включает базовую зарплату, бонусы, штрафы, награды за квесты
    """
    try:
        salary_info = calculate_waiter_salary(
            db=db,
            waiter_id=waiter_id,
            date=date,
            organization_id=organization_id,
        )
        
        if not salary_info:
            raise HTTPException(
                status_code=404,
                detail="Waiter not found or invalid date format",
            )
        
        return salary_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating waiter salary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/waiter/{waiter_id}/sales-today", response_model=WaiterSalesResponse)
def get_waiter_sales_today(
    waiter_id: int = Path(..., description="ID официанта (employee_id)"),
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY (по умолчанию сегодня)"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user=Depends(require_self_or_role("waiter_id", "Менеджер")),
):
    """
    Получить сумму продаж официанта за день и количество чеков.
    """
    try:
        sales = get_waiter_daily_sales(
            db=db,
            waiter_id=waiter_id,
            date=date,
            organization_id=organization_id,
        )
        if not sales:
            raise HTTPException(status_code=404, detail="Waiter not found or invalid date")

        return WaiterSalesResponse(
            date=sales["date"],
            totalAmount=sales["totalAmount"],
            ordersCount=sales["ordersCount"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting waiter sales: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


