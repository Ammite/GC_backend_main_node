from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from models.d_order import DOrder
from models.organization import Organization
from models.sales import Sales
from models.restaurant_sections import RestaurantSection
from models.item import Item
from models.tables import Table
from models.employees import Employees
from models.user import User
from models.t_order import TOrder
from models.terminal_groups import TerminalGroup
from models.payment_type import PaymentType
from schemas.orders import (
    OrderResponse,
    OrderItemResponse,
    CreateOrderRequest,
    UpdateOrderRequest,
    CancelOrderRequest,
)
from utils.cache import cached, invalidate_cache
from services.iiko.iiko_service import IikoService, IikoApiType


logger = logging.getLogger(__name__)

iiko_service = IikoService()


@cached(ttl_seconds=300, key_prefix="orders")  # Кэш на 5 минут
def get_all_orders(
    db: Session,
    organization_id: Optional[int] = None,
    user_id: Optional[int] = None,
    state: Optional[str] = None,
    date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
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
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%d.%m.%Y").replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(DOrder.time_order >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%d.%m.%Y").replace(hour=23, minute=59, second=59, microsecond=999999)
            query = query.filter(DOrder.time_order <= dt_to)
        except ValueError:
            pass
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
            
            # Ищем наш id товара по dish_id (iiko_id) из sale
            sale_product_id = None
            if sale.dish_id:
                sale_product = db.query(Item).filter(Item.iiko_id == sale.dish_id).first()
                if sale_product:
                    sale_product_id = sale_product.id

            items.append(OrderItemResponse(
                product_id=sale_product_id,
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
            # При дублях кодов (legacy от старой iiko) предпочитаем «настоящую»
            # организацию — ту, у которой заполнен iiko_id_cloud.
            organization = (
                db.query(Organization)
                .filter(Organization.code == organization_code)
                .order_by(Organization.iiko_id_cloud.is_(None).asc())
                .first()
            )
            if organization:
                organization_name = organization.name

        
        if not sales_items:
            # Для заказов, созданных через наше приложение, выводим имя помещения
            # из связки external_data.tableId → Table → RestaurantSection.
            # Это надёжнее, чем доверять текстовому order.room.
            room_name = None
            ext = order.external_data or {}
            local_table_id = ext.get("tableId")
            if local_table_id:
                section_name = (
                    db.query(RestaurantSection.name)
                    .join(Table, Table.section_id == RestaurantSection.id)
                    .filter(Table.id == local_table_id)
                    .scalar()
                )
                if section_name:
                    room_name = section_name
            if not room_name:
                room_name = order.room or "Заказ №" + str(order.id)
            # Fallback: берём items из JSON-колонки (заказы созданные через наше приложение)
            raw_items = order.items or []
            if isinstance(raw_items, str):
                import json as _json
                raw_items = _json.loads(raw_items)
            for raw in raw_items:
                product_name = None
                product_id = raw.get("productId")
                if product_id:
                    product = db.query(Item).filter(Item.id == product_id).first()
                    product_name = product.name if product else None
                items.append(OrderItemResponse(
                    product_id=product_id,
                    open_time=None,
                    dish_name=product_name,
                    dish_amount_int=int(raw.get("amount", 0)),
                    dish_category=None,
                    dish_group=None,
                    dish_discount_sum_int=float(raw.get("price", 0)),
                    restaurant_section_id=None,
                    table_num=None,
                    order_waiter_id=None,
                    pay_types=None,
                    product_cost_base_product_cost=None,
                    comment=raw.get("comment"),
                ))

        result.append(OrderResponse(
            id=order.id,
            organization_name=organization_name,
            table=str(table_num) if table_num is not None else order.tab_name,
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
        
        # Ищем наш id товара по dish_id (iiko_id) из sale
        sale_product_id = None
        if sale.dish_id:
            sale_product = db.query(Item).filter(Item.iiko_id == sale.dish_id).first()
            if sale_product:
                sale_product_id = sale_product.id

        items.append(OrderItemResponse(
            product_id=sale_product_id,
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
    
    if not room_name:
        # Пытаемся достать помещение из связки external_data.tableId → section
        ext = order.external_data or {}
        local_table_id = ext.get("tableId")
        if local_table_id:
            section_name = (
                db.query(RestaurantSection.name)
                .join(Table, Table.section_id == RestaurantSection.id)
                .filter(Table.id == local_table_id)
                .scalar()
            )
            if section_name:
                room_name = section_name
    if not room_name:
        room_name = order.room

    return OrderResponse(
        id=order.id,
        organization_name=organization_name,
        table=str(table_num) if table_num is not None else order.tab_name,
        room=room_name,
        status=order.state_order,
        items=items,
        bank_commission=float(order.bank_commission) if order.bank_commission else None,
    )


def get_order_by_user(db: Session, user_id: int, limit: int = 100, offset: int = 0) -> List[OrderResponse]:
    return get_all_orders(db=db, user_id=user_id, limit=limit, offset=offset)


def get_order_by_state(db: Session, state: str, limit: int = 100, offset: int = 0) -> List[OrderResponse]:
    return get_all_orders(db=db, state=state, limit=limit, offset=offset)


def create_order_from_app(
    db: Session,
    data: CreateOrderRequest,
    user_id: Optional[int],
) -> DOrder:
    """
    Создать заказ в нашей БД и подготовить все данные для возможной отправки в iiko Cloud.
    
    Отправка в iiko выполняется отдельной асинхронной функцией, чтобы избежать await в sync-коде.
    """
    # Валидация и преобразование organizationId
    organization_id = data.organizationId
    if organization_id is not None:
        org = db.query(Organization).filter(Organization.id == organization_id).first()
        if not org:
            raise ValueError(f"Organization with id {organization_id} not found")
        organization_id = org.id  # Используем наш id

    # Валидация и преобразование tableId
    table_iiko_id = None
    table_number = None
    table_obj = None
    if data.tableId:
        table_obj = db.query(Table).filter(Table.id == data.tableId).first()
        if not table_obj:
            raise ValueError(f"Table with id {data.tableId} not found")
        table_iiko_id = table_obj.iiko_id
        table_number = str(table_obj.number)

    # Если organizationId не пришёл от фронта, но указан tableId —
    # выводим организацию из связки table → section → terminal_group → organization.
    # Без этого create_order_in_iiko потом не сможет найти cloud uuid организации.
    if organization_id is None and table_obj is not None:
        derived_org_id = (
            db.query(TerminalGroup.organization_id)
            .join(RestaurantSection, RestaurantSection.terminal_group_id == TerminalGroup.id)
            .filter(RestaurantSection.id == table_obj.section_id)
            .scalar()
        )
        if derived_org_id:
            organization_id = derived_org_id
            logger.info(
                f"organizationId не передан, выведен из tableId={data.tableId}: "
                f"organization_id={organization_id}"
            )
        else:
            logger.warning(
                f"Не удалось вывести organization_id из tableId={data.tableId} "
                f"(table.section_id={table_obj.section_id})"
            )
    
    # Валидация и преобразование waiterId (принимаем user id, ищем employee через iiko_id)
    waiter_iiko_id = None
    if data.waiterId:
        user = db.query(User).filter(User.id == data.waiterId).first()
        if not user:
            raise ValueError(f"User with id {data.waiterId} not found")
        waiter = db.query(Employees).filter(Employees.iiko_id == user.iiko_id).first()
        if not waiter:
            raise ValueError(f"Employee for user {data.waiterId} not found (no matching iiko_id)")
        waiter_iiko_id = waiter.iiko_id
    
    # Валидация и преобразование позиций (productId -> iiko_id)
    items_json = []
    for idx, item in enumerate(data.items, 1):
        product = db.query(Item).filter(Item.id == item.productId).first()
        if not product:
            raise ValueError(
                f"Товар с id {item.productId} не найден в базе данных. "
                f"Проверьте, что товар существует и не удален. "
                f"Получить список доступных товаров можно через эндпоинт GET /menu"
            )
        
        if product.deleted:
            raise ValueError(
                f"Товар с id {item.productId} (название: {product.name}) удален и не может быть добавлен в заказ. "
                f"Используйте другой товар."
            )
        
        items_json.append({
            "productId": item.productId,  # Сохраняем наш id
            "productIikoId": product.iiko_id,  # Сохраняем iiko_id для будущей отправки в iiko
            "amount": item.amount,
            "price": item.price,
            "sum": item.sum,
            "comment": item.comment,
        })
    
    # Считаем сумму заказа из позиций
    total_sum = sum(item.sum for item in data.items) if data.items else 0.0

    now = datetime.now()

    # Обработка оплат
    payments_info = []
    if data.payments:
        for p in data.payments:
            pt = db.query(PaymentType).filter(PaymentType.id == p.paymentTypeId).first()
            if not pt:
                raise ValueError(f"Вид оплаты с id {p.paymentTypeId} не найден")
            payments_info.append({
                "paymentTypeId": p.paymentTypeId,
                "paymentTypeIikoId": pt.iiko_id,
                "paymentTypeKind": pt.payment_type_kind,
                "paymentTypeName": pt.name,
                "sum": p.sum,
                "isProcessedExternally": p.isProcessedExternally,
            })

    external_data = {
        "source": "our_app",
        "waiterId": data.waiterId,  # Наш id
        "waiterIikoId": waiter_iiko_id,  # iiko_id для будущей отправки
        "tableId": data.tableId,  # Наш id
        "tableIikoId": table_iiko_id,  # iiko_id для будущей отправки
        "tableNumber": table_number,  # Номер стола
        "guests": data.guests,
        "comment": data.comment,
        "payments_info": payments_info if payments_info else None,
    }

    new_order = DOrder(
        organization_id=organization_id,
        terminal_group_id=None,
        external_number=None,
        phone=None,
        guest_count=data.guests or 0,
        tab_name=table_number,  # Сохраняем номер стола
        room=data.room,
        price_category_id=None,
        order_type_id=None,
        sum_order=total_sum,
        user_id=user_id,
        state_order="CREATED",
        discount=None,
        service=None,
        bank_commission=None,
        time_order=now,
        customer=None,
        items=items_json,
        combos=None,
        payments=None,
        tips=None,
        discounts_info=None,
        loyalty_info=None,
        cheque_additional_info=None,
        external_data=external_data,
        deleted=False,
    )

    # Логируем создание заказа (до commit, чтобы сохранилось)
    _add_order_log(new_order, "CREATED", user_id, "Заказ создан")

    db.add(new_order)
    db.flush()  # Получаем ID заказа перед commit
    
    # Создаем записи в t_orders для каждой позиции
    for order_item_data, request_item in zip(items_json, data.items):
        t_order = TOrder(
            order_id=new_order.id,
            item_id=order_item_data["productId"],  # ID товара из нашей таблицы items
            count_order=int(order_item_data["amount"]),  # Количество (преобразуем float в int)
            time_order=now,
            comment_order=order_item_data.get("comment"),  # Комментарий к позиции
            iiko_id=None,  # Пока нет iiko_id, так как заказ создается только локально
        )
        db.add(t_order)
    
    db.commit()
    db.refresh(new_order)

    # Инвалидируем кэш get_all_orders для актуальности списка
    try:
        invalidate_cache("orders")
    except Exception:
        # Если что-то пойдёт не так с кэшем — не ломаем основной поток
        logger.warning("Failed to invalidate orders cache after creating order")

    return new_order


async def create_order_in_iiko(
    db: Session,
    order: DOrder,
    guests: Optional[int],
    comment: Optional[str],
) -> Dict[str, Any]:
    """
    Асинхронно создать заказ в iiko Cloud для уже существующего локального заказа.

    Возвращает словарь с метаданными ответа iiko (correlationId, orderId, number, fullSum).
    """
    try:
        # Получаем iiko_id организации и терминальной группы из БД
        org = db.query(Organization).filter(Organization.id == order.organization_id).first()
        if not org:
            logger.error(f"Организация для заказа {order.id} не найдена")
            return {}
        org_cloud_id = org.iiko_id_cloud or org.iiko_id
        if not org_cloud_id:
            logger.error(f"Организация {org.id} не имеет iiko_id")
            return {}

        # Получаем терминальную группу через Cloud API по iiko_id_cloud организации
        cloud_terminal_groups = await iiko_service.get_cloud_terminal_groups(org_cloud_id)
        if not cloud_terminal_groups:
            logger.error(f"Терминальные группы для организации {org_cloud_id} не найдены в Cloud API")
            return {}
        terminal_group_id = cloud_terminal_groups[0]["id"]

        items = order.items or []

        iiko_items: List[Dict[str, Any]] = []
        for item in items:
            if not item.get("productIikoId"):
                logger.warning(
                    f"Пропуск позиции без productIikoId при отправке в iiko: {item}"
                )
                continue
            iiko_items.append(
                {
                    "productId": item["productIikoId"],
                    "type": "Product",
                    "amount": item["amount"],
                    "price": item["price"],
                    "comment": item.get("comment") or "",
                }
            )

        ext = order.external_data or {}
        table_iiko_id = ext.get("tableIikoId")
        waiter_iiko_id = ext.get("waiterIikoId")

        order_body: Dict[str, Any] = {
            "externalNumber": str(order.id),
            "phone": None,
            "comment": comment or "",
            "guests": {
                "count": guests or 0,
            },
            "items": iiko_items,
            "payments": [],
        }
        if table_iiko_id:
            order_body["tableIds"] = [table_iiko_id]
        if waiter_iiko_id:
            # iiko Cloud table order поддерживает поле waiterId (uuid сотрудника)
            order_body["waiterId"] = waiter_iiko_id

        iiko_order_payload: Dict[str, Any] = {
            "organizationId": org_cloud_id,
            "terminalGroupId": terminal_group_id,
            "createPaymentIfNotExists": False,
            "checkStopList": False,
            "order": order_body,
            "createOrderSettings": {
                "servicePrint": True,
            },
        }

        logger.info(f"Отправка заказа {order.id} в iiko Cloud: {iiko_order_payload}")
        iiko_response = await iiko_service._make_request(
            api_type=IikoApiType.CLOUD,
            endpoint="/api/1/order/create",
            method="POST",
            data=iiko_order_payload,
        )

        if not isinstance(iiko_response, Dict):
            logger.warning(
                f"Неожиданный ответ от iiko /api/1/order/create: {iiko_response}"
            )
            return {}

        logger.info(f"Ответ iiko /api/1/order/create для заказа {order.id}: {iiko_response}")

        correlation_id = iiko_response.get("correlationId")
        order_info = iiko_response.get("orderInfo") or {}
        order_id = order_info.get("id") or iiko_response.get("orderId")
        number = order_info.get("number") or iiko_response.get("number")
        creation_status = order_info.get("creationStatus")
        full_sum = iiko_response.get("fullSum")

        if order_id:
            order.iiko_id = order_id
        else:
            logger.warning(
                f"iiko не вернул id заказа для {order.id}: {iiko_response}"
            )
        if order.external_data is None:
            order.external_data = {}
        order.external_data.setdefault("iiko_create_order", {})
        order.external_data["iiko_create_order"].update(
            {
                "correlationId": correlation_id,
                "orderId": order_id,
                "number": number,
                "creationStatus": creation_status,
                "fullSum": full_sum,
            }
        )
        flag_modified(order, "external_data")
        db.commit()
        db.refresh(order)

        return {
            "correlationId": correlation_id,
            "orderId": order_id,
            "number": number,
            "creationStatus": creation_status,
            "fullSum": full_sum,
        }
    except Exception as e:
        logger.error(
            f"Ошибка при создании заказа {order.id} в iiko Cloud: {e}",
            exc_info=True,
        )
        return {}


async def close_order_in_iiko(db: Session, order: DOrder, pay_data=None) -> Dict[str, Any]:
    """
    Асинхронно закрыть заказ в iiko Cloud после оплаты.
    Если заказ не был отправлен в iiko (iiko_id is None), ничего не делает.
    """
    if order.iiko_id is None:
        return {}

    try:
        org = db.query(Organization).filter(Organization.id == order.organization_id).first()
        if not org:
            logger.error(f"Организация для заказа {order.id} не найдена")
            return {}
        org_cloud_id = org.iiko_id_cloud or org.iiko_id
        if not org_cloud_id:
            logger.error(f"Организация {org.id} не имеет iiko_id")
            return {}

        # По официальной спеке (CloseTableOrderRequest) есть только три поля:
        # organizationId, orderId, chequeAdditionalInfo. Никаких paymentItems тут
        # не существует — оплаты ставятся отдельно через /api/1/order/change_payments
        # ДО вызова close. См. change_payments_in_iiko.
        payload: Dict[str, Any] = {
            "organizationId": org_cloud_id,
            "orderId": order.iiko_id,
        }

        logger.info(f"Закрытие заказа {order.id} в iiko Cloud: {payload}")
        iiko_response = await iiko_service._make_request(
            api_type=IikoApiType.CLOUD,
            endpoint="/api/1/order/close",
            method="POST",
            data=payload,
        )

        if order.external_data is None:
            order.external_data = {}
        order.external_data["iiko_close_order"] = iiko_response if isinstance(iiko_response, dict) else {}
        flag_modified(order, "external_data")
        db.commit()
        db.refresh(order)

        return iiko_response if isinstance(iiko_response, dict) else {}
    except Exception as e:
        logger.error(
            f"Ошибка при закрытии заказа {order.id} в iiko Cloud: {e}",
            exc_info=True,
        )
        return {}


async def cancel_order_in_iiko(
    db: Session,
    order: DOrder,
    reason: Optional[str],
    removal_type_id: Optional[str],
    user_iiko_id: Optional[str],
) -> Dict[str, Any]:
    """
    Асинхронно отменить заказ в iiko Cloud через POST /api/1/order/cancel.
    Если заказ не был отправлен в iiko (iiko_id is None), ничего не делает.
    """
    if order.iiko_id is None:
        logger.warning(
            f"Отмена заказа {order.id} в iiko пропущена: iiko_id отсутствует"
        )
        return {}

    try:
        from config import IIKO_DEFAULT_REMOVAL_TYPE_ID

        org = db.query(Organization).filter(Organization.id == order.organization_id).first()
        if not org:
            logger.error(f"Организация для заказа {order.id} не найдена")
            return {}
        org_cloud_id = org.iiko_id_cloud or org.iiko_id
        if not org_cloud_id:
            logger.error(f"Организация {org.id} не имеет iiko_id")
            return {}

        effective_removal_type_id = removal_type_id or IIKO_DEFAULT_REMOVAL_TYPE_ID
        if not effective_removal_type_id:
            logger.error(
                f"Отмена заказа {order.id} в iiko пропущена: не задан removalTypeId "
                f"(ни в запросе, ни в IIKO_DEFAULT_REMOVAL_TYPE_ID)"
            )
            return {}

        payload: Dict[str, Any] = {
            "organizationId": org_cloud_id,
            "orderId": order.iiko_id,
            "removalTypeId": effective_removal_type_id,
            "removalComment": reason or "",
        }
        if user_iiko_id:
            payload["userIdForWriteoff"] = user_iiko_id

        logger.info(f"Отмена заказа {order.id} в iiko Cloud: {payload}")
        iiko_response = await iiko_service._make_request(
            api_type=IikoApiType.CLOUD,
            endpoint="/api/1/order/cancel",
            method="POST",
            data=payload,
        )

        logger.info(f"Ответ iiko /api/1/order/cancel для заказа {order.id}: {iiko_response}")

        if order.external_data is None:
            order.external_data = {}
        order.external_data["iiko_cancel_order"] = iiko_response if isinstance(iiko_response, dict) else {"raw": str(iiko_response)}
        flag_modified(order, "external_data")
        db.commit()
        db.refresh(order)

        return iiko_response if isinstance(iiko_response, dict) else {}
    except Exception as e:
        logger.error(
            f"Ошибка при отмене заказа {order.id} в iiko Cloud: {e}",
            exc_info=True,
        )
        return {}


async def change_payments_in_iiko(
    db: Session,
    order: DOrder,
    pay_data: Any,
) -> Dict[str, Any]:
    """
    Асинхронно установить оплаты на открытом iiko-заказе через
    POST /api/1/order/change_payments.

    Должно вызываться ПЕРЕД close_order_in_iiko, иначе iiko закроет заказ
    без оплат и в iikoFront он будет выглядеть «не пробит».

    pay_data — объект PayOrderRequest с полем paymentTypes (List[PayOrderPaymentType]).
    Если у заказа нет iiko_id или нет paymentTypes — ничего не делает.
    """
    if order.iiko_id is None:
        logger.warning(
            f"change_payments пропущен для заказа {order.id}: iiko_id отсутствует"
        )
        return {}

    if not pay_data:
        logger.warning(
            f"change_payments пропущен для заказа {order.id}: pay_data пустой"
        )
        return {}

    try:
        org = db.query(Organization).filter(Organization.id == order.organization_id).first()
        if not org:
            logger.error(f"Организация для заказа {order.id} не найдена")
            return {}
        org_cloud_id = org.iiko_id_cloud or org.iiko_id
        if not org_cloud_id:
            logger.error(f"Организация {org.id} не имеет iiko_id")
            return {}

        # Резолвим список типов оплат в единый формат:
        #   [(iiko_id, payment_type_kind), ...]
        # Поддерживаем оба варианта от фронта:
        #   1. paymentType: 8           — одиночный int (наш internal id)
        #   2. paymentTypes: [{...}]    — массив объектов с iiko_id/payment_type_kind
        resolved: List[tuple] = []

        single_id = getattr(pay_data, "paymentType", None)
        if single_id is not None:
            pt_row = db.query(PaymentType).filter(PaymentType.id == single_id).first()
            if not pt_row:
                logger.warning(
                    f"change_payments для заказа {order.id}: paymentType id={single_id} "
                    f"не найден в БД"
                )
            elif not pt_row.iiko_id:
                logger.warning(
                    f"change_payments для заказа {order.id}: paymentType id={single_id} "
                    f"найден, но без iiko_id"
                )
            else:
                resolved.append((pt_row.iiko_id, pt_row.payment_type_kind or "Cash"))

        for pt in (getattr(pay_data, "paymentTypes", None) or []):
            if pt.iiko_id:
                resolved.append((pt.iiko_id, pt.payment_type_kind or "Cash"))

        if not resolved:
            logger.warning(
                f"change_payments пропущен для заказа {order.id}: "
                f"не удалось собрать ни одного валидного paymentType"
            )
            return {}

        # Локально для совместимости с дальнейшим кодом
        valid_types = resolved

        total_sum = float(order.sum_order) if order.sum_order else 0.0
        # Если резолвили несколько типов оплаты — делим сумму поровну.
        # Это упрощение: фронт сейчас не передаёт sum per item. TODO: расширить
        # схему PayOrderRequest, чтобы фронт мог явно указывать sum по каждой оплате.
        if len(valid_types) > 1:
            logger.warning(
                f"change_payments для заказа {order.id}: получено "
                f"{len(valid_types)} типов оплат, делим сумму {total_sum} поровну"
            )
        per_payment = total_sum / len(valid_types) if valid_types else 0.0

        payments_payload: List[Dict[str, Any]] = []
        for iiko_id, kind in valid_types:
            payments_payload.append(
                {
                    "paymentTypeKind": kind,
                    "sum": per_payment,
                    "paymentTypeId": iiko_id,
                    "isProcessedExternally": True,
                }
            )

        payload: Dict[str, Any] = {
            "organizationId": org_cloud_id,
            "orderId": order.iiko_id,
            "payments": payments_payload,
        }

        logger.info(f"Установка оплат на заказ {order.id} в iiko Cloud: {payload}")
        iiko_response = await iiko_service._make_request(
            api_type=IikoApiType.CLOUD,
            endpoint="/api/1/order/change_payments",
            method="POST",
            data=payload,
        )

        logger.info(f"Ответ iiko /api/1/order/change_payments для заказа {order.id}: {iiko_response}")

        if order.external_data is None:
            order.external_data = {}
        order.external_data["iiko_change_payments"] = iiko_response if isinstance(iiko_response, dict) else {"raw": str(iiko_response)}
        flag_modified(order, "external_data")
        db.commit()
        db.refresh(order)

        return iiko_response if isinstance(iiko_response, dict) else {}
    except Exception as e:
        logger.error(
            f"Ошибка при change_payments для заказа {order.id}: {e}",
            exc_info=True,
        )
        return {}


async def add_items_to_iiko_order(
    db: Session,
    order: DOrder,
    items_to_add: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Асинхронно добавить позиции в существующий iiko-заказ через
    POST /api/1/order/add_items.

    `items_to_add` — список наших internal-items (как в order.items),
    откуда берётся productIikoId/amount/price/comment.

    iiko Cloud API не поддерживает удаление/изменение позиций — только добавление.
    Если у заказа нет iiko_id (он не был отправлен в iiko) — ничего не делаем.
    """
    if order.iiko_id is None:
        logger.warning(
            f"add_items пропущен для заказа {order.id}: iiko_id отсутствует"
        )
        return {}

    if not items_to_add:
        logger.info(f"add_items пропущен для заказа {order.id}: нет новых позиций")
        return {}

    try:
        org = db.query(Organization).filter(Organization.id == order.organization_id).first()
        if not org:
            logger.error(f"Организация для заказа {order.id} не найдена")
            return {}
        org_cloud_id = org.iiko_id_cloud or org.iiko_id
        if not org_cloud_id:
            logger.error(f"Организация {org.id} не имеет iiko_id")
            return {}

        iiko_items: List[Dict[str, Any]] = []
        for item in items_to_add:
            if not item.get("productIikoId"):
                logger.warning(
                    f"Пропуск позиции без productIikoId при add_items: {item}"
                )
                continue
            iiko_items.append(
                {
                    "productId": item["productIikoId"],
                    "type": "Product",
                    "amount": item["amount"],
                    "price": item["price"],
                    "comment": item.get("comment") or "",
                }
            )

        if not iiko_items:
            logger.info(f"add_items пропущен для заказа {order.id}: после фильтра позиций не осталось")
            return {}

        payload: Dict[str, Any] = {
            "organizationId": org_cloud_id,
            "orderId": order.iiko_id,
            "items": iiko_items,
        }

        logger.info(f"Добавление позиций в заказ {order.id} в iiko Cloud: {payload}")
        iiko_response = await iiko_service._make_request(
            api_type=IikoApiType.CLOUD,
            endpoint="/api/1/order/add_items",
            method="POST",
            data=payload,
        )

        logger.info(f"Ответ iiko /api/1/order/add_items для заказа {order.id}: {iiko_response}")

        if order.external_data is None:
            order.external_data = {}
        order.external_data["iiko_add_items"] = iiko_response if isinstance(iiko_response, dict) else {"raw": str(iiko_response)}
        flag_modified(order, "external_data")
        db.commit()
        db.refresh(order)

        return iiko_response if isinstance(iiko_response, dict) else {}
    except Exception as e:
        logger.error(
            f"Ошибка при add_items для заказа {order.id} в iiko Cloud: {e}",
            exc_info=True,
        )
        return {}


def _add_order_log(order: DOrder, action: str, user_id: Optional[int], message: str, details: Optional[dict] = None) -> None:
    """
    Добавить запись в лог операций заказа.
    Логи хранятся в external_data['logs'] как массив записей.
    """
    if order.external_data is None:
        order.external_data = {}
    
    if "logs" not in order.external_data:
        order.external_data["logs"] = []
    
    log_entry = {
        "action": action,
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "message": message,
        "details": details or {},
    }
    
    order.external_data["logs"].append(log_entry)
    order_id_str = str(order.id) if order.id else "new"
    logger.info(f"Order {order_id_str}: {action} - {message} (user_id={user_id})")


def pay_order(
    db: Session,
    order_id: int,
    user_id: Optional[int] = None,
    pay_data=None,
) -> DOrder:
    """
    Оплатить заказ - меняет статус на PAID.
    """
    order = db.query(DOrder).filter(DOrder.id == order_id).first()
    if not order:
        raise ValueError(f"Order with id {order_id} not found")

    if order.deleted:
        raise ValueError(f"Order {order_id} is deleted")

    old_status = order.state_order
    order.state_order = "PAID"

    # Обновляем payments в external_data или создаем запись
    if order.external_data is None:
        order.external_data = {}

    if "payments" not in order.external_data:
        order.external_data["payments"] = []

    payment_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "amount": float(order.sum_order) if order.sum_order else 0.0,
    }

    # Сохраняем данные об оплате от фронта
    if pay_data:
        if pay_data.paymentTypes:
            payment_types_info = [
                {
                    "id": pt.id,
                    "iiko_id": pt.iiko_id,
                    "name": pt.name,
                    "code": pt.code,
                    "payment_type_kind": pt.payment_type_kind,
                    "comment": pt.comment,
                    "combinable": pt.combinable,
                    "print_cheque": pt.print_cheque,
                    "payment_processing_type": pt.payment_processing_type,
                }
                for pt in pay_data.paymentTypes
            ]
            order.external_data["payment_types_info"] = payment_types_info
            payment_entry["payment_types"] = payment_types_info
        if pay_data.tipAmount:
            order.external_data["tip_amount"] = pay_data.tipAmount
            order.tips = float(pay_data.tipAmount)
            payment_entry["tip_amount"] = pay_data.tipAmount

    order.external_data["payments"].append(payment_entry)

    # Логируем оплату
    _add_order_log(order, "PAID", user_id, f"Заказ оплачен. Старый статус: {old_status}")

    # Обновляем прогресс квестов
    from services.quests.quests_service import update_quest_progress_for_order
    update_quest_progress_for_order(db, order)

    flag_modified(order, "external_data")
    db.commit()
    db.refresh(order)

    # Инвалидируем кэш
    try:
        invalidate_cache("orders")
    except Exception:
        logger.warning("Failed to invalidate orders cache after paying order")

    logger.info(f"Order {order_id} paid by user {user_id}")
    return order


def update_order(
    db: Session,
    order_id: int,
    data: UpdateOrderRequest,
    user_id: Optional[int] = None,
) -> DOrder:
    """
    Редактировать заказ - обновляет поля заказа.
    """
    order = db.query(DOrder).filter(DOrder.id == order_id).first()
    if not order:
        raise ValueError(f"Order with id {order_id} not found")
    
    if order.deleted:
        raise ValueError(f"Order {order_id} is deleted")
    
    if order.state_order in ["PAID", "CANCELLED", "CANCELED"]:
        raise ValueError(f"Cannot update order {order_id} with status {order.state_order}")
    
    # Сохраняем старое состояние для лога
    old_data = {
        "organizationId": order.organization_id,
        "tableId": int(order.tab_name) if order.tab_name else None,
        "guests": order.guest_count,
        "items_count": len(order.items) if order.items else 0,
        "sum": float(order.sum_order) if order.sum_order else 0.0,
    }
    
    # Обновляем поля с преобразованием id в iiko_id
    if data.organizationId is not None:
        org = db.query(Organization).filter(Organization.id == data.organizationId).first()
        if not org:
            raise ValueError(f"Organization with id {data.organizationId} not found")
        order.organization_id = data.organizationId
    
    if data.tableId is not None:
        table = db.query(Table).filter(Table.id == data.tableId).first()
        if not table:
            raise ValueError(f"Table with id {data.tableId} not found")
        order.tab_name = str(table.number)  # Сохраняем номер стола
        if order.external_data is None:
            order.external_data = {}
        order.external_data["tableId"] = data.tableId
        order.external_data["tableIikoId"] = table.iiko_id
        order.external_data["tableNumber"] = str(table.number)
    
    if data.guests is not None:
        order.guest_count = data.guests
    
    if data.items is not None:
        # Обновляем позиции с преобразованием productId в iiko_id
        items_json = []
        for item in data.items:
            product = db.query(Item).filter(Item.id == item.productId).first()
            if not product:
                raise ValueError(
                    f"Товар с id {item.productId} не найден в базе данных. "
                    f"Проверьте, что товар существует и не удален. "
                    f"Получить список доступных товаров можно через эндпоинт GET /menu"
                )
            
            if product.deleted:
                raise ValueError(
                    f"Товар с id {item.productId} (название: {product.name}) удален и не может быть добавлен в заказ. "
                    f"Используйте другой товар."
                )
            
            items_json.append({
                "productId": item.productId,  # Наш id
                "productIikoId": product.iiko_id,  # iiko_id для будущей отправки
                "amount": item.amount,
                "price": item.price,
                "sum": item.sum,
                "comment": item.comment,
            })
        order.items = items_json
        # Пересчитываем сумму
        total_sum = sum(item.sum for item in data.items)
        order.sum_order = total_sum
        
        # Удаляем старые записи в t_orders и создаем новые
        db.query(TOrder).filter(TOrder.order_id == order_id).delete()
        now = datetime.now()
        for order_item_data, request_item in zip(items_json, data.items):
            t_order = TOrder(
                order_id=order_id,
                item_id=order_item_data["productId"],
                count_order=int(order_item_data["amount"]),
                time_order=now,
                comment_order=order_item_data.get("comment"),
                iiko_id=None,
            )
            db.add(t_order)
    
    if data.comment is not None:
        if order.external_data is None:
            order.external_data = {}
        order.external_data["comment"] = data.comment
    
    if data.waiterId is not None:
        user = db.query(User).filter(User.id == data.waiterId).first()
        if not user:
            raise ValueError(f"User with id {data.waiterId} not found")
        waiter = db.query(Employees).filter(Employees.iiko_id == user.iiko_id).first()
        if not waiter:
            raise ValueError(f"Employee for user {data.waiterId} not found (no matching iiko_id)")
        if order.external_data is None:
            order.external_data = {}
        order.external_data["waiterId"] = data.waiterId
        order.external_data["waiterIikoId"] = waiter.iiko_id
    
    # Логируем редактирование
    new_data = {
        "organizationId": order.organization_id,
        "tableId": int(order.tab_name) if order.tab_name else None,
        "guests": order.guest_count,
        "items_count": len(order.items) if order.items else 0,
        "sum": float(order.sum_order) if order.sum_order else 0.0,
    }
    _add_order_log(order, "UPDATED", user_id, "Заказ отредактирован", {
        "old": old_data,
        "new": new_data,
    })

    flag_modified(order, "external_data")
    db.commit()
    db.refresh(order)
    
    # Инвалидируем кэш
    try:
        invalidate_cache("orders")
    except Exception:
        logger.warning("Failed to invalidate orders cache after updating order")
    
    logger.info(f"Order {order_id} updated by user {user_id}")
    return order


def cancel_order(
    db: Session,
    order_id: int,
    data: CancelOrderRequest,
    user_id: Optional[int] = None,
) -> DOrder:
    """
    Отменить заказ - меняет статус на CANCELLED.
    """
    order = db.query(DOrder).filter(DOrder.id == order_id).first()
    if not order:
        raise ValueError(f"Order with id {order_id} not found")
    
    if order.deleted:
        raise ValueError(f"Order {order_id} is deleted")
    
    if order.state_order == "PAID":
        raise ValueError(f"Cannot cancel paid order {order_id}")
    
    old_status = order.state_order
    order.state_order = "CANCELLED"
    
    # Сохраняем причину отмены
    if order.external_data is None:
        order.external_data = {}
    order.external_data["cancel_reason"] = data.reason
    
    # Логируем отмену
    _add_order_log(order, "CANCELLED", user_id, f"Заказ отменен. Причина: {data.reason or 'Не указана'}. Старый статус: {old_status}")

    flag_modified(order, "external_data")
    db.commit()
    db.refresh(order)
    
    # Инвалидируем кэш
    try:
        invalidate_cache("orders")
    except Exception:
        logger.warning("Failed to invalidate orders cache after cancelling order")
    
    logger.info(f"Order {order_id} cancelled by user {user_id}, reason: {data.reason}")
    return order
