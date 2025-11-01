from sqlalchemy import Column, String, ForeignKey, Integer, DateTime
from sqlalchemy.orm import relationship
from database.database import Base
from datetime import datetime as dt

class RestaurantSection(Base):
    __tablename__ = "restaurant_sections"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)
    terminal_group_id = Column(Integer, ForeignKey("terminal_groups.id"), nullable=False)
    name = Column(String(255), nullable=False)

    created_at = Column(DateTime, default=dt.now)
    updated_at = Column(DateTime, default=dt.now)

    # связь с terminal group
    terminal_group = relationship("TerminalGroup", back_populates="restaurant_sections")

    # связь с tables
    tables = relationship("Table", back_populates="section")
