from sqlalchemy import Column, Integer, String, Text, ForeignKey, Numeric, Boolean
from sqlalchemy.orm import relationship
from database.database import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    code = Column(String(50), nullable=True)
    num = Column(String(50), nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    deleted = Column(Boolean, default=False)


    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="items")


    menu_category_id = Column(Integer, ForeignKey("menu_categories.id"), nullable=True)
    menu_category = relationship("MenuCategory", back_populates="items")

    product_group_id = Column(Integer, ForeignKey("product_groups.id"), nullable=True)
    product_group = relationship("ProductGroup", back_populates="items")

    modifiers = relationship("Modifier", back_populates="item")


