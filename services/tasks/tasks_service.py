from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime
import logging

from models.task import Task
from models.employees import Employees

logger = logging.getLogger(__name__)


def get_tasks(
    db: Session,
    organization_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    date: Optional[str] = None,
    due_date: Optional[str] = None,
) -> List[Task]:
    query = db.query(Task)

    if organization_id is not None:
        query = query.filter(Task.organization_id == organization_id)
    if employee_id is not None:
        query = query.filter(Task.employee_id == employee_id)
    if date:
        try:
            target_date = datetime.strptime(date, "%d.%m.%Y").replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            query = query.filter(Task.due_date >= target_date)
        except ValueError:
            pass
    if due_date:
        try:
            target_date = datetime.strptime(due_date, "%d.%m.%Y")
            start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            query = query.filter(Task.due_date >= start_of_day, Task.due_date <= end_of_day)
        except ValueError:
            pass

    return query.order_by(Task.created_at.desc()).all()


def create_task(
    db: Session,
    description: str,
    employee_id: int,
    title: Optional[str] = None,
    organization_id: Optional[int] = None,
    due_date: Optional[str] = None,
) -> Task:
    # Проверяем что сотрудник существует
    employee = db.query(Employees).filter(Employees.id == employee_id).first()
    if not employee:
        raise ValueError(f"Employee with id {employee_id} not found")

    # Парсим дату
    parsed_due_date = None
    if due_date:
        try:
            parsed_due_date = datetime.strptime(due_date, "%d.%m.%Y").replace(
                hour=23, minute=59, second=59
            )
        except ValueError:
            pass

    new_task = Task(
        title=title if title else None,
        description=description,
        employee_id=employee_id,
        organization_id=organization_id,
        is_completed=False,
        due_date=parsed_due_date,
    )

    db.add(new_task)
    db.flush()

    # Если название не задано — генерируем по шаблону
    if not new_task.title:
        employee = db.query(Employees).filter(Employees.id == employee_id).first()
        employee_name = employee.name if employee and employee.name else f"Employee {employee_id}"
        new_task.title = f"Задача для {employee_name} #{new_task.id}"

    db.commit()
    db.refresh(new_task)
    return new_task


def complete_task(
    db: Session,
    task_id: int,
) -> Task:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise ValueError(f"Task with id {task_id} not found")

    task.is_completed = not task.is_completed
    db.commit()
    db.refresh(task)

    logger.info(f"Task {task_id} is_completed toggled to {task.is_completed}")
    return task
