from sqlalchemy import Column, String, ForeignKey, Integer, Boolean, DateTime
from sqlalchemy.orm import relationship
from database.database import Base
from datetime import datetime as dt


class Table(Base):
    __tablename__ = "tables"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)
    section_id = Column(Integer, ForeignKey("restaurant_sections.id"), nullable=False)

    number = Column(Integer, nullable=False)
    name = Column(String(255), nullable=True)
    revision = Column(String(50), nullable=True)
    is_deleted = Column(Boolean, default=False)
    pos_id = Column(String(50), nullable=True)
    
    created_at = Column(DateTime, default=dt.now)
    updated_at = Column(DateTime, default=dt.now, onupdate=dt.now)

    section = relationship("RestaurantSection", back_populates="tables")
