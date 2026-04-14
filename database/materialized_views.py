"""
Создание и управление материализованными представлениями для оптимизации запросов
Материализованные представления хранят предрасчитанные агрегаты
"""
from sqlalchemy import text
from sqlalchemy.orm import Session
from database.database import engine
import logging

logger = logging.getLogger(__name__)


def create_materialized_views(db: Session):
    """
    Создать материализованные представления для оптимизации запросов
    
    Args:
        db: сессия БД
    """
    try:
        # 1. Материализованное представление для ежедневной выручки по категориям
        db.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS daily_revenue_summary AS
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
            WHERE cashier != 'Удаление позиций'
                AND order_deleted != 'DELETED'
                AND dish_sum_int IS NOT NULL
            GROUP BY open_date_typed, organization_id, category
        """))
        
        # Создаем индекс для быстрого поиска
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_daily_revenue_date_org 
            ON daily_revenue_summary(date, organization_id)
        """))
        
        # 2. Материализованное представление для ежедневных расходов
        db.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS daily_expenses_summary AS
            SELECT 
                date_typed as date,
                organization_id,
                account_type,
                account_name,
                SUM(sum_resigned) as total_expense
            FROM transactions
            WHERE is_active = TRUE
                AND sum_resigned IS NOT NULL
            GROUP BY date_typed, organization_id, account_type, account_name
        """))
        
        # Создаем индекс
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_daily_expenses_date_org 
            ON daily_expenses_summary(date, organization_id)
        """))
        
        # 3. Материализованное представление для ежедневных транзакций по счетам
        db.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS daily_transactions_summary AS
            SELECT 
                date_typed as date,
                organization_id,
                account_id,
                account_name,
                account_hierarchy_second,
                SUM(sum_incoming) as total_incoming,
                SUM(sum_outgoing) as total_outgoing,
                SUM(sum_resigned) as total_resigned
            FROM transactions
            WHERE is_active = TRUE
            GROUP BY date_typed, organization_id, account_id, account_name, account_hierarchy_second
        """))
        
        # Создаем индекс
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_daily_transactions_date_org 
            ON daily_transactions_summary(date, organization_id, account_id)
        """))
        
        db.commit()
        logger.info("Материализованные представления созданы успешно")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при создании материализованных представлений: {e}")
        raise


def refresh_materialized_views(db: Session):
    """
    Обновить материализованные представления
    
    Args:
        db: сессия БД
    """
    try:
        db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY daily_revenue_summary"))
        db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY daily_expenses_summary"))
        db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY daily_transactions_summary"))
        db.commit()
        logger.info("Материализованные представления обновлены")
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при обновлении материализованных представлений: {e}")
        raise


def drop_materialized_views(db: Session):
    """
    Удалить материализованные представления
    
    Args:
        db: сессия БД
    """
    try:
        db.execute(text("DROP MATERIALIZED VIEW IF EXISTS daily_revenue_summary CASCADE"))
        db.execute(text("DROP MATERIALIZED VIEW IF EXISTS daily_expenses_summary CASCADE"))
        db.execute(text("DROP MATERIALIZED VIEW IF EXISTS daily_transactions_summary CASCADE"))
        db.commit()
        logger.info("Материализованные представления удалены")
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка при удалении материализованных представлений: {e}")
        raise


def get_materialized_view_stats(db: Session) -> dict:
    """
    Получить статистику по материализованным представлениям
    
    Args:
        db: сессия БД
        
    Returns:
        Словарь со статистикой
    """
    try:
        result = db.execute(text("""
            SELECT 
                schemaname,
                matviewname,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||matviewname)) as size,
                (SELECT COUNT(*) FROM information_schema.tables 
                 WHERE table_name = matviewname) as exists
            FROM pg_matviews
            WHERE schemaname = 'public'
            ORDER BY matviewname
        """))
        
        views = []
        for row in result:
            views.append({
                "name": row.matviewname,
                "size": row.size,
                "exists": row.exists > 0
            })
        
        return {"views": views}
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        return {"views": []}

