from sqlalchemy import Column, Integer, ForeignKey, TIMESTAMP
from sqlalchemy.sql import func
from database.database import Base


class Reward(Base):
    __tablename__ = "rewards"

    id = Column(Integer, primary_key=True, index=True)
    create_ddate = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    start_date = Column(TIMESTAMP, nullable=False)
    end_date = Column(TIMESTAMP, nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    end_goal = Column(Integer, nullable=False)
    prize_sum = Column(Integer, nullable=False)
