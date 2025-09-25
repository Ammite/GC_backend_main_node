from pydantic import BaseModel
from typing import List, Optional


class ItemResponse(BaseModel):
    name: str

class MenuArrayResponse(BaseModel):
    success: bool
    message: str
    items: Optional[List[ItemResponse]] = []
