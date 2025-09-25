from sqlalchemy import Column, Integer, Text, ForeignKey
from database.database import Base


class Penalty(Base):
    __tablename__ = "penalty"

    id = Column(Integer, primary_key=True, index=True)
    penalty_sum = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    roles_id = Column(Integer, ForeignKey("roles.id"))
