from pydantic import BaseModel
from typing import Optional


class UserProfileStats(BaseModel):
    """Статистика работы для официанта"""

    shiftDuration: Optional[str] = None  # HH:mm:ss
    totalAmount: Optional[float] = None
    ordersCount: Optional[int] = None


class UserProfileResponse(BaseModel):
    """Профиль пользователя с базовой информацией и, при необходимости, статистикой"""

    success: bool = True
    message: str = "User profile"

    id: int
    name: Optional[str] = None
    login: str
    role: Optional[str] = None
    organization_id: Optional[int] = None
    employee_id: Optional[int] = None  # ID из таблицы employees (связь через iiko_id)

    stats: Optional[UserProfileStats] = None

