from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database.database import Base

class DOrder(Base):
    __tablename__ = "d_order"

    id = Column(Integer, primary_key=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)
    date = Column(DateTime)
    customer_name = Column(String(255))
    total_amount = Column(Integer)

    order_type_id = Column(Integer, ForeignKey("order_types.id"))
    order_type = relationship("OrderType")
