from sqlalchemy import Column, Integer, ForeignKey, String, DateTime
from database.database import Base
from datetime import datetime as dt


class UserReward(Base):
    __tablename__ = "user_rewards"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True)
    reward_id = Column(Integer, ForeignKey("rewards.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    current_progress = Column(Integer)
    
    created_at = Column(DateTime, default=dt.now)
    updated_at = Column(DateTime, default=dt.now, onupdate=dt.now)
