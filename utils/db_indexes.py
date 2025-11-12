"""
Утилита для управления индексами базы данных
Создает индексы для оптимизации частых запросов
"""

from sqlalchemy import Index, text
from sqlalchemy.orm import Session
from database.database import engine
import logging

logger = logging.getLogger(__name__)


# Определение индексов для каждой таблицы
INDEXES = {
    "d_orders": [
        Index("idx_d_orders_organization_id", "organization_id"),
        Index("idx_d_orders_time_order", "time_order"),
        Index("idx_d_orders_deleted", "deleted"),
        Index("idx_d_orders_org_time", "organization_id", "time_order"),
        Index("idx_d_orders_org_deleted", "organization_id", "deleted"),
        Index("idx_d_orders_iiko_id", "iiko_id"),
    ],
    "sales": [
        Index("idx_sales_organization_id", "organization_id"),
        Index("idx_sales_open_date_typed", "open_date_typed"),
        Index("idx_sales_payment_transaction_id", "payment_transaction_id"),
        Index("idx_sales_department_code", "department_code"),
        Index("idx_sales_deleted_with_writeoff", "deleted_with_writeoff"),
        Index("idx_sales_order_id", "order_id"),
        Index("idx_sales_precheque_time", "precheque_time"),
        Index("idx_sales_org_date", "organization_id", "open_date_typed"),
        Index("idx_sales_org_deleted", "organization_id", "deleted_with_writeoff"),
        Index("idx_sales_payment_transaction", "payment_transaction_id", "organization_id"),
        Index("idx_sales_item_sale_event_id", "item_sale_event_id"),
    ],
    "transactions": [
        Index("idx_transactions_organization_id", "organization_id"),
        Index("idx_transactions_date_typed", "date_typed"),
        Index("idx_transactions_account_id", "account_id"),
        Index("idx_transactions_account_hierarchy_second", "account_hierarchy_second"),
        Index("idx_transactions_org_date", "organization_id", "date_typed"),
        Index("idx_transactions_org_account", "organization_id", "account_id"),
        Index("idx_transactions_iiko_id", "iiko_id"),
    ],
    "employees": [
        Index("idx_employees_preferred_organization_id", "preferred_organization_id"),
        Index("idx_employees_deleted", "deleted"),
        Index("idx_employees_main_role_code", "main_role_code"),
        Index("idx_employees_iiko_id", "iiko_id"),
        Index("idx_employees_org_deleted", "preferred_organization_id", "deleted"),
    ],
    "shifts": [
        Index("idx_shifts_employee_id", "employee_id"),
        Index("idx_shifts_start_time", "start_time"),
        Index("idx_shifts_employee_start", "employee_id", "start_time"),
    ],
    "items": [
        Index("idx_items_organization_id", "organization_id"),
        Index("idx_items_category_id", "category_id"),
        Index("idx_items_iiko_id", "iiko_id"),
        Index("idx_items_org_category", "organization_id", "category_id"),
    ],
    "t_orders": [
        Index("idx_t_orders_order_id", "order_id"),
        Index("idx_t_orders_item_id", "item_id"),
    ],
    "bank_commissions": [
        Index("idx_bank_commissions_organization_id", "organization_id"),
        Index("idx_bank_commissions_order_id", "order_id"),
        Index("idx_bank_commissions_time_transaction", "time_transaction"),
        Index("idx_bank_commissions_org_time", "organization_id", "time_transaction"),
    ],
}


def create_indexes(db: Session = None):
    """
    Создает все индексы для оптимизации запросов
    
    Args:
        db: Сессия БД (опционально, если не указана, создается новая)
    """
    close_db = False
    if db is None:
        from database.database import SessionLocal
        db = SessionLocal()
        close_db = True
    
    try:
        created_count = 0
        skipped_count = 0
        error_count = 0
        
        for table_name, indexes in INDEXES.items():
            for index in indexes:
                try:
                    # Проверяем, существует ли индекс
                    index_name = index.name
                    
                    # Для SQLite
                    if engine.url.drivername == "sqlite":
                        # SQLite не поддерживает IF NOT EXISTS для индексов напрямую
                        # Проверяем существование через запрос
                        result = db.execute(text(
                            f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index_name}'"
                        )).fetchone()
                        
                        if result:
                            logger.debug(f"Индекс {index_name} уже существует, пропускаем")
                            skipped_count += 1
                            continue
                        
                        # Создаем индекс через SQL
                        columns = ', '.join(index.columns.keys())
                        db.execute(text(f"CREATE INDEX {index_name} ON {table_name} ({columns})"))
                        db.commit()
                        logger.info(f"Создан индекс {index_name} для таблицы {table_name}")
                        created_count += 1
                    
                    # Для PostgreSQL
                    elif engine.url.drivername == "postgresql":
                        # Проверяем существование индекса
                        result = db.execute(text(
                            f"SELECT indexname FROM pg_indexes WHERE indexname = '{index_name}'"
                        )).fetchone()
                        
                        if result:
                            logger.debug(f"Индекс {index_name} уже существует, пропускаем")
                            skipped_count += 1
                            continue
                        
                        # Создаем индекс с IF NOT EXISTS
                        db.execute(text(
                            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({', '.join(index.columns.keys())})"
                        ))
                        db.commit()
                        logger.info(f"Создан индекс {index_name} для таблицы {table_name}")
                        created_count += 1
                    
                except Exception as e:
                    logger.error(f"Ошибка при создании индекса {index.name}: {e}")
                    error_count += 1
                    if engine.url.drivername == "postgresql":
                        db.rollback()
        
        logger.info(
            f"Создание индексов завершено: создано {created_count}, "
            f"пропущено {skipped_count}, ошибок {error_count}"
        )
        
        return {
            "created": created_count,
            "skipped": skipped_count,
            "errors": error_count
        }
        
    except Exception as e:
        logger.error(f"Ошибка при создании индексов: {e}")
        if engine.url.drivername == "postgresql" and db:
            db.rollback()
        raise
    
    finally:
        if close_db:
            db.close()


def drop_indexes(db: Session = None):
    """
    Удаляет все индексы (используется для пересоздания)
    
    Args:
        db: Сессия БД (опционально, если не указана, создается новая)
    """
    close_db = False
    if db is None:
        from database.database import SessionLocal
        db = SessionLocal()
        close_db = True
    
    try:
        dropped_count = 0
        error_count = 0
        
        for table_name, indexes in INDEXES.items():
            for index in indexes:
                try:
                    index_name = index.name
                    
                    # Для SQLite
                    if engine.url.drivername == "sqlite":
                        result = db.execute(text(
                            f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index_name}'"
                        )).fetchone()
                        
                        if result:
                            db.execute(text(f"DROP INDEX {index_name}"))
                            logger.info(f"Удален индекс {index_name}")
                            dropped_count += 1
                    
                    # Для PostgreSQL
                    elif engine.url.drivername == "postgresql":
                        result = db.execute(text(
                            f"SELECT indexname FROM pg_indexes WHERE indexname = '{index_name}'"
                        )).fetchone()
                        
                        if result:
                            db.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
                            db.commit()
                            logger.info(f"Удален индекс {index_name}")
                            dropped_count += 1
                    
                except Exception as e:
                    logger.error(f"Ошибка при удалении индекса {index.name}: {e}")
                    error_count += 1
                    if engine.url.drivername == "postgresql":
                        db.rollback()
        
        logger.info(f"Удаление индексов завершено: удалено {dropped_count}, ошибок {error_count}")
        
        return {
            "dropped": dropped_count,
            "errors": error_count
        }
        
    except Exception as e:
        logger.error(f"Ошибка при удалении индексов: {e}")
        if engine.url.drivername == "postgresql" and db:
            db.rollback()
        raise
    
    finally:
        if close_db:
            db.close()


def recreate_indexes(db: Session = None):
    """
    Пересоздает все индексы (удаляет и создает заново)
    Полезно после массовых операций синхронизации
    
    Args:
        db: Сессия БД (опционально, если не указана, создается новая)
    """
    logger.info("Начало пересоздания индексов...")
    drop_result = drop_indexes(db)
    create_result = create_indexes(db)
    
    return {
        "dropped": drop_result.get("dropped", 0),
        "created": create_result.get("created", 0),
        "errors": drop_result.get("errors", 0) + create_result.get("errors", 0)
    }


def optimize_indexes(db: Session = None):
    """
    Оптимизирует индексы (ANALYZE для PostgreSQL, VACUUM для SQLite)
    Полезно вызывать после массовых операций синхронизации
    
    Args:
        db: Сессия БД (опционально, если не указана, создается новая)
    """
    close_db = False
    if db is None:
        from database.database import SessionLocal
        db = SessionLocal()
        close_db = True
    
    try:
        if engine.url.drivername == "postgresql":
            # Для PostgreSQL выполняем ANALYZE для обновления статистики
            db.execute(text("ANALYZE"))
            db.commit()
            logger.info("Выполнен ANALYZE для обновления статистики индексов PostgreSQL")
        
        elif engine.url.drivername == "sqlite":
            # Для SQLite выполняем ANALYZE для обновления статистики
            db.execute(text("ANALYZE"))
            db.commit()
            logger.info("Выполнен ANALYZE для обновления статистики индексов SQLite")
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Ошибка при оптимизации индексов: {e}")
        if engine.url.drivername == "postgresql" and db:
            db.rollback()
        return {"success": False, "error": str(e)}
    
    finally:
        if close_db:
            db.close()

