from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from database.database import Base
from datetime import datetime as dt, timedelta, timezone

_TZ_PLUS5 = timezone(timedelta(hours=5))


def _now_plus5():
    return dt.now(_TZ_PLUS5).replace(tzinfo=None)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    is_completed = Column(Boolean, default=False, nullable=False)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now_plus5)
    updated_at = Column(DateTime, default=_now_plus5, onupdate=_now_plus5)
