"""
Создание и управление сводными таблицами для предрасчитанных данных
Сводные таблицы обновляются периодически или через триггеры
"""
from sqlalchemy import text, Column, Integer, Numeric, Date, String, DateTime
from sqlalchemy.orm import Session
from database.database import Base, engine
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Модели для сводных таблиц (опционально, можно использовать raw SQL)
class DailyRevenueSummary(Base):
    """Сводная таблица ежедневной выручки"""
    __tablename__ = "daily_revenue_summary"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    category = Column(String(50), nullable=False)
    total_base = Column(Numeric(15, 2), nullable=False, default=0)
    total_discount = Column(Numeric(15, 2), nullable=False, default=0)
    total_increase = Column(Numeric(15, 2), nullable=False, default=0)
    total_revenue = Column(Numeric(15, 2), nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class DailyExpensesSummary(Base):
    """Сводная таблица ежедневных расходов"""
    __tablename__ = "daily_expenses_summary"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    account_type = Column(String(100), nullable=True)
    account_name = Column(String(255), nullable=True)
    total_expense = Column(Numeric(15, 2), nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


def create_summary_tables(db: Session):
    """
    Создать сводные таблицы для предрасчитанных данных
    
    Args:
        db: сессия БД
    """
    try:
        # Создаем таблицу ежедневной выручки
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS daily_revenue_summary (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                organization_id INTEGER,
                category VARCHAR(50) NOT NULL,
                total_base NUMERIC(15, 2) DEFAULT 0,
                total_discount NUMERIC(15, 2) DEFAULT 0,
                total_increase NUMERIC(15, 2) DEFAULT 0,
                total_revenue NUMERIC(15, 2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Индексы для быстрого поиска
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_daily_revenue_date 
            ON daily_revenue_summary(date, organization_id, category)
        """))
        
        # Создаем таблицу ежедневных расходов
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS daily_expenses_summary (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                organization_id INTEGER,
                account_type VARCHAR(100),
                account_name VARCHAR(255),
                total_expense NUMERIC(15, 2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Индексы
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_daily_expenses_date 
            ON daily_expenses_summary(date, organization_id)
        """))
        
        db.commit()
        logger.info("Сводные таблицы созданы успешно")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при создании сводных таблиц: {e}")
        raise


def update_daily_revenue_summary(
    db: Session,
    target_date: datetime,
    organization_id: Optional[int] = None
):
    """
    Обновить сводную таблицу выручки за конкретную дату
    
    Args:
        db: сессия БД
        target_date: целевая дата
        organization_id: ID организации (опционально)
    """
    try:
        date_str = target_date.date().isoformat()
        
        # Удаляем старые данные за эту дату
        delete_query = """
            DELETE FROM daily_revenue_summary 
            WHERE date = :date
        """
        params = {"date": date_str}
        
        if organization_id:
            delete_query += " AND organization_id = :org_id"
            params["org_id"] = organization_id
        
        db.execute(text(delete_query), params)
        
        # Вставляем новые данные
        insert_query = """
            INSERT INTO daily_revenue_summary 
            (date, organization_id, category, total_base, total_discount, total_increase, total_revenue)
            SELECT 
                open_date_typed as date,
                organization_id,
                CASE 
                    WHEN LOWER(cooking_place_type) LIKE '%кухня%' THEN 'Кухня'
                    WHEN cooking_place_type IS NOT NULL THEN 'Бар'
                    ELSE 'Прочее'
                END as category,
                SUM(dish_sum_int) as total_base,
                SUM(discount_sum) as total_discount,
                SUM(increase_sum) as total_increase,
                SUM(dish_discount_sum_int) as total_revenue
            FROM sales
            WHERE open_date_typed = :date
                AND cashier != 'Удаление позиций'
                AND order_deleted != 'DELETED'
                AND dish_sum_int IS NOT NULL
        """
        
        if organization_id:
            insert_query += " AND organization_id = :org_id"
        
        insert_query += " GROUP BY open_date_typed, organization_id, category"
        
        db.execute(text(insert_query), params)
        db.commit()
        logger.info(f"Сводная таблица выручки обновлена для даты {date_str}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при обновлении сводной таблицы выручки: {e}")
        raise


def update_daily_expenses_summary(
    db: Session,
    target_date: datetime,
    organization_id: Optional[int] = None
):
    """
    Обновить сводную таблицу расходов за конкретную дату
    
    Args:
        db: сессия БД
        target_date: целевая дата
        organization_id: ID организации (опционально)
    """
    try:
        date_str = target_date.date().isoformat()
        
        # Удаляем старые данные за эту дату
        delete_query = """
            DELETE FROM daily_expenses_summary 
            WHERE date = :date
        """
        params = {"date": date_str}
        
        if organization_id:
            delete_query += " AND organization_id = :org_id"
            params["org_id"] = organization_id
        
        db.execute(text(delete_query), params)
        
        # Вставляем новые данные
        insert_query = """
            INSERT INTO daily_expenses_summary 
            (date, organization_id, account_type, account_name, total_expense)
            SELECT 
                date_typed as date,
                organization_id,
                account_type,
                account_name,
                SUM(sum_resigned) as total_expense
            FROM transactions
            WHERE date_typed = :date
                AND is_active = TRUE
                AND sum_resigned IS NOT NULL
        """
        
        if organization_id:
            insert_query += " AND organization_id = :org_id"
        
        insert_query += " GROUP BY date_typed, organization_id, account_type, account_name"
        
        db.execute(text(insert_query), params)
        db.commit()
        logger.info(f"Сводная таблица расходов обновлена для даты {date_str}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при обновлении сводной таблицы расходов: {e}")
        raise


def get_summary_table_stats(db: Session) -> dict:
    """
    Получить статистику по сводным таблицам
    
    Args:
        db: сессия БД
        
    Returns:
        Словарь со статистикой
    """
    try:
        revenue_stats = db.execute(text("""
            SELECT 
                COUNT(*) as total_rows,
                MIN(date) as min_date,
                MAX(date) as max_date,
                pg_size_pretty(pg_total_relation_size('daily_revenue_summary')) as size
            FROM daily_revenue_summary
        """)).fetchone()
        
        expenses_stats = db.execute(text("""
            SELECT 
                COUNT(*) as total_rows,
                MIN(date) as min_date,
                MAX(date) as max_date,
                pg_size_pretty(pg_total_relation_size('daily_expenses_summary')) as size
            FROM daily_expenses_summary
        """)).fetchone()
        
        return {
            "revenue_summary": {
                "total_rows": revenue_stats[0] if revenue_stats else 0,
                "min_date": str(revenue_stats[1]) if revenue_stats and revenue_stats[1] else None,
                "max_date": str(revenue_stats[2]) if revenue_stats and revenue_stats[2] else None,
                "size": revenue_stats[3] if revenue_stats else "0 bytes"
            },
            "expenses_summary": {
                "total_rows": expenses_stats[0] if expenses_stats else 0,
                "min_date": str(expenses_stats[1]) if expenses_stats and expenses_stats[1] else None,
                "max_date": str(expenses_stats[2]) if expenses_stats and expenses_stats[2] else None,
                "size": expenses_stats[3] if expenses_stats else "0 bytes"
            }
        }
    except Exception as e:
        logger.error(f"Ошибка при получении статистики сводных таблиц: {e}")
        return {"revenue_summary": {}, "expenses_summary": {}}

