"""
ОПТИМИЗИРОВАННЫЙ скрипт для запуска конвертации данных из sales в d_orders.

ОСОБЕННОСТИ:
- Один SQL-запрос с GROUP BY для получения всех данных
- Batch операции (commit каждые N записей)
- Суммирование на уровне БД
- JOIN с order_types
- JSON агрегация для customer, payments, discounts
- Создаются только d_orders (без t_orders)

Примеры использования:
1. Конвертировать все записи:
   python utils/run_sales_conversion.py --all

2. Конвертировать за период:
   python utils/run_sales_conversion.py --start 2025-09-01 --end 2025-10-05

3. Конвертировать за последние N дней:
   python utils/run_sales_conversion.py --days 7

4. С настройкой batch size:
   python utils/run_sales_conversion.py --all --batch-size 200
"""

import argparse
from datetime import datetime, timedelta
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.database import SessionLocal
from utils.order_from_sales import convert_sales_to_orders


def parse_date(date_string: str) -> datetime:
    """Парсит строку даты в формате YYYY-MM-DD."""
    try:
        return datetime.strptime(date_string, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Неверный формат даты: {date_string}. Используйте YYYY-MM-DD")


def main():
    parser = argparse.ArgumentParser(
        description="ОПТИМИЗИРОВАННАЯ конвертация данных из таблицы sales в d_orders",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s --all                           # Конвертировать все записи
  %(prog)s --start 2024-01-01 --end 2024-01-31  # За период
  %(prog)s --days 7                        # За последние 7 дней
  %(prog)s --days 30                       # За последний месяц
  %(prog)s --all --batch-size 200          # Batch size 200
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument(
        '--all',
        action='store_true',
        help='Конвертировать все записи из таблицы sales'
    )
    group.add_argument(
        '--days',
        type=int,
        help='Конвертировать записи за последние N дней'
    )
    
    parser.add_argument(
        '--start',
        type=str,
        help='Начальная дата в формате YYYY-MM-DD (используется вместе с --end)'
    )
    parser.add_argument(
        '--end',
        type=str,
        help='Конечная дата в формате YYYY-MM-DD (используется вместе с --start)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Размер пакета для batch commit (по умолчанию: 100)'
    )
    
    args = parser.parse_args()
    
    # Валидация аргументов - проверяем, что указан хотя бы один режим
    has_mode = bool(args.all or args.days or (args.start and args.end))
    if not has_mode:
        parser.error("Необходимо указать один из режимов: --all, --days, или --start/--end")
    
    # Валидация комбинации start/end
    if args.start and not args.end:
        parser.error("--start требует --end")
    if args.end and not args.start:
        parser.error("--end требует --start")
    
    # Валидация взаимной исключительности
    if (args.start or args.end) and (args.all or args.days):
        parser.error("--start/--end не могут использоваться с --all или --days")
    
    # Определяем параметры конвертации
    start_date = None
    end_date = None
    
    if args.all:
        print("🔄 Режим: Конвертация ВСЕХ записей из sales")
    elif args.days:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)
        print(f"🔄 Режим: Конвертация за последние {args.days} дней")
        print(f"   Период: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}")
    elif args.start and args.end:
        start_date = parse_date(args.start)
        end_date = parse_date(args.end)
        print(f"🔄 Режим: Конвертация за период")
        print(f"   Период: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}")
    
    print(f"⚙️  Batch size: {args.batch_size}")
    print("\n" + "="*60)
    
    # Создаем сессию БД
    db = SessionLocal()
    
    try:
        # Замеряем время выполнения
        import time
        start_time = time.time()
        
        # Запускаем конвертацию
        stats = convert_sales_to_orders(
            db=db,
            start_date=start_date,
            end_date=end_date,
            batch_size=args.batch_size
        )
        
        elapsed_time = time.time() - start_time
        
        # Сохраняем изменения (уже закоммичены в batch'ах, но на всякий случай)
        db.commit()
        
        print("\n" + "="*60)
        print("✅ Все изменения успешно сохранены в базу данных!")
        print(f"⏱️  Время выполнения: {elapsed_time:.2f} секунд")
        print("="*60)
        
        # Возвращаем код успеха
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Операция прервана пользователем")
        db.rollback()
        return 1
        
    except Exception as e:
        print(f"\n\n❌ Критическая ошибка: {str(e)}")
        print("   Откат всех изменений...")
        db.rollback()
        
        # Выводим полный traceback для отладки
        import traceback
        print("\n📋 Детальная информация об ошибке:")
        print(traceback.format_exc())
        
        return 1
        
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

