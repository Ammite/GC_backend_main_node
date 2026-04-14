from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    organization_id: Optional[int] = None
    is_completed: bool
    due_date: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]


class CreateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: str
    employee_id: int
    organization_id: Optional[int] = None
    due_date: Optional[str] = None  # "DD.MM.YYYY"


class CreateTaskResponse(BaseModel):
    success: bool
    message: str
    task: TaskResponse


class CompleteTaskResponse(BaseModel):
    success: bool
    message: str
    task: TaskResponse
