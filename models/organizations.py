from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from database.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(50), primary_key=True, index=True)  # iiko ID
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)
    orders = relationship("Orders", back_populates="organization")
    terminal_groups = relationship("TerminalGroup", back_populates="organization")
    terminals = relationship("Terminal", back_populates="organization")