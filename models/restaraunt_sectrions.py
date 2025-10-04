from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from database.database import Base

class RestaurantSection(Base):
    __tablename__ = "restaurant_sections"

    id = Column(String(50), primary_key=True)
    terminal_group_id = Column(String(50), ForeignKey("terminal_groups.id"), nullable=False)
    name = Column(String(255), nullable=False)

    # связь с terminal group
    terminal_group = relationship("TerminalGroup", back_populates="restaurant_sections")

    # связь с tables
    tables = relationship("Table", back_populates="section")
