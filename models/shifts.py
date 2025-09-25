from sqlalchemy import Column, Integer, ForeignKey, TIMESTAMP
from sqlalchemy.sql import func
from database.database import Base


class Shift(Base):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True, index=True)

    start_time = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    end_time = Column(TIMESTAMP, nullable=False)

    role_id = Column(Integer, ForeignKey("roles.id"))
    user_id = Column(Integer, ForeignKey("users.id"))

    schedule_type_id = Column(Integer, ForeignKey("schedule_types.id"))

    attendance_type_id = Column(Integer, ForeignKey("attendance_types.id"))
