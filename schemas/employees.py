from pydantic import BaseModel
from typing import List, Optional


class EmployeeResponse(BaseModel):
    id: int
    iiko_id: str
    name: Optional[str] = None
    login: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    main_role_code: Optional[str] = None
    preferred_organization_id: Optional[int] = None
    deleted: bool


class EmployeeArrayResponse(BaseModel):
    success: bool
    message: str
    employees: Optional[List[EmployeeResponse]] = []

class EmployeeWithShiftsResponse(BaseModel):
    """
    
    array of objects:
        {
            id: "1",
            name: "Аслан Аманов",
            role: "Оффицант",
            avatarUrl:
                "https://api.builder.io/api/v1/image/assets/TEMP/3a1a0f795dd6cebc375ac2f7fbeab6a0d791efc8?width=80",
            totalAmount: "56 897 тг",
            shiftTime: "00:56:25",
            isActive: true,
        }
    """

    id: int
    name: Optional[str] = None
    deleted: bool = False
    role: Optional[str] = None
    avatarUrl: Optional[str] = None
    totalAmount: Optional[str] = None
    shiftTime: Optional[str] = None
    isActive: bool = False

class EmployeeWithShiftsArrayResponse(BaseModel):
    success: bool
    message: str
    employees: Optional[List[EmployeeWithShiftsResponse]] = []


class EmployeeSummaryItem(BaseModel):
    """Элемент сводки по сотруднику"""
    id: int
    name: str
    amount: float


class EmployeesSummaryResponse(BaseModel):
    """Сводка по сотрудникам"""
    activeEmployeesCount: int
    totalAmount: float
    employees: List[EmployeeSummaryItem]


class EmployeeSummaryResponse(BaseModel):
    """Сводка по конкретному сотруднику"""
    id: int
    firstName: str
    lastName: str
    name: str
    shiftDuration: str  # HH:mm:ss
    totalAmount: float
    ordersCount: int


class EmployeeTableItem(BaseModel):
    """Элемент стола сотрудника"""
    id: int
    number: str
    roomName: Optional[str] = None
    orderId: str
    amount: float


class EmployeeDetailsResponse(BaseModel):
    """Детали сотрудника"""
    shiftDuration: str  # HH:mm:ss
    totalAmount: float
    ordersCount: int
    tables: List[EmployeeTableItem]


class EmployeeCheckItem(BaseModel):
    """Элемент блюда в чеке"""
    name: str
    quantity: int
    price: float
    total: float


class EmployeeOpenCheckResponse(BaseModel):
    """Детали открытого счета сотрудника"""
    orderId: str
    tableId: Optional[int] = None
    tableNumber: Optional[str] = None
    roomName: Optional[str] = None
    items: List[EmployeeCheckItem]
    totalAmount: float
    status: str


class EmployeeClosedTableItem(BaseModel):
    """Элемент истории закрытых столиков"""
    orderId: str
    tableId: Optional[int] = None
    tableNumber: Optional[str] = None
    roomName: Optional[str] = None
    closedAt: Optional[str] = None  # ISO format
    totalAmount: float
    itemsCount: int


class EmployeeClosedTablesHistoryResponse(BaseModel):
    """История закрытых столиков сотрудника"""
    success: bool
    message: str
    orders: List[EmployeeClosedTableItem]