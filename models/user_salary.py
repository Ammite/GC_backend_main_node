from sqlalchemy import Column, Integer, ForeignKey
from database.database import Base


class UserSalary(Base):
    __tablename__ = "user_salary"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("roles.id"))
    salary = Column(Integer)
