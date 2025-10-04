from sqlalchemy import Column, String, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from database.database import Base


class Terminal(Base):
    __tablename__ = "terminals"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"))
    terminal_group_id = Column(Integer, ForeignKey("terminal_groups.id"))

    name = Column(String(255))
    address = Column(String(255))
    time_zone = Column(String(20))

    organization = relationship("Organization", back_populates="terminals")
    terminal_group = relationship("TerminalGroup", back_populates="terminals")
