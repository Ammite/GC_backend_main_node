from pydantic import BaseModel
from typing import List, Optional


class TableResponse(BaseModel):
    """Информация о столе"""
    id: str
    number: str
    roomId: Optional[str] = None
    roomName: Optional[str] = None
    capacity: int
    status: str  # "available" | "occupied" | "disabled"
    currentOrderId: Optional[str] = None
    assignedEmployeeId: Optional[str] = None

    class Config:
        from_attributes = True


class RoomResponse(BaseModel):
    """Информация о помещении"""
    id: str
    name: str  # "Общий зал" | "VIP-залы" | "Летняя терраса"
    capacity: int
    tables: List[TableResponse]

    class Config:
        from_attributes = True


class RoomsArrayResponse(BaseModel):
    """Список помещений"""
    rooms: List[RoomResponse]


class TablesArrayResponse(BaseModel):
    """Список столов"""
    tables: List[TableResponse]

