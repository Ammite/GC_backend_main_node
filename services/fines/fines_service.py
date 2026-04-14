"""
Сервис для работы со штрафами
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional, Dict, Any
from datetime import datetime
from models.penalty import Penalty
from models.employees import Employees


def get_fines_summary(
    db: Session,
    date: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Получить сводку всех штрафов за день
    
    Args:
        db: сессия БД
        date: Дата в формате DD.MM.YYYY (по умолчанию сегодня)
        organization_id: ID организации для фильтрации
        
    Returns:
        Массив штрафов с:
        - id, employeeId, employeeName
        - amount, reason, date
        - createdAt
    """
    # Парсим дату
    if date:
        try:
            target_date = datetime.strptime(date, "%d.%m.%Y")
        except ValueError:
            target_date = datetime.now()
    else:
        target_date = datetime.now()
    
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Получаем штрафы за день
    fines_query = db.query(Penalty).filter(
        and_(
            Penalty.created_at >= start_of_day,
            Penalty.created_at <= end_of_day
        )
    )
    
    # Фильтруем по организации через Employees
    if organization_id is not None:
        fines_query = fines_query.join(
            Employees, Penalty.employee_id == Employees.id
        ).filter(Employees.preferred_organization_id == organization_id)
    
    fines = fines_query.order_by(Penalty.created_at.desc()).all()
    
    result = []
    for fine in fines:
        employee = None
        employee_name = None
        if fine.employee_id:
            employee = db.query(Employees).filter(Employees.id == fine.employee_id).first()
            if employee:
                employee_name = employee.name
        
        result.append({
            "id": fine.id,
            "employeeId": fine.employee_id,
            "employeeName": employee_name or "",
            "amount": float(fine.penalty_sum),
            "reason": fine.description or "",
            "date": target_date.strftime("%d.%m.%Y"),
            "createdAt": fine.created_at.isoformat() if fine.created_at else None
        })
    
    return result


def update_fine(
    db: Session,
    fine_id: int,
    amount: Optional[float] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Изменить штраф
    
    Args:
        db: сессия БД
        fine_id: ID штрафа
        amount: Новая сумма (опционально)
        reason: Новая причина (опционально)
        
    Returns:
        Словарь с результатом обновления
    """
    fine = db.query(Penalty).filter(Penalty.id == fine_id).first()
    if not fine:
        raise ValueError(f"Fine with id {fine_id} not found")
    
    if amount is not None:
        fine.penalty_sum = amount
    if reason is not None:
        fine.description = reason
    
    fine.updated_at = datetime.now()
    db.commit()
    db.refresh(fine)
    
    return {
        "success": True,
        "message": "Fine updated successfully",
        "fine_id": fine.id
    }


def delete_fine(
    db: Session,
    fine_id: int,
) -> Dict[str, Any]:
    """
    Удалить штраф
    
    Args:
        db: сессия БД
        fine_id: ID штрафа
        
    Returns:
        Словарь с результатом удаления
    """
    fine = db.query(Penalty).filter(Penalty.id == fine_id).first()
    if not fine:
        raise ValueError(f"Fine with id {fine_id} not found")
    
    db.delete(fine)
    db.commit()
    
    return {
        "success": True,
        "message": "Fine deleted successfully"
    }

