"""
Модели для складских документов (поступление, списание)
"""
from sqlalchemy import Column, Integer, String, ForeignKey, Numeric, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from database.database import Base


class WarehouseDocumentType(enum.Enum):
    """Тип складского документа"""
    RECEIPT = "RECEIPT"  # Поступление
    WRITEOFF = "WRITEOFF"  # Списание
    INCOMING_INVOICE = "INCOMING_INVOICE"  # Приходная накладная
    OUTGOING_INVOICE = "OUTGOING_INVOICE"  # Расходная накладная
    INVENTORY = "INVENTORY"  # Инвентаризация


class WarehouseDocument(Base):
    """Складской документ (поступление, списание, приходная/расходная накладная, инвентаризация)"""
    __tablename__ = "warehouse_documents"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True, index=True)  # ID документа в iiko
    document_type = Column(String(20), nullable=False, index=True)  # RECEIPT, WRITEOFF, INCOMING_INVOICE, OUTGOING_INVOICE
    document_source = Column(String(20), nullable=True, index=True)  # WRITEOFF, INCOMING_INVOICE, OUTGOING_INVOICE
    document_number = Column(String(100), nullable=True, index=True)  # Номер документа
    date = Column(DateTime, nullable=False, index=True)  # Дата документа
    date_incoming = Column(DateTime, nullable=True)  # Дата поступления (для актов списания)
    
    # Статус документа
    status = Column(String(20), nullable=True, index=True)  # NEW, PROCESSED, DELETED
    
    # Связи
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    store_id = Column(String(50), nullable=True, index=True)  # ID склада в iiko
    default_store = Column(String(50), nullable=True)  # Склад по умолчанию (для приходных накладных)
    default_store_id = Column(String(50), nullable=True)  # ID склада по умолчанию (для расходных накладных)
    default_store_code = Column(String(50), nullable=True)  # Код склада по умолчанию (для расходных накладных)
    account_id = Column(String(50), nullable=True, index=True)  # ID счета (iiko_id) - для актов списания
    account_to_code = Column(String(50), nullable=True)  # Счет для списания товаров (для расходных накладных)
    revenue_account_code = Column(String(50), nullable=True)  # Счет выручки (для расходных накладных)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # Кто создал документ
    
    # Поля для приходных накладных
    conception = Column(String(50), nullable=True)  # Концепция (guid)
    conception_code = Column(String(50), nullable=True)  # Код концепции
    invoice = Column(String(100), nullable=True)  # Номер счет-фактуры
    supplier = Column(String(50), nullable=True)  # Поставщик (guid)
    due_date = Column(DateTime, nullable=True)  # Срок оплаты
    incoming_date = Column(DateTime, nullable=True)  # Входящая дата внешнего документа
    use_default_document_time = Column(Boolean, nullable=True, default=False)  # Использовать настройки проведения документов
    incoming_document_number = Column(String(100), nullable=True)  # Входящий номер внешнего документа
    employee_pass_to_account = Column(String(50), nullable=True)  # Сотрудник (поле "зачесть сотруднику")
    transport_invoice_number = Column(String(100), nullable=True)  # Номер товарно-транспортной накладной
    linked_outgoing_invoice_id = Column(String(50), nullable=True)  # UUID связанной расходной накладной
    distribution_algorithm = Column(String(50), nullable=True)  # Алгоритм распределения дополнительных расходов
    
    # Поля для расходных накладных
    counteragent_id = Column(String(50), nullable=True)  # Контрагент (id)
    counteragent_code = Column(String(50), nullable=True)  # Контрагент (код)
    conception_id = Column(String(50), nullable=True)  # Концепция (id)
    
    # Дополнительная информация
    comment = Column(Text, nullable=True)  # Комментарий к документу
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    
    # Связи
    organization = relationship("Organization", backref="warehouse_documents")
    user = relationship("User", backref="warehouse_documents")
    items = relationship("WarehouseDocumentItem", back_populates="document", cascade="all, delete-orphan")


class WarehouseDocumentItem(Base):
    """Позиция складского документа"""
    __tablename__ = "warehouse_document_items"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    document_id = Column(Integer, ForeignKey("warehouse_documents.id"), nullable=False, index=True)
    
    # Номер позиции
    num = Column(Integer, nullable=True)  # Номер позиции в документе
    
    # Товар
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)  # Связь с товаром в нашей БД
    item_iiko_id = Column(String(50), nullable=True, index=True)  # ID товара в iiko
    item_name = Column(String(255), nullable=True)  # Название товара
    product_id = Column(String(50), nullable=True)  # ID товара (для актов списания)
    product_article = Column(String(100), nullable=True)  # Артикул товара
    product_size_id = Column(String(50), nullable=True)  # ID размера товара (для актов списания)
    
    # Поля для приходных накладных
    supplier_product = Column(String(50), nullable=True)  # Товар у поставщика (guid)
    supplier_product_article = Column(String(100), nullable=True)  # Товар у поставщика (артикул)
    producer = Column(String(50), nullable=True)  # Производитель/импортер
    is_additional_expense = Column(Boolean, nullable=True, default=False)  # Является дополнительным расходом
    
    # Количество и цены
    quantity = Column(Numeric(10, 3), nullable=False)  # Количество
    amount = Column(Numeric(10, 3), nullable=True)  # Количество в основных единицах измерения
    actual_amount = Column(Numeric(10, 3), nullable=True)  # Фактическое (подтвержденное) количество
    amount_factor = Column(Numeric(10, 3), nullable=True)  # Коэффициент количества (для актов списания)
    price = Column(Numeric(15, 2), nullable=True)  # Цена за единицу
    price_unit = Column(String(50), nullable=True)  # Цена единицы измерения (guid)
    price_without_vat = Column(Numeric(15, 2), nullable=True)  # Цена без НДС за фасовку с учетом скидки
    sum = Column(Numeric(15, 2), nullable=True)  # Сумма строки без учета скидки
    amount_total = Column(Numeric(15, 2), nullable=True)  # Сумма (quantity * price) - для обратной совместимости
    
    # НДС и скидки
    discount_sum = Column(Numeric(15, 2), nullable=True)  # Сумма скидки
    vat_percent = Column(Numeric(10, 2), nullable=True)  # Процент НДС (увеличено для больших значений)
    vat_sum = Column(Numeric(15, 2), nullable=True)  # Сумма НДС
    
    # Единицы измерения и фасовка
    measure_unit_id = Column(String(50), nullable=True)  # ID единицы измерения (для актов списания)
    amount_unit = Column(String(50), nullable=True)  # Базовая единица измерения (guid)
    container_id = Column(String(50), nullable=True)  # Фасовка (guid)
    container_code = Column(String(50), nullable=True)  # Код фасовки
    actual_unit_weight = Column(Numeric(10, 3), nullable=True)  # Вес единицы измерения
    
    # Склад
    store = Column(String(50), nullable=True)  # Склад (guid) - для приходных накладных
    store_id = Column(String(50), nullable=True)  # Склад (id) - для расходных накладных
    store_code = Column(String(50), nullable=True)  # Склад (код) - для расходных накладных
    
    # Дополнительные поля
    code = Column(String(100), nullable=True)  # Код
    cost = Column(Numeric(15, 2), nullable=True)  # Стоимость (для актов списания)
    customs_declaration_number = Column(String(100), nullable=True)  # Номер государственной таможенной декларации
    
    # Партии и сроки годности
    batch_number = Column(String(100), nullable=True)  # Номер партии
    expiry_date = Column(DateTime, nullable=True)  # Срок годности
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    
    # Связи
    document = relationship("WarehouseDocument", back_populates="items")
    item = relationship("Item", backref="warehouse_document_items")

