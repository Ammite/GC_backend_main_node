from sqlalchemy import Column, Integer, ForeignKey, TIMESTAMP, String
from sqlalchemy.sql import func
from database.database import Base


class Shift(Base):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True)

    start_time = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    end_time = Column(TIMESTAMP, nullable=False)

    roles_id = Column(Integer, ForeignKey("roles.id"))

    attendance_type_id = Column(Integer, ForeignKey("attendance_types.id"))

    employee_id = Column(Integer, ForeignKey("employees.id"))
