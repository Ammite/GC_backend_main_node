from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class CashFlowCategoryResponse(BaseModel):
    """Статья движения денежных средств"""

    id: str
    code: Optional[str] = None
    parentCategoryId: Optional[str] = None
    type: Optional[str] = None


class ConceptionResponse(BaseModel):
    """Концепция"""

    id: Optional[str] = None
    code: Optional[str] = None
    name: Optional[str] = None


class PayOutTypeApiResponse(BaseModel):
    """
    Тип изъятия/внесения в формате, возвращаемом iiko API.
    Используется для внутренней синхронизации, не для публичного API.
    """

    id: str
    chiefAccount: Optional[str] = None
    account: Optional[str] = None
    counteragentType: str  # NONE, COUNTERAGENT, EMPLOYEE, SUPPLIER, CLIENT, INTERNAL_SUPPLIER
    transactionType: str  # PAYIN, PAYOUT
    cashFlowCategory: Optional[CashFlowCategoryResponse] = None
    conception: Optional[ConceptionResponse] = None
    limit: Optional[float] = None
    comment: Optional[str] = None
    mandatoryFrontComment: Optional[bool] = None
    isDeleted: Optional[bool] = None


class PayOutTypeResponse(BaseModel):
    """
    Упрощенный тип изъятия для фронтенда.

    Важно:
    - `id` — GUID типа из iiko.
    - `account_name` — человеко-читаемое название счета (связь с accounts_list.name).
    - Дополнительно отдаем transactionType и counteragentType.
    """

    id: str
    account_name: Optional[str] = None
    chief_account_name: Optional[str] = None
    transactionType: Optional[str] = None
    counteragentType: Optional[str] = None
    comment: Optional[str] = None


class PayrollResponse(BaseModel):
    """Платежная ведомость"""
    id: str
    dateFrom: str  # ISO формат
    dateTo: str  # ISO формат
    department: str  # UUID торгового предприятия
    documentNumber: Optional[str] = None
    status: Optional[str] = None  # NEW, PROCESSED, DELETED
    comment: Optional[str] = None


class CreatePayOutRequest(BaseModel):
    """Запрос на создание изъятия.

    Поле `counteragent_id` — ID контрагента из **нашей** базы данных.
    Нужен ли он и из какой таблицы брать — зависит от `counteragentType` выбранного типа изъятия
    (поле возвращается в GET /pay-out-types):

    - `NONE` — контрагент не требуется, `counteragent_id` не передаём
    - `EMPLOYEE` — ID сотрудника из таблицы `employees` (получить через `/employees`)
    - `SUPPLIER` — ID поставщика из таблицы `suppliers`
    """
    payOutTypeId: str = Field(..., description="UUID типа изъятия (из GET /pay-out-types)")
    payOutDate: str = Field(..., description="Дата в формате yyyy-MM-dd")
    counteragent_id: Optional[int] = Field(default=None, description="ID контрагента из нашей БД (employees или suppliers, в зависимости от counteragentType типа изъятия)")
    departmentSumMap: Dict[str, float] = Field(..., description="Словарь: UUID торгового предприятия -> сумма изъятия")
    payrollId: Optional[str] = Field(default=None, description="UUID платежной ведомости (опционально)")
    comment: Optional[str] = Field(default=None, description="Комментарий к изъятию")
    
    @field_validator('payOutDate')
    @classmethod
    def validate_date_format(cls, v):
        """Проверка формата даты yyyy-MM-dd"""
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError('Дата должна быть в формате yyyy-MM-dd (например, 2025-01-15)')
        return v
    
    @field_validator('departmentSumMap')
    @classmethod
    def validate_department_sum_map(cls, v):
        """Проверка, что словарь не пустой и суммы положительные"""
        if not v:
            raise ValueError('departmentSumMap не может быть пустым')
        for department_id, amount in v.items():
            if amount <= 0:
                raise ValueError(f'Сумма изъятия для торгового предприятия {department_id} должна быть положительной')
        return v


class PayOutErrorResponse(BaseModel):
    """Ошибка из ответа API"""
    value: Optional[str] = None
    code: Optional[str] = None


class PayOutSettingsResponse(BaseModel):
    """Параметры изъятия из ответа API"""
    payOutTypeId: str
    payOutDate: str
    counteragent: Optional[str] = None
    departmentSumMap: Dict[str, float]
    payrollId: Optional[str] = None
    comment: Optional[str] = None


class CreatePayOutResponse(BaseModel):
    """Ответ на создание изъятия"""
    success: bool
    message: str
    result: Optional[str] = None  # SUCCESS, ERROR
    errors: Optional[List[PayOutErrorResponse]] = None
    payOutSettings: Optional[PayOutSettingsResponse] = None
    pay_out_id: Optional[int] = None  # ID в локальной БД


class SyncPayOutTypesResponse(BaseModel):
    """Ответ на синхронизацию типов изъятий"""
    success: bool
    message: str
    synced: int
