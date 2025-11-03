from pydantic import BaseModel
from typing import List, Optional


class DishItem(BaseModel):
    """Информация о блюде"""
    id: int
    name: str
    quantity: int  # Количество проданных порций
    revenue: float  # Выручка от блюда
    average_price: float  # Средняя цена за порцию


class PopularDishesResponse(BaseModel):
    """Ответ с популярными и непопулярными блюдами"""
    success: bool
    message: str
    
    # Топ популярных блюд
    popular_dishes: List[DishItem]
    
    # Топ непопулярных блюд
    unpopular_dishes: List[DishItem]
    
    # Статистика
    total_dishes_sold: int  # Всего блюд продано
    total_revenue: float  # Общая выручка
    
    class Config:
        from_attributes = True

