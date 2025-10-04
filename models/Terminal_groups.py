from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class TerminalGroup(Base):
    __tablename__ = "terminal_groups"

    id = Column(String(50), primary_key=True)
    organization_id = Column(String(50), ForeignKey("organizations.id"))
    organization = relationship("Organization", back_populates="terminal_groups")

    terminals = relationship("Terminal", back_populates="terminal_group")
    restaurant_sections = relationship("RestaurantSection", back_populates="terminal_group")
