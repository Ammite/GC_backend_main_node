from sqlalchemy import Column, Integer, ForeignKey, String
from database.database import Base


class UserReward(Base):
    __tablename__ = "user_rewards"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True)
    reward_id = Column(Integer, ForeignKey("rewards.id"))
    user_id = Column(Integer, ForeignKey("roles.id"))
    current_progress = Column(Integer)
