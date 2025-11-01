from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database.database import Base
from datetime import datetime as dt


class ProductGroup(Base):
    __tablename__ = "product_groups"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)  # ID из iiko
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    num = Column(String(50), nullable=True)
    code = Column(String(50), nullable=True)
    deleted = Column(Boolean, default=False)

    parent_iiko_id = Column(String(50), nullable=True)  # Внешний ID родителя (из iiko)
    parent_id = Column(Integer, ForeignKey("product_groups.id"), nullable=True)  # Внутренний FK
    parent = relationship("ProductGroup", remote_side=[id], back_populates="children")

    children = relationship("ProductGroup", back_populates="parent", cascade="all, delete-orphan")

    accounting_category_id = Column(String(50), nullable=True)
    front_image_id = Column(String(50), nullable=True)
    position = Column(String(50), nullable=True)
    modifier_schema_id = Column(String(50), nullable=True)
    visibility_filter = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=dt.now)
    updated_at = Column(DateTime, default=dt.now, onupdate=dt.now)

    items = relationship("Item", back_populates="product_group", cascade="all, delete-orphan")


