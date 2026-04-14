from pydantic import BaseModel
from typing import List, Optional


class OrganizationResponse(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    is_active: bool
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class OrganizationArrayResponse(BaseModel):
    success: bool
    message: str
    organizations: Optional[List[OrganizationResponse]] = []
