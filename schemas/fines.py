from pydantic import BaseModel
from typing import Optional, List


class CreateFineRequest(BaseModel):
    """Запрос на создание штрафа"""
    employeeId: str
    employeeName: str
    reason: str
    amount: float
    date: str  # "DD.MM.YYYY"


class CreateFineResponse(BaseModel):
    """Ответ на создание штрафа"""
    success: bool
    message: str
    fine_id: int


class UpdateShiftTimeRequest(BaseModel):
    """Запрос на обновление времени смены"""
    shiftTime: str  # "HH:mm"


class UpdateShiftTimeResponse(BaseModel):
    """Ответ на обновление времени смены"""
    success: bool
    message: str


class FineItem(BaseModel):
    """Элемент штрафа"""
    id: int
    employeeId: Optional[int] = None
    employeeName: str
    amount: float
    reason: str
    date: str
    createdAt: Optional[str] = None


class FinesSummaryResponse(BaseModel):
    """Сводка всех штрафов"""
    success: bool
    message: str
    fines: List[FineItem]


class UpdateFineRequest(BaseModel):
    """Запрос на обновление штрафа"""
    amount: Optional[float] = None
    reason: Optional[str] = None


class UpdateFineResponse(BaseModel):
    """Ответ на обновление штрафа"""
    success: bool
    message: str
    fine_id: int


class DeleteFineResponse(BaseModel):
    """Ответ на удаление штрафа"""
    success: bool
    message: str

