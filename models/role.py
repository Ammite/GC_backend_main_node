from sqlalchemy import Column, Integer, String, ForeignKey, Table
from database.database import Base
from sqlalchemy.orm import relationship


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    code = Column(String, nullable=True)

    users = relationship("User", secondary=user_roles, back_populates="roles")