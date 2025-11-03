from pydantic import BaseModel
from typing import List, Optional


class ItemResponse(BaseModel):
    id: int
    name: str
    price: float
    description: Optional[str] = None
    image: Optional[str] = None
    category: Optional[str] = None

class MenuArrayResponse(BaseModel):
    success: bool
    message: str
    items: Optional[List[ItemResponse]] = []
