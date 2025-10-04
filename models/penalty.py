from sqlalchemy import Column, Integer, Text, ForeignKey, Numeric, String
from database.database import Base


class Penalty(Base):
    __tablename__ = "penalties"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True)
    penalty_sum = Column(Numeric(10, 2), nullable=False)
    description = Column(Text, nullable=True)
    roles_id = Column(Integer, ForeignKey("roles.id"))
