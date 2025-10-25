import json
from datetime import datetime
import os

from models.d_order import DOrder


def parse_report(report_path: str) -> list:
    """
    Парсит отчет и возвращает структурированные данные.
    В нужном формате:
    {
        "transaction": dict,
        "date": datetime,
        "amount": float,
        "terminal_address": str,
        "commission": float
    }
    """
    if report_path.endswith('.pdf'):
        raw_data = parse_pdf_report(report_path)
    elif report_path.endswith('.xlsx') or report_path.endswith('.XLSX'):
        raw_data = parse_excel_report(report_path)
    else:
        raise ValueError(f"Unsupported file format: {report_path}")

    # Приводим к единому формату
    normalized_transactions = []
    
    if isinstance(raw_data, dict) and 'transactions' in raw_data:
        # Данные из PDF парсера
        for transaction in raw_data['transactions']:
            normalized = normalize_transaction_to_standard_format(transaction)
            if normalized:
                normalized_transactions.append(normalized)
    elif isinstance(raw_data, list):
        # Данные из Excel парсера
        for transaction in raw_data:
            normalized = normalize_transaction_to_standard_format(transaction)
            if normalized:
                normalized_transactions.append(normalized)
    
    return normalized_transactions

def normalize_transaction_to_standard_format(transaction: dict) -> dict:
    """
    Приводит транзакцию к стандартному формату:
    {
        "transaction": dict,
        "date": datetime,
        "amount": float,
        "terminal_address": str,
        "commission": float,
        "source": str
    }
    """
    from datetime import datetime
    
    normalized = {}
    
    # Извлекаем дату
    date_str = transaction.get('Дата операции') or transaction.get('Дата транзакции')
    time_str = transaction.get('Время') or transaction.get('Время транзакции')
    
    if date_str:
        try:
            if isinstance(date_str, str):
                # Формат DD.MM.YYYY
                if '.' in date_str:
                    day, month, year = date_str.split('.')
                    date_obj = datetime(int(year), int(month), int(day))
                else:
                    # Другие форматы даты
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            else:
                date_obj = date_str
            
            # Добавляем время если есть
            if time_str and isinstance(time_str, str):
                try:
                    hour, minute, second = time_str.split(':')
                    date_obj = date_obj.replace(hour=int(hour), minute=int(minute), second=int(second))
                except:
                    pass
            
            normalized['date'] = date_obj
        except:
            pass
    
    # Извлекаем сумму
    amount = transaction.get('Сумма операции (т)') or transaction.get('Сумма транзакции')
    if amount:
        try:
            normalized['amount'] = float(amount)
        except:
            pass
    
    # Извлекаем адрес терминала
    address = transaction.get('Адрес точки продаж') or transaction.get('Адрес транзакции')
    if address:
        normalized['terminal_address'] = str(address).strip()
    
    # Извлекаем комиссию - ищем по разным полям в зависимости от типа отчета
    commission = None
    commission_field_used = None
    
    # Сначала ищем "Общая комиссия банка" (для БЦК)
    if transaction.get('Общая комиссия банка'):
        commission_raw = transaction.get('Общая комиссия банка')
        # Триммим и убираем переносы строк и лишние пробелы
        try:
            commission_clean = str(commission_raw).strip().replace('\n', '').replace('\r', '').replace(' ', '').replace(',', '')
            if commission_clean:
                commission = commission_clean
                commission_field_used = 'Общая комиссия банка'
        except:
            commission = commission_raw
            commission_field_used = 'Общая комиссия банка'
    # Затем ищем другие поля комиссии
    elif transaction.get('Комиссия за операции (т)'):
        commission = transaction.get('Комиссия за операции (т)')
        commission_field_used = 'Комиссия за операции (т)'
    elif transaction.get('Комиссия за операции по карте (т)'):
        commission = transaction.get('Комиссия за операции по карте (т)')
        commission_field_used = 'Комиссия за операции по карте (т)'
    elif transaction.get('Комиссия Kaspi Pay (т)'):
        commission = transaction.get('Комиссия Kaspi Pay (т)')
        commission_field_used = 'Комиссия Kaspi Pay (т)'
    elif transaction.get('Комиссия Kaspi Travel (т)'):
        commission = transaction.get('Комиссия Kaspi Travel (т)')
        commission_field_used = 'Комиссия Kaspi Travel (т)'
    elif transaction.get('Комиссия за обеспечение платежа (т)'):
        commission = transaction.get('Комиссия за обеспечение платежа (т)')
        commission_field_used = 'Комиссия за обеспечение платежа (т)'
    
    if commission:
        try:
            # Преобразуем в положительное число (комиссия всегда положительная)
            normalized['commission'] = abs(float(commission))
            # Добавляем информацию о том, какое поле использовалось
            normalized['commission_field'] = commission_field_used
        except Exception as e:
            print(f"   ⚠️ Ошибка парсинга комиссии '{commission_field_used}': {commission} - {e}")
    else:
        print(f"   ⚠️ Поле комиссии не найдено в транзакции")
    
    # Сохраняем оригинальную транзакцию
    normalized['transaction'] = transaction
    normalized['source'] = transaction.get('file_path', '') #file path of the report
    # Проверяем что есть обязательные поля
    if normalized.get('date') and normalized.get('amount'):
        return normalized
    
    return None

def get_reports(reports_path: str) -> list[str]:
    """
    Получает все отчеты из папки и возвращает список путей к файлам.
    """
    reports = []
    for file in os.listdir(reports_path):
        if 'terminals_report_pdf' in reports_path:
            # В папке PDF только PDF файлы
            if file.endswith('.pdf'):
                reports.append(os.path.join(reports_path, file))
        else:
            # В обычной папке PDF и Excel файлы
            if file.endswith('.pdf') or file.endswith('.xlsx') or file.endswith('.XLSX'):
                reports.append(os.path.join(reports_path, file))
    return reports

def parse_pdf_report(report_path: str) -> dict:
    """
    Парсит PDF отчет и возвращает структурированные данные.
    """
    import pdfplumber
    import pandas as pd
    import re

    data = []
    transactions = []

    # Открываем PDF и извлекаем таблицы
    with pdfplumber.open(report_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if any(cell and cell.strip() for cell in row):  # пропуск пустых строк
                        data.append(row)

    # Преобразуем в DataFrame
    df = pd.DataFrame(data)

    # Попробуем автоматически убрать заголовки и пустые колонки
    df = df.dropna(how='all', axis=1)
    
    # Фильтруем строки с номерами операций (первая колонка должна содержать число)
    df = df[df[0].astype(str).str.match(r'^\d+$', na=False)]

    # Определяем заголовки на основе структуры данных
    # Обычно в БЦК отчетах структура: номер, дата, время, сумма, адрес, комиссия и т.д.
    headers = [
        'Номер операции',
        'Дата операции', 
        'Время',
        'Сумма операции (т)',
        'Адрес точки продаж',
        'Общая комиссия банка',
        'Комиссия за операции (т)',
        'Комиссия за операции по карте (т)',
        'Комиссия Kaspi Pay (т)',
        'Комиссия Kaspi Travel (т)',
        'Комиссия за обеспечение платежа (т)'
    ]

    # Если у нас больше колонок чем заголовков, добавляем дополнительные
    while len(headers) < len(df.columns):
        headers.append(f'Дополнительное поле {len(headers) + 1}')

    # Присваиваем заголовки
    df.columns = headers[:len(df.columns)]

    # Преобразуем каждую строку в словарь транзакции
    for index, row in df.iterrows():
        transaction = {}
        
        # Заполняем поля транзакции
        for col_name, value in row.items():
            if pd.notna(value) and str(value).strip():
                transaction[col_name] = str(value).strip()
        
        # Добавляем путь к файлу для отслеживания источника
        transaction['file_path'] = report_path
        
        transactions.append(transaction)

    print(f"Извлечено транзакций из PDF: {len(transactions)}")
    
    return transactions

def parse_excel_report(report_path: str) -> dict:
    """
    Парсит Excel отчет и возвращает структурированные данные.
    """
    from utils.terminal_report_parsing import parse_terminal_report
    return parse_terminal_report(report_path)

def get_transactions_from_db(transactions: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Синхронизирует транзакции с базой данных.

    1) Собираем список транзакций из отчета
    2) Ищем транзакцию в базе данных по условиям:
        - Дата транзакции из отчета. Мы ставим фильтр на от 00:00 текущего дня до 04:00 следующего дня.
        - Сумма транзакции с максимальной погрешностью в 1%. 
        - Организация из отчета сопоставляется с организацией в базе данных.
    3) Если найдена одна транзакция, которая совпадает по всем условиям, то записываем ее.
    4) Если найдено несколько транзакций, то выбираем лучшую по сумме и времени.
    5) Если не найдено транзакций, то записываем в список несовпавших транзакций.
    6) Возвращаем список с совпавшими и несовпавшими транзакциями.
    """

    matched_transactions = []
    unmatched_transactions = []
    print(f"Starting to get transactions from database...")
    check_count = 0
    total_transactions = len(transactions)
    
    for transaction in transactions:
        transactions_in_db = find_transaction_in_db(transaction)
        if transactions_in_db:
            if len(transactions_in_db) == 1:
                matched_transactions.append({
                    "order_id": transactions_in_db[0]['order_id'],
                    "transaction": transaction,
                    "transaction_in_db": transactions_in_db[0]
                })
            else:
                for transaction_in_db in transactions_in_db:
                    unmatched_transactions.append({
                        "order_id": transaction_in_db['order_id'],
                        "transaction": transaction,
                        "transaction_in_db": transaction_in_db
                    })
        else:
            unmatched_transactions.append({
                "transaction": transaction,
                "transaction_in_db": None
            })
        check_count += 1
        if check_count % 100 == 0:  # Выводим прогресс каждые 100 транзакций
            print(f"Checked {check_count} of {total_transactions} transactions")
    
    print(f"Database matching completed: {check_count} transactions processed")
    return matched_transactions, unmatched_transactions

def update_transaction_in_db(order_id: str, commission: float) -> bool:
    """
    Обновляет заказ в базе данных.
    """
    from database.database import SessionLocal
    from models.d_order import DOrder
    session = SessionLocal()
    d_order = session.query(DOrder).filter(DOrder.iiko_id == order_id).first()
    if not d_order:
        session.close()
        return False
    d_order.bank_commission = commission
    session.commit()
    session.close()
    return True

def sync_transactions_with_db(transactions: list[dict]) -> bool:
    """
    Синхронизирует транзакции с базой данных.
    """
    check_count = 0
    total_transactions = len(transactions)
    for transaction in transactions:
        check_count += 1
        if check_count % 100 == 0:  # Выводим прогресс каждые 100 транзакций
            print(f"Synced {check_count} of {total_transactions} transactions")
        update_transaction_in_db(transaction['order_id'], transaction['transaction'].get('commission', 0))
    print(f"Sync completed: {check_count} transactions processed")
    return True


def find_transaction_in_db(transaction: dict) -> list:
    """
    Ищем транзакцию в базе данных по условиям:
    - Дата транзакции из отчета. Мы ставим фильтр на от 00:00 текущего дня до 04:00 следующего дня.
    - Сумма транзакции с максимальной погрешностью в 1%. 
    - Организация из отчета сопоставляется с организацией в базе данных.

    1) Ищем в базе данных в таблице sales по дате и организации.
    2) Группируем список транзакций по payment_transaction_id. Это id транзакции внутри бд.
    3) Сравниваем сумму транзакции с суммой чека.
    4) Если сумма транзакции совпадает с суммой чека, то это нужная нам транзакция.
    5) Возвращаем транзакцию.
    """
    from database.database import SessionLocal
    from models import Sales
    from sqlalchemy import and_
    from sqlalchemy.orm import Session
    from sqlalchemy.sql import func
    from sqlalchemy.sql.functions import coalesce
    from datetime import timedelta

    session = SessionLocal()
    query = session.query(Sales).filter(
        Sales.precheque_time.between(
            transaction['date'].replace(hour=0, minute=0, second=0, microsecond=0), 
            transaction['date'].replace(hour=4, minute=0, second=0, microsecond=0) + timedelta(days=1)
        )
    )
    
    if transaction.get('terminal_address'):
        dept_code = get_department_code_by_terminal(transaction['terminal_address'])
        if dept_code:
            query = query.filter(Sales.department_code == dept_code)

    sales_records = query.all()

    payment_transaction_ids = {}

    for sale in sales_records:
        if sale.payment_transaction_id not in payment_transaction_ids:
            payment_transaction_ids[sale.payment_transaction_id] = {
                "sum": sale.dish_discount_sum_int,
                "time": sale.precheque_time,
                "order_id": sale.order_id
            }
        else:
            payment_transaction_ids[sale.payment_transaction_id]["sum"] += sale.dish_discount_sum_int

    matched_transaction = []
    for payment_transaction_id, transaction_data in payment_transaction_ids.items():
        if transaction_data["sum"] == transaction['amount']:
            matched_transaction.append(transaction_data)

    session.close()
    return matched_transaction

def get_department_code_by_terminal(terminal_address: str) -> str:
    """
    Получает department_code по адресу точки продаж.
    """
    terminal_organization_mapping = {
        # Фабрика 
        # Экспо
        "Astana, Kabanbay batyr prospekt, 58B": "8",
        "Gruzin Kuzin Ekspo": "8",
        "ASTANA G KAZAHSTAN, NUR-SULTAN": "8",
        # Магазин Цех
        # 72 Блок
        # Бокейхана
        "Nur-Sultan, ulica Alihana Bokeyhanova, 8": "6",
        "Gruzin Kuzin Bokeyhana": "6",
        "ASTANA G BOKEJHANA UL, DOM 8": "6",
        # Нурсая
        "Astana, Kunaeva, 14": "12",
        "Gruzin Kuzin Kunaeva": "12",
        "ASTANA G KONAEVA UL, DOM 14": "12",
        # Мангилик
        "Astana, Mangilik el, 50": "1",
        "Gruzin Kuzin Mangilik": "1",
        "г. Астана, Пр. Мангилик Ел, 50": "1",
        # Премьера
        # Шарль
        "Astana, SHarl de Goll, 1a": "10",
        "Gruzin Kuzin SHarl de Goll": "10",
        "ASTANA G SHARL DE GOLLYA UL, DOM": "10",
        "г. Астана, Ул. Шарль Де Голль, 3": "10",
        # Мухамедханова
        "Astana, Kayym Muhamedhanova, 5": "18",
        "Gruzin Kuzin Mahamedhanova": "18",
        "ASTANA G NURA RN, MUHAMEDHANOVA": "18",
        # Магазин ET-KZ
        # Хайвил 3
        "Astana, Prospekt Rakymzhan Koshkarbaev, 8": "9",
        "Gruzin Kuzin Hayvil": "9",
        "ASTANA G KOSHKARBAEVA UL, DOM 8": "9",
        # Площадь
        "Astana, Kabanbay Batyr prospekt, 34": "2",
        "Gruzin Kuzin Plochshad": "2",
        "г. Астана, Пр. Кабанбай Батыра, 34": "2",
    }

    return terminal_organization_mapping.get(terminal_address, '')
    

def analyze_unmatched_transactions(transactions: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Анализирует несовпавшие транзакции.
    
    1) Собираем список несовпавших транзакций.
    2) Проверяем уже по d_order.discount сумму.
    3) Если находим совпадение по точке, дате и сумме, то записываем в базу данных.
    4) Если не находим совпадение, то записываем в список несовпавших транзакций.
    5) Возвращаем список с совпавшими и несовпавшими транзакциями.
    """
    from sqlalchemy.orm import Session
    from datetime import timedelta
    from models.d_order import DOrder
    from models.organization import Organization
    from database.database import SessionLocal

    matched_transactions_after_analysis = []
    unmatched_transactions_after_analysis = []
    check_count = 0
    total_transactions = len(transactions)
    
    # Используем одну сессию для всех запросов
    session = SessionLocal()
    
    try:
        for transaction in transactions:
            amount = transaction.get("transaction", {}).get("amount", 0)
            if amount == 0:
                unmatched_transactions_after_analysis.append({
                    "transaction": transaction,
                    "d_order": None
                })
                continue
            
            query = session.query(DOrder).filter(DOrder.discount == amount)
            
            if transaction.get('terminal_address'):
                dept_code = get_department_code_by_terminal(transaction['terminal_address'])
                if dept_code:
                    organization = session.query(Organization).filter(Organization.code == dept_code).first()
                    if organization:
                        query = query.filter(DOrder.organization_id == organization.id)
            
            if transaction.get('date'):
                query = query.filter(DOrder.time_order.between(
                    transaction['date'].replace(hour=0, minute=0, second=0, microsecond=0), 
                    transaction['date'].replace(hour=4, minute=0, second=0, microsecond=0) + timedelta(days=1)
                ))
            
            d_order = query.first()
            if d_order:
                matched_transactions_after_analysis.append({
                    "order_id": d_order.iiko_id,
                    "transaction": transaction,
                    "d_order": d_order
                })
            else:
                unmatched_transactions_after_analysis.append({
                    "transaction": transaction,
                    "d_order": None
                })
            
            check_count += 1
            if check_count % 100 == 0:  # Выводим прогресс каждые 100 транзакций
                print(f"Checked {check_count} of {total_transactions} transactions")
    
    finally:
        session.close()
    
    print(f"Analysis completed: {check_count} transactions processed")
    return matched_transactions_after_analysis, unmatched_transactions_after_analysis




if __name__ == "__main__":
    reports_path = "temp_files/terminals_report"
    pdf_reports_path = "temp_files/terminals_report_pdf"

    reports = get_reports(reports_path)
    pdf_reports = get_reports(pdf_reports_path)

    reports.extend(pdf_reports)
    transactions = []
    for report in reports:
        transactions.extend(parse_report(report))

    matched_transactions, unmatched_transactions = get_transactions_from_db(transactions)

    # sync_transactions_with_db(matched_transactions)

    matched_transactions_after_analysis, unmatched_transactions_after_analysis = analyze_unmatched_transactions(unmatched_transactions)

    data_to_write = {
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "summary": {
            "total_matched": len(matched_transactions),
            "total_unmatched": len(unmatched_transactions),
            "total_transactions": len(matched_transactions) + len(unmatched_transactions),
            "match_percentage": (len(matched_transactions) / (len(matched_transactions) + len(unmatched_transactions)) * 100) if (len(matched_transactions) + len(unmatched_transactions)) > 0 else 0
        },
        "metadata": {
            "source_file": reports_path,
            "source_type": "terminal",
            "processing_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "total_transactions": len(matched_transactions) + len(unmatched_transactions),
            "matched": len(matched_transactions),
            "unmatched": len(unmatched_transactions),
            "match_percentage": (len(matched_transactions) / (len(matched_transactions) + len(unmatched_transactions)) * 100) if (len(matched_transactions) + len(unmatched_transactions)) > 0 else 0
        },
        "matched_transactions": matched_transactions,
        "unmatched_transactions": unmatched_transactions,
        "matched_transactions_after_analysis": matched_transactions_after_analysis,
        "unmatched_transactions_after_analysis": unmatched_transactions_after_analysis
    }

    with open('temp_files/report_parsing_result.json', 'w', encoding='utf-8') as f:
        json.dump(data_to_write, f, ensure_ascii=False, indent=2)

    print(f"Report parsing result saved to temp_files/report_parsing_result.json")


    