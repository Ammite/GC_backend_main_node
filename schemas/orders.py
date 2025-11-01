from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class OrderItemResponse(BaseModel):
    open_time: Optional[datetime]
    dish_name: Optional[str]
    dish_amount_int: Optional[int]
    dish_category: Optional[str]
    dish_group: Optional[str]
    dish_discount_sum_int: Optional[float]
    restaurant_section_id: Optional[str]
    table_num: Optional[int]
    order_waiter_id: Optional[str]
    pay_types: Optional[str]
    product_cost_base_product_cost: Optional[float]


class OrderResponse(BaseModel):
    id: int
    organization_name: Optional[str]
    table: Optional[int]
    room: Optional[str]
    status: Optional[str]
    items: List[OrderItemResponse]
    bank_commission: Optional[float]


class OrderArrayResponse(BaseModel):
    success: bool
    message: str
    orders: Optional[List[OrderResponse]] = []
