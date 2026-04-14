from pydantic import BaseModel
from typing import Optional, List


class ConceptionResponse(BaseModel):
    """Информация о концепции"""

    id: int
    iiko_id: str
    name: str
    code: Optional[str] = None
    comment: Optional[str] = None

    class Config:
        from_attributes = True


class ConceptionListResponse(BaseModel):
    """Ответ со списком концепций"""

    success: bool
    message: str
    conceptions: List[ConceptionResponse]
    total: int


class SyncConceptionsResponse(BaseModel):
    """Ответ на синхронизацию концепций"""

    success: bool
    message: str
    synced: int


class SupplierResponse(BaseModel):
    """Информация о поставщике"""

    id: int
    iiko_id: str
    name: str
    code: Optional[str] = None
    comment: Optional[str] = None

    class Config:
        from_attributes = True


class SupplierListResponse(BaseModel):
    """Ответ со списком поставщиков"""

    success: bool
    message: str
    suppliers: List[SupplierResponse]
    total: int


class SyncSuppliersResponse(BaseModel):
    """Ответ на синхронизацию поставщиков"""

    success: bool
    message: str
    synced: int

