from fastapi import APIRouter, Depends, Query, HTTPException, Path, Body
from sqlalchemy.orm import Session
from schemas.orders import (
    OrderArrayResponse,
    CreateOrderRequest,
    CreateOrderResponse,
    UpdateOrderRequest,
    UpdateOrderResponse,
    PayOrderRequest,
    PayOrderResponse,
    CancelOrderRequest,
    CancelOrderResponse,
)
import logging
from services.orders.orders_services import (
    get_all_orders,
    create_order_from_app,
    pay_order,
    update_order,
    cancel_order,
    cancel_order_in_iiko,
    add_items_to_iiko_order,
)
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
    date: Optional[str] = Query(default=None, description="Точная дата DD.MM.YYYY"),
    date_from: Optional[str] = Query(default=None, description="Начало периода DD.MM.YYYY"),
    date_to: Optional[str] = Query(default=None, description="Конец периода DD.MM.YYYY"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Получить список заказов.

    Фильтрация по дате:
    - **date** — точная дата (DD.MM.YYYY)
    - **date_from** / **date_to** — диапазон дат (DD.MM.YYYY)
    """
    orders = get_all_orders(
        db=db,
        organization_id=organization_id,
        user_id=user_id,
        state=state,
        date=date,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {
        "success": True,
        "message": "got orders",
        "orders": orders,
    }


@router.post("/orders", response_model=CreateOrderResponse)
async def create_order(
    order_data: CreateOrderRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Создать заказ только в нашей БД (без отправки в iiko),
    с пометкой, что он создан через наше приложение.
    
    **Описание полей запроса:**
    
    - `organizationId` (int, опциональное): ID организации из нашей таблицы `organizations`.
      Получить список организаций можно через эндпоинт `GET /organizations`.
      Если не указано, заказ будет создан без привязки к организации.
    
    - `tableId` (int, опциональное): ID стола из нашей таблицы `tables`.
      Получить список столов можно через эндпоинт `GET /tables`.
      Если указано, система автоматически преобразует наш ID в iiko_id стола.
    
    - `waiterId` (int, опциональное): ID официанта из нашей таблицы `employees`.
      Получить список сотрудников можно через эндпоинт `GET /employees`.
      Если указано, система автоматически преобразует наш ID в iiko_id официанта.
      **Для тестов используй id 322256**
    
    - `guests` (int, опциональное): Количество гостей за столом.
      Должно быть положительным числом.
    
    - `items` (List[CreateOrderItemRequest], обязательное): Список позиций заказа.
      Минимум 1 позиция. Каждая позиция содержит:
      - `productId` (int, обязательное): ID товара из нашей таблицы `items`.
        Получить список товаров можно через эндпоинт `GET /menu`.
        Система автоматически преобразует наш ID в iiko_id товара.
      - `amount` (float, обязательное): Количество товара (должно быть > 0).
      - `price` (float, обязательное): Цена за единицу товара (должна быть >= 0).
      - `sum` (float, обязательное): Сумма позиции (обычно = amount * price, должна быть >= 0).
      - `comment` (str, опциональное): Комментарий к позиции.
    
    - `payments` (List[OrderPayment], опциональное): Список оплат.
      Получить доступные виды оплат можно через эндпоинт `GET /payment-types`.
      Каждая оплата содержит:
      - `paymentTypeId` (int, обязательное): ID вида оплаты из нашей таблицы `payment_types`.
      - `sum` (float, обязательное): Сумма оплаты.
      - `isProcessedExternally` (bool, опциональное): Обработана ли оплата внешне (по умолчанию true).

    - `comment` (str, опциональное): Комментарий к заказу.

    **Пример запроса:**
    ```json
    {
      "organizationId": 1,
      "tableId": 5,
      "waiterId": 3,
      "guests": 2,
      "items": [
        {
          "productId": 10,
          "amount": 2.0,
          "price": 1500.0,
          "sum": 3000.0,
          "comment": "Без лука"
        }
      ],
      "payments": [
        {
          "paymentTypeId": 1,
          "sum": 3000.0
        }
      ],
      "comment": "Столик у окна"
    }
    ```
    
    **Ответ:**
    - `success` (bool): Успешность операции
    - `message` (str): Сообщение о результате
    - `order_id` (int): ID созданного заказа в нашей БД
    - `iiko_id` (str, опциональное): ID заказа в iiko (пока null, так как заказ создается только локально)
    
    **Пример запроса из TODO.md:**
    ```json
    {
      "organizationId": 1,
      "tableId": 5,
      "waiterId": 322256,
      "guests": 2,
      "items": [
        {
          "productId": 2239,
          "amount": 2.0,
          "price": 1500.0,
          "sum": 3000.0,
          "comment": "Без лука"
        },
        {
          "productId": 2259,
          "amount": 1.0,
          "price": 2500.0,
          "sum": 2500.0,
          "comment": "Острое"
        }
      ],
      "comment": "Столик у окна"
    }
    ```
    """
    try:
        new_order = create_order_from_app(
            db=db,
            data=order_data,
            user_id=user.id if hasattr(user, "id") else None,
        )

        # Отправляем заказ в iiko Cloud, если включена отправка
        from config import IIKO_SEND_ORDERS

        iiko_meta = None
        if IIKO_SEND_ORDERS:
            from services.orders.orders_services import create_order_in_iiko

            iiko_meta = await create_order_in_iiko(
                db=db,
                order=new_order,
                guests=order_data.guests,
                comment=order_data.comment,
            )

        return CreateOrderResponse(
            success=True,
            message="Order created locally and sent to iiko" if IIKO_SEND_ORDERS else "Order created locally (iiko sending disabled)",
            order_id=new_order.id,
            iiko_id=new_order.iiko_id,
            iiko_correlation_id=iiko_meta.get("correlationId") if iiko_meta else None,
            iiko_number=iiko_meta.get("number") if iiko_meta else None,
            iiko_full_sum=float(iiko_meta.get("fullSum"))
            if iiko_meta and iiko_meta.get("fullSum") is not None
            else None,
        )
    except ValueError as e:
        logger.error(f"Error creating order: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating order: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.post("/orders/{order_id}/pay", response_model=PayOrderResponse)
async def pay_order_endpoint(
    order_id: int = Path(..., description="ID заказа в нашей БД"),
    pay_data: PayOrderRequest = Body(default=None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Оплатить заказ - меняет статус на PAID.
    После создания заказ имеет статус CREATED, после оплаты - PAID.
    
    **Path Parameters:**
    - `order_id` (int, обязательное): ID заказа в нашей БД, который нужно оплатить.
      Получить список заказов можно через эндпоинт `GET /orders`.
    
    **Описание:**
    - Операция оплаты логируется в `external_data['logs']` заказа.
    - Информация об оплате сохраняется в `external_data['payments']`.
    - После оплаты заказ нельзя редактировать или отменять.
    
    **Ответ:**
    - `success` (bool): Успешность операции
    - `message` (str): Сообщение о результате
    - `order_id` (int): ID заказа
    - `status` (str): Новый статус заказа ("PAID")
    
    **Ошибки:**
    - `404`: Заказ не найден или удален
    """
    try:
        order = pay_order(
            db=db,
            order_id=order_id,
            user_id=user.id if hasattr(user, "id") else None,
            pay_data=pay_data,
        )

        # Закрываем заказ в iiko Cloud, если включена отправка.
        # Двухэтапный процесс по спеке iiko Cloud:
        #   1. /api/1/order/change_payments — установить оплаты на открытый заказ.
        #   2. /api/1/order/close — фискально закрыть заказ.
        # Без шага 1 iiko закроет заказ «без оплат», и в iikoFront он будет
        # выглядеть «не пробит».
        from config import IIKO_SEND_ORDERS
        if IIKO_SEND_ORDERS and order.iiko_id:
            from services.orders.orders_services import (
                change_payments_in_iiko,
                close_order_in_iiko,
            )
            await change_payments_in_iiko(db=db, order=order, pay_data=pay_data)
            await close_order_in_iiko(db=db, order=order, pay_data=pay_data)

        return PayOrderResponse(
            success=True,
            message="Order paid successfully",
            order_id=order.id,
            status=order.state_order,
        )
    except ValueError as e:
        logger.error(f"Error paying order: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error paying order: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.put("/orders/{order_id}", response_model=UpdateOrderResponse)
async def update_order_endpoint(
    order_id: int = Path(..., description="ID заказа в нашей БД"),
    order_data: UpdateOrderRequest = Body(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Редактировать заказ - обновляет поля заказа (позиции, комментарий, стол и т.д.).
    Можно редактировать только заказы со статусом CREATED (не оплаченные и не отмененные).
    
    **Path Parameters:**
    - `order_id` (int, обязательное): ID заказа в нашей БД, который нужно отредактировать.
      Получить список заказов можно через эндпоинт `GET /orders`.
    
    **Описание полей запроса:**
    
    Все поля опциональны - обновляются только указанные поля.
    
    - `organizationId` (int, опциональное): ID организации из нашей таблицы `organizations`.
      Получить список организаций можно через эндпоинт `GET /organizations`.
    
    - `tableId` (int, опциональное): ID стола из нашей таблицы `tables`.
      Получить список столов можно через эндпоинт `GET /tables`.
      Система автоматически преобразует наш ID в iiko_id стола.
    
    - `waiterId` (int, опциональное): ID официанта из нашей таблицы `employees`.
      Получить список сотрудников можно через эндпоинт `GET /employees`.
      Система автоматически преобразует наш ID в iiko_id официанта.
      **Для тестов используй id 322256**
    
    - `guests` (int, опциональное): Количество гостей за столом.
      Должно быть положительным числом.
    
    - `items` (List[CreateOrderItemRequest], опциональное): Список позиций заказа.
      Если указано, **полностью заменяет** все существующие позиции заказа.
      Каждая позиция содержит:
      - `productId` (int, обязательное): ID товара из нашей таблицы `items`.
        Получить список товаров можно через эндпоинт `GET /menu`.
        Система автоматически преобразует наш ID в iiko_id товара.
      - `amount` (float, обязательное): Количество товара (должно быть > 0).
      - `price` (float, обязательное): Цена за единицу товара (должна быть >= 0).
      - `sum` (float, обязательное): Сумма позиции (обычно = amount * price, должна быть >= 0).
      - `comment` (str, опциональное): Комментарий к позиции.
    
    - `comment` (str, опциональное): Комментарий к заказу.
    
    **Пример запроса:**
    ```json
    {
      "tableId": 7,
      "guests": 3,
      "items": [
        {
          "productId": 15,
          "amount": 1.0,
          "price": 2000.0,
          "sum": 2000.0
        }
      ],
      "comment": "Обновленный комментарий"
    }
    ```
    
    **Ошибки:**
    - `404`: Заказ не найден
    - `400`: Заказ нельзя редактировать (уже оплачен или отменен), или указаны неверные ID (товар, стол, официант не найдены)
    """
    try:
        # Снимаем снапшот старых items ДО апдейта, чтобы потом diff'ить
        # и отправить в iiko через add_items только реально новые позиции.
        from models.d_order import DOrder as _DOrder
        old_order_row = db.query(_DOrder).filter(_DOrder.id == order_id).first()
        old_items = list(old_order_row.items or []) if old_order_row else []

        order = update_order(
            db=db,
            order_id=order_id,
            data=order_data,
            user_id=user.id if hasattr(user, "id") else None,
        )

        # iiko Cloud не умеет редактировать существующий зальный заказ
        # (нет удаления/изменения позиций, только добавление через /api/1/order/add_items).
        # Поэтому отправляем в iiko ТОЛЬКО новые позиции (которых не было в old_items).
        # Удаления, изменения количества, смена стола/гостей/комментария — только локально.
        from config import IIKO_SEND_ORDERS
        if IIKO_SEND_ORDERS and order.iiko_id and order_data.items is not None:
            old_iiko_ids = {
                item.get("productIikoId")
                for item in old_items
                if item.get("productIikoId")
            }
            new_items_to_send = [
                item for item in (order.items or [])
                if item.get("productIikoId") and item.get("productIikoId") not in old_iiko_ids
            ]
            if new_items_to_send:
                await add_items_to_iiko_order(
                    db=db,
                    order=order,
                    items_to_add=new_items_to_send,
                )
            else:
                logger.info(
                    f"Order {order.id}: новых позиций для iiko не найдено, "
                    f"add_items не вызываем"
                )

        return UpdateOrderResponse(
            success=True,
            message="Order updated successfully",
            order_id=order.id,
        )
    except ValueError as e:
        logger.error(f"Error updating order: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating order: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.post("/orders/{order_id}/cancel", response_model=CancelOrderResponse)
async def cancel_order_endpoint(
    order_id: int = Path(..., description="ID заказа в нашей БД"),
    cancel_data: CancelOrderRequest = Body(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Отменить заказ - меняет статус на CANCELLED.
    Можно отменить только неоплаченные заказы.
    Все операции логируются в external_data заказа.
    
    **Path Parameters:**
    - `order_id` (int, обязательное): ID заказа в нашей БД, который нужно отменить.
      Получить список заказов можно через эндпоинт `GET /orders`.
    
    **Описание полей запроса:**
    - `reason` (str, опциональное): Причина отмены заказа.
      Сохраняется в `external_data['cancel_reason']` заказа.
    
    **Пример запроса:**
    ```json
    {
      "reason": "Клиент передумал"
    }
    ```
    
    **Ответ:**
    - `success` (bool): Успешность операции
    - `message` (str): Сообщение о результате
    - `order_id` (int): ID заказа
    - `status` (str): Новый статус заказа ("CANCELLED")
    
    **Ошибки:**
    - `404`: Заказ не найден или удален
    - `400`: Заказ нельзя отменить (уже оплачен)
    """
    try:
        order = cancel_order(
            db=db,
            order_id=order_id,
            data=cancel_data,
            user_id=user.id if hasattr(user, "id") else None,
        )

        # Отменяем заказ в iiko Cloud, если включена отправка
        from config import IIKO_SEND_ORDERS
        if IIKO_SEND_ORDERS and order.iiko_id:
            user_iiko_id = getattr(user, "iiko_id", None)
            await cancel_order_in_iiko(
                db=db,
                order=order,
                reason=cancel_data.reason,
                removal_type_id=cancel_data.removalTypeId,
                user_iiko_id=user_iiko_id,
            )

        return CancelOrderResponse(
            success=True,
            message="Order cancelled successfully",
            order_id=order.id,
            status=order.state_order,
        )
    except ValueError as e:
        logger.error(f"Error cancelling order: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error cancelling order: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )