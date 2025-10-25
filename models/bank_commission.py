from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, Numeric, Boolean, JSON
from sqlalchemy.orm import relationship
from database.database import Base


class BankCommission(Base):
    __tablename__ = "bank_commissions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # id of the order in the database
    order_id = Column(Integer, ForeignKey("d_orders.id"), nullable=True)
    order = relationship("DOrder")

    # iiko_id of the order
    order_iiko_id = Column(String(50), nullable=True)

    amount = Column(Numeric(10, 2), nullable=True)
    bank_commission = Column(Numeric(10, 2), nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    organization = relationship("Organization")
    time_transaction = Column(TIMESTAMP, nullable=True)
    
    # source of the transaction
    source = Column(String(100), nullable=True)
    
