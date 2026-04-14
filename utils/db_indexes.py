"""
Утилита для управления индексами базы данных
Создает индексы для оптимизации частых запросов
"""

from sqlalchemy import Index, text
from sqlalchemy.orm import Session
from database.database import engine
import logging

logger = logging.getLogger(__name__)


def is_postgresql() -> bool:
    """
    Проверяет, является ли БД PostgreSQL (включая варианты с драйверами типа postgresql+psycopg2)
    """
    return engine.url.drivername.startswith("postgresql")


def is_sqlite() -> bool:
    """
    Проверяет, является ли БД SQLite (включая варианты с драйверами типа sqlite+pysqlite)
    """
    return engine.url.drivername.startswith("sqlite")


# Определение индексов для каждой таблицы
# Формат: (имя_индекса, [список_колонок])
INDEXES = {
    "d_orders": [
        ("idx_d_orders_organization_id", ["organization_id"]),
        ("idx_d_orders_time_order", ["time_order"]),
        ("idx_d_orders_deleted", ["deleted"]),
        ("idx_d_orders_org_time", ["organization_id", "time_order"]),
        ("idx_d_orders_org_deleted", ["organization_id", "deleted"]),
        ("idx_d_orders_iiko_id", ["iiko_id"]),
    ],
    "sales": [
        ("idx_sales_organization_id", ["organization_id"]),
        ("idx_sales_open_date_typed", ["open_date_typed"]),
        ("idx_sales_payment_transaction_id", ["payment_transaction_id"]),
        ("idx_sales_department_code", ["department_code"]),
        ("idx_sales_deleted_with_writeoff", ["deleted_with_writeoff"]),
        ("idx_sales_order_id", ["order_id"]),
        ("idx_sales_precheque_time", ["precheque_time"]),
        ("idx_sales_org_date", ["organization_id", "open_date_typed"]),
        ("idx_sales_org_deleted", ["organization_id", "deleted_with_writeoff"]),
        ("idx_sales_payment_transaction", ["payment_transaction_id", "organization_id"]),
        ("idx_sales_item_sale_event_id", ["item_sale_event_id"]),
    ],
    "transactions": [
        ("idx_transactions_organization_id", ["organization_id"]),
        ("idx_transactions_date_typed", ["date_typed"]),
        ("idx_transactions_account_id", ["account_id"]),
        ("idx_transactions_account_hierarchy_second", ["account_hierarchy_second"]),
        ("idx_transactions_org_date", ["organization_id", "date_typed"]),
        ("idx_transactions_org_account", ["organization_id", "account_id"]),
        ("idx_transactions_iiko_id", ["iiko_id"]),
    ],
    "employees": [
        ("idx_employees_preferred_organization_id", ["preferred_organization_id"]),
        ("idx_employees_deleted", ["deleted"]),
        ("idx_employees_main_role_code", ["main_role_code"]),
        ("idx_employees_iiko_id", ["iiko_id"]),
        ("idx_employees_org_deleted", ["preferred_organization_id", "deleted"]),
    ],
    "shifts": [
        ("idx_shifts_employee_id", ["employee_id"]),
        ("idx_shifts_start_time", ["start_time"]),
        ("idx_shifts_employee_start", ["employee_id", "start_time"]),
    ],
    "items": [
        ("idx_items_organization_id", ["organization_id"]),
        ("idx_items_category_id", ["category_id"]),
        ("idx_items_iiko_id", ["iiko_id"]),
        ("idx_items_org_category", ["organization_id", "category_id"]),
    ],
    "t_orders": [
        ("idx_t_orders_order_id", ["order_id"]),
        ("idx_t_orders_item_id", ["item_id"]),
    ],
    "bank_commissions": [
        ("idx_bank_commissions_organization_id", ["organization_id"]),
        ("idx_bank_commissions_order_id", ["order_id"]),
        ("idx_bank_commissions_time_transaction", ["time_transaction"]),
        ("idx_bank_commissions_org_time", ["organization_id", "time_transaction"]),
    ],
    "daily_analytics": [
        ("idx_daily_analytics_metric_key", ["metric_key"]),
        ("idx_daily_analytics_metric_date_org", ["metric_key", "date", "organization_id"]),
        ("idx_daily_analytics_date_org", ["date", "organization_id"]),
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
            logger.debug(f"Обработка таблицы {table_name}, индексов: {len(indexes)}")
            for index_def in indexes:
                try:
                    # index_def - это кортеж (имя_индекса, [колонки])
                    if isinstance(index_def, tuple) and len(index_def) == 2:
                        index_name, column_names = index_def
                    else:
                        # Обратная совместимость со старым форматом (Index объекты)
                        if hasattr(index_def, 'name'):
                            index_name = index_def.name
                            column_names = []
                            for col in index_def.columns:
                                if isinstance(col, str):
                                    column_names.append(col)
                                else:
                                    column_names.append(col.name if hasattr(col, 'name') else str(col))
                        else:
                            logger.warning(f"Неверный формат определения индекса: {index_def}, пропускаем")
                            error_count += 1
                            continue
                    
                    if not column_names:
                        logger.warning(f"Не удалось определить колонки для индекса {index_name}, пропускаем")
                        error_count += 1
                        continue
                    
                    columns_str = ', '.join(column_names)
                    logger.debug(f"Создание индекса {index_name} на таблице {table_name} для колонок: {columns_str}")
                    
                    # Для SQLite
                    if is_sqlite():
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
                        db.execute(text(f"CREATE INDEX {index_name} ON {table_name} ({columns_str})"))
                        db.commit()
                        logger.info(f"Создан индекс {index_name} для таблицы {table_name}")
                        created_count += 1
                    
                    # Для PostgreSQL
                    elif is_postgresql():
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
                            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"
                        ))
                        db.commit()
                        logger.info(f"Создан индекс {index_name} для таблицы {table_name}")
                        created_count += 1
                    else:
                        logger.warning(f"Неподдерживаемый тип БД: {engine.url.drivername}")
                        error_count += 1
                    
                except Exception as e:
                    index_name_for_error = index_def[0] if isinstance(index_def, tuple) else (index_def.name if hasattr(index_def, 'name') else 'unknown')
                    logger.error(f"Ошибка при создании индекса {index_name_for_error}: {e}", exc_info=True)
                    error_count += 1
                    if is_postgresql():
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
        if is_postgresql() and db:
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
            for index_def in indexes:
                try:
                    # index_def - это кортеж (имя_индекса, [колонки])
                    if isinstance(index_def, tuple) and len(index_def) == 2:
                        index_name = index_def[0]
                    else:
                        # Обратная совместимость со старым форматом (Index объекты)
                        index_name = index_def.name if hasattr(index_def, 'name') else None
                        if not index_name:
                            logger.warning(f"Неверный формат определения индекса: {index_def}, пропускаем")
                            error_count += 1
                            continue
                    
                    # Для SQLite
                    if is_sqlite():
                        result = db.execute(text(
                            f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index_name}'"
                        )).fetchone()
                        
                        if result:
                            db.execute(text(f"DROP INDEX {index_name}"))
                            logger.info(f"Удален индекс {index_name}")
                            dropped_count += 1
                    
                    # Для PostgreSQL
                    elif is_postgresql():
                        result = db.execute(text(
                            f"SELECT indexname FROM pg_indexes WHERE indexname = '{index_name}'"
                        )).fetchone()
                        
                        if result:
                            db.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
                            db.commit()
                            logger.info(f"Удален индекс {index_name}")
                            dropped_count += 1
                    
                except Exception as e:
                    index_name_for_error = index_def[0] if isinstance(index_def, tuple) else (index_def.name if hasattr(index_def, 'name') else 'unknown')
                    logger.error(f"Ошибка при удалении индекса {index_name_for_error}: {e}")
                    error_count += 1
                    if is_postgresql():
                        db.rollback()
        
        logger.info(f"Удаление индексов завершено: удалено {dropped_count}, ошибок {error_count}")
        
        return {
            "dropped": dropped_count,
            "errors": error_count
        }
        
    except Exception as e:
        logger.error(f"Ошибка при удалении индексов: {e}")
        if is_postgresql() and db:
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
        if is_postgresql():
            # Для PostgreSQL выполняем ANALYZE для обновления статистики
            db.execute(text("ANALYZE"))
            db.commit()
            logger.info("Выполнен ANALYZE для обновления статистики индексов PostgreSQL")
        
        elif is_sqlite():
            # Для SQLite выполняем ANALYZE для обновления статистики
            db.execute(text("ANALYZE"))
            db.commit()
            logger.info("Выполнен ANALYZE для обновления статистики индексов SQLite")
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Ошибка при оптимизации индексов: {e}")
        if is_postgresql() and db:
            db.rollback()
        return {"success": False, "error": str(e)}
    
    finally:
        if close_db:
            db.close()

