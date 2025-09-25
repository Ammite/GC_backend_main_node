from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP
from database.database import Base


class DOrder(Base):
    __tablename__ = "d_order"

    id = Column(Integer, primary_key=True, index=True)
    sum_order = Column(Integer, nullable=True)
    user_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    state_order = Column(String, nullable=True)
    discount = Column(Integer, nullable=True)
    service = Column(Integer, nullable=True)
    time_order = Column(TIMESTAMP, nullable=True)
