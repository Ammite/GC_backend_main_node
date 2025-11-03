from sqlalchemy import Column, Integer, Text, ForeignKey, Numeric, String, DateTime
from database.database import Base
from datetime import datetime as dt


class Penalty(Base):
    __tablename__ = "penalties"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True)
    penalty_sum = Column(Numeric(10, 2), nullable=False)
    description = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    
    created_at = Column(DateTime, default=dt.now)
    updated_at = Column(DateTime, default=dt.now, onupdate=dt.now)
