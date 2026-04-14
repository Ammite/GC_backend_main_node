from fastapi import APIRouter, Depends, Query, HTTPException, Path, Body
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from utils.security import get_current_user
from database.database import get_db
from services.employees.employees_service import get_employees, get_employees_summary, get_employee_summary, get_employee_details, get_employee_open_check, get_employee_closed_tables_history, create_users_for_all_employees, regenerate_user_logins, recreate_all_credentials
from schemas.employees import EmployeeArrayResponse, EmployeeWithShiftsArrayResponse, EmployeesSummaryResponse, EmployeeSummaryResponse, EmployeeDetailsResponse, EmployeeOpenCheckResponse, EmployeeClosedTablesHistoryResponse
from schemas.fines import (
    CreateFineRequest, CreateFineResponse, UpdateShiftTimeRequest, UpdateShiftTimeResponse,
    FinesSummaryResponse, UpdateFineRequest, UpdateFineResponse, DeleteFineResponse
)
from services.fines.fines_service import get_fines_summary, update_fine, delete_fine
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


@router.get("/employees/summary", response_model=EmployeesSummaryResponse)
def get_employees_summary_endpoint(
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY (по умолчанию сегодня)"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить сводку по сотрудникам - количество сотрудников с открытой смены и их сумма чеков
    
    **Query Parameters:**
    - `date` (optional): Дата в формате "DD.MM.YYYY" (по умолчанию сегодня)
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - activeEmployeesCount: количество сотрудников с открытой сменой
    - totalAmount: общая сумма чеков активных сотрудников
    - employees: массив с id, name, amount для каждого активного сотрудника
    """
    try:
        summary = get_employees_summary(
            db=db,
            date=date,
            organization_id=organization_id
        )
        return summary
    except Exception as e:
        logger.error(f"Error getting employees summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/employees/{employee_id}/summary", response_model=EmployeeSummaryResponse)
def get_employee_summary_endpoint(
    employee_id: int = Path(..., description="ID сотрудника"),
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY (по умолчанию сегодня)"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить сводку по конкретному сотруднику - имя фамилия сотрудника, длительность смены и сумма
    
    **Path Parameters:**
    - `employee_id`: ID сотрудника
    
    **Query Parameters:**
    - `date` (optional): Дата в формате "DD.MM.YYYY" (по умолчанию сегодня)
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - id, firstName, lastName, name
    - shiftDuration: длительность смены в формате HH:mm:ss
    - totalAmount: сумма чеков за день
    - ordersCount: количество чеков за день
    """
    try:
        summary = get_employee_summary(
            db=db,
            employee_id=employee_id,
            date=date,
            organization_id=organization_id
        )
        return summary
    except ValueError as e:
        logger.error(f"Error getting employee summary: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting employee summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/employees/{employee_id}/details", response_model=EmployeeDetailsResponse)
def get_employee_details_endpoint(
    employee_id: int = Path(..., description="ID сотрудника"),
    table_id: Optional[int] = Query(default=None, description="ID стола для фильтрации"),
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY (по умолчанию сегодня)"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить детали по одному сотруднику - длительность смены, сумма чеков и столы на которых открыты чеки
    
    **Path Parameters:**
    - `employee_id`: ID сотрудника
    
    **Query Parameters:**
    - `table_id` (optional): ID стола для фильтрации
    - `date` (optional): Дата в формате "DD.MM.YYYY" (по умолчанию сегодня)
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - shiftDuration: длительность смены в формате HH:mm:ss
    - totalAmount: сумма чеков за день
    - ordersCount: количество чеков за день
    - tables: массив столов с id, number, roomName, orderId, amount
    """
    try:
        details = get_employee_details(
            db=db,
            employee_id=employee_id,
            table_id=table_id,
            date=date,
            organization_id=organization_id
        )
        return details
    except ValueError as e:
        logger.error(f"Error getting employee details: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting employee details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/employees/{employee_id}/open-check", response_model=EmployeeOpenCheckResponse)
def get_employee_open_check_endpoint(
    employee_id: int = Path(..., description="ID сотрудника"),
    dateTime: str = Query(..., description="Дата и время в формате ISO (YYYY-MM-DDTHH:mm:ssZ)"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить детали открытого счета сотрудника - содержимое чека
    
    **Path Parameters:**
    - `employee_id`: ID сотрудника
    
    **Query Parameters:**
    - `dateTime` (required): Дата и время в формате ISO (YYYY-MM-DDTHH:mm:ssZ или YYYY-MM-DDTHH:mm:ss)
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - orderId: ID заказа
    - tableId, tableNumber, roomName: информация о столе
    - items: массив блюд с name, quantity, price, total
    - totalAmount: общая сумма
    - status: статус заказа
    """
    try:
        check = get_employee_open_check(
            db=db,
            employee_id=employee_id,
            date_time=dateTime,
            organization_id=organization_id
        )
        return check
    except ValueError as e:
        logger.error(f"Error getting employee open check: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting employee open check: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/employees/{employee_id}/closed-tables-history", response_model=EmployeeClosedTablesHistoryResponse)
def get_employee_closed_tables_history_endpoint(
    employee_id: int = Path(..., description="ID сотрудника"),
    from_date: Optional[str] = Query(default=None, description="Дата начала периода в формате DD.MM.YYYY"),
    to_date: Optional[str] = Query(default=None, description="Дата конца периода в формате DD.MM.YYYY"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Посмотреть историю закрытых столиков сотрудника - список чеков закрытых сотрудником и суммы
    
    **Path Parameters:**
    - `employee_id`: ID сотрудника
    
    **Query Parameters:**
    - `from_date` (optional): Дата начала периода в формате "DD.MM.YYYY" (по умолчанию 30 дней назад)
    - `to_date` (optional): Дата конца периода в формате "DD.MM.YYYY" (по умолчанию сегодня)
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - Массив закрытых чеков с:
      - orderId, tableId, tableNumber, roomName
      - closedAt: дата/время закрытия в формате ISO
      - totalAmount: сумма чека
      - itemsCount: количество позиций в чеке
    """
    try:
        orders = get_employee_closed_tables_history(
            db=db,
            employee_id=employee_id,
            from_date=from_date,
            to_date=to_date,
            organization_id=organization_id
        )
        return {
            "success": True,
            "message": f"История закрытых столиков сотрудника {employee_id}",
            "orders": orders
        }
    except ValueError as e:
        logger.error(f"Error getting employee closed tables history: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting employee closed tables history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/fines/summary", response_model=FinesSummaryResponse)
def get_fines_summary_endpoint(
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY (по умолчанию сегодня)"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить сводку всех штрафов - список всех штрафов за текущий день
    
    **Query Parameters:**
    - `date` (optional): Дата в формате "DD.MM.YYYY" (по умолчанию сегодня)
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - Массив штрафов с:
      - id, employeeId, employeeName
      - amount, reason, date
      - createdAt: дата/время создания в формате ISO
    """
    try:
        fines = get_fines_summary(
            db=db,
            date=date,
            organization_id=organization_id
        )
        return {
            "success": True,
            "message": f"Сводка штрафов за {date or 'сегодня'}",
            "fines": fines
        }
    except Exception as e:
        logger.error(f"Error getting fines summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/fines/{fine_id}", response_model=UpdateFineResponse)
def update_fine_endpoint(
    fine_id: int = Path(..., description="ID штрафа"),
    fine_data: UpdateFineRequest = Body(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Изменить штраф сотруднику
    
    **Path Parameters:**
    - `fine_id`: ID штрафа
    
    **Request Body:**
    ```json
    {
      "amount": 5000,  // Опционально
      "reason": "Новая причина"  // Опционально
    }
    ```
    
    **Response:**
    - success, message, fine_id
    """
    try:
        result = update_fine(
            db=db,
            fine_id=fine_id,
            amount=fine_data.amount,
            reason=fine_data.reason
        )
        return result
    except ValueError as e:
        logger.error(f"Error updating fine: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating fine: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/fines/{fine_id}", response_model=DeleteFineResponse)
def delete_fine_endpoint(
    fine_id: int = Path(..., description="ID штрафа"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Удалить штраф сотрудника

    **Path Parameters:**
    - `fine_id`: ID штрафа

    **Response:**
    - success, message
    """
    try:
        result = delete_fine(db=db, fine_id=fine_id)
        return result
    except ValueError as e:
        logger.error(f"Error deleting fine: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting fine: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/employees/create-users")
def create_users_for_employees_endpoint(
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Создать пользователей для всех сотрудников, у которых ещё нет учётной записи.

    Логин = имя сотрудника. Пароль генерируется случайно (8 символов).
    Возвращает список созданных пользователей с паролями (для передачи менеджеру).

    Требуется роль: manager или owner.
    """
    try:
        created = create_users_for_all_employees(db=db)
        return {
            "success": True,
            "message": f"Создано пользователей: {len(created)}",
            "count": len(created),
            "users": created,
        }
    except Exception as e:
        logger.error(f"Error creating users for employees: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/employees/regenerate-logins")
def regenerate_logins_endpoint(
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Перегенерировать логины всех пользователей на латиницу (кроме admin и ofik).

    Пароли НЕ меняются. Логин = транслитерация имени сотрудника (латиница, точка вместо пробела).
    """
    try:
        updated = regenerate_user_logins(db=db)
        return {
            "success": True,
            "message": f"Обновлено логинов: {len(updated)}",
            "count": len(updated),
            "users": updated,
        }
    except Exception as e:
        logger.error(f"Error regenerating logins: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Endpoint /employees/recreate-credentials отключён:
# одноразовая операция выполнена, повторный запуск перезапишет все пароли.
# Логика остаётся в services.employees.employees_service.recreate_all_credentials
# на случай, если понадобится вызвать её вручную.
