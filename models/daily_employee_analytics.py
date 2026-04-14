from sqlalchemy import Column, Integer, Numeric, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from database.database import Base


class DailyEmployeeAnalytics(Base):
    """
    Таблица дневных агрегированных метрик по сотрудникам для ускорения аналитических запросов.

    Ключевая идея:
    - Храним уже посчитанные значения по дням, сотрудникам и (опционально) по организации.
    - Пример:
        date = 2025-12-18
        employee_id = 123
        organization_id = 1
        revenue = 50000.00
        checks_count = 25
        returns_count = 2
        average_check = 2000.00
    """

    __tablename__ = "daily_employee_analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Дата, за которую посчитана метрика
    date = Column(Date, nullable=False, index=True)

    # Сотрудник
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    employee = relationship("Employees", backref="daily_employee_analytics")

    # Организация (может быть NULL, если метрика общая по всем организациям)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    organization = relationship("Organization", backref="daily_employee_analytics")

    # Выручка за день
    revenue = Column(Numeric(20, 2), nullable=False, default=0)

    # Количество чеков (уникальные order_id)
    checks_count = Column(Integer, nullable=False, default=0)

    # Количество возвратов (уникальные order_id с возвратами)
    returns_count = Column(Integer, nullable=False, default=0)

    # Средний чек (выручка / количество чеков)
    average_check = Column(Numeric(20, 2), nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            "date",
            "employee_id",
            "organization_id",
            name="uq_daily_employee_analytics_unique",
        ),
    )

