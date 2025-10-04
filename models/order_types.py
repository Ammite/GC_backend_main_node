from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database.database import Base


class OrderType(Base):
    __tablename__ = "order_types"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    is_deleted = Column(Boolean, default=False)
