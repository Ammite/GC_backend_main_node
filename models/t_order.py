from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship
from database.database import Base


class TOrder(Base):
    __tablename__ = "t_orders"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    item = relationship("Item")
    count_order = Column(Integer)
    order_id = Column(Integer, ForeignKey("d_orders.id"))
    order = relationship("DOrder", back_populates="order_items")
    time_order = Column(TIMESTAMP)
    comment_order = Column(String(500), nullable=True)
