from sqlalchemy.orm import Session
from typing import List, Optional
from models.d_order import DOrder
from schemas.orders import OrderResponse


def get_all_orders(
    db: Session,
    organization_id: Optional[int] = None,
    user_id: Optional[int] = None,
    state: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[OrderResponse]:
    query = db.query(DOrder)

    if organization_id is not None:
        query = query.filter(DOrder.organization_id == organization_id)
    if user_id is not None:
        query = query.filter(DOrder.user_id == user_id)
    if state:
        query = query.filter(DOrder.state_order == state)

    query = query.filter(DOrder.deleted == False)  # noqa: E712
    orders = query.offset(offset).limit(limit).all()

    # Временно отдадим короткий ответ
    return [OrderResponse(name=str(o.id)) for o in orders]


def get_order_by_id(db: Session, order_id: int) -> Optional[OrderResponse]:
    order = db.query(DOrder).filter(DOrder.id == order_id, DOrder.deleted == False).first()  # noqa: E712
    return OrderResponse(name=str(order.id)) if order else None


def get_order_by_user(db: Session, user_id: int, limit: int = 100, offset: int = 0) -> List[OrderResponse]:
    orders = (
        db.query(DOrder)
        .filter(DOrder.user_id == user_id, DOrder.deleted == False)  # noqa: E712
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [OrderResponse(name=str(o.id)) for o in orders]


def get_order_by_state(db: Session, state: str, limit: int = 100, offset: int = 0) -> List[OrderResponse]:
    orders = (
        db.query(DOrder)
        .filter(DOrder.state_order == state, DOrder.deleted == False)  # noqa: E712
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [OrderResponse(name=str(o.id)) for o in orders]