from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from database.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    d_orders = relationship("DOrder", back_populates="organization")
    terminal_groups = relationship("TerminalGroup", back_populates="organization")
    terminals = relationship("Terminal", back_populates="organization")
    transactions = relationship("Transaction", back_populates="organization")
    sales = relationship("Sales", back_populates="organization")
    items = relationship("Item", back_populates="organization")