from pydantic import BaseModel
from typing import Optional


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

