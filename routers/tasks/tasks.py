from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from utils.security import get_current_user, require_role
from database.database import get_db
from models.employees import Employees
from services.tasks.tasks_service import get_tasks, create_task, complete_task
from schemas.tasks import (
    TaskResponse,
    TaskListResponse,
    CreateTaskRequest,
    CreateTaskResponse,
    CompleteTaskResponse,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["tasks"])


def _task_to_response(task, db) -> TaskResponse:
    employee = db.query(Employees).filter(Employees.id == task.employee_id).first()
    return TaskResponse(
        id=task.id,
        title=task.title or "",
        description=task.description,
        employee_id=task.employee_id,
        employee_name=employee.name if employee else None,
        organization_id=task.organization_id,
        is_completed=task.is_completed,
        due_date=task.due_date.strftime("%d.%m.%Y") if task.due_date else None,
        created_at=task.created_at.isoformat() if task.created_at else None,
    )


@router.get("/tasks", response_model=TaskListResponse)
def get_tasks_endpoint(
    organization_id: Optional[int] = Query(default=None, description="ID организации"),
    employee_id: Optional[int] = Query(default=None, description="ID сотрудника"),
    date: Optional[str] = Query(default=None, description="Дата DD.MM.YYYY — вернуть таски с due_date >= этой даты"),
    due_date: Optional[str] = Query(default=None, description="Точная дата дедлайна DD.MM.YYYY"),
    date_from: Optional[str] = Query(default=None, description="DD.MM.YYYY — нижняя граница due_date (приоритет над date)"),
    date_to: Optional[str] = Query(default=None, description="DD.MM.YYYY — верхняя граница due_date (приоритет над date)"),
    db: Session = Depends(get_db),
    user=Depends(require_role("Менеджер")),
):
    """
    Получить список задач.

    Все ID — внутренние (из БД). Фильтрация по organization_id, employee_id, диапазону дат.
    Время created_at возвращается в часовом поясе UTC+5.

    **Параметры:**
    - **organization_id** (int, опц.): фильтр по организации
    - **employee_id** (int, опц.): ID сотрудника
    - **date_from / date_to** (str, опц.): DD.MM.YYYY — интервал по `due_date`.
      Если ни один параметр диапазона/даты не задан — по умолчанию выбираются **последние 7 дней**.
    - **date** (str, опц.): DD.MM.YYYY — вернуть таски с due_date >= этой даты (legacy)
    - **due_date** (str, опц.): DD.MM.YYYY — точная дата дедлайна (legacy)
    """
    try:
        # Если фронт ничего не передал — выставляем дефолт «последние 7 дней».
        if not any([date, due_date, date_from, date_to]):
            today = datetime.now().date()
            date_to = today.strftime("%d.%m.%Y")
            date_from = (today - timedelta(days=7)).strftime("%d.%m.%Y")

        tasks = get_tasks(
            db=db,
            organization_id=organization_id,
            employee_id=employee_id,
            date=date,
            due_date=due_date,
            date_from=date_from,
            date_to=date_to,
        )
        return TaskListResponse(
            tasks=[_task_to_response(t, db) for t in tasks]
        )
    except Exception as e:
        logger.error(f"Error getting tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/tasks", response_model=CreateTaskResponse)
def create_task_endpoint(
    data: CreateTaskRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role("Менеджер")),
):
    """
    Создать новую задачу.

    user_id — внутренний ID пользователя (User.id). due_date в формате DD.MM.YYYY.
    created_at проставляется в часовом поясе UTC+5.

    **Поля запроса:**
    - **title** (str, опц.): название задачи (если не указано — генерируется автоматически)
    - **description** (str, обяз.): описание задачи
    - **employee_id** (int, обяз.): ID сотрудника-исполнителя
    - **organization_id** (int, опц.): ID организации
    - **due_date** (str, опц.): дедлайн DD.MM.YYYY
    """
    try:
        task = create_task(
            db=db,
            description=data.description,
            employee_id=data.employee_id,
            title=data.title,
            organization_id=data.organization_id,
            due_date=data.due_date,
        )
        return CreateTaskResponse(
            success=True,
            message="Task created successfully",
            task=_task_to_response(task, db),
        )
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/tasks/{task_id}/complete", response_model=CompleteTaskResponse)
def complete_task_endpoint(
    task_id: int = Path(..., description="ID задачи"),
    db: Session = Depends(get_db),
    user=Depends(require_role("Менеджер")),
):
    """
    Переключить статус задачи (выполнена / не выполнена).

    **task_id** — внутренний ID задачи. Возвращает 404, если задача не найдена.
    updated_at обновляется в часовом поясе UTC+5.
    """
    try:
        task = complete_task(db=db, task_id=task_id)
        return CompleteTaskResponse(
            success=True,
            message="Task completed" if task.is_completed else "Task uncompleted",
            task=_task_to_response(task, db),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error completing task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
