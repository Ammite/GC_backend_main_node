from pydantic import BaseModel
from typing import List, Optional


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float

class MenuArrayResponse(BaseModel):
    success: bool
    message: str
    items: Optional[List[ItemResponse]] = []
