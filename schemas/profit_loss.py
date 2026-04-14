from pydantic import BaseModel
from typing import List, Optional


class RevenueByCategory(BaseModel):
    """Доход по категории"""
    id: str  # metric_key, например "revenue_kitchen", "revenue_bar"
    category: str  # "Кухня" или "Бар"
    amount: float


class ExpenseByType(BaseModel):
    """Расход по типу"""
    id: str  # например "expense_account:Аренда", "cost_goods_total", "bank_commission"
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


class ProfitLossDetailByOrg(BaseModel):
    """Детализация по одной организации"""
    organization_id: int
    organization_name: str
    amount: float


class ProfitLossDetailResponse(BaseModel):
    """Ответ детализации статьи P&L по организациям"""
    success: bool
    item_id: str
    item_type: str  # "revenue" или "expense"
    item_name: str
    total: float
    by_organization: List[ProfitLossDetailByOrg]

