from pydantic import BaseModel
from typing import Optional


class ShiftResponse(BaseModel):
    """Информация о смене"""
    id: str
    date: str  # "DD.MM.YYYY"
    startTime: str  # "HH:mm"
    endTime: Optional[str] = None  # "HH:mm"
    elapsedTime: str  # "HH:mm:ss"
    openEmployees: int
    totalAmount: float
    finesCount: int
    motivationCount: int  # Количество квестов
    questsCount: int
    status: str  # "active" | "completed" | "cancelled"

    class Config:
        from_attributes = True


class ShiftStatusResponse(BaseModel):
    """Статус смены официанта"""
    isActive: bool
    shiftId: Optional[str] = None
    startTime: Optional[str] = None  # "HH:mm"
    elapsedTime: Optional[str] = None  # "HH:mm:ss"

    class Config:
        from_attributes = True


class StartShiftResponse(BaseModel):
    """Ответ на запуск смены официанта"""

    success: bool
    message: str
    shiftId: int


class EndShiftResponse(BaseModel):
    """Ответ на завершение смены официанта"""

    success: bool
    message: str
    shiftId: int
    startTime: Optional[str] = None  # "HH:mm"
    endTime: Optional[str] = None  # "HH:mm"

