from sqlalchemy import Column, String, ForeignKey, Integer, Boolean, ARRAY, DateTime, Date, Text
from sqlalchemy.orm import relationship
from database.database import Base


class Employees(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)

    # Основные поля
    code = Column(String(50), nullable=True)
    name = Column(String(255), nullable=True)  # Полное имя
    login = Column(String(100), nullable=True)
    password = Column(String(255), nullable=True)  # Не отображается, только для изменения

    # Имена
    first_name = Column(String(100), nullable=True)
    middle_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)

    # Контакты
    phone = Column(String(20), nullable=True)
    cell_phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)

    # Даты
    birthday = Column(DateTime, nullable=True)
    hire_date = Column(String(30), nullable=True)
    hire_document_number = Column(String(100), nullable=True)
    fire_date = Column(Date, nullable=True)
    activation_date = Column(DateTime, nullable=True)
    deactivation_date = Column(DateTime, nullable=True)

    # Дополнительная информация
    note = Column(Text, nullable=True)
    card_number = Column(String(50), nullable=True)
    pin_code = Column(String(20), nullable=True)
    taxpayer_id_number = Column(String(20), nullable=True)  # ИНН
    snils = Column(String(20), nullable=True)  # СНИЛС
    gln = Column(String(50), nullable=True)  # Global Location Number

    # Роли и должности
    main_role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    main_role = relationship("Roles", foreign_keys=[main_role_id], backref="employees_main_role")
    
    roles_id = Column(ARRAY(Integer), nullable=True)
    main_role_code = Column(String(50), nullable=True)
    role_codes = Column(ARRAY(String), nullable=True)

    # Организации и подразделения
    organizations_id = Column(ARRAY(Integer), nullable=True)
    
    preferred_organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    preferred_organization = relationship("Organization", foreign_keys=[preferred_organization_id], backref="employees_preferred")
    
    responsibility_organization_id = Column(ARRAY(Integer), nullable=True)

    # Подразделения
    preferred_department_code = Column(String(50), nullable=True)
    department_codes = Column(ARRAY(String), nullable=True)
    responsibility_department_codes = Column(ARRAY(String), nullable=True)

    # Статусы
    deleted = Column(Boolean, default=False)
    client = Column(Boolean, default=False)
    supplier = Column(Boolean, default=False)
    employee = Column(Boolean, default=False)
    represents_store = Column(Boolean, default=False)


