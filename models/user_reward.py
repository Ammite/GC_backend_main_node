from sqlalchemy import Column, Integer, ForeignKey
from database.database import Base


class UserReward(Base):
    __tablename__ = "user_reward"

    id = Column(Integer, primary_key=True, index=True)
    reward_id = Column(Integer, ForeignKey("rewards.id"))
    user_id = Column(Integer, ForeignKey("roles.id"))
    current_progress = Column(Integer)
