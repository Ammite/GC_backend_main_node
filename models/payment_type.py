from sqlalchemy import Column, Integer, String, Boolean, BigInteger, Text, DateTime, JSON
from database.database import Base
from datetime import datetime


class PaymentType(Base):
    __tablename__ = "payment_types"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False, index=True)

    code = Column(String(100), nullable=True)
    name = Column(String(255), nullable=True)
    comment = Column(Text, nullable=True)
    combinable = Column(Boolean, default=False)
    external_revision = Column(BigInteger, nullable=True)
    is_deleted = Column(Boolean, default=False)
    print_cheque = Column(Boolean, default=False)
    payment_processing_type = Column(String(50), nullable=True)
    payment_type_kind = Column(String(50), nullable=True)  # Cash, Card, Credit, etc.
    # True если этим видом оплаты реально оплачивают на кассе.
    # False — служебные операции (Перемещение, Бракераж, Дегустация, Маркетинг,
    # Стафф питание, Представительские, Под зп сотрудникам, Сертификат и т.п.).
    # По умолчанию роутер /payment-types возвращает только is_payable=True.
    is_payable = Column(Boolean, default=True, nullable=False, server_default='true')
    # Источник данных: 'cloud' (полная схема), 'server' (минимум, дополнено эвристиками)
    source = Column(String(20), nullable=True)

    # JSON массив iiko_id организаций (cloud uuid).
    # NULL = доступен для всех организаций (например, сертификаты, бонусы).
    # [] = не привязан ни к одной (фактически невидим).
    # [uuid1, uuid2] = ограничен этими организациями.
    organization_iiko_ids = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
