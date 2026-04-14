from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class WarehouseDocumentItemRequest(BaseModel):
    """Позиция складского документа для создания/обновления"""
    item_id: Optional[int] = None  # ID товара в нашей БД
    item_iiko_id: Optional[str] = None  # ID товара в iiko
    item_name: Optional[str] = None  # Название товара (если нет item_id)
    quantity: float
    price: Optional[float] = None
    amount: Optional[float] = None  # Если не указано, будет рассчитано как quantity * price
    batch_number: Optional[str] = None
    expiry_date: Optional[str] = None  # ISO формат


class WarehouseDocumentItemResponse(BaseModel):
    """Позиция складского документа в ответе"""
    id: int
    document_id: int
    item_id: Optional[int] = None
    item_iiko_id: Optional[str] = None
    item_name: Optional[str] = None
    quantity: float
    price: Optional[float] = None
    amount: Optional[float] = None
    batch_number: Optional[str] = None
    expiry_date: Optional[str] = None  # ISO формат
    created_at: str  # ISO формат
    updated_at: str  # ISO формат

    class Config:
        from_attributes = True


class CreateWarehouseDocumentRequest(BaseModel):
    """Запрос на создание складского документа"""
    document_type: str  # "RECEIPT", "WRITEOFF", "INCOMING_INVOICE", "OUTGOING_INVOICE", "INVENTORY"
    document_number: Optional[str] = None  # Если не указан, будет сгенерирован
    date: str  # "DD.MM.YYYY" или ISO формат
    date_incoming: Optional[str] = None  # Дата поступления для накладных и актов
    organization_id: Optional[int] = None
    store_id: Optional[int] = None  # ID склада в нашей БД (Store.id)
    comment: Optional[str] = None
    items: List[WarehouseDocumentItemRequest]  # Список позиций документа
    
    # Поля для актов списания (WRITEOFF)
    account_id: Optional[int] = None  # ID счета в нашей БД (Account.id)
    status: Optional[str] = None  # Статус документа
    
    # Поля для приходных накладных (INCOMING_INVOICE)
    conception_id: Optional[int] = None  # ID концепции в нашей БД (Conception.id)
    invoice: Optional[str] = None  # Номер счет-фактуры
    supplier_id: Optional[int] = None  # ID поставщика в нашей БД (Supplier.id)
    due_date: Optional[str] = None  # Срок оплаты
    incoming_date: Optional[str] = None  # Входящая дата внешнего документа
    use_default_document_time: Optional[bool] = False
    incoming_document_number: Optional[str] = None  # Входящий номер внешнего документа
    employee_pass_to_account: Optional[str] = None  # Сотрудник
    transport_invoice_number: Optional[str] = None  # Номер товарно-транспортной накладной
    distribution_algorithm: Optional[str] = None  # Алгоритм распределения дополнительных расходов
    default_store: Optional[int] = None  # ID склада по умолчанию в нашей БД (Store.id)
    
    # Поля для расходных накладных (OUTGOING_INVOICE)
    account_to_code: Optional[str] = None  # Счет для списания товаров (код счета)
    revenue_account_code: Optional[str] = None  # Счет выручки (код счета)
    default_store_id: Optional[int] = None  # ID склада по умолчанию в нашей БД (Store.id)
    default_store_code: Optional[str] = None  # Код склада по умолчанию
    counteragent_id: Optional[int] = None  # ID контрагента в нашей БД (если будет модель Counteragent)
    counteragent_code: Optional[str] = None  # Контрагент (код)
    conception_id_outgoing: Optional[int] = None  # ID концепции для расходных накладных (Conception.id)
    
    # Deprecated поля для обратной совместимости (используйте новые поля выше)
    store_iiko_id: Optional[str] = None  # Deprecated: используйте store_id
    conception_iiko_id: Optional[str] = None  # Deprecated: используйте conception_id
    supplier_iiko_id: Optional[str] = None  # Deprecated: используйте supplier_id
    account_iiko_id: Optional[str] = None  # Deprecated: используйте account_id
    counteragent_iiko_id: Optional[str] = None  # Deprecated: используйте counteragent_id


class CreateWarehouseDocumentResponse(BaseModel):
    """Ответ на создание складского документа"""
    success: bool
    message: str
    document_id: Optional[int] = None  # ID документа в нашей БД
    iiko_id: Optional[str] = None  # ID документа в iiko (если создан через API)


class WarehouseDocumentResponse(BaseModel):
    """Складской документ в ответе"""
    id: int
    iiko_id: Optional[str] = None
    document_type: str
    document_number: Optional[str] = None
    date: str  # ISO формат
    organization_id: Optional[int] = None
    store_id: Optional[str] = None
    created_by: Optional[int] = None
    comment: Optional[str] = None
    created_at: str  # ISO формат
    updated_at: str  # ISO формат
    items: List[WarehouseDocumentItemResponse] = []

    class Config:
        from_attributes = True


class WarehouseDocumentsListResponse(BaseModel):
    """Список складских документов"""
    success: bool
    message: str
    documents: List[WarehouseDocumentResponse]
    total: int  # Общее количество документов


class WarehouseDocumentDetailResponse(BaseModel):
    """Детали складского документа"""
    success: bool
    message: str
    document: WarehouseDocumentResponse


class UpdateWarehouseDocumentRequest(BaseModel):
    """Запрос на обновление складского документа"""
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    date: Optional[str] = None  # "DD.MM.YYYY" или ISO формат
    store_id: Optional[str] = None
    comment: Optional[str] = None
    items: Optional[List[WarehouseDocumentItemRequest]] = None  # Если указано, заменяет все позиции


class UpdateWarehouseDocumentResponse(BaseModel):
    """Ответ на обновление складского документа"""
    success: bool
    message: str
    document_id: int


class DeleteWarehouseDocumentResponse(BaseModel):
    """Ответ на удаление складского документа"""
    success: bool
    message: str


class SyncWarehouseDocumentsRequest(BaseModel):
    """Запрос на синхронизацию складских документов из iiko"""
    from_date: Optional[str] = None  # "DD.MM.YYYY" или ISO формат
    to_date: Optional[str] = None  # "DD.MM.YYYY" или ISO формат
    organization_id: Optional[int] = None


class SyncWarehouseDocumentsResponse(BaseModel):
    """Ответ на синхронизацию складских документов"""
    success: bool
    message: str
    created: int
    updated: int
    errors: int


class CreateWriteoffItemRequest(BaseModel):
    """Позиция акта списания для создания в iiko"""
    item_id: Optional[int] = None  # ID товара в нашей БД (Item.id)
    product_id: Optional[str] = None  # ID товара в iiko (Item.iiko_id) - обязательное, если не указан item_id
    amount: float = Field(gt=0)  # Количество (должно быть > 0) - обязательное
    product_size_id: Optional[str] = None  # ID размера товара
    amount_factor: Optional[float] = Field(default=None, ge=0)  # Коэффициент количества (>= 0)
    measure_unit_id: Optional[str] = None  # ID единицы измерения
    container_id: Optional[str] = None  # ID фасовки
    cost: Optional[float] = Field(default=None, ge=0)  # Стоимость (>= 0) - опциональное
    num: Optional[int] = Field(default=None, gt=0)  # Номер позиции (если указан, должен быть > 0)


class CreateWriteoffDocumentRequest(BaseModel):
    """Запрос на создание акта списания в iiko"""
    date_incoming: str  # Дата в формате "YYYY-MM-DD" или "DD.MM.YYYY" - обязательное
    store_id: int  # ID склада в нашей БД (Store.id) - обязательное
    account_id: int  # ID счета в нашей БД (Account.id) - обязательное
    organization_id: int  # ID организации в нашей БД
    status: Optional[str] = None  # Статус документа (по умолчанию "NEW")
    document_number: Optional[str] = None  # Номер документа (если не указан, генерируется автоматически)
    comment: Optional[str] = None  # Комментарий к документу
    items: List[CreateWriteoffItemRequest] = Field(min_length=1)  # Список позиций (минимум 1 позиция) - обязательное
    
    # Поля для склада и концепции
    store_iiko_id: Optional[str] = None  # iiko_id склада (используется если указан)
    account_iiko_id: Optional[str] = None  # iiko_id счета (используется если указан)
    conception_iiko_id: Optional[str] = None  # iiko_id концепции (опционально)
    
    @field_validator('items')
    @classmethod
    def validate_items_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Список позиций не может быть пустым')
        return v


class CreateWriteoffDocumentResponse(BaseModel):
    """Ответ на создание акта списания в iiko"""
    success: bool
    message: str
    iiko_id: Optional[str] = None  # ID созданного документа в iiko
    document_id: Optional[int] = None  # ID документа в нашей БД (если сохранен)


class SimpleWriteoffItemRequest(BaseModel):
    """Упрощенная позиция акта списания"""
    id: int = Field(description="ID товара из таблицы items")
    amount: float = Field(gt=0, description="Количество товара")
    price: Optional[float] = Field(default=None, ge=0, description="Цена за единицу (опционально)")
    sum: Optional[float] = Field(default=None, ge=0, description="Сумма позиции (опционально)")


class SimpleInvoiceItemRequest(BaseModel):
    """Упрощенная позиция накладной (приходной/расходной)
    
    Формат как в тестовом скрипте:
    - id: ID товара из таблицы items (нашего)
    - amount: количество товара
    - price: цена за единицу
    - sum: сумма (обязательное поле)
    """
    id: int = Field(description="ID товара из таблицы items")
    amount: float = Field(gt=0, description="Количество товара")
    price: float = Field(ge=0, description="Цена за единицу")
    sum: float = Field(ge=0, description="Сумма позиции")


class SimpleWriteoffDocumentRequest(BaseModel):
    """Упрощенный запрос на создание акта списания
    
    Поля:
    - storeId: ID склада из таблицы stores (опционально, в TESTING_MODE используется фиксированный)
    - conceptionId: ID концепции из таблицы conceptions (опционально)
    - account_id: ID аккаунта из таблицы account_list
    - date: дата/время (ISO формат или YYYY-MM-DDTHH:MM)
    - comment: комментарий
    - items: список позиций (id, amount)
    """

    storeId: Optional[int] = Field(default=None, description="ID склада из таблицы stores (опционально)")
    conceptionId: Optional[int] = Field(default=None, description="ID концепции из таблицы conceptions (опционально)")
    account_id: int = Field(description="ID аккаунта из таблицы account_list")
    date: str = Field(description="Дата со временем (ISO формат или YYYY-MM-DDTHH:MM)")
    comment: Optional[str] = Field(default=None, description="Комментарий к документу")
    items: List[SimpleWriteoffItemRequest] = Field(min_length=1, description="Список позиций документа")
    
    @field_validator('items')
    @classmethod
    def validate_items_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Список позиций не может быть пустым')
        return v


class AccountResponse(BaseModel):
    """Ответ с информацией о счете"""
    id: int
    iiko_id: str
    name: Optional[str] = None
    code: Optional[str] = None
    type: Optional[str] = None
    system: Optional[bool] = None
    
    class Config:
        from_attributes = True


class AccountsListResponse(BaseModel):
    """Ответ со списком счетов"""
    accounts: List[AccountResponse]


class SimpleIncomingInvoiceRequest(BaseModel):
    """Упрощенный запрос на создание приходной накладной
    
    Поля:
    - storeId: ID склада из таблицы stores (опционально, в TESTING_MODE используется фиксированный)
    - conceptionId: ID концепции из таблицы conceptions (опционально)
    - dateIncoming: дата в формате dd.mm.YYYY
    - comment: комментарий
    - supplier: iiko_id поставщика (опционально)
    - invoice: номер счет-фактуры (опционально)
    - items: список позиций с id (нашего), amount, price, sum
    """
    storeId: Optional[int] = Field(default=None, description="ID склада из таблицы stores (опционально)")
    conceptionId: Optional[int] = Field(default=None, description="ID концепции из таблицы conceptions (опционально)")
    dateIncoming: str = Field(description="Дата в формате dd.mm.YYYY")
    comment: Optional[str] = Field(default=None, description="Комментарий к документу")
    supplier: Optional[str] = Field(default=None, description="iiko_id поставщика")
    invoice: Optional[str] = Field(default=None, description="Номер счет-фактуры")
    items: List[SimpleInvoiceItemRequest] = Field(min_length=1, description="Список позиций документа")
    
    @field_validator('items')
    @classmethod
    def validate_items_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Список позиций не может быть пустым')
        return v


class SimpleOutgoingInvoiceRequest(BaseModel):
    """Упрощенный запрос на создание расходной накладной
    
    Поля:
    - storeId: ID склада из таблицы stores (опционально, в TESTING_MODE используется фиксированный)
    - conceptionId: ID концепции из таблицы conceptions (опционально)
    - dateIncoming: дата в формате dd.mm.YYYY
    - comment: комментарий
    - accountToCode: код счета (опционально)
    - supplier: iiko_id поставщика (опционально)
    - items: список позиций с id (нашего), amount, price, sum
    """
    storeId: Optional[int] = Field(default=None, description="ID склада из таблицы stores (опционально)")
    conceptionId: Optional[int] = Field(default=None, description="ID концепции из таблицы conceptions (опционально)")
    dateIncoming: str = Field(description="Дата в формате dd.mm.YYYY")
    comment: Optional[str] = Field(default=None, description="Комментарий к документу")
    accountToCode: Optional[str] = Field(default=None, description="Код счета выручки")
    supplier: Optional[str] = Field(default=None, description="iiko_id поставщика (опционально)")
    items: List[SimpleInvoiceItemRequest] = Field(min_length=1, description="Список позиций документа")
    
    @field_validator('items')
    @classmethod
    def validate_items_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Список позиций не может быть пустым')
        return v


class SimpleInventoryItemRequest(BaseModel):
    """Упрощенная позиция инвентаризации
    
    Формат как в тестовом скрипте:
    - id: ID товара из таблицы items (нашего)
    - amount: количество (будет использовано как amountContainer)
    - price: цена (опционально)
    - sum: сумма (опционально)
    - containerId: iiko_id фасовки (опционально)
    - comment: комментарий к позиции (опционально)
    """
    id: int = Field(description="ID товара из таблицы items")
    amount: float = Field(gt=0, description="Количество товара (будет использовано как amountContainer)")
    price: Optional[float] = Field(default=None, ge=0, description="Цена за единицу")
    sum: Optional[float] = Field(default=None, ge=0, description="Сумма позиции")
    containerId: Optional[str] = Field(default=None, description="iiko_id фасовки")
    comment: Optional[str] = Field(default=None, description="Комментарий к позиции")


class SimpleInventoryRequest(BaseModel):
    """Упрощенный запрос на создание инвентаризации
    
    Поля:
    - storeId: ID склада из таблицы stores (опционально, в TESTING_MODE используется фиксированный)
    - dateIncoming: дата в формате dd.mm.YYYY
    - comment: комментарий к документу
    - accountSurplusCode: код счета для излишков (по умолчанию "5.10")
    - accountShortageCode: код счета для недостачи (по умолчанию "5.09")
    - items: список позиций с id (нашего), amount, price, sum
    """
    storeId: Optional[int] = Field(default=None, description="ID склада из таблицы stores (опционально)")
    dateIncoming: str = Field(description="Дата в формате dd.mm.YYYY")
    comment: Optional[str] = Field(default=None, description="Комментарий к документу")
    accountSurplusCode: Optional[str] = Field(default="5.10", description="Код счета для излишков")
    accountShortageCode: Optional[str] = Field(default="5.09", description="Код счета для недостачи")
    items: List[SimpleInventoryItemRequest] = Field(min_length=1, description="Список позиций документа")
    
    @field_validator('items')
    @classmethod
    def validate_items_not_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Список позиций не может быть пустым')
        return v


class BalanceProductResponse(BaseModel):
    """Товар в остатках"""
    item: str  # Название товара
    amount: float  # Количество
    sum: float  # Сумма


class BalanceStoreResponse(BaseModel):
    """Остатки по складу"""
    store: str  # Название склада
    sum: float  # Сумма всех товаров
    products: List[BalanceProductResponse]  # Список товаров


class BalanceStoresResponse(BaseModel):
    """Ответ на запрос остатков по складам"""
    success: bool
    message: str
    data: List[BalanceStoreResponse]  # Список остатков по складам


class StoreResponse(BaseModel):
    """Информация о складе из iiko"""
    id: str = Field(..., description="iiko_id склада")
    name: Optional[str] = Field(None, description="Название склада")
    code: Optional[str] = Field(None, description="Код склада")


class StoresListResponse(BaseModel):
    """Ответ со списком складов"""
    success: bool
    message: str
    data: List[StoreResponse]  # Список складов

