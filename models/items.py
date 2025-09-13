from sqlalchemy import Column, Integer, BigInteger, Text
from database.database import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    price = Column(Integer, nullable=False)
    articul = Column(Integer, nullable=False, unique=True)
    barcode = Column(BigInteger, unique=True)
    description = Column(Text, nullable=True)
    image = Column(Text, nullable=True)
