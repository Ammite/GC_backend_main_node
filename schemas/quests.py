from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class QuestResponse(BaseModel):
    """Схема ответа для квеста"""
    id: str
    title: str
    description: str
    reward: float  # Награда в тенге
    current: int  # Текущее значение
    target: int  # Целевое значение
    unit: str  # Единица измерения ("десерт", "стейк", "заказов")
    completed: bool
    progress: float  # Процент выполнения (0-100)
    expiresAt: Optional[str] = None  # ISO 8601

    class Config:
        from_attributes = True


class QuestsArrayResponse(BaseModel):
    """Схема ответа для списка квестов"""
    quests: List[QuestResponse]


class EmployeeQuestProgress(BaseModel):
    """Прогресс сотрудника по квесту"""
    employeeId: str
    employeeName: str
    progress: float  # 0-100
    completed: bool
    points: int
    rank: int


class QuestDetailResponse(QuestResponse):
    """Детальная информация о квесте (для CEO)"""
    totalEmployees: int
    completedEmployees: int
    employeeNames: List[str]
    date: str  # "DD.MM.YYYY"
    employeeProgress: List[EmployeeQuestProgress]


class CreateQuestRequest(BaseModel):
    """Запрос на создание квеста"""
    title: str
    description: str
    reward: float
    target: int
    unit: str
    date: str  # "DD.MM.YYYY"
    employeeIds: Optional[List[str]] = None  # Опционально, если для конкретных сотрудников
    organization_id: Optional[int] = None


class CreateQuestResponse(BaseModel):
    """Ответ на создание квеста"""
    success: bool
    message: str
    quest: QuestResponse

