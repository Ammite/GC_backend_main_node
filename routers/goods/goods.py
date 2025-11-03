from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from schemas.goods import GoodsArrayResponse
import logging
from services.goods import get_goods_by_categories
from utils.security import get_current_user
from database.database import get_db


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["goods"])


@router.get("/goods", response_model=GoodsArrayResponse)
def get_goods(
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить товары по категориям (Заготовки и их дочерние группы)
    
    Возвращает массив категорий с товарами:
    - category_id: ID категории
    - category_iiko_id: iiko ID категории
    - category_name: Название категории
    - items: Массив товаров с полями name, price, code, description
    """
    try:
        categories = get_goods_by_categories(db=db)
        return {
            "success": True,
            "message": f"Получено категорий: {len(categories)}",
            "categories": categories,
        }
    except Exception as e:
        logger.error(f"Ошибка при получении товаров: {str(e)}")
        return {
            "success": False,
            "message": f"Ошибка при получении товаров: {str(e)}",
            "categories": [],
        }

