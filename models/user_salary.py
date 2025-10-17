from sqlalchemy import Column, Integer, ForeignKey, Numeric, String
from database.database import Base


class UserSalary(Base):
    __tablename__ = "user_salaries"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    salary = Column(Numeric(10, 2), nullable=False)
