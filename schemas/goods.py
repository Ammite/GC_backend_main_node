from pydantic import BaseModel
from typing import List, Optional


class GoodsItemResponse(BaseModel):
    id: int
    iiko_id: str
    name: str
    price: Optional[float]
    code: Optional[str]
    amount: Optional[int]
    amount_unit: Optional[str]
    description: Optional[str]


class GoodsCategoryResponse(BaseModel):
    category_id: int
    category_iiko_id: str
    category_name: str
    items: List[GoodsItemResponse]


class GoodsArrayResponse(BaseModel):
    success: bool
    message: str
    categories: Optional[List[GoodsCategoryResponse]] = []

