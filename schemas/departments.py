from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class DepartmentResponse(BaseModel):
    """Ответ с информацией о департаменте"""
    
    id: int
    iiko_id: str
    parent_id: Optional[str] = None
    code: Optional[str] = None
    name: str
    taxpayer_id_number: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DepartmentListResponse(BaseModel):
    """Ответ со списком департаментов"""
    
    success: bool
    message: str
    departments: List[DepartmentResponse]
    total: int


class SyncDepartmentsResponse(BaseModel):
    """Ответ на синхронизацию департаментов"""
    
    success: bool
    message: str
    created: int
    updated: int
    total: int
