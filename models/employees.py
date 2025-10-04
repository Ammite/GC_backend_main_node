from sqlalchemy import Column, String, ForeignKey, Integer, Boolean
from sqlalchemy.orm import relationship
from database.database import Base


class Employees(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)

    code = Column(String(50), nullable=True)

    first_name = Column(String(100), nullable=False)
    middle_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=False)

    phone = Column(String(20), nullable=True)
    cell_phone = Column(String(20), nullable=True)

    birthday = Column(String(30), nullable=True)
    hire_date = Column(String(30), nullable=True)

    deleted = Column(Boolean, default=False)

    main_role_id = Column(Integer, ForeignKey("roles.id"))
    main_role = relationship("Roles", backref="employees")
