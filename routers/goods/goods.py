from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from schemas.goods import GoodsArrayResponse
import logging
from services.goods import get_goods_by_categories
from utils.security import get_current_user, require_role
from database.database import get_db


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["goods"])


@router.get("/goods", response_model=GoodsArrayResponse)
def get_goods(
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Получить товары по категориям (Заготовки и их дочерние группы).

    Возвращает массив категорий с товарами. Каждая категория содержит:
    - category_id: внутренний ID категории (int)
    - category_iiko_id: iiko UUID категории (str)
    - category_name: Название категории
    - items: Массив товаров (id — внутренний, iiko_id — UUID из iiko, name, price, code, description)
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

