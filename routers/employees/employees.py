from fastapi import APIRouter, Depends, Query, HTTPException, Path, Body
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from utils.security import get_current_user
from database.database import get_db
from services.employees.employees_service import get_employees
from schemas.employees import EmployeeArrayResponse, EmployeeWithShiftsArrayResponse
from schemas.fines import CreateFineRequest, CreateFineResponse, UpdateShiftTimeRequest, UpdateShiftTimeResponse
from models.penalty import Penalty
from models.user import User
from models.employees import Employees
from models.shifts import Shift
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["employees"])


@router.get("/employees", response_model=EmployeeWithShiftsArrayResponse)
def list_employees(
    name: Optional[str] = Query(default=None),
    login: Optional[str] = Query(default=None),
    organization_id: Optional[int] = Query(default=None),
    role_code: Optional[str] = Query(default=None),
    deleted: Optional[bool] = Query(default=None),
    status: Optional[str] = Query(default=None),
    date: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=0, le=5000, description="Количество записей. 0 = все записи без ограничения"),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить список сотрудников
    """
    employees = get_employees(
        db=db,
        name=name,
        login=login,
        organization_id=organization_id,
        role_code=role_code,
        deleted=deleted,
        status=status,
        date=date,
        limit=limit,
        offset=offset,
    )
    return {
        "success": True,
        "message": "got employees",
        "employees": employees,
    }


@router.post("/fines", response_model=CreateFineResponse)
def create_fine(
    fine_data: CreateFineRequest = Body(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Создать штраф для сотрудника
    
    **Request Body:**
    ```json
    {
      "employeeId": "1",
      "employeeName": "Аслан Аманов",
      "reason": "Опоздание на работу",
      "amount": 5000,
      "date": "15.01.2025"
    }
    ```
    """
    try:
        # Получаем сотрудника
        employee_id = int(fine_data.employeeId)
        employee = db.query(Employees).filter(Employees.id == employee_id).first()
        
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Пытаемся найти пользователя системы по iiko_id
        user_obj = db.query(User).filter(User.iiko_id == employee.iiko_id).first()
        
        # Создаем штраф (используем employee_id всегда, user_id - если найден)
        new_penalty = Penalty(
            penalty_sum=fine_data.amount,
            description=fine_data.reason,
            employee_id=employee_id,
            user_id=user_obj.id if user_obj else None
        )
        
        db.add(new_penalty)
        db.commit()
        db.refresh(new_penalty)
        
        return CreateFineResponse(
            success=True,
            message="Fine created successfully",
            fine_id=new_penalty.id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating fine: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/employees/{employee_id}/shift-time", response_model=UpdateShiftTimeResponse)
def update_employee_shift_time(
    employee_id: int = Path(..., description="ID сотрудника"),
    shift_data: UpdateShiftTimeRequest = Body(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Обновить время смены сотрудника
    
    **Request Body:**
    ```json
    {
      "shiftTime": "09:30"
    }
    ```
    """
    try:
        # Получаем сотрудника
        employee = db.query(Employees).filter(Employees.id == employee_id).first()
        
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Парсим время
        try:
            shift_time = datetime.strptime(shift_data.shiftTime, "%H:%M").time()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time format. Use HH:mm")
        
        # Получаем текущую смену сотрудника
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        shift = db.query(Shift).filter(
            Shift.employee_id == employee_id,
            Shift.start_time >= start_of_day
        ).order_by(Shift.start_time.desc()).first()
        
        if shift:
            # Обновляем время начала смены
            new_start_time = datetime.combine(shift.start_time.date(), shift_time)
            shift.start_time = new_start_time
            db.commit()
        
        return UpdateShiftTimeResponse(
            success=True,
            message="Shift time updated successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating shift time: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
