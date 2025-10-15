from sqlalchemy import Column, Integer, String, ForeignKey
from database.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True)
    name = Column(String(100), nullable=True)
    login = Column(String(100), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    roles_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
