from utils.commission_reports.matching_commission_w_sales_n_orders import generate_commission_report
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
    print("Starting commission syncing with orders...")
    
    # Генерируем отчет по сопоставлению комиссий
    report = generate_commission_report()
    
    print(f"Commission syncing completed!")
    print(f"Summary:")
    print(f"  Total commissions: {report['summary']['total_commissions']}")
    print(f"  Matched commissions: {report['summary']['matched_commissions']}")
    print(f"  Unmatched commissions: {report['summary']['unmatched_commissions']}")
    print(f"  Match percentage: {report['summary']['match_percentage']:.2f}%")
    print(f"  Total commission amount: {report['summary']['total_commission_amount']:.2f}")
    print(f"  Matched commission amount: {report['summary']['matched_commission_amount']:.2f}")
    print(f"  Unmatched commission amount: {report['summary']['unmatched_commission_amount']:.2f}")
    print(f"  Orders with commission: {report['summary']['orders_with_commission']}")
    print(f"  Total commission in orders: {report['summary']['total_commission_in_orders']:.2f}")
    
    # Сохраняем отчет в файл
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'temp_files/commission_syncing_report_{timestamp}.json'
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=json_serializer)
    
    print(f"Report saved to {filename}")
    print("Commission syncing process completed successfully!")
