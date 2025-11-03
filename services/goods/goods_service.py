from sqlalchemy.orm import Session
from typing import List
from models.product_group import ProductGroup
from models.item import Item
from schemas.goods import GoodsCategoryResponse, GoodsItemResponse
import logging

logger = logging.getLogger(__name__)

# ID категорий товаров из iiko
GOODS_CATEGORY_IDS = [165, 447, 446, 435, 377]


def get_all_children_groups(db: Session, parent_iiko_id: str) -> List[ProductGroup]:
    """
    Рекурсивно получает все дочерние группы для заданной родительской группы
    """
    children = db.query(ProductGroup).filter(
        ProductGroup.parent_iiko_id == parent_iiko_id,
        ProductGroup.deleted == False  # noqa: E712
    ).all()
    
    all_children = list(children)
    for child in children:
        all_children.extend(get_all_children_groups(db, child.iiko_id))
    
    return all_children


def get_goods_by_categories(db: Session) -> List[GoodsCategoryResponse]:
    """
    Получает товары по заданным категориям и их дочерним группам
    """
    result = []
    
    # Получаем основные группы по ID
    main_groups = db.query(ProductGroup).filter(
        ProductGroup.id.in_(GOODS_CATEGORY_IDS),
        ProductGroup.deleted == False  # noqa: E712
    ).all()
    
    logger.info(f"Найдено основных групп: {len(main_groups)}")
    
    for group in main_groups:
        # Получаем все дочерние группы
        children_groups = get_all_children_groups(db, group.iiko_id)
        
        # Собираем ID всех групп (основная + дочерние)
        all_group_ids = [group.id] + [child.id for child in children_groups]
        
        logger.info(f"Группа {group.name} (ID: {group.id}): найдено {len(children_groups)} дочерних групп")
        
        # Получаем все товары из этих групп
        items = db.query(Item).filter(
            Item.product_group_id.in_(all_group_ids),
            Item.deleted == False  # noqa: E712
        ).all()
        
        logger.info(f"Группа {group.name}: найдено {len(items)} товаров")
        
        # Формируем список товаров
        items_response = []
        for item in items:
            items_response.append(GoodsItemResponse(
                id=item.id,
                iiko_id=item.iiko_id,
                name=item.name,
                price=float(item.price) if item.price else None,
                code=item.code,
                amount=int(item.weight) if item.weight else None,
                amount_unit=item.measure_unit,
                description=item.description
            ))
        
        # Добавляем категорию с товарами в результат
        result.append(GoodsCategoryResponse(
            category_id=group.id,
            category_iiko_id=group.iiko_id,
            category_name=group.name,
            items=items_response
        ))
    
    return result

