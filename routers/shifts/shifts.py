from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user
from database.database import get_db
from services.shifts.shifts_service import get_shifts, get_waiter_shift_status
from schemas.shifts import ShiftResponse, ShiftStatusResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["shifts"])


@router.get("/shifts", response_model=ShiftResponse)
def get_shifts_endpoint(
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY"),
    employee_id: Optional[int] = Query(default=None, description="ID сотрудника для фильтрации"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить информацию о смене
    
    **Query Parameters:**
    - `date` (optional): Дата в формате "DD.MM.YYYY" - дата смены (по умолчанию сегодня)
    - `employee_id` (optional): ID сотрудника для фильтрации
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - Информация о смене: время начала/окончания, количество сотрудников, выручка, штрафы, квесты
    """
    try:
        shift = get_shifts(
            db=db,
            date=date,
            employee_id=employee_id,
            organization_id=organization_id
        )
        return shift
    except Exception as e:
        logger.error(f"Error getting shifts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/waiter/{waiter_id}/shift/status", response_model=ShiftStatusResponse)
def get_waiter_shift_status_endpoint(
    waiter_id: int = Path(..., description="ID официанта"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Проверить активность смены официанта
    
    **Query Parameters:**
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - Статус смены: активна ли смена, время начала, прошедшее время
    """
    try:
        status = get_waiter_shift_status(
            db=db,
            waiter_id=waiter_id,
            organization_id=organization_id
        )
        return status
    except Exception as e:
        logger.error(f"Error getting waiter shift status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

