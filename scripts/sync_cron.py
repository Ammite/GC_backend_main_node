#!/usr/bin/env python3
"""
Скрипт для автоматической синхронизации данных из iiko API.
Предназначен для запуска через cron каждые 3 часа.

Выполняет:
1. Синхронизацию по дате изменения транзакций (за последние 7 дней)
2. Синхронизацию транзакций за сегодня
3. Синхронизацию продаж за сегодня
"""

import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.database import SessionLocal
from services.iiko import iiko_sync
from services.cash.pay_out_service import sync_pay_out_types_from_iiko

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(project_root / 'logs' / 'sync_cron.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)




async def sync_by_modification():
    """
    Синхронизация по дате изменения транзакций.
    
    Логика:
    - Дата изменения (DateSecondary.DateTyped) = только сегодня
    - Дата создания (DateTime.DateTyped) = от 3 месяцев назад до сегодня включительно
    
    Функция get_transactions_by_modification_date использует:
    - from_date и to_date для разбивки по дням для даты изменения
    - Вычисляет период для даты создания как (to_date - 90 дней) до (to_date + 1 день)
    """
    db = SessionLocal()
    try:
        # Дата изменения = только сегодня (передаем для разбивки по дням)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        logger.info(f"Синхронизация: дата изменения = сегодня ({today.strftime('%Y-%m-%d')})")
        logger.info(f"Фильтр по дате создания: от 3 месяцев назад до сегодня включительно")
        
        # Синхронизация счетов перед основной синхронизацией
        logger.info("Синхронизация счетов...")
        accounts_result = await iiko_sync.sync_accounts(db)
        logger.info(f"Синхронизация счетов завершена: {accounts_result}")
        
        # Передаем сегодня для разбивки по дням (будет только один день)
        # Функция сама вычислит период для даты создания как (today - 90 дней) до (today + 1 день)
        result = await iiko_sync.sync_by_modification_date(db, today, today)
        logger.info(f"Синхронизация по дате изменения завершена: {result}")
        
        return result
    except Exception as e:
        logger.error(f"Ошибка синхронизации по дате изменения: {e}", exc_info=True)
        raise
    finally:
        db.close()


async def main():
    """Основная функция для запуска всех синхронизаций"""
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(f"Запуск автоматической синхронизации в {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    try:
        # 0. Справочники: pay-out-types, salaries, shifts
        logger.info("\n--- Шаг 0: Синхронизация справочников ---")
        db = SessionLocal()
        try:
            # Типы изъятий
            logger.info("Синхронизация типов изъятий...")
            pay_out_result = await sync_pay_out_types_from_iiko(db)
            logger.info(f"Типы изъятий: {pay_out_result}")

            # Оклады сотрудников
            logger.info("Синхронизация окладов...")
            salaries_result = await iiko_sync.sync_salaries(db)
            logger.info(f"Оклады: {salaries_result}")

            # Типы явок
            logger.info("Синхронизация типов явок...")
            attendance_result = await iiko_sync.sync_attendance_types(db)
            logger.info(f"Типы явок: {attendance_result}")

            # Смены за последние 30 дней (по умолчанию)
            logger.info("Синхронизация смен...")
            shifts_result = await iiko_sync.sync_shifts(db)
            logger.info(f"Смены: {shifts_result}")
        except Exception as e:
            logger.error(f"Ошибка синхронизации справочников: {e}", exc_info=True)
        finally:
            db.close()

        # 1. Синхронизация по дате изменения (включает счета, транзакции, продажи)
        logger.info("\n--- Шаг 1: Синхронизация по дате изменения ---")
        modification_result = await sync_by_modification()
        
        # sync_by_modification_date уже включает синхронизацию за сегодня,
        # поэтому дополнительная синхронизация не требуется
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("=" * 80)
        logger.info(f"Синхронизация завершена за {duration:.2f} секунд")
        logger.info(f"Время окончания: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)
        
        # Итоговая статистика
        logger.info("\nИтоговая статистика:")
        logger.info(f"  Синхронизация по дате изменения:")
        logger.info(f"    - Транзакций: создано {modification_result.get('transactions', {}).get('created', 0)}, "
                   f"удалено {modification_result.get('transactions', {}).get('deleted', 0)}, "
                   f"ошибок {modification_result.get('transactions', {}).get('errors', 0)}")
        logger.info(f"    - Продаж: создано {modification_result.get('sales', {}).get('created', 0)}, "
                   f"удалено {modification_result.get('sales', {}).get('deleted', 0)}, "
                   f"ошибок {modification_result.get('sales', {}).get('errors', 0)}")
        dates_synced = modification_result.get('dates_synced', [])
        if dates_synced:
            logger.info(f"    - Синхронизированные даты: {', '.join(dates_synced)}")
        
        return 0
    except Exception as e:
        logger.error(f"Критическая ошибка при выполнении синхронизации: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    # Создаем директорию для логов, если её нет
    logs_dir = project_root / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    # Запускаем асинхронную функцию
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

