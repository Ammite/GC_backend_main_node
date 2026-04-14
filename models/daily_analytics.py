from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from database.database import Base


class DailyAnalytics(Base):
    """
    Таблица дневных агрегированных метрик для ускорения аналитических запросов.

    Ключевая идея:
    - Храним уже посчитанные значения по дням и (опционально) по организации и под-ключу.
    - Пример:
        date = 2025-12-18
        organization_id = 1
        metric_key = "revenue_total"
        metric_subkey = None
        value = 123456.78
    """

    __tablename__ = "daily_analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Дата, за которую посчитана метрика
    date = Column(Date, nullable=False, index=True)

    # Организация (может быть NULL, если метрика общая по всем организациям)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    organization = relationship("Organization", backref="daily_analytics")

    # Ключ метрики (например: revenue_total, revenue_kitchen, expenses_total, cost_of_goods_total)
    metric_key = Column(String(100), nullable=False)

    # Дополнительный под-ключ (например, категория, тип оплаты, название счета)
    metric_subkey = Column(String(255), nullable=True)

    # Значение метрики
    value = Column(Numeric(20, 2), nullable=False)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint(
            "date",
            "organization_id",
            "metric_key",
            "metric_subkey",
            name="uq_daily_analytics_unique_metric",
        ),
    )


