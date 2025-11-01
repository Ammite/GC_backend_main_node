from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from database.database import Base
from datetime import datetime as dt


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)  # внутренний id
    iiko_id = Column(String(50), unique=True, nullable=False)  # id из iiko
    name = Column(String(255), nullable=False)
    is_deleted = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=dt.now)
    updated_at = Column(DateTime, default=dt.now, onupdate=dt.now)

    items = relationship("Item", back_populates="menu_category")


