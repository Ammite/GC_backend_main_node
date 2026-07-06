from sqlalchemy import Column, Integer, ForeignKey, Numeric, Date, DateTime
from sqlalchemy.orm import relationship
from database.database import Base
from datetime import datetime


class WaiterSalesPercent(Base):
    """
    Персональный процент официанта с продаж, с периодом действия.
    Активная запись на дату X: date_from <= X AND (date_to IS NULL OR date_to >= X).
    """
    __tablename__ = "waiter_sales_percent"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    percent = Column(Numeric(5, 2), nullable=False)
    date_from = Column(Date, nullable=False)
    date_to = Column(Date, nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    employee = relationship("Employees", foreign_keys=[employee_id])
