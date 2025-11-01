from pydantic import BaseModel
from typing import List, Optional


class ChangeMetric(BaseModel):
    """Метрика изменения"""
    value: str  # "+21%", "-28%"
    trend: str  # "up" | "down"


class Metric(BaseModel):
    """Метрика аналитики"""
    id: int
    label: str
    value: str  # Форматированная строка
    change: Optional[ChangeMetric] = None


class Report(BaseModel):
    """Отчет"""
    id: int
    title: str
    value: str  # Форматированная строка
    date: str  # "DD.MM"
    type: str  # "expense" | "income"


class OrderMetric(BaseModel):
    """Метрика заказов"""
    id: int
    label: str
    value: str
    type: Optional[str] = None  # "negative" | "positive"


class FinancialMetric(BaseModel):
    """Финансовая метрика"""
    id: int
    label: str
    value: str
    type: Optional[str] = None  # "negative" | "positive"


class InventoryMetric(BaseModel):
    """Метрика инвентаря"""
    id: int
    label: str
    value: str
    type: Optional[str] = None  # "negative" | "positive"


class EmployeeAnalytic(BaseModel):
    """Аналитика по сотруднику"""
    id: int
    name: str
    amount: str  # Форматированная сумма
    avatar: str


class AnalyticsResponse(BaseModel):
    """Ответ с аналитикой (для CEO)"""
    metrics: List[Metric]
    reports: List[Report]
    orders: List[OrderMetric]
    financial: List[FinancialMetric]
    inventory: List[InventoryMetric]
    employees: List[EmployeeAnalytic]

    class Config:
        from_attributes = True

