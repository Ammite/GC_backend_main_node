from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from database.database import Base


class Modifier(Base):
    __tablename__ = "modifiers"

    id = Column(Integer, primary_key=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)

    deleted = Column(Boolean, default=False)
    default_amount = Column(Float, default=0)
    free_of_charge_amount = Column(Float, default=0)
    minimum_amount = Column(Float, default=0)
    maximum_amount = Column(Float, default=0)
    hide_if_default_amount = Column(Boolean, default=False)
    child_modifiers_have_min_max_restrictions = Column(Boolean, default=False)
    splittable = Column(Boolean, default=False)


    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    item = relationship("Item", back_populates="modifiers")


    parent_id = Column(Integer, ForeignKey("modifier.id"), nullable=True)
    children = relationship("Modifier", backref="parent", remote_side=[id])
