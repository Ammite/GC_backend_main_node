from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, Numeric
from database.database import Base


class DOrder(Base):
    __tablename__ = "d_orders"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True)
    sum_order = Column(Numeric(10, 2), nullable=True)
    user_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    state_order = Column(String(255), nullable=True)
    discount = Column(Numeric(10, 2), nullable=True)
    service = Column(Numeric(10, 2), nullable=True)
    time_order = Column(TIMESTAMP, nullable=True)
