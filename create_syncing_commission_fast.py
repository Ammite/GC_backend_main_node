"""
Быстрая синхронизация комиссий с заказами.

Этот скрипт использует оптимизированную версию синхронизации:
- Один SQL-запрос для поиска совпадений по сумме и организации
- ПРАВИЛЬНАЯ логика сопоставления:
  * Сравнивает transaction_time (время оплаты на терминале) со ВСЕМИ тремя временами:
    1. order_time (время создания заказа)
    2. sale_precheque_time (время предоплаты)
    3. sale_open_time (время открытия заказа)
  * Для каждого заказа берет МИНИМАЛЬНУЮ разницу из трех
  * Если минимальная разница больше max_time_diff часов - отбрасывает заказ
  * Из оставшихся выбирает заказ с наименьшей разницей
  
  Это нужно, потому что заказ может быть:
  - Открыт (order_time)
  - Оплачен частично как предоплата (sale_precheque_time)
  - И потом через несколько дней оплачен полностью (transaction_time)

- Batch операции (commit каждые N записей)
- Запись payment_id в cheque_additional_info заказа

ВАЖНО: Если минимальная разница между transaction_time и любым из трех времен
больше указанного лимита, заказ НЕ будет сопоставлен с комиссией.

Рекомендуется использовать этот скрипт вместо create_syncing_commission.py
для больших объемов данных.

Использование:
    python create_syncing_commission_fast.py --start_date 2025-10-01 --end_date 2025-10-20
    python create_syncing_commission_fast.py --start_date 2025-10-01 --end_date 2025-10-20 --dry_run
    python create_syncing_commission_fast.py --start_date 2025-10-01 --end_date 2025-10-20 --batch_size 50
    python create_syncing_commission_fast.py --start_date 2025-10-01 --end_date 2025-10-20 --max_time_diff 12
"""

from utils.commission_reports.fast_matching_commission import generate_commission_report_fast
from datetime import datetime
import json
import argparse


def json_serializer(obj):
    """JSON serializer для объектов datetime, Decimal и SQLAlchemy"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Decimal':
        return float(obj)
    elif hasattr(obj, '__class__') and 'sqlalchemy' in str(obj.__class__.__module__):
        # Для SQLAlchemy объектов пытаемся извлечь основные атрибуты
        try:
            if hasattr(obj, '__dict__'):
                result = {}
                for key, value in obj.__dict__.items():
                    if not key.startswith('_'):  # Исключаем приватные атрибуты
                        if isinstance(value, datetime):
                            result[key] = value.isoformat()
                        elif hasattr(value, '__class__') and value.__class__.__name__ == 'Decimal':
                            result[key] = float(value)
                        elif hasattr(value, '__class__') and 'sqlalchemy' in str(value.__class__.__module__):
                            result[key] = None  # Рекурсивно обрабатываем вложенные объекты
                        else:
                            result[key] = value
                return result
            else:
                return None
        except:
            return None
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


if __name__ == "__main__":
    # Парсим аргументы командной строки
    parser = argparse.ArgumentParser(
        description='Быстрая синхронизация комиссий с заказами',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python create_syncing_commission_fast.py --start_date 2025-10-01 --end_date 2025-10-20
  python create_syncing_commission_fast.py --start_date 2025-10-01 --end_date 2025-10-20 --dry_run
  python create_syncing_commission_fast.py --start_date 2025-10-01 --end_date 2025-10-20 --batch_size 50
  python create_syncing_commission_fast.py --start_date 2025-10-29 --end_date 2025-10-29 --dry_run
  python create_syncing_commission_fast.py --start_date 2025-10-01 --end_date 2025-10-20 --max_time_diff 12
  python create_syncing_commission_fast.py --dry_run --max_time_diff 6
        """
    )
    parser.add_argument('--start_date', type=str, help='Начальная дата (YYYY-MM-DD)', default=None)
    parser.add_argument('--end_date', type=str, help='Конечная дата (YYYY-MM-DD)', default=None)
    parser.add_argument('--batch_size', type=int, help='Размер batch для commit (по умолчанию 100)', default=100)
    parser.add_argument('--max_time_diff', type=int, help='Максимальная разница во времени в часах (по умолчанию 24)', default=24)
    parser.add_argument('--dry_run', action='store_true', help='Режим просмотра без записи в БД')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("FAST COMMISSION SYNCING - START")
    print("=" * 80)
    print("\nОсобенности быстрой синхронизации:")
    print("  ✓ Один SQL-запрос для поиска совпадений")
    print("  ✓ Batch операции (commit каждые N записей)")
    print("  ✓ ПРАВИЛЬНАЯ ЛОГИКА: сравнивает transaction_time со ВСЕМИ тремя временами:")
    print("    - order_time (время создания заказа)")
    print("    - sale_precheque_time (время предоплаты)")
    print("    - sale_open_time (время открытия заказа)")
    print("  ✓ Для каждого заказа берется МИНИМАЛЬНАЯ разница из трех")
    print("  ✓ Фильтр: отсекаются заказы, где минимальная разница > max_time_diff часов")
    print("  ✓ Запись payment_id в d_order.cheque_additional_info")
    print("  ✓ Фильтрация по полю open_date_typed в таблице sales")
    print()
    
    # Параметры запуска
    print("Параметры запуска:")
    print(f"  Начальная дата:       {args.start_date or 'не указана (все даты)'}")
    print(f"  Конечная дата:        {args.end_date or 'не указана (все даты)'}")
    print(f"  Batch size:           {args.batch_size}")
    print(f"  Макс. разница время:  {args.max_time_diff} часов")
    print(f"  Режим:                {'DRY RUN (без записи)' if args.dry_run else 'ЗАПИСЬ В БД'}")
    print()
    
    if args.dry_run:
        print("⚠️  DRY RUN MODE: Изменения НЕ будут сохранены в базу данных")
        print("   Используйте этот режим для проверки результатов перед реальной синхронизацией")
        print()
    
    print(f"⏱️  Будут отфильтрованы заказы, где минимальная разница во времени больше {args.max_time_diff} часов")
    print(f"   (сравнение: transaction_time со всеми тремя временами: order_time, sale_precheque_time, sale_open_time)")
    print()
    
    print(f"Starting fast commission syncing...")
    print()
    
    # Генерируем отчет по сопоставлению комиссий
    report = generate_commission_report_fast(
        batch_size=args.batch_size,
        start_date=args.start_date,
        end_date=args.end_date,
        dry_run=args.dry_run,
        max_time_diff_hours=args.max_time_diff
    )
    
    print("\n" + "=" * 80)
    print("SYNCING RESULTS")
    print("=" * 80)
    print(f"Elapsed time:                   {report['elapsed_time_seconds']:.2f} seconds")
    print(f"Batch size:                     {report['batch_size']}")
    print(f"Start date:                     {report['start_date'] or 'не указана'}")
    print(f"End date:                       {report['end_date'] or 'не указана'}")
    print(f"Max time diff:                  {report['max_time_diff_hours']} hours")
    print(f"Mode:                           {'DRY RUN (no changes saved)' if report['dry_run'] else 'SAVED TO DATABASE'}")
    print()
    print(f"Total matches found by SQL:     {report['summary']['total_matches_found']}")
    print(f"Successfully matched:           {report['summary']['matched_commissions']}")
    print(f"Failed to match:                {report['summary']['failed_matches']}")
    print(f"  └─ Rejected by time filter:  {report['summary']['rejected_by_time_filter']}")
    print(f"Unmatched by SQL:               {report['summary']['unmatched_by_sql']}")
    print(f"Summed with existing:           {report['summary']['summed_commissions']}")
    print(f"Match percentage:               {report['summary']['match_percentage']:.2f}%")
    print()
    print(f"Total commission amount:        {report['summary']['total_commission_amount']:.2f} ₸")
    print(f"Matched commission amount:      {report['summary']['matched_commission_amount']:.2f} ₸")
    print(f"Failed commission amount:       {report['summary']['failed_commission_amount']:.2f} ₸")
    print(f"  └─ Rejected by time filter:  {report['summary']['rejected_by_time_filter_amount']:.2f} ₸")
    print(f"Unmatched commission amount:    {report['summary']['unmatched_commission_amount']:.2f} ₸")
    print()
    print(f"Orders updated (unique):        {report['summary']['orders_updated']}{' (simulated)' if report['dry_run'] else ''}")
    
    # Сохраняем отчет в файл
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'temp_files/commission_syncing_fast_report_{timestamp}.json'
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=json_serializer)
        print()
        print(f"Report saved to: {filename}")
    except Exception as e:
        print(f"Warning: Could not save report to file: {str(e)}")
    
    print("\n" + "=" * 80)
    print("FAST COMMISSION SYNCING - COMPLETE")
    print("=" * 80)
    
    # Выводим топ-5 несопоставленных транзакций (если есть)
    if report['details']['failed_transactions']:
        print("\n" + "=" * 80)
        print("TOP 5 FAILED TRANSACTIONS (ошибки при сопоставлении)")
        print("=" * 80)
        for i, transaction in enumerate(report['details']['failed_transactions'][:5], 1):
            print(f"\n{i}. Commission ID: {transaction['commission_id']}")
            print(f"   Amount: {transaction['amount']:.2f} ₸")
            print(f"   Commission: {transaction['commission']:.2f} ₸")
            print(f"   Organization ID: {transaction['organization_id']}")
            print(f"   Time: {transaction['time_transaction']}")
            print(f"   Error: {transaction['error']}")
        
        total_failed = len(report['details']['failed_transactions'])
        if total_failed > 5:
            print(f"\n... и еще {total_failed - 5} несопоставленных транзакций")
        print()
        print(f"Полный список в файле: {filename}")
    
    # Выводим топ-10 несопоставленных комиссий SQL (не нашли sales)
    if report['details'].get('unmatched_commissions'):
        print("\n" + "=" * 80)
        print("TOP 10 UNMATCHED COMMISSIONS (не найдены в sales)")
        print("=" * 80)
        print("Эти комиссии не нашли соответствующих записей в sales")
        print("Причины: нет sales с такой суммой, нет payment_transaction_id, или разные organization_id")
        print()
        
        for i, commission in enumerate(report['details']['unmatched_commissions'][:10], 1):
            print(f"\n{i}. Commission ID: {commission['commission_id']}")
            print(f"   Amount: {commission['amount']:.2f} ₸")
            print(f"   Commission: {commission['commission']:.2f} ₸")
            print(f"   Organization ID: {commission['organization_id']}")
            print(f"   Time: {commission['time_transaction']}")
            print(f"   Source: {commission['source']}")
        
        total_unmatched = len(report['details']['unmatched_commissions'])
        if total_unmatched > 10:
            print(f"\n... и еще {min(total_unmatched - 10, 90)} несопоставленных комиссий (показаны первые 100 из {report['summary']['unmatched_by_sql']})")
        print()
        print(f"Полный список в файле: {filename}")

