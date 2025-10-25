from utils.commission_reports.parsing_reports import *
from datetime import datetime
import json


def json_serializer(obj):
    """JSON serializer для объектов datetime, Decimal и SQLAlchemy"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'Decimal':
        return float(obj)
    elif hasattr(obj, '__class__') and obj.__class__.__name__ == 'DOrder':
        # Специальная обработка для DOrder
        try:
            return {
                'id': obj.id,
                'iiko_id': obj.iiko_id,
                'time_order': obj.time_order.isoformat() if obj.time_order else None,
                'discount': float(obj.discount) if obj.discount else None,
                'bank_commission': float(obj.bank_commission) if obj.bank_commission else None,
                'organization_id': obj.organization_id
            }
        except:
            return None
    elif hasattr(obj, '__class__') and 'sqlalchemy' in str(obj.__class__.__module__):
        # Для других SQLAlchemy объектов пытаемся извлечь основные атрибуты
        try:
            # Если это объект с атрибутами, создаем словарь
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
    print("Starting report parsing...")
    reports_path = "temp_files/terminals_report"
    pdf_reports_path = "temp_files/terminals_report_pdf"

    reports = scan_reports_folder(reports_path)
    pdf_reports = scan_reports_folder(pdf_reports_path)
    print(f"Found {len(reports['xlsx_reports'])} reports and {len(pdf_reports['pdf_reports'])} pdf reports")

    transactions = []
    for report in reports['xlsx_reports']:
        transactions.extend(parse_file(report, 'xlsx'))
    for report in pdf_reports['pdf_reports']:
        transactions.extend(parse_file(report, 'pdf'))
    
    transactions = normalize_transaction_data(transactions)
    
    print(f"Found {len(transactions)} transactions")
    
    print(f"Starting to create bank commissions...")
    create_bank_commission(transactions)
    print(f"Bank commissions created")

    data_to_write = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "summary": {
            "total_commissions": len(transactions),
            "total_amount": sum(transaction['amount'] for transaction in transactions),
            "total_bank_commission": sum(transaction['commission'] if transaction['commission'] is not None else 0 for transaction in transactions),
        },
    }
    print(json.dumps(data_to_write, ensure_ascii=False, indent=2, default=json_serializer))
    print(f"Bank commissions created")

