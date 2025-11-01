from sqlalchemy import Column, String, ForeignKey, Integer, DateTime
from sqlalchemy.orm import relationship
from database.database import Base
from datetime import datetime as dt


class TerminalGroup(Base):
    __tablename__ = "terminal_groups"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    name = Column(String(255), nullable=False)
    
    created_at = Column(DateTime, default=dt.now)
    updated_at = Column(DateTime, default=dt.now, onupdate=dt.now)
    
    organization = relationship("Organization", back_populates="terminal_groups")
    terminals = relationship("Terminal", back_populates="terminal_group")
    restaurant_sections = relationship("RestaurantSection", back_populates="terminal_group")
