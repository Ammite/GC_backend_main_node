from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from database.database import Base
class Table(Base):
    __tablename__ = "tables"

    id = Column(String(50), primary_key=True)
    section_id = Column(String(50), ForeignKey("restaurant_sections.id"), nullable=False)

    number = Column(Integer, nullable=False)
    name = Column(String(255), nullable=True)
    revision = Column(String(50), nullable=True)
    is_deleted = Column(Boolean, default=False)
    pos_id = Column(String(50), nullable=True)

    section = relationship("RestaurantSection", back_populates="tables")
