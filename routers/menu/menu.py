from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from schemas.menu import MenuArrayResponse, ItemResponse
import logging
from services.menu.menu_services import get_all_menu_items
from utils.security import get_current_user
from database.database import get_db
from typing import Optional, List


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["menu"])

@router.get("/menu", response_model=MenuArrayResponse)
def get_menu(
    organization_id: Optional[int] = Query(default=None),
    category_id: Optional[int] = Query(default=None),
    name: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=0, le=10000, description="Количество записей. 0 — вернуть все записи без ограничения."),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить список позиций меню.

    organization_id и category_id — внутренние ID (из БД).
    Возвращает id, name, price, description, image, category для каждой позиции.

    **limit=0** — вернуть все записи без ограничения.
    """
    items: List[ItemResponse] = get_all_menu_items(
        db=db,
        organization_id=organization_id,
        category_id=category_id,
        name=name,
        limit=limit if limit > 0 else None,
        offset=offset,
    )
    return {
        "success": True,
        "message": "got menu",
        "items": items,
    }