from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP
from database.database import Base


class TOrder(Base):
    __tablename__ = "t_order"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    count_order = Column(Integer)
    order_id = Column(Integer, ForeignKey("d_order.id"))
    time_order = Column(TIMESTAMP)
    comment_order = Column(String)
