from sqlalchemy import Column, Integer, ForeignKey, TIMESTAMP
from sqlalchemy.sql import func
from database.database import Base


class Shift(Base):
    __tablename__ = "shifts"

    id = Column(Integer, primary_key=True, index=True)
    starttime = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    endtime = Column(TIMESTAMP, nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"))
