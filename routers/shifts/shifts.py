from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user, require_role, require_self_or_role
from database.database import get_db
from models.user import User
from models.employees import Employees
from services.shifts.shifts_service import get_shifts, get_waiter_shift_status, start_shift, end_shift, clockin_employee_in_iiko, clockout_employee_in_iiko
from schemas.shifts import ShiftResponse, ShiftStatusResponse, StartShiftResponse, EndShiftResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["shifts"])


def _resolve_employee_id(db: Session, waiter_id: int) -> int:
    """
    Резолвит waiter_id в employee_id.
    Фронт передаёт user_id, поэтому сначала пробуем найти User → Employee.
    Если не нашли — считаем что передан employee_id напрямую.
    """
    user = db.query(User).filter(User.id == waiter_id).first()
    if user and user.iiko_id:
        employee = db.query(Employees).filter(Employees.iiko_id == user.iiko_id).first()
        if employee:
            return employee.id
    # Фолбэк: может быть передан employee_id напрямую
    employee = db.query(Employees).filter(Employees.id == waiter_id).first()
    if employee:
        return employee.id
    raise ValueError(f"Employee not found for waiter_id {waiter_id}")


@router.get("/shifts", response_model=ShiftResponse)
def get_shifts_endpoint(
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY"),
    employee_id: Optional[int] = Query(default=None, description="ID сотрудника для фильтрации"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
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
    waiter_id: int = Path(..., description="ID пользователя или сотрудника"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(require_self_or_role("waiter_id", "Менеджер")),
):
    """
    Проверить активность смены официанта.
    waiter_id — принимает как user_id, так и employee_id (автоматически резолвится).
    """
    try:
        employee_id = _resolve_employee_id(db, waiter_id)
        status = get_waiter_shift_status(
            db=db,
            waiter_id=employee_id,
            organization_id=organization_id
        )
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting waiter shift status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/waiter/{waiter_id}/shift/start", response_model=StartShiftResponse)
async def start_waiter_shift(
    waiter_id: int = Path(..., description="ID пользователя или сотрудника"),
    organization_id: Optional[int] = Query(default=None, description="ID организации"),
    db: Session = Depends(get_db),
    user=Depends(require_self_or_role("waiter_id", "Менеджер")),
):
    """
    Запустить смену официанта.
    waiter_id — принимает как user_id, так и employee_id (автоматически резолвится).

    - Если активная смена уже есть, просто возвращаем её ID.
    - Если нет — создаём новую смену с текущим временем.
    """
    try:
        employee_id = _resolve_employee_id(db, waiter_id)

        shift = start_shift(
            db=db,
            waiter_id=employee_id,
            organization_id=organization_id,
        )

        message = "Shift started"
        if shift.end_time is None and shift.start_time:
            message = "Shift is active"

        return StartShiftResponse(
            success=True,
            message=message,
            shiftId=shift.id,
        )
    except ValueError as e:
        logger.error(f"Error starting shift: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting shift: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/waiter/{waiter_id}/shift/end", response_model=EndShiftResponse)
async def end_waiter_shift(
    waiter_id: int = Path(..., description="ID пользователя или сотрудника"),
    organization_id: Optional[int] = Query(default=None, description="ID организации"),
    db: Session = Depends(get_db),
    user=Depends(require_self_or_role("waiter_id", "Менеджер")),
):
    """
    Завершить активную смену официанта.
    waiter_id — принимает как user_id, так и employee_id (автоматически резолвится).

    - Находит активную смену (end_time is NULL).
    - Устанавливает end_time = текущее время.
    """
    try:
        employee_id = _resolve_employee_id(db, waiter_id)

        shift = end_shift(
            db=db,
            waiter_id=employee_id,
            organization_id=organization_id,
        )

        try:
            await clockout_employee_in_iiko(db=db, employee_id=employee_id, organization_id=organization_id)
        except Exception:
            logger.warning(f"Failed to clockout employee {employee_id} in iiko")

        return EndShiftResponse(
            success=True,
            message="Shift ended successfully",
            shiftId=shift.id,
            startTime=shift.start_time.strftime("%H:%M") if shift.start_time else None,
            endTime=shift.end_time.strftime("%H:%M") if shift.end_time else None,
        )
    except ValueError as e:
        logger.error(f"Error ending shift: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error ending shift: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

