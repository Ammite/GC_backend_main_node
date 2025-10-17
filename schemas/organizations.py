from pydantic import BaseModel
from typing import List, Optional


class OrganizationResponse(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    is_active: bool


class OrganizationArrayResponse(BaseModel):
    success: bool
    message: str
    organizations: Optional[List[OrganizationResponse]] = []
