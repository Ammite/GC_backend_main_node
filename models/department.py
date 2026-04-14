from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database.database import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False, index=True)
    parent_id = Column(String(50), nullable=True, index=True)  # iiko_id родительского департамента
    code = Column(String(50), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    taxpayer_id_number = Column(String(50), nullable=True)  # ИНН
    
    # Связь с родительским департаментом (self-referential через iiko_id)
    parent = relationship(
        "Department",
        remote_side=[iiko_id],
        primaryjoin="Department.parent_id == Department.iiko_id",
        foreign_keys=[parent_id],
        backref="children"
    )
    
    # Метаданные
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
