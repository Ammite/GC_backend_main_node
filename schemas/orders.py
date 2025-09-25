from pydantic import BaseModel
from typing import List, Optional


class OrderResponse(BaseModel):
    name: str

class OrderArrayResponse(BaseModel):
    success: bool
    message: str
    orders: Optional[List[OrderResponse]] = []
