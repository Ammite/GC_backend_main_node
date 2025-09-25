from sqlalchemy import Column, String, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
import uuid
from database.database import Base


class ScheduleType(Base):
    __tablename__ = "schedule_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    code = Column(String, nullable=False)
    name = Column(String, nullable=False)

    start_time = Column(String, nullable=False)

    length_minutes = Column(Integer, nullable=False)

    comment = Column(String, nullable=True)

    overtime = Column(Boolean, default=False)
