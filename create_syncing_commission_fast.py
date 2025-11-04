"""
Быстрая синхронизация комиссий с заказами.

Этот скрипт использует оптимизированную версию синхронизации:
- Один SQL-запрос для поиска совпадений
- Batch операции (commit каждые N записей)
- Выбор ближайшего заказа по времени
- Запись payment_id в cheque_additional_info

Рекомендуется использовать этот скрипт вместо create_syncing_commission.py
для больших объемов данных.
"""

from utils.commission_reports.fast_matching_commission import generate_commission_report_fast
from datetime import datetime
import json


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
    print("=" * 80)
    print("FAST COMMISSION SYNCING - START")
    print("=" * 80)
    print("\nОсобенности быстрой синхронизации:")
    print("  ✓ Один SQL-запрос для поиска совпадений")
    print("  ✓ Batch операции (commit каждые 100 записей)")
    print("  ✓ Выбор ближайшего заказа: сравнивает transaction_time с precheque_time и open_time")
    print("  ✓ Запись payment_id в d_order.cheque_additional_info")
    print()
    
    # Можно изменить batch_size для оптимизации
    # Большие значения = меньше commit'ов, быстрее, но больше риск потери данных при ошибке
    # Меньшие значения = больше commit'ов, медленнее, но безопаснее
    BATCH_SIZE = 100
    
    print(f"Starting fast commission syncing (batch_size={BATCH_SIZE})...")
    print()
    
    # Генерируем отчет по сопоставлению комиссий
    report = generate_commission_report_fast(batch_size=BATCH_SIZE)
    
    print("\n" + "=" * 80)
    print("SYNCING RESULTS")
    print("=" * 80)
    print(f"Elapsed time:                   {report['elapsed_time_seconds']:.2f} seconds")
    print(f"Batch size:                     {report['batch_size']}")
    print()
    print(f"Total matches found by SQL:     {report['summary']['total_matches_found']}")
    print(f"Successfully matched:           {report['summary']['matched_commissions']}")
    print(f"Failed to match:                {report['summary']['failed_matches']}")
    print(f"Unmatched by SQL:               {report['summary']['unmatched_by_sql']}")
    print(f"Summed with existing:           {report['summary']['summed_commissions']}")
    print(f"Match percentage:               {report['summary']['match_percentage']:.2f}%")
    print()
    print(f"Total commission amount:        {report['summary']['total_commission_amount']:.2f} ₸")
    print(f"Matched commission amount:      {report['summary']['matched_commission_amount']:.2f} ₸")
    print(f"Failed commission amount:       {report['summary']['failed_commission_amount']:.2f} ₸")
    print(f"Unmatched commission amount:    {report['summary']['unmatched_commission_amount']:.2f} ₸")
    print()
    print(f"Orders updated:                 {report['summary']['orders_updated']}")
    
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
        print("TOP 5 FAILED TRANSACTIONS")
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

