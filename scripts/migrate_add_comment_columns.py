"""
Миграция: добавление колонки comment в таблицы suppliers и conceptions.

Запуск:
    python scripts/migrate_add_comment_columns.py

Автор: AI Assistant
Дата: 2026-01-27
"""

import sys
import os

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database.database import engine, SessionLocal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_column_exists(db, table_name: str, column_name: str) -> bool:
    """Проверяет, существует ли колонка в таблице."""
    result = db.execute(
        text("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = :table_name 
                AND column_name = :column_name
            )
        """),
        {"table_name": table_name, "column_name": column_name}
    )
    return result.scalar()


def add_column_if_not_exists(db, table_name: str, column_name: str, column_type: str):
    """Добавляет колонку в таблицу, если она не существует."""
    if check_column_exists(db, table_name, column_name):
        logger.info(f"Колонка {table_name}.{column_name} уже существует, пропускаем")
        return False
    
    logger.info(f"Добавляем колонку {table_name}.{column_name} ({column_type})")
    db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
    db.commit()
    logger.info(f"Колонка {table_name}.{column_name} успешно добавлена")
    return True


def main():
    """Основная функция миграции."""
    db = SessionLocal()
    try:
        migrations = [
            ("suppliers", "comment", "TEXT"),
            ("conceptions", "comment", "TEXT"),
        ]
        
        added_count = 0
        for table_name, column_name, column_type in migrations:
            try:
                if add_column_if_not_exists(db, table_name, column_name, column_type):
                    added_count += 1
            except Exception as e:
                logger.error(f"Ошибка при добавлении колонки {table_name}.{column_name}: {e}")
                db.rollback()
        
        logger.info(f"Миграция завершена. Добавлено колонок: {added_count}")
        return added_count
        
    except Exception as e:
        logger.error(f"Критическая ошибка миграции: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
