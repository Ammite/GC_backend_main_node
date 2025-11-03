from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database.database import Base


class Account(Base):
    __tablename__ = "accounts_list"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False, index=True)
    
    # Поля из iiko Server API
    root_type = Column(String(100), nullable=True)
    account_parent_id = Column(String(50), nullable=True)
    parent_corporate_id = Column(String(50), nullable=True)
    type = Column(String(100), nullable=True)
    system = Column(Boolean, nullable=True)
    custom_transactions_allowed = Column(Boolean, nullable=True)
    deleted = Column(Boolean, nullable=True, default=False)
    code = Column(String(50), nullable=True)
    name = Column(String(255), nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

