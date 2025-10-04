from sqlalchemy import Column, Integer, String, Boolean
from database.database import Base


class ScheduleType(Base):
    __tablename__ = "schedule_types"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)

    code = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)

    start_time = Column(String(10), nullable=True)
    length_minutes = Column(Integer, nullable=True)
    comment = Column(String(255), nullable=True)

    overtime = Column(Boolean, default=False)
