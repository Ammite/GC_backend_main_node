from sqlalchemy import Column, Integer, String, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID
from database.database import Base


class Roles(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(UUID(as_uuid=True), unique=True, nullable=False)

    code = Column(String(50), nullable=False, index=True)
    name = Column(String(100), nullable=False)

    payment_per_hour = Column(Numeric(10, 2), default=0)
    steady_salary = Column(Numeric(10, 2), default=0)
    schedule_type = Column(String(50), nullable=True)

    deleted = Column(Boolean, default=False)
