from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class OrderItemResponse(BaseModel):
    product_id: Optional[int] = None
    open_time: Optional[datetime] = None
    dish_name: Optional[str] = None
    dish_amount_int: Optional[int] = None
    dish_category: Optional[str] = None
    dish_group: Optional[str] = None
    dish_discount_sum_int: Optional[float] = None
    restaurant_section_id: Optional[str] = None
    table_num: Optional[int] = None
    order_waiter_id: Optional[str] = None
    pay_types: Optional[str] = None
    product_cost_base_product_cost: Optional[float] = None
    comment: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    organization_name: Optional[str]
    table: Optional[str] = None
    room: Optional[str]
    status: Optional[str]
    sum_order: Optional[float]
    final_sum: Optional[float]
    bank_commission: Optional[float]
    items: List[OrderItemResponse]


class OrderArrayResponse(BaseModel):
    success: bool
    message: str
    orders: Optional[List[OrderResponse]] = []


class CreateOrderItemRequest(BaseModel):
    """Позиция заказа при создании из нашего приложения
    
    **Поля:**
    - `productId` (int, обязательное): ID товара из нашей таблицы `items` (получить можно через эндпоинт `/items`)
    - `amount` (float, обязательное): Количество товара (должно быть > 0)
    - `price` (float, обязательное): Цена за единицу товара (должна быть >= 0)
    - `sum` (float, обязательное): Сумма позиции (обычно = amount * price, должна быть >= 0)
    - `comment` (str, опциональное): Комментарий к позиции
    """

    productId: int  # ID из нашей таблицы items
    amount: float
    price: float
    sum: float
    comment: Optional[str] = None


class OrderPayment(BaseModel):
    """Оплата в заказе

    **Поля:**
    - `paymentTypeId` (int, обязательное): ID вида оплаты из нашей таблицы `payment_types` (получить через `/payment-types`)
    - `sum` (float, обязательное): Сумма оплаты
    - `isProcessedExternally` (bool, опциональное): Обработана ли оплата внешне (по умолчанию True)
    """
    paymentTypeId: int
    sum: float
    isProcessedExternally: Optional[bool] = True


class CreateOrderRequest(BaseModel):
    """Создание заказа (пока только в нашей БД, формат iiko-like упрощённый)

    **Поля:**
    - `organizationId` (int, опциональное): ID организации из нашей таблицы `organizations` (получить через `/organizations`)
    - `tableId` (int, опциональное): ID стола из нашей таблицы `tables` (получить через `/tables`)
    - `waiterId` (int, опциональное): ID официанта из нашей таблицы `employees` (получить через `/employees`)
    - `guests` (int, опциональное): Количество гостей
    - `room` (str, опциональное): Название зала ("Зал", "Летник" и т.д.)
    - `items` (List[CreateOrderItemRequest], обязательное): Список позиций заказа (минимум 1 позиция)
    - `payments` (List[OrderPayment], опциональное): Список оплат (получить виды оплат через `/payment-types`)
    - `comment` (str, опциональное): Комментарий к заказу
    """

    organizationId: Optional[int] = None  # ID из нашей таблицы organizations
    tableId: Optional[int] = None  # ID из нашей таблицы tables
    waiterId: Optional[int] = None  # ID из нашей таблицы employees
    guests: Optional[int] = None
    room: Optional[str] = None  # Название зала ("Зал", "Летник" и т.д.)
    items: List[CreateOrderItemRequest]
    payments: Optional[List[OrderPayment]] = None
    comment: Optional[str] = None


class CreateOrderResponse(BaseModel):
    success: bool
    message: str
    order_id: int
    iiko_id: Optional[str] = None
    iiko_correlation_id: Optional[str] = None
    iiko_number: Optional[str] = None
    iiko_full_sum: Optional[float] = None


class UpdateOrderRequest(BaseModel):
    """Редактирование заказа (можно изменить позиции, комментарий и т.д.)
    
    **Поля:**
    - `organizationId` (int, опциональное): ID организации из нашей таблицы `organizations` (получить через `/organizations`)
    - `tableId` (int, опциональное): ID стола из нашей таблицы `tables` (получить через `/tables`)
    - `waiterId` (int, опциональное): ID официанта из нашей таблицы `employees` (получить через `/employees`)
    - `guests` (int, опциональное): Количество гостей
    - `items` (List[CreateOrderItemRequest], опциональное): Список позиций заказа (если указано, заменяет все позиции)
    - `comment` (str, опциональное): Комментарий к заказу
    """

    organizationId: Optional[int] = None  # ID из нашей таблицы organizations
    tableId: Optional[int] = None  # ID из нашей таблицы tables
    waiterId: Optional[int] = None  # ID из нашей таблицы employees
    guests: Optional[int] = None
    items: Optional[List[CreateOrderItemRequest]] = None
    comment: Optional[str] = None


class PayOrderPaymentType(BaseModel):
    """Вид оплаты, приходящий от фронта при оплате"""
    id: Optional[int] = None
    iiko_id: Optional[str] = None
    name: Optional[str] = None
    code: Optional[str] = None
    payment_type_kind: Optional[str] = None
    comment: Optional[str] = None
    combinable: Optional[bool] = None
    print_cheque: Optional[bool] = None
    payment_processing_type: Optional[str] = None


class PayOrderRequest(BaseModel):
    # Фронт обычно шлёт одиночный int — наш внутренний id вида оплаты
    # из таблицы payment_types. Бэк сам резолвит iiko_id и payment_type_kind.
    paymentType: Optional[int] = None
    # Запасной/расширенный вариант: список объектов с уже готовыми iiko_id.
    # Используется, если фронт умеет передавать несколько способов оплаты.
    paymentTypes: Optional[List[PayOrderPaymentType]] = None
    tipAmount: Optional[str] = None


class PayOrderResponse(BaseModel):
    success: bool
    message: str
    order_id: int
    status: str


class CancelOrderRequest(BaseModel):
    """Запрос на отмену заказа"""

    reason: Optional[str] = None
    removalTypeId: Optional[str] = None  # iiko uuid типа списания (для /api/1/order/cancel)


class CancelOrderResponse(BaseModel):
    success: bool
    message: str
    order_id: int
    status: str


class UpdateOrderResponse(BaseModel):
    success: bool
    message: str
    order_id: int

