from sqlalchemy import Column, Integer, String, Boolean, Numeric
from database.database import Base


class AttendanceType(Base):
    __tablename__ = "attendance_types"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)

    code = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)

    pay_rate = Column(Numeric(10, 2), default=1.0)
    status = Column(Boolean, default=True)
