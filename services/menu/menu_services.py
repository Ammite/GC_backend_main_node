from sqlalchemy.orm import Session
from typing import List, Optional
from utils.cache import cached
from models.item import Item
from models.menu_category import MenuCategory
from schemas.menu import ItemResponse


@cached(ttl_seconds=600, key_prefix="menu")  # Кэш на 10 минут
def get_all_menu_items(
    db: Session,
    organization_id: Optional[int] = None,
    category_id: Optional[int] = None,
    name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[ItemResponse]:
    # Джойним с menu_categories для получения названия категории
    query = db.query(
        Item,
        MenuCategory.name.label("category_name")
    ).outerjoin(
        MenuCategory, Item.menu_category_id == MenuCategory.id
    )

    if organization_id is not None:
        query = query.filter(Item.organization_id == organization_id)
    if category_id is not None:
        # Фильтруем по menu_category_id
        query = query.filter(Item.menu_category_id == category_id)
    if name:
        query = query.filter(Item.name.ilike(f"%{name}%"))

    query = query.filter(Item.deleted == False)  # noqa: E712
    query = query.filter(Item.type_server == 'DISH')
    
    results = query.offset(offset).limit(limit).all()

    return [ItemResponse(
        id=item.id, 
        name=item.name, 
        price=float(item.price),
        description=item.description or "",
        image="",
        category=category_name or ""
        ) for item, category_name in results]