from pydantic import BaseModel
from typing import List, Optional


class UserResponse(BaseModel):
    login: str
    password: str

class UserArrayResponse(BaseModel):
    success: bool
    message: str
    user: Optional[List[UserResponse]] = []
