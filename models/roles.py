from sqlalchemy import Column, Integer, String, Boolean, Numeric, DateTime
from database.database import Base
from datetime import datetime as dt


class Roles(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)

    code = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=False)

    payment_per_hour = Column(Numeric(10, 2), default=0)
    steady_salary = Column(Numeric(10, 2), default=0)
    schedule_type = Column(String(50), nullable=True)

    deleted = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=dt.now)
    updated_at = Column(DateTime, default=dt.now, onupdate=dt.now)
