"""
Модель для изъятий из кассы
"""
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from database.database import Base


class PayOut(Base):
    """Изъятие из кассы"""
    __tablename__ = "pay_outs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    
    # ID изъятия в iiko (если возвращается API)
    iiko_id = Column(String(50), unique=True, nullable=True, index=True)
    
    # Основные поля изъятия
    pay_out_type_id = Column(String(50), nullable=False, index=True)  # UUID типа изъятия
    pay_out_date = Column(DateTime, nullable=False, index=True)  # Дата изъятия
    counteragent_id = Column(String(50), nullable=True, index=True)  # UUID контрагента
    department_id = Column(String(50), nullable=False, index=True)  # UUID торгового предприятия
    amount = Column(Numeric(15, 2), nullable=False)  # Сумма изъятия
    payroll_id = Column(String(50), nullable=True, index=True)  # UUID платежной ведомости
    comment = Column(Text, nullable=True)  # Комментарий
    
    # Результат операции
    result = Column(String(20), nullable=False, index=True)  # SUCCESS, ERROR
    errors = Column(JSON, nullable=True)  # Список ошибок из ответа API
    
    # Связи
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    
    # Relationships
    organization = relationship("Organization", backref="pay_outs")
    user = relationship("User", backref="pay_outs")


class PayOutType(Base):
    """
    Тип изъятия/внесения, синхронизируемый из iiko API.
    Храним полный набор полей и связи с таблицей счетов accounts_list.
    """

    __tablename__ = "pay_out_types"

    # GUID типа из iiko
    id = Column(String(50), primary_key=True, index=True)

    # Связанные счета (по iiko_id -> Account.iiko_id)
    chief_account_iiko_id = Column(String(50), nullable=True, index=True)
    account_iiko_id = Column(String(50), nullable=True, index=True)
    chief_account_id = Column(Integer, ForeignKey("accounts_list.id"), nullable=True)
    account_id = Column(Integer, ForeignKey("accounts_list.id"), nullable=True)

    # Базовые поля из iiko
    counteragent_type = Column(String(50), nullable=True)
    transaction_type = Column(String(20), nullable=True)
    cash_flow_category_id = Column(String(50), nullable=True)
    cash_flow_category_code = Column(String(50), nullable=True)
    cash_flow_category_type = Column(String(50), nullable=True)

    conception_iiko_id = Column(String(50), nullable=True)
    limit = Column(Numeric(15, 2), nullable=True)
    comment = Column(Text, nullable=True)
    mandatory_front_comment = Column(Boolean, nullable=True)
    is_deleted = Column(Boolean, nullable=True)

    # Метаданные
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

