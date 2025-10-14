from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, Numeric, Boolean, JSON
from sqlalchemy.orm import relationship
from database.database import Base


class DOrder(Base):
    __tablename__ = "d_orders"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    organization = relationship("Organization", back_populates="d_orders")
    terminal_group_id = Column(Integer, ForeignKey("terminal_groups.id"), nullable=True)
    external_number = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)
    guest_count = Column(Integer, default=0)
    tab_name = Column(String(100), nullable=True)
    price_category_id = Column(String(50), nullable=True)
    order_type_id = Column(Integer, ForeignKey("order_types.id"), nullable=True)
    order_type = relationship("OrderType")
    
    sum_order = Column(Numeric(10, 2), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    state_order = Column(String(255), nullable=True)
    discount = Column(Numeric(10, 2), nullable=True)
    service = Column(Numeric(10, 2), nullable=True)
    bank_commission = Column(Numeric(10, 2), nullable=True)
    time_order = Column(TIMESTAMP, nullable=True)
    
    # JSON поля для детальной информации
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
    
    # Связь с позициями заказа
    order_items = relationship("TOrder", back_populates="order")
