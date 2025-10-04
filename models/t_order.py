from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP
from database.database import Base


class TOrder(Base):
    __tablename__ = "t_orders"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    count_order = Column(Integer)
    order_id = Column(Integer, ForeignKey("d_orders.id"))
    time_order = Column(TIMESTAMP)
    comment_order = Column(String(500), nullable=True)
