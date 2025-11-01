from sqlalchemy.orm import Session
from typing import List, Optional
from models.item import Item
from schemas.menu import ItemResponse


def get_all_menu_items(
    db: Session,
    organization_id: Optional[int] = None,
    category_id: Optional[int] = None,
    name: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[ItemResponse]:
    query = db.query(Item)

    if organization_id is not None:
        query = query.filter(Item.organization_id == organization_id)
    if category_id is not None:
        query = query.filter(Item.category_id == category_id)
    if name:
        query = query.filter(Item.name.ilike(f"%{name}%"))

    query = query.filter(Item.deleted == False)  # noqa: E712
    query = query.filter(Item.type == 'dish')
    items = query.offset(offset).limit(limit).all()

    return [ItemResponse(id=i.id, name=i.name, price=float(i.price)) for i in items]