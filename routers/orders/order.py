from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from schemas.orders import OrderArrayResponse
import logging
from services.orders.orders_services import get_all_orders
from utils.security import get_current_user
from database.database import get_db
from typing import Optional


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["orders"])

@router.get("/orders", response_model=OrderArrayResponse)
def get_orders(
    organization_id: Optional[int] = Query(default=None),
    user_id: Optional[int] = Query(default=None),
    state: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    orders = get_all_orders(
        db=db,
        organization_id=organization_id,
        user_id=user_id,
        state=state,
        limit=limit,
        offset=offset,
    )
    return {
        "success": True,
        "message": "got orders",
        "orders": orders,
    }