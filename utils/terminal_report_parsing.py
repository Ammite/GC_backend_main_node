# -*- coding: utf-8 -*-
"""
Парсер отчетов от терминала оплаты (Kaspi)

Этот модуль предоставляет функции для чтения и парсинга Excel файлов 
с выгрузками от терминала оплаты Kaspi.

Основные функции:
-----------------
- inspect_excel_file(file_path, max_rows) - детальный просмотр структуры файла для анализа
- parse_terminal_report(file_path) - полный парсинг отчета с метаданными и транзакциями
- get_transactions_by_date(file_path, date) - получение транзакций за определенную дату
- get_transactions_by_type(file_path, type) - получение транзакций по типу операции
- get_transactions_summary(file_path) - детальная сводная информация
- get_total_amount(file_path) - общая сумма транзакций
- get_total_to_credit(file_path) - сумма к зачислению
- get_total_commission(file_path) - общая комиссия

Пример использования:
--------------------
    from utils.terminal_report_parsing import parse_terminal_report
    
    data = parse_terminal_report("report.xlsx")
    print(f"Всего транзакций: {data['total_transactions']}")
    print(f"Общая сумма: {data['total_amount']} тг")
    print(f"Комиссия: {data['total_commission']} тг")

Требования:
-----------
- pandas >= 2.2.3
- openpyxl >= 3.1.5
"""

import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime
import os
import sys

# Настройка кодировки для Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def inspect_excel_file(file_path: str, max_rows: int = 10) -> None:
    """
    Подробно отображает структуру и содержимое Excel файла для анализа.
    
    Args:
        file_path: Путь к Excel файлу
        max_rows: Максимальное количество строк для отображения (по умолчанию 10)
    """
    if not os.path.exists(file_path):
        print(f"❌ Файл не найден: {file_path}")
        return
    
    print("=" * 80)
    print("📋 ДЕТАЛЬНЫЙ ПРОСМОТР СТРУКТУРЫ ФАЙЛА")
    print("=" * 80)
    print(f"\n📁 Файл: {file_path}")
    
    try:
        # Читаем файл полностью без заголовков
        df_raw = pd.read_excel(file_path, engine='openpyxl', header=None)
        
        print(f"\n📊 Размер файла: {len(df_raw)} строк × {len(df_raw.columns)} колонок")
        
        # Показываем первые N строк "как есть"
        print(f"\n" + "=" * 80)
        print(f"ПЕРВЫЕ {min(max_rows, len(df_raw))} СТРОК (БЕЗ ОБРАБОТКИ)")
        print("=" * 80)
        
        for idx, row in df_raw.head(max_rows).iterrows():
            print(f"\n📌 Строка {idx + 1}:")
            non_empty_cells = []
            for col_idx, value in enumerate(row):
                if pd.notna(value) and str(value).strip():
                    non_empty_cells.append(f"  Колонка {col_idx}: {value}")
            
            if non_empty_cells:
                for cell in non_empty_cells[:10]:  # Показываем первые 10 непустых ячеек
                    print(cell)
            else:
                print("  (пустая строка)")
        
        # Находим строку с заголовками
        print(f"\n" + "=" * 80)
        print("🔍 ПОИСК СТРОКИ С ЗАГОЛОВКАМИ")
        print("=" * 80)
        
        header_row_idx = None
        for idx, row in df_raw.iterrows():
            if row.iloc[0] == '#':
                header_row_idx = idx
                print(f"\n✅ Найдена строка с заголовками: строка {idx + 1}")
                print(f"\nЗаголовки:")
                for col_idx, value in enumerate(row):
                    if pd.notna(value) and str(value).strip():
                        print(f"  {col_idx + 1}. {value}")
                break
        
        if header_row_idx is None:
            print("\n⚠️ Строка с заголовками не найдена (ищем по символу '#')")
            return
        
        # Читаем с правильными заголовками
        df = pd.read_excel(file_path, engine='openpyxl', header=header_row_idx)
        df = df.dropna(how='all')
        df = df[df.iloc[:, 0].apply(lambda x: str(x).isdigit() if pd.notna(x) else False)]
        
        print(f"\n" + "=" * 80)
        print("📋 СПИСОК ВСЕХ КОЛОНОК С ПРИМЕРАМИ ДАННЫХ")
        print("=" * 80)
        print(f"\nВсего колонок: {len(df.columns)}")
        
        for i, col in enumerate(df.columns, 1):
            print(f"\n{i}. 📌 {col}")
            print(f"   Тип данных: {df[col].dtype}")
            
            # Показываем статистику для числовых колонок
            if pd.api.types.is_numeric_dtype(df[col]):
                non_null = df[col].dropna()
                if len(non_null) > 0:
                    print(f"   Непустых значений: {len(non_null)}")
                    print(f"   Минимум: {non_null.min()}")
                    print(f"   Максимум: {non_null.max()}")
                    print(f"   Среднее: {non_null.mean():.2f}")
            else:
                # Для текстовых показываем уникальные значения
                unique_vals = df[col].dropna().unique()
                print(f"   Непустых значений: {df[col].notna().sum()}")
                if len(unique_vals) > 0:
                    print(f"   Уникальных значений: {len(unique_vals)}")
                    if len(unique_vals) <= 5:
                        print(f"   Значения: {', '.join(map(str, unique_vals))}")
                    else:
                        print(f"   Примеры: {', '.join(map(str, unique_vals[:3]))}...")
            
            # Показываем первые 3 значения
            first_vals = df[col].head(3).tolist()
            print(f"   Первые значения: {first_vals}")
        
        # Показываем несколько полных записей
        print(f"\n" + "=" * 80)
        print("📝 ПРИМЕРЫ ПОЛНЫХ ЗАПИСЕЙ (ТРАНЗАКЦИЙ)")
        print("=" * 80)
        
        for idx in range(min(3, len(df))):
            print(f"\n{'=' * 40}")
            print(f"Транзакция #{idx + 1}")
            print('=' * 40)
            
            row = df.iloc[idx]
            important_cols = [
                '#', 'Адрес точки продаж', 'Дата операции', 'Время',
                'Тип операции', 'Тип оплаты', 'Номер карты',
                'Сумма операции (т)', 'Сумма к зачислению/ списанию (т)',
                'Комиссия за операции (т)', 'Комиссия Kaspi Pay (т)'
            ]
            
            for col in important_cols:
                if col in df.columns:
                    value = row[col]
                    if pd.notna(value):
                        print(f"{col}: {value}")
        
        print(f"\n" + "=" * 80)
        print("✅ ПРОСМОТР ЗАВЕРШЕН")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Ошибка при чтении файла: {e}")
        import traceback
        traceback.print_exc()


def extract_metadata(file_path: str) -> Dict[str, str]:
    """
    Извлекает метаданные из начала файла (период, ИИН/БИН, наименование).
    
    Args:
        file_path: Путь к Excel файлу
        
    Returns:
        Словарь с метаданными
    """
    df_meta = pd.read_excel(file_path, engine='openpyxl', nrows=3)
    metadata = {}
    
    for idx, row in df_meta.iterrows():
        if pd.notna(row.iloc[1]):
            key = str(row.iloc[1]).replace(':', '').strip()
            value = str(row.iloc[2]) if pd.notna(row.iloc[2]) else None
            metadata[key] = value
    
    return metadata


def read_terminal_report(file_path: str) -> pd.DataFrame:
    """
    Читает Excel файл с выгрузкой от терминала оплаты.
    
    Args:
        file_path: Путь к Excel файлу
        
    Returns:
        DataFrame с данными отчета (только транзакции)
        
    Raises:
        FileNotFoundError: Если файл не найден
        Exception: Если не удалось прочитать файл
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    
    try:
        # Сначала читаем весь файл без заголовков, чтобы найти строку с заголовками
        df_raw = pd.read_excel(file_path, engine='openpyxl', header=None)
        
        # Ищем строку с заголовками (содержит "#" в первой колонке)
        header_row_idx = None
        for idx, row in df_raw.iterrows():
            if row.iloc[0] == '#':
                header_row_idx = idx
                break
        
        if header_row_idx is None:
            raise Exception("Не удалось найти строку с заголовками в файле")
        
        # Читаем файл заново, используя найденную строку как заголовки
        df = pd.read_excel(file_path, engine='openpyxl', header=header_row_idx)
        
        # Удаляем полностью пустые строки
        df = df.dropna(how='all')
        
        # Удаляем строки, где нет номера транзакции (первая колонка)
        # Проверяем, что это число или можно преобразовать в число
        df = df[df.iloc[:, 0].apply(lambda x: str(x).isdigit() if pd.notna(x) else False)]
        
        # Сбрасываем индекс
        df = df.reset_index(drop=True)
        
        return df
    except Exception as e:
        raise Exception(f"Ошибка при чтении файла {file_path}: {str(e)}")


def parse_terminal_report(file_path: str) -> Dict[str, Any]:
    """
    Парсит Excel файл с выгрузкой от терминала оплаты и возвращает структурированные данные.
    
    Args:
        file_path: Путь к Excel файлу
        
    Returns:
        Словарь с распарсенными данными:
        {
            'metadata': dict,            # Метаданные (период, ИИН/БИН, наименование)
            'total_transactions': int,   # Общее количество транзакций
            'total_amount': float,       # Общая сумма операций
            'total_to_credit': float,    # Общая сумма к зачислению
            'total_commission': float,   # Общая комиссия
            'transactions': list,        # Список транзакций
            'summary': dict              # Сводная информация
        }
    """
    # Извлекаем метаданные
    metadata = extract_metadata(file_path)
    
    # Читаем транзакции
    df = read_terminal_report(file_path)
    
    # Получаем список транзакций
    transactions = []
    for idx, row in df.iterrows():
        transaction = {}
        for col in df.columns:
            value = row[col]
            # Преобразуем NaN в None
            if pd.isna(value):
                transaction[col] = None
            # Преобразуем Timestamp в строку
            elif isinstance(value, pd.Timestamp):
                transaction[col] = value.strftime('%Y-%m-%d %H:%M:%S')
            else:
                transaction[col] = value
        transactions.append(transaction)
    
    # Подсчитываем сводную информацию
    total_transactions = len(transactions)
    
    # Извлекаем финансовые итоги
    # Колонка "Сумма операции (т)" - сумма операций
    amount_col = 'Сумма операции (т)'
    total_amount = 0.0
    if amount_col in df.columns:
        # Преобразуем в числовой формат, заменяя None на 0
        df[amount_col] = pd.to_numeric(df[amount_col], errors='coerce').fillna(0)
        total_amount = float(df[amount_col].sum())
    
    # Колонка "Сумма к зачислению/ списанию (т)" - сумма к зачислению
    credit_col = 'Сумма к зачислению/ списанию (т)'
    total_to_credit = 0.0
    if credit_col in df.columns:
        df[credit_col] = pd.to_numeric(df[credit_col], errors='coerce').fillna(0)
        total_to_credit = float(df[credit_col].sum())
    
    # Различные виды комиссий
    commission_cols = [
        'Комиссия за операции (т)',
        'Комиссия за операции по карте (т)',
        'Комиссия за обеспечение платежа (т)',
        'Комиссия Kaspi Pay (т)',
        'Комиссия Kaspi Travel (т)'
    ]
    
    total_commission = 0.0
    commission_details = {}
    for comm_col in commission_cols:
        if comm_col in df.columns:
            df[comm_col] = pd.to_numeric(df[comm_col], errors='coerce').fillna(0)
            commission_sum = float(df[comm_col].sum())
            commission_details[comm_col] = commission_sum
            total_commission += abs(commission_sum)
    
    return {
        'metadata': metadata,
        'total_transactions': total_transactions,
        'total_amount': total_amount,
        'total_to_credit': total_to_credit,
        'total_commission': total_commission,
        'commission_details': commission_details,
        'transactions': transactions,
        'summary': {
            'columns': list(df.columns),
            'first_transaction': transactions[0] if transactions else None,
            'last_transaction': transactions[-1] if transactions else None,
        }
    }


def get_transactions_by_date(file_path: str, target_date: str) -> List[Dict[str, Any]]:
    """
    Получает транзакции за определенную дату.
    
    Args:
        file_path: Путь к Excel файлу
        target_date: Дата в формате 'DD.MM.YYYY' или 'YYYY-MM-DD'
        
    Returns:
        Список транзакций за указанную дату
    """
    data = parse_terminal_report(file_path)
    transactions = data['transactions']
    
    # Нормализуем формат даты
    if '-' in target_date:
        # Преобразуем YYYY-MM-DD в DD.MM.YYYY
        parts = target_date.split('-')
        target_date = f"{parts[2]}.{parts[1]}.{parts[0]}"
    
    # Фильтруем транзакции по дате
    filtered_transactions = []
    date_field = 'Дата операции'
    
    for transaction in transactions:
        if date_field in transaction and transaction[date_field]:
            trans_date = str(transaction[date_field])
            if trans_date == target_date or trans_date.startswith(target_date):
                filtered_transactions.append(transaction)
    
    return filtered_transactions


def get_total_amount(file_path: str) -> float:
    """
    Возвращает общую сумму всех транзакций в отчете.
    
    Args:
        file_path: Путь к Excel файлу
        
    Returns:
        Общая сумма транзакций
    """
    data = parse_terminal_report(file_path)
    return data['total_amount']


def get_total_to_credit(file_path: str) -> float:
    """
    Возвращает общую сумму к зачислению.
    
    Args:
        file_path: Путь к Excel файлу
        
    Returns:
        Общая сумма к зачислению
    """
    data = parse_terminal_report(file_path)
    return data['total_to_credit']


def get_total_commission(file_path: str) -> float:
    """
    Возвращает общую сумму комиссий.
    
    Args:
        file_path: Путь к Excel файлу
        
    Returns:
        Общая сумма комиссий
    """
    data = parse_terminal_report(file_path)
    return data['total_commission']


def get_transactions_by_type(file_path: str, operation_type: str) -> List[Dict[str, Any]]:
    """
    Получает транзакции по типу операции.
    
    Args:
        file_path: Путь к Excel файлу
        operation_type: Тип операции (например, 'Покупка', 'Возврат')
        
    Returns:
        Список транзакций указанного типа
    """
    data = parse_terminal_report(file_path)
    transactions = data['transactions']
    
    type_field = 'Тип операции'
    filtered_transactions = [
        t for t in transactions 
        if type_field in t and t[type_field] == operation_type
    ]
    
    return filtered_transactions


def get_transactions_summary(file_path: str) -> Dict[str, Any]:
    """
    Возвращает детальную сводную информацию о транзакциях.
    
    Args:
        file_path: Путь к Excel файлу
        
    Returns:
        Словарь со сводной информацией
    """
    data = parse_terminal_report(file_path)
    df = read_terminal_report(file_path)
    
    # Статистика по типам операций
    operation_stats = {}
    if 'Тип операции' in df.columns:
        operation_counts = df['Тип операции'].value_counts().to_dict()
        operation_stats = {str(k): int(v) for k, v in operation_counts.items()}
    
    # Статистика по типам оплаты
    payment_stats = {}
    if 'Тип оплаты' in df.columns:
        payment_counts = df['Тип оплаты'].value_counts().to_dict()
        payment_stats = {str(k): int(v) for k, v in payment_counts.items()}
    
    summary = {
        'metadata': data['metadata'],
        'total_transactions': data['total_transactions'],
        'total_amount': data['total_amount'],
        'total_to_credit': data['total_to_credit'],
        'total_commission': data['total_commission'],
        'commission_details': data['commission_details'],
        'operation_types': operation_stats,
        'payment_types': payment_stats,
        'date_range': {
            'first': data['summary']['first_transaction'].get('Дата операции') if data['summary']['first_transaction'] else None,
            'last': data['summary']['last_transaction'].get('Дата операции') if data['summary']['last_transaction'] else None,
        }
    }
    
    return summary


# Пример использования
if __name__ == "__main__":
    # Тестовый запуск
    test_file = r"C:\Documents\sidework\backend\GC_backend_main_node\temp_files\sales report from terminal.xlsx"
    
    # Проверяем аргументы командной строки
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'inspect':
        # Режим детального просмотра
        print("🔍 РЕЖИМ ДЕТАЛЬНОГО ПРОСМОТРА ФАЙЛА\n")
        inspect_excel_file(test_file, max_rows=15)
        sys.exit(0)
    
    try:
        print("=" * 60)
        print("ПАРСЕР ОТЧЕТОВ ОТ ТЕРМИНАЛА ОПЛАТЫ")
        print("=" * 60)
        
        # Полный парсинг отчета
        data = parse_terminal_report(test_file)
        
        # Метаданные
        print("\n📋 МЕТАДАННЫЕ:")
        for key, value in data['metadata'].items():
            print(f"  {key}: {value}")
        
        # Финансовая сводка
        print("\n💰 ФИНАНСОВАЯ СВОДКА:")
        print(f"  Всего транзакций: {data['total_transactions']}")
        print(f"  Общая сумма операций: {data['total_amount']:,.2f} тг")
        print(f"  Сумма к зачислению: {data['total_to_credit']:,.2f} тг")
        print(f"  Общая комиссия: {data['total_commission']:,.2f} тг")
        
        # Детали комиссий
        if data['commission_details']:
            print("\n  Детализация комиссий:")
            for comm_type, amount in data['commission_details'].items():
                if amount != 0:
                    print(f"    - {comm_type}: {amount:,.2f} тг")
        
        # Детальная сводка
        print("\n📊 ДЕТАЛЬНАЯ СТАТИСТИКА:")
        summary = get_transactions_summary(test_file)
        
        if summary['operation_types']:
            print("\n  Типы операций:")
            for op_type, count in summary['operation_types'].items():
                print(f"    - {op_type}: {count} шт.")
        
        if summary['payment_types']:
            print("\n  Типы оплаты:")
            for pay_type, count in summary['payment_types'].items():
                print(f"    - {pay_type}: {count} шт.")
        
        print(f"\n  Период операций:")
        print(f"    Первая транзакция: {summary['date_range']['first']}")
        print(f"    Последняя транзакция: {summary['date_range']['last']}")
        
        # Примеры транзакций
        print("\n📝 ПРИМЕРЫ ТРАНЗАКЦИЙ (первые 3):")
        for i, transaction in enumerate(data['transactions'][:3], 1):
            print(f"\n  Транзакция #{i}:")
            important_fields = [
                '#', 'Дата операции', 'Время', 'Тип операции', 
                'Тип оплаты', 'Сумма операции (т)', 
                'Сумма к зачислению/ списанию (т)', 'Комиссия Kaspi Pay (т)'
            ]
            for field in important_fields:
                if field in transaction and transaction[field] is not None:
                    print(f"    {field}: {transaction[field]}")
        
        # Примеры использования других функций
        print("\n" + "=" * 60)
        print("ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ ФУНКЦИЙ:")
        print("=" * 60)
        
        # Получение транзакций по дате
        if data['transactions']:
            first_date = data['transactions'][0].get('Дата операции')
            if first_date:
                transactions_by_date = get_transactions_by_date(test_file, str(first_date))
                print(f"\n🗓️  Транзакций за {first_date}: {len(transactions_by_date)}")
        
        # Получение транзакций по типу
        purchases = get_transactions_by_type(test_file, 'Покупка')
        print(f"\n🛒 Покупок: {len(purchases)}")
        
        # Получение итоговых сумм
        print(f"\n💵 Общая сумма (функция): {get_total_amount(test_file):,.2f} тг")
        print(f"💵 К зачислению (функция): {get_total_to_credit(test_file):,.2f} тг")
        print(f"💵 Комиссия (функция): {get_total_commission(test_file):,.2f} тг")
        
        print("\n" + "=" * 60)
        print("✅ ПАРСИНГ ЗАВЕРШЕН УСПЕШНО")
        print("=" * 60)
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


"""
=============================================================================
КРАТКОЕ РУКОВОДСТВО ПО ИСПОЛЬЗОВАНИЮ
=============================================================================

0. ДЕТАЛЬНЫЙ ПРОСМОТР ФАЙЛА (для анализа структуры):
   
   from utils.terminal_report_parsing import inspect_excel_file
   
   # Показывает полную структуру файла, все колонки и примеры данных
   inspect_excel_file("файл.xlsx", max_rows=10)
   
   # Или запустить из командной строки:
   # python utils/terminal_report_parsing.py inspect


1. ОСНОВНОЙ ПАРСИНГ:
   
   from utils.terminal_report_parsing import parse_terminal_report
   
   data = parse_terminal_report("путь/к/файлу.xlsx")
   
   Возвращает словарь с полями:
   - metadata: метаданные (период, ИИН/БИН, наименование)
   - total_transactions: общее количество транзакций
   - total_amount: общая сумма операций
   - total_to_credit: сумма к зачислению
   - total_commission: общая комиссия
   - commission_details: детализация комиссий
   - transactions: список всех транзакций
   - summary: сводная информация


2. ПОЛУЧЕНИЕ ТРАНЗАКЦИЙ ПО ДАТЕ:
   
   from utils.terminal_report_parsing import get_transactions_by_date
   
   # Формат даты: DD.MM.YYYY или YYYY-MM-DD
   transactions = get_transactions_by_date("файл.xlsx", "29.09.2025")


3. ПОЛУЧЕНИЕ ТРАНЗАКЦИЙ ПО ТИПУ:
   
   from utils.terminal_report_parsing import get_transactions_by_type
   
   purchases = get_transactions_by_type("файл.xlsx", "Покупка")
   refunds = get_transactions_by_type("файл.xlsx", "Возврат")


4. ПОЛУЧЕНИЕ СВОДНОЙ ИНФОРМАЦИИ:
   
   from utils.terminal_report_parsing import get_transactions_summary
   
   summary = get_transactions_summary("файл.xlsx")
   # Возвращает: метаданные, итоги, статистику по типам операций и оплаты


5. ПОЛУЧЕНИЕ ФИНАНСОВЫХ ИТОГОВ:
   
   from utils.terminal_report_parsing import (
       get_total_amount, 
       get_total_to_credit, 
       get_total_commission
   )
   
   total = get_total_amount("файл.xlsx")
   credit = get_total_to_credit("файл.xlsx")
   commission = get_total_commission("файл.xlsx")


6. ПРЯМОЕ ЧТЕНИЕ DATAFRAME:
   
   from utils.terminal_report_parsing import read_terminal_report
   
   df = read_terminal_report("файл.xlsx")
   # Возвращает pandas DataFrame с транзакциями


7. ИЗВЛЕЧЕНИЕ МЕТАДАННЫХ:
   
   from utils.terminal_report_parsing import extract_metadata
   
   metadata = extract_metadata("файл.xlsx")
   # Возвращает: {'Период': '29.09.2025', 'ИИН/БИН': '...', ...}

=============================================================================
"""
