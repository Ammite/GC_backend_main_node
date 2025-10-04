from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from database.database import Base


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)  # внутренний id
    iiko_id = Column(String(50), unique=True, nullable=False)  # id из iiko
    name = Column(String(255), nullable=False)
    is_deleted = Column(Boolean, default=False)


    items = relationship("Item", back_populates="menu_category")
