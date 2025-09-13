from sqlalchemy import Column, Integer, ForeignKey, TIMESTAMP
from sqlalchemy.sql import func
from database.database import Base


class Reward(Base):
    __tablename__ = "rewards"

    id = Column(Integer, primary_key=True, index=True)
    createddate = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    startdate = Column(TIMESTAMP, nullable=False)
    enddate = Column(TIMESTAMP, nullable=False)
    itemid = Column(Integer, ForeignKey("items.id"), nullable=False)
    endgoal = Column(Integer, nullable=False)
    prizesum = Column(Integer, nullable=False)
