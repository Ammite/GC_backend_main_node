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
    category: Optional[str] = None  # Категория меню
    payment_type: Optional[str] = None  # Тип оплаты


class IncomeByCategoryItem(BaseModel):
    """Доход по категории меню"""
    id: int
    category: str  # Название категории (Горячие блюда, Напитки и т.д.)
    amount: float


class IncomeByPaymentItem(BaseModel):
    """Доход по типу оплаты"""
    id: int
    payment_type: str  # Тип оплаты (Kaspi, Наличные и т.д.)
    amount: float


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
    income_by_category: List[IncomeByCategoryItem]  # Доходы по категориям меню
    income_by_pay_type: List[IncomeByPaymentItem]   # Доходы по типам оплаты


class MoneyFlowResponse(BaseModel):
    """Денежные потоки"""
    dishes: DishesMetric
    writeoffs: WriteoffsMetric
    expenses: ExpensesMetric
    incomes: IncomesMetric

    class Config:
        from_attributes = True

