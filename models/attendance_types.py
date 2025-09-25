from sqlalchemy import Column, String, Numeric, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
from database.database import Base


class AttendanceType(Base):
    __tablename__ = "attendance_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    code = Column(String, nullable=False)

    name = Column(String, nullable=False)

    pay_rate = Column(Numeric(10, 2), nullable=False)

    status = Column(Boolean, default=True)
