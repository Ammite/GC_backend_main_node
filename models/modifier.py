from sqlalchemy import Column, Integer, String, Boolean, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from database.database import Base
from datetime import datetime as dt


class Modifier(Base):
    """Модификатор - отдельная сущность, может применяться к разным товарам"""
    __tablename__ = "modifiers"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)  # Уникальный ID модификатора из iiko
    name = Column(String(255), nullable=True)  # Имя модификатора (если будет в данных)
    description = Column(Text, nullable=True)  # Описание модификатора
    deleted = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=dt.now)
    updated_at = Column(DateTime, default=dt.now, onupdate=dt.now)
    
    # Связь с промежуточной таблицей
    item_modifiers = relationship("ItemModifier", back_populates="modifier", cascade="all, delete-orphan")


class ItemModifier(Base):
    """Промежуточная таблица для связи товара и модификатора с параметрами применения"""
    __tablename__ = "item_modifiers"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    
    # Связи
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    item = relationship("Item", back_populates="item_modifiers")
    
    modifier_id = Column(Integer, ForeignKey("modifiers.id"), nullable=False)
    modifier = relationship("Modifier", back_populates="item_modifiers")
    
    # Иерархия модификаторов в рамках товара
    parent_modifier_iiko_id = Column(String(50), nullable=True)  # iiko_id родительского модификатора в иерархии
    parent_item_modifier_id = Column(Integer, ForeignKey("item_modifiers.id"), nullable=True)
    children = relationship("ItemModifier", backref="parent", remote_side=[id])
    
    # Параметры применения модификатора к товару
    deleted = Column(Boolean, default=False)
    default_amount = Column(Numeric(10, 2), default=0)
    free_of_charge_amount = Column(Numeric(10, 2), default=0)
    minimum_amount = Column(Numeric(10, 2), default=0)
    maximum_amount = Column(Numeric(10, 2), default=0)
    hide_if_default_amount = Column(Boolean, default=False)
    child_modifiers_have_min_max_restrictions = Column(Boolean, default=False)
    splittable = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=dt.now)
    updated_at = Column(DateTime, default=dt.now, onupdate=dt.now)


