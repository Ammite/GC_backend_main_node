from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship

from database.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)
    d_orders = relationship("DOrder", back_populates="organization")
    terminal_groups = relationship("TerminalGroup", back_populates="organization")
    terminals = relationship("Terminal", back_populates="organization")