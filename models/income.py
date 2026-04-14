"""
Модель для доходов
"""
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from database.database import Base


class Income(Base):
    """Доход"""
    __tablename__ = "incomes"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    
    # Основные поля
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    income_type = Column(String(100), nullable=False, index=True)  # тип дохода
    amount = Column(Numeric(15, 2), nullable=False)  # Сумма дохода
    date = Column(DateTime, nullable=False, index=True)  # Дата дохода
    comment = Column(Text, nullable=True)  # Комментарий к доходу
    
    # Связь со счетом
    account_id = Column(String(50), nullable=True, index=True)  # ID счета из Account (iiko_id)
    
    # Связь со складским документом (приходная накладная)
    warehouse_document_id = Column(Integer, ForeignKey("warehouse_documents.id"), nullable=True, index=True)
    
    # Кто создал
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    
    # Связи
    organization = relationship("Organization", backref="incomes")
    user = relationship("User", backref="incomes")
    warehouse_document = relationship("WarehouseDocument", backref="incomes")

