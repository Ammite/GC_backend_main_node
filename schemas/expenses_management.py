from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CreateExpenseRequest(BaseModel):
    """Запрос на создание расхода"""
    organization_id: Optional[int] = None
    expense_type: str  # UUID типа изъятия из iiko (pay_out_type_id)
    amount: float
    date: str  # "DD.MM.YYYY" или ISO формат
    comment: Optional[str] = None
    account_id: Optional[str] = None  # ID счета из Account (iiko_id)
    counteragent_id: Optional[int] = None  # ID контрагента из нашей БД (employees/suppliers, зависит от counteragentType)


class CreateExpenseResponse(BaseModel):
    """Ответ на создание расхода"""
    success: bool
    message: str
    expense_id: int


class ExpenseItem(BaseModel):
    """Элемент расхода"""
    id: int
    organization_id: Optional[int] = None
    expense_type: str
    amount: float
    date: str  # ISO формат
    comment: Optional[str] = None
    account_id: Optional[str] = None
    created_by: Optional[int] = None
    created_at: str  # ISO формат
    updated_at: str  # ISO формат

    class Config:
        from_attributes = True


class ExpensesListResponse(BaseModel):
    """Список расходов"""
    success: bool
    message: str
    expenses: List[ExpenseItem]
    total: float  # Общая сумма расходов


class ExpenseDetailResponse(BaseModel):
    """Детали расхода"""
    success: bool
    message: str
    expense: ExpenseItem


class UpdateExpenseRequest(BaseModel):
    """Запрос на обновление расхода"""
    expense_type: Optional[str] = None
    amount: Optional[float] = None
    date: Optional[str] = None  # "DD.MM.YYYY" или ISO формат
    comment: Optional[str] = None
    account_id: Optional[str] = None


class UpdateExpenseResponse(BaseModel):
    """Ответ на обновление расхода"""
    success: bool
    message: str
    expense_id: int


class DeleteExpenseResponse(BaseModel):
    """Ответ на удаление расхода"""
    success: bool
    message: str

