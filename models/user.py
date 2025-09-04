from sqlalchemy import Column, Integer, String, ForeignKey, Table
from database.database import Base
from sqlalchemy.orm import relationship
from models.role import user_roles


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    login = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)

    roles = relationship("Role", secondary=user_roles, back_populates="users")