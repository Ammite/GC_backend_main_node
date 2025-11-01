from pydantic import BaseModel
from typing import List, Optional
from schemas.analytics import ChangeMetric


class CheckMetric(BaseModel):
    """Метрика чека"""
    id: int
    label: str
    value: str
    type: Optional[str] = None  # "negative" | "positive"


class ReturnMetric(BaseModel):
    """Метрика возвратов"""
    id: int
    label: str
    value: str
    type: Optional[str] = None  # "negative" | "positive"


class AverageMetric(BaseModel):
    """Средняя метрика"""
    id: int
    label: str
    value: str
    change: Optional[ChangeMetric] = None


class OrderReportsResponse(BaseModel):
    """Отчеты по заказам"""
    checks: CheckMetric
    returns: ReturnMetric
    averages: List[AverageMetric]

    class Config:
        from_attributes = True


class DishCost(BaseModel):
    """Стоимость блюда"""
    id: int
    name: str
    amount: float
    quantity: int


class WriteoffItem(BaseModel):
    """Элемент списания"""
    id: int
    item: str
    quantity: int
    reason: str


class ExpenseItem(BaseModel):
    """Элемент расхода"""
    id: int
    reason: str
    amount: float
    date: str


class IncomeItem(BaseModel):
    """Элемент дохода"""
    id: int
    source: str
    amount: float
    date: str


class DishesMetric(BaseModel):
    """Метрика блюд"""
    id: int
    label: str
    value: str
    data: List[DishCost]


class WriteoffsMetric(BaseModel):
    """Метрика списаний"""
    id: int
    label: str
    value: str
    data: List[WriteoffItem]


class ExpensesMetric(BaseModel):
    """Метрика расходов"""
    id: int
    label: str
    value: str
    type: str  # "negative"
    data: List[ExpenseItem]


class IncomesMetric(BaseModel):
    """Метрика доходов"""
    id: int
    label: str
    value: str
    type: str  # "positive"
    data: List[IncomeItem]


class MoneyFlowResponse(BaseModel):
    """Денежные потоки"""
    dishes: DishesMetric
    writeoffs: WriteoffsMetric
    expenses: ExpensesMetric
    incomes: IncomesMetric

    class Config:
        from_attributes = True

