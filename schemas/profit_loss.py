from pydantic import BaseModel
from typing import List, Optional


class RevenueByCategory(BaseModel):
    """Доход по категории"""
    category: str  # "Кухня" или "Бар"
    amount: float


class ExpenseByType(BaseModel):
    """Расход по типу"""
    transaction_type: str
    transaction_name: str
    amount: float


class ProfitLossResponse(BaseModel):
    """Отчет о прибылях и убытках"""
    success: bool
    message: str
    
    # Доходы
    total_revenue: float  # Общий доход
    revenue_by_category: List[RevenueByCategory]  # Доходы по категориям (Кухня, Бар)
    
    # Расходы
    total_expenses: float  # Общие расходы
    expenses_by_type: List[ExpenseByType]  # Расходы по типам
    
    # Комиссии банка
    bank_commission: float  # Комиссия банка
    
    # Прибыль
    gross_profit: float  # Валовая прибыль (Доход - Расходы - Комиссия)
    profit_margin: Optional[float]  # Маржа прибыли в процентах
    
    class Config:
        from_attributes = True

