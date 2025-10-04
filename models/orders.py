from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)
    organization_id = Column(String(50), ForeignKey("organizations.id"))
    organization = relationship("Organization", back_populates="orders")
    terminal_group_id = Column(String(50), nullable=True)
    external_number = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    guest_count = Column(Integer, default=0)
    tab_name = Column(String(100), nullable=True)
    price_category_id = Column(String(50), nullable=True)
    order_type_id = Column(String(50), ForeignKey("order_types.iiko_id"), nullable=True)


    order_type = relationship("OrderType")


    customer = Column(JSON, nullable=True)
    items = Column(JSON, nullable=True)
    combos = Column(JSON, nullable=True)
    payments = Column(JSON, nullable=True)
    tips = Column(JSON, nullable=True)
    discounts_info = Column(JSON, nullable=True)
    loyalty_info = Column(JSON, nullable=True)
    cheque_additional_info = Column(JSON, nullable=True)
    external_data = Column(JSON, nullable=True)


    deleted = Column(Boolean, default=False)
