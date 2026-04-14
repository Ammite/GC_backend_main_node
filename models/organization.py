from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from database.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)
    iiko_id_cloud = Column(String(50), unique=True, nullable=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    # True для записей, оставшихся от старой iiko-системы (миграция ~28-29.01.2026).
    # У них iiko_id_cloud=None, в Cloud `/api/1/organizations` отсутствуют, в Server
    # `/resto/api/corporation/departments` тоже. Не показывать в выпадашках, но
    # сохранять для исторических отчётов.
    is_legacy = Column(Boolean, default=False, nullable=False, server_default='false')
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    address = Column(Text, nullable=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    conception_id = Column(Integer, ForeignKey("conceptions.id"), nullable=True)
    
    department = relationship("Department", foreign_keys=[department_id])
    conception_ref = relationship("Conception", foreign_keys=[conception_id])

    d_orders = relationship("DOrder", back_populates="organization")
    terminal_groups = relationship("TerminalGroup", back_populates="organization")
    terminals = relationship("Terminal", back_populates="organization")
    transactions = relationship("Transaction", back_populates="organization")
    sales = relationship("Sales", back_populates="organization")
    items = relationship("Item", back_populates="organization")
    stores = relationship("Store", back_populates="organization")
    suppliers = relationship("Supplier", back_populates="organization")