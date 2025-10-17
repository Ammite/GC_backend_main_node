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
