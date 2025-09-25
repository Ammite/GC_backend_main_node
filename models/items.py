from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database.database import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)  # локальный id
    iiko_id = Column(String(50), unique=True, nullable=False)  # внешний id iiko
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    code = Column(String(50), nullable=True)
    num = Column(String(50), nullable=True)
    price = Column(Float, nullable=False)
    deleted = Column(Boolean, default=False)


    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="items")


    modifiers = relationship("Modifier", back_populates="item")
