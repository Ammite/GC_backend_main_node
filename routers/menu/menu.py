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
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    items: List[ItemResponse] = get_all_menu_items(
        db=db,
        organization_id=organization_id,
        category_id=category_id,
        name=name,
        limit=limit,
        offset=offset,
    )
    return {
        "success": True,
        "message": "got menu",
        "items": items,
    }