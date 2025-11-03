from sqlalchemy.orm import Session
from typing import List, Optional
from models.d_order import DOrder
from models.organization import Organization
from models.sales import Sales
from models.restaurant_sections import RestaurantSection
from schemas.orders import OrderResponse, OrderItemResponse
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def get_all_orders(
    db: Session,
    organization_id: Optional[int] = None,
    user_id: Optional[int] = None,
    state: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[OrderResponse]:
    query = db.query(DOrder).outerjoin(Organization, DOrder.organization_id == Organization.id)

    if organization_id is not None:
        query = query.filter(DOrder.organization_id == organization_id)
    if user_id is not None:
        query = query.filter(DOrder.user_id == user_id)
    if state:
        query = query.filter(DOrder.state_order == state)
    if date:
        datetime_from = datetime.strptime(date, "%d.%m.%Y").replace(hour=0, minute=0, second=0, microsecond=0)
        datetime_to = datetime.strptime(date, "%d.%m.%Y").replace(hour=23, minute=59, second=59, microsecond=999999)
        query = query.filter(DOrder.time_order >= datetime_from, DOrder.time_order <= datetime_to)
    query = query.filter(DOrder.deleted == False)  # noqa: E712
    orders = query.offset(offset).limit(limit).all()

    result = []
    for order in orders:
        # Получаем organization_name
        organization = db.query(Organization).filter(Organization.id == order.organization_id).first()
        organization_name = organization.name if organization else None
        
        # Получаем sales items по iiko_id заказа
        sales_items = db.query(Sales).filter(
            Sales.order_id == order.iiko_id,
            # Sales.delivery_is_delivery == 'ORDER_WITHOUT_DELIVERY',
            Sales.deleted_with_writeoff == 'NOT_DELETED',
            Sales.dish_discount_sum_int > 0
        ).all()
        
        # Формируем список items
        items = []
        table_num = None
        room_name = None
        organization_code = None
        
        for sale in sales_items:
            # Получаем room name по restaurant_section_id
            if sale.restaurant_section_id and not room_name:
                section = db.query(RestaurantSection).filter(
                    RestaurantSection.iiko_id == sale.restaurant_section_id
                ).first()
                if section:
                    room_name = section.name
            
            # Берем table_num из первого sale
            if sale.table_num and not table_num:
                table_num = sale.table_num

            organization_code = sale.department_code if organization_code is None and sale.department_code else None
            
            items.append(OrderItemResponse(
                open_time=sale.open_time,
                dish_name=sale.dish_name,
                dish_amount_int=sale.dish_amount_int,
                dish_category=sale.dish_category,
                dish_group=sale.dish_group,
                dish_discount_sum_int=float(sale.dish_discount_sum_int) if sale.dish_discount_sum_int else None,
                restaurant_section_id=sale.restaurant_section_id,
                table_num=sale.table_num,
                order_waiter_id=sale.order_waiter_id,
                pay_types=sale.pay_types,
                product_cost_base_product_cost=float(sale.product_cost_base_product_cost) if sale.product_cost_base_product_cost else None,
            ))
        
        if organization_name is None and organization_code is not None:
            organization = db.query(Organization).filter(Organization.code == organization_code).first()
            if organization:
                organization_name = organization.name

        
        if not sales_items:
            room_name = "Доставка"
        
        result.append(OrderResponse(
            id=order.id,
            organization_name=organization_name,
            table=table_num,
            room=room_name,
            status=order.state_order,
            sum_order=float(order.sum_order) if order.sum_order else None,
            final_sum=float(order.discount) if order.discount else None,
            bank_commission=float(order.bank_commission) if order.bank_commission else None,
            items=items
        ))
    
    return result


def get_order_by_id(db: Session, order_id: int) -> Optional[OrderResponse]:
    order = db.query(DOrder).outerjoin(Organization, DOrder.organization_id == Organization.id).filter(
        DOrder.id == order_id, DOrder.deleted == False  # noqa: E712
    ).first()
    
    if not order:
        return None
    
    # Получаем organization_name
    organization_name = order.organization.name if order.organization else None
    
    # Получаем sales items по iiko_id заказа
    sales_items = db.query(Sales).filter(
        Sales.order_id == order.iiko_id,
        Sales.delivery_is_delivery == 'ORDER_WITHOUT_DELIVERY',
        Sales.deleted_with_writeoff == 'NOT_DELETED',
        Sales.dish_discount_sum_int > 0
    ).all()
    
    # Формируем список items
    items = []
    table_num = None
    room_name = None
    
    for sale in sales_items:
        # Получаем room name по restaurant_section_id
        if sale.restaurant_section_id and not room_name:
            section = db.query(RestaurantSection).filter(
                RestaurantSection.iiko_id == sale.restaurant_section_id
            ).first()
            if section:
                room_name = section.name
        
        # Берем table_num из первого sale
        if sale.table_num and not table_num:
            table_num = sale.table_num
        
        items.append(OrderItemResponse(
            open_time=sale.open_time,
            dish_name=sale.dish_name,
            dish_amount_int=sale.dish_amount_int,
            dish_category=sale.dish_category,
            dish_group=sale.dish_group,
            dish_discount_sum_int=float(sale.dish_discount_sum_int) if sale.dish_discount_sum_int else None,
            restaurant_section_id=sale.restaurant_section_id,
            table_num=sale.table_num,
            order_waiter_id=sale.order_waiter_id,
            pay_types=sale.pay_types,
            product_cost_base_product_cost=float(sale.product_cost_base_product_cost) if sale.product_cost_base_product_cost else None,
        ))
    
    return OrderResponse(
        id=order.id,
        organization_name=organization_name,
        table=table_num,
        room=room_name,
        status=order.state_order,
        items=items,
        bank_commission=float(order.bank_commission) if order.bank_commission else None,
    )


def get_order_by_user(db: Session, user_id: int, limit: int = 100, offset: int = 0) -> List[OrderResponse]:
    return get_all_orders(db=db, user_id=user_id, limit=limit, offset=offset)


def get_order_by_state(db: Session, state: str, limit: int = 100, offset: int = 0) -> List[OrderResponse]:
    return get_all_orders(db=db, state=state, limit=limit, offset=offset)