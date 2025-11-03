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

class ExpenseTransactionItem(BaseModel):
    """Отдельная транзакция расхода"""
    transaction_id: int
    transaction_type: str  # К примеру "EXPENSES"
    transaction_name: str  # К примеру "Расходы на зарплату"
    transaction_amount: float  # К примеру 1000.00
    transaction_datetime: str  # К примеру "2025-01-01 10:00:00"
    transaction_comment: Optional[str]  # К примеру "Расходы на зарплату"


class ExpenseTypeData(BaseModel):
    """Группа расходов по типу"""
    transaction_type: str  # К примеру "EXPENSES"
    transaction_name: str  # К примеру "Расходы на зарплату"
    transaction_amount: float  # Сумма всех транзакций по этому типу
    transactions: List[ExpenseTransactionItem]


class ExpensesAnalyticsResponse(BaseModel):
    """Ответ с аналитикой расходов"""
    success: bool
    message: str
    expenses_amount: float  # Сумма всех расходов
    data: List[ExpenseTypeData]
    
    class Config:
        from_attributes = True