from sqlalchemy import Column, Integer, ForeignKey, String, DateTime
from database.database import Base
from datetime import datetime as dt


class UserReward(Base):
    __tablename__ = "user_rewards"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True)
    reward_id = Column(Integer, ForeignKey("rewards.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Связь с пользователем системы
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)  # Связь с сотрудником из iiko
    current_progress = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=dt.now)
    updated_at = Column(DateTime, default=dt.now, onupdate=dt.now)
