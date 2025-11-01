from sqlalchemy import Column, Integer, ForeignKey, TIMESTAMP, Numeric, String, DateTime
from sqlalchemy.sql import func
from database.database import Base
from datetime import datetime as dt


class Reward(Base):
    __tablename__ = "rewards"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True)
    create_date = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    start_date = Column(TIMESTAMP, nullable=False)
    end_date = Column(TIMESTAMP, nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    end_goal = Column(Integer, nullable=False)
    prize_sum = Column(Numeric(10, 2), nullable=False)
    
    created_at = Column(DateTime, default=dt.now)
    updated_at = Column(DateTime, default=dt.now, onupdate=dt.now)
