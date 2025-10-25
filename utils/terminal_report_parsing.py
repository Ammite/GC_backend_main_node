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

Функции для сопоставления с БД:
--------------------------------
- analyze_matching_fields(file_path, db) - анализ полей для сопоставления данных
- compare_terminal_report_with_db(file_path, db) - сравнение транзакций с БД и статистика
- match_transaction_with_sales(transaction, db) - поиск транзакции в таблице Sales
- parse_transaction_datetime(transaction) - парсинг даты и времени транзакции

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
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import os
import sys
import json
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

# Настройка кодировки для Windows
if sys.platform == 'win32':
    import codecs
    # Проверяем, не был ли stdout уже переопределен
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if hasattr(sys.stderr, 'buffer'):
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
    try:
        df_meta = pd.read_excel(file_path, engine='openpyxl', nrows=10, header=None)
        metadata = {}
        
        # Пробуем разные форматы метаданных
        for idx, row in df_meta.iterrows():
            # Формат 1: ключ в колонке 1, значение в колонке 2 (Kaspi)
            if len(row) > 2 and pd.notna(row.iloc[1]):
                key_str = str(row.iloc[1])
                if ':' in key_str or any(word in key_str for word in ['Период', 'ИИН', 'БИН', 'Наименование']):
                    key = key_str.replace(':', '').strip()
                    value = str(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else None
                    if value and value != 'nan':
                        metadata[key] = value
            
            # Формат 2: ключ и значение в колонке 0 (банковская выписка)
            if pd.notna(row.iloc[0]):
                cell_str = str(row.iloc[0])
                # Извлекаем БИН/ИИН
                if 'БИН/ИИН' in cell_str or 'ИИН/БИН' in cell_str:
                    parts = cell_str.split(':')
                    if len(parts) > 1:
                        metadata['ИИН/БИН'] = parts[1].strip()
                # Извлекаем период из заголовка
                elif 'период' in cell_str.lower() and 'по' in cell_str:
                    # Ищем даты в формате DD.MM.YYYY
                    import re
                    dates = re.findall(r'\d{2}\.\d{2}\.\d{4}', cell_str)
                    if len(dates) >= 2:
                        metadata['Период'] = f"{dates[0]} - {dates[1]}"
        
        return metadata
    except Exception as e:
        print(f"⚠️ Предупреждение: не удалось извлечь метаданные из {file_path}: {e}")
        return {}


def detect_report_type(file_path: str) -> str:
    """
    Определяет тип отчета терминала по структуре файла.
    
    Args:
        file_path: Путь к Excel файлу
        
    Returns:
        Тип отчета (TerminalReportType)
    """
    try:
        df_raw = pd.read_excel(file_path, engine='openpyxl', header=None, nrows=10)
        
        # Проверяем первую строку - если там "Детальная информация по операциям", то это Kaspi
        if df_raw.iloc[0, 1] if pd.notna(df_raw.iloc[0, 1]) else None:
            if 'Детальная информация по операциям' in str(df_raw.iloc[0, 1]):
                return TerminalReportType.KASPI_DETAILED
        
        # Проверяем первую ячейку - если там "Выписка по POS", то это банковская выписка
        if df_raw.iloc[0, 0] if pd.notna(df_raw.iloc[0, 0]) else None:
            if 'Выписка по POS' in str(df_raw.iloc[0, 0]):
                return TerminalReportType.BANK_STATEMENT
        
        # Ищем строку с символом '#' в первой колонке - признак Kaspi отчета
        for idx, row in df_raw.iterrows():
            if row.iloc[0] == '#':
                return TerminalReportType.KASPI_DETAILED
        
        return TerminalReportType.UNKNOWN
        
    except Exception as e:
        print(f"⚠️ Ошибка при определении типа отчета: {e}")
        return TerminalReportType.UNKNOWN


def read_kaspi_detailed_report(file_path: str) -> pd.DataFrame:
    """
    Читает отчет Kaspi с детальной информацией по операциям.
    
    Args:
        file_path: Путь к Excel файлу
        
    Returns:
        DataFrame с данными транзакций
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    
    try:
        # Читаем весь файл без заголовков, чтобы найти строку с заголовками
        df_raw = pd.read_excel(file_path, engine='openpyxl', header=None)
        
        # Ищем строку с заголовками (содержит "#" в первой колонке)
        header_row_idx = None
        for idx, row in df_raw.iterrows():
            if row.iloc[0] == '#':
                header_row_idx = idx
                break
        
        if header_row_idx is None:
            raise Exception("Не удалось найти строку с заголовками (с символом '#')")
        
        # Читаем файл заново, используя найденную строку как заголовки
        df = pd.read_excel(file_path, engine='openpyxl', header=header_row_idx)
        
        # Удаляем полностью пустые строки
        df = df.dropna(how='all')
        
        # Удаляем строки, где нет номера транзакции (первая колонка должна быть числом)
        df = df[df.iloc[:, 0].apply(lambda x: str(x).isdigit() if pd.notna(x) else False)]
        
        # Сбрасываем индекс
        df = df.reset_index(drop=True)
        
        return df
    except Exception as e:
        raise Exception(f"Ошибка при чтении Kaspi отчета {file_path}: {str(e)}")


def read_bank_statement_report(file_path: str) -> pd.DataFrame:
    """
    Читает банковскую выписку по POS-терминалам (Народный Банк и др.).
    
    Args:
        file_path: Путь к Excel файлу
        
    Returns:
        DataFrame с данными транзакций
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    
    try:
        # Читаем весь файл без заголовков
        df_raw = pd.read_excel(file_path, engine='openpyxl', header=None)
        
        # Ищем строку с заголовками (ищем строку где есть "Дата" и "транзакции")
        header_row_idx = None
        for idx, row in df_raw.iterrows():
            # Проверяем несколько ячеек на наличие ключевых слов
            row_str = ' '.join([str(cell) for cell in row if pd.notna(cell)])
            if 'Дата' in row_str and ('транзакции' in row_str or 'зачисления' in row_str):
                header_row_idx = idx
                break
        
        if header_row_idx is None:
            raise Exception("Не удалось найти строку с заголовками в банковской выписке")
        
        # Читаем файл заново, используя найденную строку как заголовки
        df = pd.read_excel(file_path, engine='openpyxl', header=header_row_idx)
        
        # Удаляем полностью пустые строки
        df = df.dropna(how='all')
        
        # Удаляем строки где нет даты (первая колонка должна быть датой или содержать дату)
        # Оставляем только строки с датой в первой колонке
        df = df[df.iloc[:, 0].apply(lambda x: pd.notna(x) and (isinstance(x, (pd.Timestamp, datetime)) or ('.' in str(x) and len(str(x).split('.')) == 3)))]
        
        # Сбрасываем индекс
        df = df.reset_index(drop=True)
        
        return df
    except Exception as e:
        raise Exception(f"Ошибка при чтении банковской выписки {file_path}: {str(e)}")


def read_terminal_report(file_path: str) -> pd.DataFrame:
    """
    Читает Excel файл с выгрузкой от терминала оплаты.
    Автоматически определяет тип отчета и использует соответствующий парсер.
    
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
    
    # Определяем тип отчета
    report_type = detect_report_type(file_path)
    
    if report_type == TerminalReportType.KASPI_DETAILED:
        return read_kaspi_detailed_report(file_path)
    elif report_type == TerminalReportType.BANK_STATEMENT:
        return read_bank_statement_report(file_path)
    else:
        raise Exception(f"Неизвестный тип отчета в файле {file_path}")


def normalize_transaction_fields(transaction: Dict[str, Any], report_type: str) -> Dict[str, Any]:
    """
    Нормализует поля транзакции из разных типов отчетов в единый формат.
    
    Args:
        transaction: Исходная транзакция
        report_type: Тип отчета
        
    Returns:
        Нормализованная транзакция с унифицированными полями
    """
    normalized = {}
    
    if report_type == TerminalReportType.KASPI_DETAILED:
        # Kaspi отчет - большинство полей уже в нужном формате
        normalized = transaction.copy()
        
    elif report_type == TerminalReportType.BANK_STATEMENT:
        # Банковская выписка - нужно привести к формату Kaspi
        # Маппинг полей:
        # "Дата и время транзакции" -> "Дата операции" + "Время"
        # "Сумма транзакции" -> "Сумма операции (т)"
        # "Сумма к зачислению" -> "Сумма к зачислению/ списанию (т)"
        # Вычисляем комиссию как разницу
        
        # Обработка даты и времени
        date_time_value = transaction.get('Дата и время\nтранзакции', transaction.get('Дата и время транзакции', ''))
        
        if date_time_value:
            if isinstance(date_time_value, datetime):
                # Если уже datetime объект
                normalized['Дата операции'] = date_time_value.strftime('%d.%m.%Y')
                normalized['Время'] = date_time_value.strftime('%H:%M:%S')
            elif isinstance(date_time_value, pd.Timestamp):
                # Если pandas Timestamp
                normalized['Дата операции'] = date_time_value.strftime('%d.%m.%Y')
                normalized['Время'] = date_time_value.strftime('%H:%M:%S')
            elif isinstance(date_time_value, str):
                # Если строка
                try:
                    dt = datetime.strptime(date_time_value, '%d.%m.%Y %H:%M:%S')
                    normalized['Дата операции'] = dt.strftime('%d.%m.%Y')
                    normalized['Время'] = dt.strftime('%H:%M:%S')
                except:
                    # Пробуем просто разделить строку
                    try:
                        parts = str(date_time_value).split()
                        if len(parts) >= 2:
                            normalized['Дата операции'] = parts[0]
                            normalized['Время'] = parts[1]
                    except:
                        pass
        
        # Адрес - пробуем разные варианты названий колонок
        normalized['Адрес точки продаж'] = (
            transaction.get('Адрес торговой точки', '') or
            transaction.get('Адрес\nторговой точки', '') or
            ''
        )
        
        normalized['ID терминала'] = transaction.get('№ терминала', '')
        normalized['Тип операции'] = transaction.get('Тип операции', 'Покупка')
        
        # Суммы - пробуем разные варианты названий колонок
        normalized['Сумма операции (т)'] = (
            transaction.get('Сумма транзакции', 0) or
            transaction.get('Сумма\nтранзакции', 0) or
            0
        )
        
        normalized['Сумма к зачислению/ списанию (т)'] = (
            transaction.get('Сумма к зачислению', 0) or
            transaction.get('Сумма к\nзачислению', 0) or
            transaction.get('Сумма\nк зачислению', 0) or
            0
        )
        
        # Вычисляем комиссию
        try:
            amount = float(normalized.get('Сумма операции (т)', 0) or 0)
            to_credit = float(normalized.get('Сумма к зачислению/ списанию (т)', 0) or 0)
            commission = amount - to_credit
            if commission != 0:
                normalized['Комиссия за операции (т)'] = -abs(commission)
        except:
            pass
        
        # Дополнительные поля
        normalized['Юр. Наименование'] = (
            transaction.get('Юр. Наименование', '') or
            transaction.get('Юр.\nНаименование', '') or
            ''
        )
        normalized['Торговое наименование'] = (
            transaction.get('Торговое наименование', '') or
            transaction.get('Торговое\nнаименование', '') or
            ''
        )
        normalized['Номер контракта'] = (
            transaction.get('Номер контракта', '') or
            transaction.get('№ контракта', '') or
            ''
        )
        normalized['Дата зачисления'] = (
            transaction.get('Дата зачисления', '') or
            transaction.get('Дата\nзачисления', '') or
            ''
        )
    
    return normalized


def parse_terminal_report(file_path: str) -> Dict[str, Any]:
    """
    Парсит Excel файл с выгрузкой от терминала оплаты и возвращает структурированные данные.
    Автоматически определяет тип отчета.
    
    Args:
        file_path: Путь к Excel файлу
        
    Returns:
        Словарь с распарсенными данными:
        {
            'file_path': str,            # Путь к файлу
            'report_type': str,          # Тип отчета
            'metadata': dict,            # Метаданные (период, ИИН/БИН, наименование)
            'total_transactions': int,   # Общее количество транзакций
            'total_amount': float,       # Общая сумма операций
            'total_to_credit': float,    # Общая сумма к зачислению
            'total_commission': float,   # Общая комиссия
            'transactions': list,        # Список транзакций
            'summary': dict              # Сводная информация
        }
    """
    # Определяем тип отчета
    report_type = detect_report_type(file_path)
    
    # Извлекаем метаданные
    metadata = extract_metadata(file_path)
    metadata['report_type'] = report_type
    
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
        
        # Нормализуем поля транзакции
        normalized_transaction = normalize_transaction_fields(transaction, report_type)
        transactions.append(normalized_transaction)
    
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
        'file_path': file_path,
        'report_type': report_type,
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


def parse_transaction_datetime(transaction: Dict[str, Any]) -> Optional[datetime]:
    """
    Парсит дату и время из транзакции терминала.
    
    Args:
        transaction: Словарь с данными транзакции
        
    Returns:
        datetime объект или None если не удалось распарсить
    """
    try:
        date_str = str(transaction.get('Дата операции', ''))
        time_str = str(transaction.get('Время', ''))
        
        if not date_str or not time_str:
            return None
        
        # Формат даты в отчете: DD.MM.YYYY или уже datetime
        if isinstance(transaction.get('Дата операции'), datetime):
            # Если уже datetime, используем его
            dt = transaction['Дата операции']
            # Добавляем время
            if time_str:
                time_parts = time_str.split(':')
                if len(time_parts) >= 2:
                    dt = dt.replace(hour=int(time_parts[0]), minute=int(time_parts[1]))
                    if len(time_parts) >= 3:
                        dt = dt.replace(second=int(time_parts[2]))
            return dt
        else:
            # Парсим строку
            datetime_str = f"{date_str} {time_str}"
            # Пробуем разные форматы
            formats = [
                '%d.%m.%Y %H:%M:%S',
                '%d.%m.%Y %H:%M',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %H:%M',
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(datetime_str, fmt)
                except ValueError:
                    continue
            
            return None
    except Exception as e:
        print(f"⚠️ Ошибка при парсинге даты/времени: {e}")
        return None


# Типы отчетов терминалов
class TerminalReportType:
    KASPI_DETAILED = "kaspi_detailed"  # Детальная информация по операциям (Kaspi)
    BANK_STATEMENT = "bank_statement"   # Выписка по POS-договору (Народный Банк и др.)
    UNKNOWN = "unknown"


# Таблица соответствий между точками терминала и organization_id в БД
TERMINAL_ORGANIZATION_MAPPING = {
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


def get_organization_id_by_terminal(terminal_address: str) -> Optional[str]:
    """
    Получает organization_id (department_code) по адресу точки продаж из отчета терминала.
    
    ЛОГИКА:
    - Если адрес найден в маппинге и org_id непустой → возвращает org_id
    - Если адрес найден в маппинге, но org_id пустая строка → возвращает None (искать по всем)
    - Если адрес не найден в маппинге → возвращает None (искать по всем)
    
    Args:
        terminal_address: Адрес точки продаж из отчета терминала
        
    Returns:
        organization_id (department_code) или None если нужно искать по всем организациям
    """
    # Нормализуем адрес (убираем лишние пробелы, приводим к нижнему регистру)
    if not terminal_address:
        return None
    
    normalized_address = str(terminal_address).strip().lower()
    
    # Ищем точное совпадение
    for terminal_addr, org_id in TERMINAL_ORGANIZATION_MAPPING.items():
        if terminal_addr.lower() == normalized_address:
            # Если org_id пустая строка или None, возвращаем None (искать по всем)
            return org_id if org_id and org_id.strip() else None
    
    # Ищем частичное совпадение
    for terminal_addr, org_id in TERMINAL_ORGANIZATION_MAPPING.items():
        if terminal_addr.lower() in normalized_address or normalized_address in terminal_addr.lower():
            # Если org_id пустая строка или None, возвращаем None (искать по всем)
            return org_id if org_id and org_id.strip() else None
    
    return None


def match_transaction_with_order(
    transaction: Dict[str, Any],
    db: Session,
    time_tolerance_minutes: int = 15,
    amount_tolerance_percent: float = 2.0,
    verbose_logging: bool = False,
    transaction_num: int = 0,
    used_payment_transactions: Optional[set] = None
) -> Optional[Dict[str, Any]]:
    """
    Ищет соответствующий чек (и заказ) в БД для транзакции терминала.
    
    СТРУКТУРА:
    - Заказ (Order) → Чеки (по payment_transaction_id) → Продажи (Sales)
    - Каждая транзакция терминала = один чек (один payment_transaction_id)
    - У заказа может быть несколько чеков (несколько payment_transaction_id)
    
    АЛГОРИТМ:
    1. Получаем organization_id по адресу точки терминала
    2. Ищем в таблице Sales по precheque_time за весь день транзакции
    3. Фильтруем по deleted_with_writeoff (только NOT_DELETED или NULL - реально оплаченные)
       Исключаем: DELETED_WITHOUT_WRITEOFF, DELETED_WITH_WRITEOFF и другие удаленные
    4. Фильтруем по organization_id
    5. **ГРУППИРУЕМ Sales по payment_transaction_id** (создаем временные "чеки" в памяти)
    6. Для каждого "чека":
       - Суммируем dish_discount_sum_int из всех Sales этого чека (сумма с учетом скидок)
       - Сравниваем с суммой транзакции терминала (±2%)
    7. Если нашли совпадение:
       - Определяем order_id из Sales
       - Проверяем заказ в d_order
       - Определяем количество чеков у заказа (для суммирования комиссий)
    
    Args:
        transaction: Словарь с данными транзакции из отчета терминала
        db: SQLAlchemy сессия базы данных
        time_tolerance_minutes: НЕ ИСПОЛЬЗУЕТСЯ (для совместимости API)
        amount_tolerance_percent: Погрешность по сумме в процентах (по умолчанию 2.0%)
        verbose_logging: Выводить ли подробное логирование (по умолчанию False)
        transaction_num: Номер транзакции для логирования
        used_payment_transactions: Множество уже обработанных payment_transaction_id
        
    Returns:
        Словарь с найденным чеком и заказом или None (если не найдено)
        {
            'order': DOrder объект,
            'check_sales': List[Sales],          # Sales записи этого чека
            'payment_transaction_id': str,       # ID чека
            'check_sum': float,                  # Сумма чека (из Sales)
            'order_checks_count': int,           # Сколько всего чеков у заказа
            'is_multi_check_order': bool,        # True если у заказа несколько чеков
            'match_confidence': 'high' | 'medium',
            'sum_diff': float,                   # разница по сумме
            'time_diff': float                   # разница по времени в секундах
        }
    """
    try:
        from models.sales import Sales
        from models.d_order import DOrder
        
        # Логирование начала обработки транзакции
        if verbose_logging:
            print(f"\n{'='*80}")
            print(f"🔍 ТРАНЗАКЦИЯ #{transaction_num}")
            print(f"{'='*80}")
        
        # 1. Получаем дату и время транзакции
        transaction_dt = parse_transaction_datetime(transaction)
        if not transaction_dt:
            if verbose_logging:
                print(f"❌ Не удалось распарсить дату/время транзакции")
                print(f"   Дата: {transaction.get('Дата операции')}")
                print(f"   Время: {transaction.get('Время')}")
            return None
        
        # 2. Получаем сумму транзакции
        amount = transaction.get('Сумма операции (т)')
        if not amount:
            if verbose_logging:
                print(f"❌ Отсутствует сумма операции")
            return None
        
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            if verbose_logging:
                print(f"❌ Не удалось преобразовать сумму: {amount}")
            return None
        
        if verbose_logging:
            print(f"\n📋 Данные транзакции:")
            print(f"   Дата/Время: {transaction_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Сумма: {amount:,.2f} тг")
            print(f"   Адрес: {transaction.get('Адрес точки продаж')}")
            print(f"   Тип операции: {transaction.get('Тип операции')}")
            print(f"   Тип оплаты: {transaction.get('Тип оплаты')}")
        
        # 3. Получаем organization_id по адресу точки терминала
        terminal_address = transaction.get('Адрес точки продаж')
        organization_id = get_organization_id_by_terminal(terminal_address)
        
        if verbose_logging:
            print(f"\n🏪 Поиск organization_id по адресу:")
            print(f"   Адрес терминала: {terminal_address}")
            if organization_id:
                print(f"   ✅ Найден department_code: {organization_id}")
                print(f"   Поиск будет выполнен ТОЛЬКО по этой организации")
            else:
                # Проверяем, есть ли адрес в маппинге с пустым значением
                is_in_mapping = terminal_address and any(
                    addr.lower() == str(terminal_address).strip().lower() 
                    for addr in TERMINAL_ORGANIZATION_MAPPING.keys()
                )
                
                if is_in_mapping:
                    print(f"   ⚠️ Адрес найден в маппинге, но department_code не указан (пустая строка)")
                    print(f"   → Поиск будет выполнен ПО ВСЕМ организациям")
                else:
                    print(f"   ⚠️ Адрес НЕ найден в таблице маппинга")
                    print(f"   → Поиск будет выполнен ПО ВСЕМ организациям (менее точный результат)")
                print(f"   💡 Для более точного поиска добавьте соответствие в TERMINAL_ORGANIZATION_MAPPING")
        
        # 4. Вычисляем диапазон времени с учетом оплаты после полуночи
        # Случай: чек выставлен поздно вечером (например, 18.10 23:55),
        # а оплачен на терминале уже после полуночи (например, 19.10 00:10)
        
        if transaction_dt.hour < 4:
            # Транзакция в первые 4 часа дня (00:00 - 03:59)
            # Ищем чеки с вечера предыдущего дня (с 20:00) до текущего времени + 4 часа
            time_start = (transaction_dt - timedelta(days=1)).replace(hour=16, minute=0, second=0, microsecond=0)
            time_end = transaction_dt.replace(hour=4, minute=0, second=0, microsecond=0)
            search_desc = "с вечера предыдущего дня (20:00) до 04:00 текущего дня"
        else:
            # Обычная транзакция - ищем весь текущий день + до 4 утра следующего
            time_start = transaction_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            time_end = (transaction_dt + timedelta(days=1)).replace(hour=4, minute=0, second=0, microsecond=0)
            search_desc = "весь день транзакции + до 4 утра следующего дня"
        
        if verbose_logging:
            print(f"\n⏰ Диапазон поиска по времени:")
            print(f"   От: {time_start.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   До: {time_end.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Поиск: {search_desc}")
            print(f"   (для покрытия случаев оплаты после полуночи)")
        
        # 5. Ищем в таблице Sales по precheque_time
        query = db.query(Sales).filter(
            Sales.precheque_time.between(time_start, time_end)
        )
        
        # Фильтруем по deleted_with_writeoff - учитываем только НЕ удаленные записи
        # NOT_DELETED или NULL - это обычные записи, которые попали в чек
        # Все остальные (DELETED_WITHOUT_WRITEOFF и т.д.) - исключаем
        query = query.filter(
            or_(
                Sales.deleted_with_writeoff.is_(None),
                Sales.deleted_with_writeoff == 'NOT_DELETED'
            )
        )
        
        # Фильтруем по organization_id если есть
        if organization_id:
            query = query.filter(Sales.department_code == organization_id)
        
        sales_records = query.all()
        
        if verbose_logging:
            print(f"\n🔎 Результаты поиска в Sales:")
            print(f"   Найдено записей: {len(sales_records)}")
            print(f"   ✅ Фильтр: deleted_with_writeoff IS NULL ИЛИ = 'NOT_DELETED' (только оплаченные позиции)")
            print(f"   (исключены удаленные позиции: DELETED_WITHOUT_WRITEOFF, DELETED_WITH_WRITEOFF и т.д.)")
            if organization_id:
                print(f"   ✅ Фильтр: department_code = '{organization_id}'")
            else:
                print(f"   ⚠️ Фильтр: ПОИСК ПО ВСЕМ ОРГАНИЗАЦИЯМ (department_code не применялся)")
                print(f"   Это может привести к ложным совпадениям, если в БД есть данные из разных точек")
        
        if not sales_records:
            if verbose_logging:
                print(f"\n❌ НЕ НАЙДЕНО записей в Sales")
                print(f"   Причина: В указанном диапазоне времени нет записей")
                # Пробуем найти ближайшие по времени
                nearest_before = db.query(Sales).filter(
                    Sales.precheque_time < time_start
                ).order_by(Sales.precheque_time.desc()).first()
                
                nearest_after = db.query(Sales).filter(
                    Sales.precheque_time > time_end
                ).order_by(Sales.precheque_time.asc()).first()
                
                if nearest_before:
                    diff_minutes = (transaction_dt - nearest_before.precheque_time).total_seconds() / 60
                    print(f"   Ближайшая ПЕРЕД: {nearest_before.precheque_time} (разница: {diff_minutes:.1f} мин)")
                
                if nearest_after:
                    diff_minutes = (nearest_after.precheque_time - transaction_dt).total_seconds() / 60
                    print(f"   Ближайшая ПОСЛЕ: {nearest_after.precheque_time} (разница: {diff_minutes:.1f} мин)")
            return None
        
        # Логируем найденные записи
        if verbose_logging and len(sales_records) > 0:
            print(f"\n   📊 Детали найденных записей в Sales:")
            for idx, sale in enumerate(sales_records, 1):
                print(f"\n      {idx}. Sales ID: {sale.id}")
                print(f"         Order ID (iiko_id): {sale.order_id}")
                print(f"         Precheque time: {sale.precheque_time}")
                print(f"         Department code: {sale.department_code}")
                print(f"         Organization ID: {sale.organization_id}")
        
        # 6. **ГРУППИРУЕМ Sales по payment_transaction_id для создания "чеков"**
        if verbose_logging:
            print(f"\n   📋 Группируем Sales по payment_transaction_id (создаем чеки в памяти)...")
        
        # Группируем записи по payment_transaction_id (чеки)
        from collections import defaultdict
        checks_map = defaultdict(list)  # payment_transaction_id -> List[Sales]
        for sale in sales_records:
            if sale.payment_transaction_id:
                checks_map[sale.payment_transaction_id].append(sale)
        
        # Также группируем чеки по order_id для статистики
        orders_checks_map = defaultdict(set)  # order_id -> Set[payment_transaction_id]
        for payment_id, sales_list in checks_map.items():
            for sale in sales_list:
                if sale.order_id:
                    orders_checks_map[sale.order_id].add(payment_id)
        
        if verbose_logging:
            print(f"   Найдено чеков (payment_transaction_id): {len(checks_map)}")
            print(f"   Найдено заказов (order_id): {len(orders_checks_map)}")
            
            # Показываем заказы с несколькими чеками
            multi_check_orders = {oid: checks for oid, checks in orders_checks_map.items() if len(checks) > 1}
            if multi_check_orders:
                print(f"\n   📦 Заказы с несколькими чеками:")
                for order_id, checks in multi_check_orders.items():
                    print(f"      Order {order_id}: {len(checks)} чеков")
            
            # Показываем первые несколько чеков
            print(f"\n   📄 Примеры чеков:")
            for idx, (payment_id, sales_list) in enumerate(list(checks_map.items())[:3], 1):
                order_id = sales_list[0].order_id if sales_list else None
                print(f"      {idx}. Чек {payment_id}: {len(sales_list)} позиций (Sales), order_id={order_id}")
        
        # 7. Вычисляем диапазон суммы транзакции с погрешностью
        amount_tolerance = amount * (amount_tolerance_percent / 100.0)
        amount_min = amount - amount_tolerance
        amount_max = amount + amount_tolerance
        
        if verbose_logging:
            print(f"\n   💰 Поиск чека по сумме:")
            print(f"      Сумма транзакции терминала: {amount:,.2f} тг")
            print(f"      Диапазон поиска: {amount_min:,.2f} - {amount_max:,.2f} тг")
            print(f"      Погрешность: ±{amount_tolerance_percent}%")
        
        # 8. Проверяем каждый чек (payment_transaction_id)
        matching_checks = []
        
        for idx, (payment_id, check_sales) in enumerate(checks_map.items(), 1):
            # НЕ пропускаем чеки здесь - проверка будет на уровне compare_terminal_report_with_db
            
            # Суммируем dish_discount_sum_int для получения суммы чека (с учетом скидок)
            check_sum = sum(float(sale.dish_discount_sum_int or 0) for sale in check_sales)
            sum_diff = abs(check_sum - amount)
            
            # Получаем order_id из первой Sales записи
            order_id = check_sales[0].order_id if check_sales else None
            
            if verbose_logging:
                print(f"\n      Проверка чека {idx}/{len(checks_map)}:")
                print(f"         Payment transaction ID: {payment_id}")
                print(f"         Order ID (iiko_id): {order_id}")
                print(f"         Позиций в чеке (Sales): {len(check_sales)}")
                print(f"         Сумма чека (dish_discount_sum_int): {check_sum:,.2f} тг")
                print(f"         Разница с терминалом: {sum_diff:,.2f} тг")
            
            # Проверяем вхождение в диапазон
            if amount_min <= check_sum <= amount_max:
                # Получаем заказ из d_order
                order = None
                if order_id:
                    order = db.query(DOrder).filter(DOrder.iiko_id == order_id).first()
                
                if order:
                    # Определяем сколько всего чеков у этого заказа
                    order_checks_count = len(orders_checks_map.get(order_id, set()))
                    is_multi_check = order_checks_count > 1
                    
                    # Вычисляем разницу по времени
                    if check_sales:
                        sale = check_sales[0]
                        time_diff_seconds = abs((sale.precheque_time - transaction_dt).total_seconds())
                    else:
                        time_diff_seconds = float('inf')
                    
                    matching_checks.append({
                        'order': order,
                        'check_sales': check_sales,
                        'payment_transaction_id': payment_id,
                        'check_sum': check_sum,
                        'order_checks_count': order_checks_count,
                        'is_multi_check_order': is_multi_check,
                        'sum_diff': sum_diff,
                        'time_diff': time_diff_seconds
                    })
                    
                    if verbose_logging:
                        print(f"         ✅ Сумма подходит! Заказ найден в d_order")
                        print(f"         Order ID (БД): {order.id}")
                        print(f"         Чеков у заказа: {order_checks_count}")
                        if is_multi_check:
                            print(f"         📦 Заказ с несколькими чеками!")
                else:
                    if verbose_logging:
                        print(f"         ⚠️ Сумма подходит, но заказ НЕ найден в d_order")
            else:
                if verbose_logging:
                    print(f"         ❌ Сумма НЕ подходит (вне диапазона)")
        
        if not matching_checks:
            if verbose_logging:
                print(f"\n   ❌ НЕ НАЙДЕНО подходящих чеков по сумме")
                print(f"      Причина: Ни один чек не имеет суммы в диапазоне {amount_min:,.2f} - {amount_max:,.2f} тг")
            return None
        
        # 9. Если нашли несколько совпадений - выбираем лучшее
        if len(matching_checks) > 1:
            if verbose_logging:
                print(f"\n   ⚠️ НАЙДЕНО НЕСКОЛЬКО ({len(matching_checks)}) подходящих чеков")
                print(f"   📋 Список всех подходящих чеков:")
                for i, match in enumerate(matching_checks, 1):
                    check = match['check_sales'][0] if match['check_sales'] else None
                    if check:
                        time_diff_minutes = match['time_diff'] / 60
                        print(f"\n      Вариант {i}:")
                        print(f"         Payment ID: {match['payment_transaction_id']}")
                        print(f"         Order ID: {match['order'].id} (iiko_id: {match['order'].iiko_id})")
                        print(f"         Сумма чека: {match['check_sum']:,.2f} тг")
                        print(f"         Разница: {match['sum_diff']:,.2f} тг")
                        print(f"         Разница по времени: {time_diff_minutes:.1f} мин")
                        if match['is_multi_check_order']:
                            print(f"         📦 Заказ с {match['order_checks_count']} чеками")
            
            # Сортируем: сначала по разнице суммы, затем по времени
            matching_checks.sort(key=lambda x: (x['sum_diff'], x['time_diff']))
            
            best_match = matching_checks[0]
            best_match['match_confidence'] = 'medium'
            
            if verbose_logging:
                print(f"\n   🎯 Выбран лучший вариант:")
                print(f"      Payment ID: {best_match['payment_transaction_id']}")
                print(f"      Order ID: {best_match['order'].id}")
                print(f"      Сумма чека: {best_match['check_sum']:,.2f} тг")
                print(f"      Разница: {best_match['sum_diff']:,.2f} тг")
                if best_match['is_multi_check_order']:
                    print(f"      📦 Заказ с {best_match['order_checks_count']} чеками")
                print(f"\n✅ СОВПАДЕНИЕ НАЙДЕНО (уверенность: medium)")
        else:
            # 10. Если нашли одно совпадение - это успех
            best_match = matching_checks[0]
            best_match['match_confidence'] = 'high'
            
            if verbose_logging:
                print(f"\n   ✅ Найден ОДИН подходящий чек")
                print(f"   🎯 Детали:")
                print(f"      Payment ID: {best_match['payment_transaction_id']}")
                print(f"      Order ID: {best_match['order'].id} (iiko_id: {best_match['order'].iiko_id})")
                print(f"      Сумма чека: {best_match['check_sum']:,.2f} тг")
                print(f"      Разница: {best_match['sum_diff']:,.2f} тг")
                if best_match['is_multi_check_order']:
                    print(f"      📦 Заказ с {best_match['order_checks_count']} чеками")
                print(f"\n✅ СОВПАДЕНИЕ НАЙДЕНО (уверенность: high)")
        
        return best_match
        
    except Exception as e:
        if verbose_logging:
            print(f"\n❌ ОШИБКА при поиске заказа в БД: {e}")
            import traceback
            traceback.print_exc()
        return None


def calculate_commission(transaction: Dict[str, Any]) -> float:
    """
    Вычисляет комиссию из транзакции терминала.
    
    Args:
        transaction: Словарь с данными транзакции
        
    Returns:
        Сумма комиссии (по модулю)
    """
    commission = 0.0
    
    # Берем все возможные поля с комиссиями
    commission_fields = [
        'Комиссия за операции (т)',
        'Комиссия за операции по карте (т)',
        'Комиссия за обеспечение платежа (т)',
        'Комиссия Kaspi Pay (т)',
        'Комиссия Kaspi Travel (т)'
    ]
    
    for field in commission_fields:
        value = transaction.get(field)
        if value:
            try:
                commission += abs(float(value))
            except (ValueError, TypeError):
                pass
    
    return commission


def update_order_commission(
    order_id: int,
    commission: float,
    db: Session,
    terminal_transaction: Optional[Dict[str, Any]] = None,
    check_info: Optional[Dict[str, Any]] = None,
    operation_type: str = "добавление"
) -> Dict[str, Any]:
    """
    Обновляет поле bank_commission в таблице d_order.
    
    Args:
        order_id: ID заказа в таблице d_order
        commission: Сумма комиссии
        db: SQLAlchemy сессия базы данных
        terminal_transaction: Данные транзакции терминала (для лога)
        check_info: Информация о чеке (для лога)
        operation_type: Тип операции (добавление, обновление, суммирование)
        
    Returns:
        Словарь с результатом операции:
        {
            'success': bool,
            'order_id': int,
            'order_iiko_id': str,
            'commission_amount': float,
            'previous_commission': float,
            'new_commission': float,
            'operation_type': str,
            'terminal_transaction': dict,
            'check_info': dict,
            'timestamp': str,
            'error': str (если есть ошибка)
        }
    """
    result = {
        'success': False,
        'order_id': order_id,
        'order_iiko_id': None,
        'commission_amount': commission,
        'previous_commission': None,
        'new_commission': None,
        'operation_type': operation_type,
        'terminal_transaction': terminal_transaction or {},
        'check_info': check_info or {},
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'error': None
    }
    
    try:
        from models.d_order import DOrder
        
        order = db.query(DOrder).filter(DOrder.id == order_id).first()
        
        if not order:
            result['error'] = f"Заказ с ID {order_id} не найден"
            return result
        
        # Сохраняем предыдущую комиссию
        previous_commission = float(order.bank_commission or 0)
        result['previous_commission'] = previous_commission
        result['order_iiko_id'] = order.iiko_id
        
        # Обновляем комиссию
        order.bank_commission = commission
        db.commit()
        
        result['new_commission'] = commission
        result['success'] = True
        
        return result
        
    except Exception as e:
        result['error'] = str(e)
        print(f"⚠️ Ошибка при обновлении комиссии: {e}")
        db.rollback()
        return result


def compare_terminal_report_with_db(
    file_path: str,
    db: Session,
    time_tolerance_minutes: int = 15,
    amount_tolerance_percent: float = 1.0,
    write_commissions: bool = False,
    verbose: bool = True,
    limit: Optional[int] = None,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    save_all_transactions_to: Optional[str] = None,
    save_commission_log_to: Optional[str] = None
) -> Dict[str, Any]:
    """
    Сравнивает транзакции из отчета терминала с заказами в БД.
    
    Алгоритм:
    1. Для каждой транзакции получаем organization_id по адресу точки
    2. Ищем в Sales по precheque_time за расширенный диапазон:
       - От 00:00:00 дня транзакции
       - До 04:00:00 следующего дня
       (это покрывает случаи когда чек выставили вечером, а оплатили после полуночи)
    3. Фильтруем по deleted_with_writeoff (только NOT_DELETED или NULL)
       Исключаем удаленные позиции (DELETED_WITHOUT_WRITEOFF, DELETED_WITH_WRITEOFF)
    4. Фильтруем по organization_id
    5. Группируем Sales по payment_transaction_id и проверяем суммы (±1%)
    6. Если найдено НЕСКОЛЬКО подходящих заказов - выбираем лучший:
       - По минимальной разнице по сумме
       - При равенстве сумм - по минимальной разнице по времени
    7. Опционально записываем комиссию в d_order.bank_commission
    
    Args:
        file_path: Путь к Excel файлу отчета терминала
        db: SQLAlchemy сессия базы данных
        time_tolerance_minutes: НЕ ИСПОЛЬЗУЕТСЯ (оставлено для совместимости API)
        amount_tolerance_percent: Погрешность по сумме в процентах (по умолчанию 1.0%)
        write_commissions: Записывать ли комиссии в БД (по умолчанию False)
        verbose: Выводить ли детальную информацию
        limit: Ограничить количество обрабатываемых транзакций (для отладки)
        date_from: Начальный день месяца для фильтрации (включительно), например 13
        date_to: Конечный день месяца для фильтрации (включительно), например 18
        
    Returns:
        Словарь со статистикой сопоставления:
        {
            'total_transactions': int,           # Всего транзакций в отчете
            'matched': int,                      # Найдено совпадений в БД
            'not_matched': int,                  # Не найдено в БД
            'match_percentage': float,           # Процент совпадений
            'commissions_written': int,          # Записано комиссий (если write_commissions=True)
            'matched_transactions': list,        # Список совпавших транзакций
            'not_matched_transactions': list,    # Список несовпавших транзакций
        }
    """
    # Парсим отчет терминала
    data = parse_terminal_report(file_path)
    transactions = data['transactions']
    
    # Фильтруем транзакции по датам если указан диапазон
    if date_from is not None or date_to is not None:
        filtered_transactions = []
        for transaction in transactions:
            date_str = transaction.get('Дата операции')
            if date_str:
                try:
                    # Парсим дату
                    if isinstance(date_str, str):
                        # Формат DD.MM.YYYY
                        parts = date_str.split('.')
                        if len(parts) == 3:
                            day = int(parts[0])
                            # Проверяем вхождение в диапазон
                            if date_from is not None and day < date_from:
                                continue
                            if date_to is not None and day > date_to:
                                continue
                            filtered_transactions.append(transaction)
                    elif isinstance(date_str, (datetime, pd.Timestamp)):
                        day = date_str.day
                        if date_from is not None and day < date_from:
                            continue
                        if date_to is not None and day > date_to:
                            continue
                        filtered_transactions.append(transaction)
                except:
                    # Если не удалось распарсить дату, пропускаем транзакцию
                    pass
        
        if verbose:
            print(f"\n📅 Применен фильтр по датам: {date_from if date_from else 1} - {date_to if date_to else 31} число месяца")
            print(f"   До фильтрации: {len(transactions)} транзакций")
            print(f"   После фильтрации: {len(filtered_transactions)} транзакций")
        
        transactions = filtered_transactions
    
    # Ограничиваем количество транзакций если задан limit
    if limit and limit > 0:
        transactions = transactions[:limit]
    
    matched_transactions = []
    not_matched_transactions = []
    commissions_written = 0
    commission_records = []  # Для лог файла
    
    # Отслеживание обработанных транзакций и чеков для предотвращения дубликатов
    processed_transactions = set()  # Уникальные ключи обработанных транзакций терминала
    used_payment_transactions = set()  # Уже использованные payment_transaction_id из БД
    processed_orders = set()  # Уже обработанные заказы (для заказов с несколькими чеками)
    
    if verbose:
        print("\n" + "=" * 80)
        print("🔍 СОПОСТАВЛЕНИЕ ТРАНЗАКЦИЙ ТЕРМИНАЛА С ЗАКАЗАМИ В БД")
        print("=" * 80)
        print(f"\n📊 Параметры поиска:")
        print(f"  - Поиск по времени: день транзакции (00:00) + до 04:00 следующего дня")
        print(f"    (покрывает случаи оплаты после полуночи)")
        print(f"  - Поиск по сумме: с погрешностью ±{amount_tolerance_percent}%")
        print(f"  - Несколько совпадений: выбирается лучший (по сумме, затем по времени)")
        print(f"  - Поле времени в БД: precheque_time в таблице Sales")
        print(f"  - Запись комиссий: {'ДА' if write_commissions else 'НЕТ'}")
        print(f"  - Предотвращение дубликатов: каждая транзакция терминала используется только один раз")
        print(f"  - Заказы с несколькими чеками: комиссия записывается только один раз")
        print(f"\n⏳ Обработка {len(transactions)} транзакций...\n")
    
    for idx, transaction in enumerate(transactions, 1):
        if not verbose and idx % 10 == 0:  # Короткие логи только если verbose выключен
            print(f"  Обработано {idx}/{len(transactions)} транзакций...")
        
        # Создаем уникальный ключ для транзакции терминала
        transaction_key = f"{transaction.get('Дата операции')}_{transaction.get('Время')}_{transaction.get('Сумма операции (т)')}_{transaction.get('Адрес точки продаж')}"
        
        # Проверяем, не обрабатывали ли мы уже эту транзакцию
        if transaction_key in processed_transactions:
            if verbose:
                print(f"\n⚠️ Транзакция #{idx} пропущена - уже обработана ранее")
                print(f"   Ключ: {transaction_key}")
            continue
        
        # Ищем соответствующий заказ
        match = match_transaction_with_order(
            transaction,
            db,
            time_tolerance_minutes,
            amount_tolerance_percent,
            verbose_logging=verbose,  # Передаем verbose для детального логирования
            transaction_num=idx,
            used_payment_transactions=used_payment_transactions  # Передаем множество уже использованных чеков
        )
        
        if match:
            # Проверяем, не использован ли уже этот чек
            if match['payment_transaction_id'] in used_payment_transactions:
                if verbose:
                    print(f"\n⚠️ Транзакция #{idx} пропущена - чек уже использован")
                    print(f"   Payment ID: {match['payment_transaction_id']}")
                not_matched_transactions.append({
                    'terminal_transaction': transaction,
                    'comment': 'Чек уже использован другой транзакцией',
                    'match_confidence': 'skipped_used_check'
                })
                continue
            
            # Отмечаем транзакцию как обработанную
            processed_transactions.add(transaction_key)
            # Отмечаем чек как использованный только после успешного сопоставления
            used_payment_transactions.add(match['payment_transaction_id'])
            
            # Добавляем информацию о совпадении
            matched_transactions.append({
                'terminal_transaction': transaction,
                'order': match['order'],
                'check_sales': match['check_sales'],
                'payment_transaction_id': match['payment_transaction_id'],
                'check_sum': match['check_sum'],
                'is_multi_check_order': match.get('is_multi_check_order', False),
                'order_checks_count': match.get('order_checks_count', 1),
                'match_confidence': match['match_confidence']
            })
            
            # Записываем комиссию если нужно
            if write_commissions:
                commission = calculate_commission(transaction)
                if commission > 0:
                    order = match['order']
                    is_multi_check = match.get('is_multi_check_order', False)
                    
                    # Подготавливаем информацию о чеке для лога
                    check_info = {
                        'payment_transaction_id': match['payment_transaction_id'],
                        'check_sum': match['check_sum'],
                        'sales_count': len(match['check_sales']),
                        'is_multi_check': is_multi_check
                    }
                    
                    # Для заказов с несколькими чеками записываем комиссию только один раз
                    # (при обработке первого чека), чтобы избежать дублирования
                    if is_multi_check:
                        # Проверяем, не записывали ли мы уже комиссию для этого заказа
                        order_id = order.id
                        if order_id not in processed_orders:  # Используем processed_orders для отслеживания заказов
                            # Заказ с несколькими чеками - записываем комиссию только один раз
                            existing_commission = float(order.bank_commission or 0)
                            total_commission = existing_commission + commission
                            
                            result = update_order_commission(
                                order.id,
                                total_commission,
                                db,
                                terminal_transaction=transaction,
                                check_info=check_info,
                                operation_type="суммирование"
                            )
                            if result['success']:
                                commissions_written += 1
                                commission_records.append(result)
                                processed_orders.add(order_id)  # Отмечаем заказ как обработанный
                    else:
                        # Заказ с одним чеком - просто записываем комиссию
                        result = update_order_commission(
                            order.id,
                            commission,
                            db,
                            terminal_transaction=transaction,
                            check_info=check_info,
                            operation_type="добавление"
                        )
                        if result['success']:
                            commissions_written += 1
                            commission_records.append(result)
        else:
            not_matched_transactions.append({
                'terminal_transaction': transaction,
                'comment': 'Не найдено подходящих чеков',
                'match_confidence': 'no_match'
            })
    
    # Подсчитываем статистику
    total = len(transactions)
    matched = len(matched_transactions)
    not_matched = len(not_matched_transactions)
    match_percentage = (matched / total * 100) if total > 0 else 0
    
    result = {
        'total_transactions': total,
        'matched': matched,
        'not_matched': not_matched,
        'match_percentage': match_percentage,
        'commissions_written': commissions_written,
        'matched_transactions': matched_transactions,
        'not_matched_transactions': not_matched_transactions,
        'terminal_total_amount': data['total_amount'],
        'terminal_total_commission': data['total_commission'],
        'commission_records': commission_records,  # Для лог файла
    }
    
    if verbose:
        print("\n" + "=" * 80)
        print("📈 СТАТИСТИКА СОПОСТАВЛЕНИЯ")
        print("=" * 80)
        print(f"\n✅ Найдено совпадений в БД: {matched} ({match_percentage:.1f}%)")
        print(f"❌ Не найдено в БД: {not_matched} ({100 - match_percentage:.1f}%)")
        print(f"📊 Всего транзакций: {total}")
        
        if write_commissions:
            print(f"\n💾 Записано комиссий: {commissions_written}")
        
        print(f"\n💰 Финансовая статистика терминала:")
        print(f"  - Общая сумма операций: {data['total_amount']:,.2f} тг")
        print(f"  - Комиссия: {data['total_commission']:,.2f} тг")
        print(f"  - К зачислению: {data['total_to_credit']:,.2f} тг")
        
        # Показываем примеры совпадений
        if matched_transactions:
            print(f"\n✅ ПРИМЕРЫ НАЙДЕННЫХ СОВПАДЕНИЙ (первые 3):")
            for i, match in enumerate(matched_transactions[:3], 1):
                trans = match['terminal_transaction']
                order = match['order']
                check_sales = match['check_sales']
                payment_id = match['payment_transaction_id']
                check_sum = match['check_sum']
                confidence = match['match_confidence']
                is_multi_check = match.get('is_multi_check_order', False)
                checks_count = match.get('order_checks_count', 1)
                
                print(f"\n  Совпадение #{i} (уверенность: {confidence}):")
                if is_multi_check:
                    print(f"    📦 ЗАКАЗ С НЕСКОЛЬКИМИ ЧЕКАМИ: {checks_count} чеков")
                print(f"    Терминал:")
                print(f"      Дата/Время: {trans.get('Дата операции')} {trans.get('Время')}")
                print(f"      Сумма: {trans.get('Сумма операции (т)')} тг")
                print(f"      Адрес: {trans.get('Адрес точки продаж')}")
                print(f"    Чек (payment_transaction_id):")
                print(f"      ID: {payment_id}")
                print(f"      Сумма чека: {check_sum:.2f} тг")
                print(f"      Позиций в чеке (Sales): {len(check_sales)}")
                if check_sales:
                    sales = check_sales[0]
                    print(f"      Precheque time: {sales.precheque_time}")
                print(f"    Заказ (Order):")
                print(f"      Order ID: {order.id} (iiko_id: {order.iiko_id})")
                print(f"      Сумма заказа: {order.sum_order} тг")
                if write_commissions and order.bank_commission:
                    print(f"      Комиссия записана: {order.bank_commission} тг")
        
        # Показываем примеры несовпадений
        if not_matched_transactions:
            print(f"\n❌ ПРИМЕРЫ НЕ НАЙДЕННЫХ ТРАНЗАКЦИЙ (первые 3):")
            for i, trans in enumerate(not_matched_transactions[:3], 1):
                print(f"\n  Транзакция #{i}:")
                print(f"    Дата/Время: {trans.get('Дата операции')} {trans.get('Время')}")
                print(f"    Сумма: {trans.get('Сумма операции (т)')} тг")
                print(f"    Адрес: {trans.get('Адрес точки продаж')}")
                print(f"    Тип операции: {trans.get('Тип операции')}")
                print(f"    Тип оплаты: {trans.get('Тип оплаты')}")
        
        print("\n" + "=" * 80)
    
    # Сохраняем полный отчет о транзакциях если указан путь
    if save_all_transactions_to:
        print("\n" + "=" * 80)
        print("💾 СОХРАНЕНИЕ ПОЛНОГО ОТЧЕТА О ТРАНЗАКЦИЯХ")
        print("=" * 80)
        
        # Подготовка метаданных
        metadata = {
            'source_file': file_path,
            'processing_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_transactions': total,
            'matched': matched,
            'not_matched': not_matched,
            'match_percentage': match_percentage,
            'commissions_written': commissions_written,
            'parameters': {
                'amount_tolerance_percent': amount_tolerance_percent,
                'date_from': date_from,
                'date_to': date_to,
                'write_commissions': write_commissions
            }
        }
        
        success = save_all_transactions_report(
            matched_transactions,
            not_matched_transactions,
            save_all_transactions_to,
            metadata
        )
        
        if success:
            print(f"\n✅ Сохранен полный отчет о транзакциях")
            print(f"   Совпавших: {matched}")
            print(f"   Несовпавших: {not_matched}")
            print(f"   Файл: {save_all_transactions_to}")
        else:
            print(f"\n❌ Не удалось сохранить полный отчет о транзакциях")
    
    # Создаем лог файл комиссий если указан путь
    if save_commission_log_to and commission_records:
        print("\n" + "=" * 80)
        print("📝 СОЗДАНИЕ ЛОГ ФАЙЛА КОМИССИЙ")
        print("=" * 80)
        
        # Подготовка метаданных для лога
        log_metadata = {
            'source_file': file_path,
            'processing_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_commission_records': len(commission_records),
            'total_commission_amount': sum(float(r.get('commission_amount', 0)) for r in commission_records),
            'parameters': {
                'amount_tolerance_percent': amount_tolerance_percent,
                'date_from': date_from,
                'date_to': date_to,
                'write_commissions': write_commissions
            }
        }
        
        success = create_commission_log_file(
            save_commission_log_to,
            commission_records,
            log_metadata
        )
        
        if success:
            print(f"\n✅ Создан лог файл комиссий")
            print(f"   Записей комиссий: {len(commission_records)}")
            print(f"   Общая сумма: {sum(float(r.get('commission_amount', 0)) for r in commission_records):,.2f} тг")
            print(f"   Файл: {save_commission_log_to}")
        else:
            print(f"\n❌ Не удалось создать лог файл комиссий")
    
    return result


def save_not_matched_transactions(
    not_matched_transactions: List[Dict[str, Any]],
    output_file: str,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Сохраняет несовпавшие транзакции в JSON файл для анализа.
    
    Args:
        not_matched_transactions: Список несовпавших транзакций
        output_file: Путь к выходному JSON файлу
        metadata: Дополнительная информация (статистика, параметры обработки и т.д.)
        
    Returns:
        True если успешно сохранено, False если ошибка
    """
    try:
        # Конвертируем datetime объекты в строки для JSON
        def convert_for_json(obj):
            if isinstance(obj, (datetime, pd.Timestamp)):
                return obj.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(obj, pd.Series):
                return obj.to_dict()
            elif isinstance(obj, (list, tuple)):
                return [convert_for_json(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: convert_for_json(v) for k, v in obj.items()}
            elif hasattr(obj, '__dict__'):
                # Для объектов SQLAlchemy моделей
                return {k: convert_for_json(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
            else:
                # Проверяем на NaN только для скалярных значений
                try:
                    if pd.isna(obj):
                        return None
                except (ValueError, TypeError):
                    # Если не можем проверить на NaN, возвращаем как есть
                    pass
                
                # Обрабатываем Decimal объекты
                from decimal import Decimal
                if isinstance(obj, Decimal):
                    return float(obj)
                
                # Обрабатываем date объекты
                from datetime import date
                if isinstance(obj, date):
                    return obj.strftime('%Y-%m-%d')
                
                return obj
        
        # Очищаем транзакции от объектов, которые нельзя сериализовать
        cleaned_transactions = []
        for trans in not_matched_transactions:
            cleaned_trans = {}
            for key, value in trans.items():
                cleaned_trans[key] = convert_for_json(value)
            cleaned_transactions.append(cleaned_trans)
        
        # Формируем структуру данных для сохранения
        output_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_not_matched': len(cleaned_transactions),
            'metadata': metadata or {},
            'not_matched_transactions': cleaned_transactions
        }
        
        # Создаем директорию если не существует
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Сохраняем в JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        return True
        
    except Exception as e:
        print(f"⚠️ Ошибка при сохранении несовпавших транзакций: {e}")
        import traceback
        traceback.print_exc()
        return False


def save_all_transactions_report(
    matched_transactions: List[Dict[str, Any]],
    not_matched_transactions: List[Dict[str, Any]],
    output_file: str,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Сохраняет полный отчет о всех транзакциях (совпавших и несовпавших) в JSON файл.
    
    Args:
        matched_transactions: Список совпавших транзакций с информацией о заказах
        not_matched_transactions: Список несовпавших транзакций
        output_file: Путь к выходному JSON файлу
        metadata: Дополнительная информация (статистика, параметры обработки и т.д.)
        
    Returns:
        True если успешно сохранено, False если ошибка
    """
    try:
        # Конвертируем datetime объекты в строки для JSON
        def convert_for_json(obj):
            if isinstance(obj, (datetime, pd.Timestamp)):
                return obj.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(obj, pd.Series):
                return obj.to_dict()
            elif isinstance(obj, (list, tuple)):
                return [convert_for_json(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: convert_for_json(v) for k, v in obj.items()}
            elif hasattr(obj, '__dict__'):
                # Для объектов SQLAlchemy моделей
                return {k: convert_for_json(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
            else:
                # Проверяем на NaN только для скалярных значений
                try:
                    if pd.isna(obj):
                        return None
                except (ValueError, TypeError):
                    # Если не можем проверить на NaN, возвращаем как есть
                    pass
                
                # Обрабатываем Decimal объекты
                from decimal import Decimal
                if isinstance(obj, Decimal):
                    return float(obj)
                
                # Обрабатываем date объекты
                from datetime import date
                if isinstance(obj, date):
                    return obj.strftime('%Y-%m-%d')
                
                return obj
        
        # Очищаем совпавшие транзакции
        cleaned_matched = []
        for match in matched_transactions:
            cleaned_match = {}
            for key, value in match.items():
                if key == 'terminal_transaction':
                    # Очищаем транзакцию терминала
                    cleaned_trans = {}
                    for k, v in value.items():
                        cleaned_trans[k] = convert_for_json(v)
                    cleaned_match[key] = cleaned_trans
                elif key == 'order':
                    # Очищаем объект заказа
                    cleaned_match[key] = convert_for_json(value)
                elif key == 'check_sales':
                    # Очищаем список Sales записей
                    cleaned_sales = []
                    for sale in value:
                        cleaned_sales.append(convert_for_json(sale))
                    cleaned_match[key] = cleaned_sales
                else:
                    cleaned_match[key] = convert_for_json(value)
            cleaned_matched.append(cleaned_match)
        
        # Очищаем несовпавшие транзакции
        cleaned_not_matched = []
        for trans in not_matched_transactions:
            cleaned_trans = {}
            for key, value in trans.items():
                cleaned_trans[key] = convert_for_json(value)
            cleaned_not_matched.append(cleaned_trans)
        
        # Формируем структуру данных для сохранения
        output_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'summary': {
                'total_matched': len(cleaned_matched),
                'total_not_matched': len(cleaned_not_matched),
                'total_transactions': len(cleaned_matched) + len(cleaned_not_matched),
                'match_percentage': (len(cleaned_matched) / (len(cleaned_matched) + len(cleaned_not_matched)) * 100) if (len(cleaned_matched) + len(cleaned_not_matched)) > 0 else 0
            },
            'metadata': metadata or {},
            'matched_transactions': cleaned_matched,
            'not_matched_transactions': cleaned_not_matched
        }
        
        # Создаем директорию если не существует
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Сохраняем в JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        return True
        
    except Exception as e:
        print(f"⚠️ Ошибка при сохранении полного отчета транзакций: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_commission_log_file(
    log_file_path: str,
    commission_records: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Создает лог файл с информацией о записи комиссий в d_order.
    
    Args:
        log_file_path: Путь к лог файлу
        commission_records: Список записей о комиссиях
        metadata: Дополнительная информация (источник, параметры обработки и т.д.)
        
    Returns:
        True если успешно создано, False если ошибка
    """
    try:
        # Создаем директорию если не существует
        log_dir = os.path.dirname(log_file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Формируем содержимое лог файла
        log_content = []
        log_content.append("=" * 80)
        log_content.append("ЛОГ ЗАПИСИ КОМИССИЙ В D_ORDER")
        log_content.append("=" * 80)
        log_content.append(f"Дата создания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_content.append("")
        
        if metadata:
            log_content.append("МЕТАДАННЫЕ:")
            log_content.append("-" * 40)
            for key, value in metadata.items():
                log_content.append(f"{key}: {value}")
            log_content.append("")
        
        log_content.append(f"ВСЕГО ЗАПИСЕЙ КОМИССИЙ: {len(commission_records)}")
        log_content.append("")
        
        # Записываем каждую запись комиссии
        for idx, record in enumerate(commission_records, 1):
            log_content.append(f"ЗАПИСЬ #{idx}")
            log_content.append("-" * 40)
            log_content.append(f"Order ID (d_order.id): {record.get('order_id')}")
            log_content.append(f"Order iiko_id: {record.get('order_iiko_id')}")
            log_content.append(f"Комиссия записана: {record.get('commission_amount')} тг")
            log_content.append(f"Предыдущая комиссия: {record.get('previous_commission', 'не было')} тг")
            log_content.append(f"Новая комиссия: {record.get('new_commission')} тг")
            log_content.append(f"Тип операции: {record.get('operation_type', 'добавление')}")
            
            # Информация о транзакции терминала
            terminal_info = record.get('terminal_transaction', {})
            if terminal_info:
                log_content.append("Транзакция терминала:")
                log_content.append(f"  Дата/Время: {terminal_info.get('Дата операции')} {terminal_info.get('Время')}")
                log_content.append(f"  Сумма: {terminal_info.get('Сумма операции (т)')} тг")
                log_content.append(f"  Адрес: {terminal_info.get('Адрес точки продаж')}")
                log_content.append(f"  Тип операции: {terminal_info.get('Тип операции')}")
            
            # Информация о чеке
            check_info = record.get('check_info', {})
            if check_info:
                log_content.append("Чек:")
                log_content.append(f"  Payment transaction ID: {check_info.get('payment_transaction_id')}")
                log_content.append(f"  Сумма чека: {check_info.get('check_sum')} тг")
                log_content.append(f"  Позиций в чеке: {check_info.get('sales_count')}")
                log_content.append(f"  Заказ с несколькими чеками: {'Да' if check_info.get('is_multi_check') else 'Нет'}")
            
            log_content.append(f"Время записи: {record.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}")
            log_content.append("")
        
        # Статистика
        total_commission = sum(float(r.get('commission_amount', 0)) for r in commission_records)
        log_content.append("СТАТИСТИКА:")
        log_content.append("-" * 40)
        log_content.append(f"Всего записей: {len(commission_records)}")
        log_content.append(f"Общая сумма комиссий: {total_commission:,.2f} тг")
        
        # Статистика по типам операций
        operation_stats = {}
        for record in commission_records:
            op_type = record.get('operation_type', 'добавление')
            operation_stats[op_type] = operation_stats.get(op_type, 0) + 1
        
        if operation_stats:
            log_content.append("По типам операций:")
            for op_type, count in operation_stats.items():
                log_content.append(f"  {op_type}: {count} записей")
        
        log_content.append("")
        log_content.append("=" * 80)
        log_content.append("КОНЕЦ ЛОГА")
        log_content.append("=" * 80)
        
        # Записываем в файл
        with open(log_file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log_content))
        
        return True
        
    except Exception as e:
        print(f"⚠️ Ошибка при создании лог файла комиссий: {e}")
        import traceback
        traceback.print_exc()
        return False


def process_and_write_commissions(
    file_path: str,
    db: Session,
    terminal_org_mapping: Dict[str, int],
    time_tolerance_minutes: int = 15,
    amount_tolerance_percent: float = 1.0,
    dry_run: bool = True,
    verbose: bool = False,
    limit: Optional[int] = None,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    save_not_matched_to: Optional[str] = None,
    save_all_transactions_to: Optional[str] = None,
    save_commission_log_to: Optional[str] = None
) -> Dict[str, Any]:
    """
    Обрабатывает отчет терминала и записывает комиссии в БД.
    
    Args:
        file_path: Путь к Excel файлу отчета терминала
        db: SQLAlchemy сессия базы данных
        terminal_org_mapping: Словарь соответствий {адрес_терминала: organization_id}
        time_tolerance_minutes: НЕ ИСПОЛЬЗУЕТСЯ (оставлено для совместимости API)
        amount_tolerance_percent: Погрешность по сумме в процентах (по умолчанию 1.0%)
        dry_run: Режим тестирования без записи в БД (по умолчанию True)
        verbose: Детальное логирование каждой транзакции (по умолчанию False)
        limit: Ограничить количество обрабатываемых транзакций (для отладки)
        date_from: Начальный день месяца для фильтрации (включительно), например 13
        date_to: Конечный день месяца для фильтрации (включительно), например 18
        save_not_matched_to: Путь к JSON файлу для сохранения несовпавших транзакций (опционально)
        save_all_transactions_to: Путь к JSON файлу для сохранения полного отчета о всех транзакциях (опционально)
        save_commission_log_to: Путь к лог файлу для записи информации о комиссиях в d_order (опционально)
        
    Returns:
        Словарь с результатами обработки
    """
    global TERMINAL_ORGANIZATION_MAPPING
    
    # Обновляем глобальный маппинг
    TERMINAL_ORGANIZATION_MAPPING.update(terminal_org_mapping)
    
    print("\n" + "=" * 80)
    print("💾 ЗАПИСЬ КОМИССИЙ ИЗ ОТЧЕТА ТЕРМИНАЛА В БД")
    print("=" * 80)
    
    if dry_run:
        print("\n⚠️  РЕЖИМ ТЕСТИРОВАНИЯ (dry_run=True) - изменения НЕ будут записаны в БД")
    else:
        print("\n✅ РЕЖИМ ЗАПИСИ (dry_run=False) - изменения БУДУТ записаны в БД")
    
    print(f"\n📋 Таблица соответствий точек:")
    for terminal_addr, org_id in terminal_org_mapping.items():
        print(f"  • {terminal_addr} → Department Code: {org_id}")
    
    if verbose:
        print(f"\n🔍 Детальное логирование: ВКЛЮЧЕНО")
    
    if limit:
        print(f"\n⚠️  Ограничение: будут обработаны только первые {limit} транзакций")
    
    if date_from is not None or date_to is not None:
        print(f"\n📅 Фильтр по датам: {date_from if date_from else 1} - {date_to if date_to else 31} число месяца")
    
    # Выполняем сопоставление
    result = compare_terminal_report_with_db(
        file_path,
        db,
        time_tolerance_minutes=time_tolerance_minutes,
        amount_tolerance_percent=amount_tolerance_percent,
        write_commissions=not dry_run,  # Записываем только если не dry_run
        verbose=verbose,  # Передаем флаг детального логирования
        limit=limit,
        date_from=date_from,
        date_to=date_to,
        save_all_transactions_to=save_all_transactions_to,
        save_commission_log_to=save_commission_log_to
    )
    
    if dry_run:
        print("\n" + "=" * 80)
        print("💡 РЕКОМЕНДАЦИЯ:")
        print("=" * 80)
        print(f"\nЧтобы записать комиссии в БД, запустите функцию с параметром:")
        print(f"  dry_run=False")
        print(f"\nЭто запишет комиссии для {result['matched']} найденных заказов")
    else:
        print("\n" + "=" * 80)
        print("✅ КОМИССИИ ЗАПИСАНЫ В БД")
        print("=" * 80)
        print(f"\nЗаписано комиссий: {result['commissions_written']} из {result['matched']} совпадений")
    
    # Сохраняем несовпавшие транзакции в JSON если указан путь
    if save_not_matched_to and result['not_matched_transactions']:
        print("\n" + "=" * 80)
        print("💾 СОХРАНЕНИЕ НЕСОВПАВШИХ ТРАНЗАКЦИЙ")
        print("=" * 80)
        
        # Подготовка метаданных
        metadata = {
            'source_file': file_path,
            'processing_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_transactions': result['total_transactions'],
            'matched': result['matched'],
            'not_matched': result['not_matched'],
            'match_percentage': result['match_percentage'],
            'parameters': {
                'amount_tolerance_percent': amount_tolerance_percent,
                'date_from': date_from,
                'date_to': date_to,
                'dry_run': dry_run
            }
        }
        
        success = save_not_matched_transactions(
            result['not_matched_transactions'],
            save_not_matched_to,
            metadata
        )
        
        if success:
            print(f"\n✅ Сохранено {result['not_matched']} несовпавших транзакций")
            print(f"   Файл: {save_not_matched_to}")
        else:
            print(f"\n❌ Не удалось сохранить несовпавшие транзакции")
    
    return result


def parse_terminals_directory(
    directory_path: str,
    file_pattern: str = "*.xlsx",
    verbose: bool = True,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None
) -> Dict[str, Any]:
    """
    Парсит все отчеты терминалов из указанной папки.
    Автоматически определяет тип каждого файла и парсит соответствующим образом.
    
    Args:
        directory_path: Путь к папке с отчетами
        file_pattern: Шаблон для поиска файлов (по умолчанию "*.xlsx")
        verbose: Выводить ли детальную информацию о процессе
        date_from: Начальный день месяца для фильтрации (включительно), например 13
        date_to: Конечный день месяца для фильтрации (включительно), например 18
        
    Returns:
        Словарь с результатами:
        {
            'total_files': int,              # Всего файлов обработано
            'success_files': int,            # Успешно обработано
            'failed_files': int,             # Ошибок при обработке
            'total_transactions': int,       # Всего транзакций
            'total_amount': float,           # Общая сумма всех операций
            'total_commission': float,       # Общая комиссия
            'reports': list,                 # Список распарсенных отчетов
            'failed_reports': list,          # Список файлов с ошибками
            'report_types_stats': dict       # Статистика по типам отчетов
        }
    """
    import glob
    
    if not os.path.exists(directory_path):
        raise FileNotFoundError(f"Папка не найдена: {directory_path}")
    
    # Ищем все файлы по шаблону
    search_pattern = os.path.join(directory_path, file_pattern)
    files = glob.glob(search_pattern)
    
    if verbose:
        print("\n" + "=" * 80)
        print("📂 ПАРСИНГ ПАПКИ С ОТЧЕТАМИ ТЕРМИНАЛОВ")
        print("=" * 80)
        print(f"\n📁 Папка: {directory_path}")
        print(f"🔍 Шаблон: {file_pattern}")
        print(f"📊 Найдено файлов: {len(files)}")
        if date_from is not None or date_to is not None:
            print(f"📅 Фильтр по датам: {date_from if date_from else 1} - {date_to if date_to else 31} число месяца")
        print()
    
    reports = []
    failed_reports = []
    total_transactions = 0
    total_amount = 0.0
    total_commission = 0.0
    report_types_stats = {}
    
    for idx, file_path in enumerate(files, 1):
        file_name = os.path.basename(file_path)
        
        if verbose:
            print(f"\n{'='*80}")
            print(f"📄 Файл {idx}/{len(files)}: {file_name}")
            print('='*80)
        
        try:
            # Парсим файл
            report_data = parse_terminal_report(file_path)
            
            # Фильтруем транзакции по датам если указан диапазон
            if date_from is not None or date_to is not None:
                original_count = len(report_data['transactions'])
                filtered_transactions = []
                
                for transaction in report_data['transactions']:
                    date_str = transaction.get('Дата операции')
                    if date_str:
                        try:
                            # Парсим дату
                            if isinstance(date_str, str):
                                # Формат DD.MM.YYYY
                                parts = date_str.split('.')
                                if len(parts) == 3:
                                    day = int(parts[0])
                                    # Проверяем вхождение в диапазон
                                    if date_from is not None and day < date_from:
                                        continue
                                    if date_to is not None and day > date_to:
                                        continue
                                    filtered_transactions.append(transaction)
                            elif isinstance(date_str, (datetime, pd.Timestamp)):
                                day = date_str.day
                                if date_from is not None and day < date_from:
                                    continue
                                if date_to is not None and day > date_to:
                                    continue
                                filtered_transactions.append(transaction)
                        except:
                            # Если не удалось распарсить дату, пропускаем транзакцию
                            pass
                
                # Обновляем данные отчета после фильтрации
                report_data['transactions'] = filtered_transactions
                report_data['total_transactions'] = len(filtered_transactions)
                
                # Пересчитываем суммы для отфильтрованных транзакций
                filtered_amount = 0.0
                filtered_commission = 0.0
                for trans in filtered_transactions:
                    amount = trans.get('Сумма операции (т)', 0)
                    if amount:
                        try:
                            filtered_amount += float(amount)
                        except:
                            pass
                    
                    # Комиссия
                    commission_fields = [
                        'Комиссия за операции (т)',
                        'Комиссия за операции по карте (т)',
                        'Комиссия за обеспечение платежа (т)',
                        'Комиссия Kaspi Pay (т)',
                        'Комиссия Kaspi Travel (т)'
                    ]
                    for field in commission_fields:
                        value = trans.get(field)
                        if value:
                            try:
                                filtered_commission += abs(float(value))
                            except:
                                pass
                
                report_data['total_amount'] = filtered_amount
                report_data['total_commission'] = filtered_commission
                
                if verbose:
                    print(f"\n   📅 Применена фильтрация:")
                    print(f"      До: {original_count} транзакций")
                    print(f"      После: {len(filtered_transactions)} транзакций")
            
            # Добавляем имя файла
            report_data['file_name'] = file_name
            
            reports.append(report_data)
            
            # Обновляем статистику
            total_transactions += report_data['total_transactions']
            total_amount += report_data['total_amount']
            total_commission += report_data['total_commission']
            
            # Статистика по типам
            report_type = report_data['report_type']
            if report_type not in report_types_stats:
                report_types_stats[report_type] = {
                    'count': 0,
                    'transactions': 0,
                    'amount': 0.0
                }
            report_types_stats[report_type]['count'] += 1
            report_types_stats[report_type]['transactions'] += report_data['total_transactions']
            report_types_stats[report_type]['amount'] += report_data['total_amount']
            
            if verbose:
                print(f"\n✅ Успешно распарсен")
                print(f"   Тип отчета: {report_type}")
                print(f"   Транзакций: {report_data['total_transactions']}")
                print(f"   Сумма операций: {report_data['total_amount']:,.2f} тг")
                print(f"   Комиссия: {report_data['total_commission']:,.2f} тг")
                
                # Показываем метаданные если есть
                if report_data['metadata']:
                    print(f"\n   Метаданные:")
                    for key, value in report_data['metadata'].items():
                        if value and key != 'report_type':
                            print(f"     • {key}: {value}")
        
        except Exception as e:
            failed_reports.append({
                'file_name': file_name,
                'file_path': file_path,
                'error': str(e)
            })
            
            if verbose:
                print(f"\n❌ Ошибка при парсинге: {e}")
    
    # Финальная статистика
    success_files = len(reports)
    failed_files = len(failed_reports)
    
    if verbose:
        print("\n" + "=" * 80)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 80)
        print(f"\n📁 Файлы:")
        print(f"   Всего файлов: {len(files)}")
        print(f"   ✅ Успешно: {success_files}")
        print(f"   ❌ Ошибок: {failed_files}")
        
        print(f"\n💰 Транзакции:")
        print(f"   Всего транзакций: {total_transactions}")
        print(f"   Общая сумма: {total_amount:,.2f} тг")
        print(f"   Общая комиссия: {total_commission:,.2f} тг")
        
        if report_types_stats:
            print(f"\n📋 По типам отчетов:")
            for report_type, stats in report_types_stats.items():
                print(f"\n   {report_type}:")
                print(f"     Файлов: {stats['count']}")
                print(f"     Транзакций: {stats['transactions']}")
                print(f"     Сумма: {stats['amount']:,.2f} тг")
        
        if failed_reports:
            print(f"\n❌ ФАЙЛЫ С ОШИБКАМИ:")
            for failed in failed_reports:
                print(f"\n   • {failed['file_name']}")
                print(f"     Ошибка: {failed['error']}")
        
        print("\n" + "=" * 80)
    
    return {
        'total_files': len(files),
        'success_files': success_files,
        'failed_files': failed_files,
        'total_transactions': total_transactions,
        'total_amount': total_amount,
        'total_commission': total_commission,
        'reports': reports,
        'failed_reports': failed_reports,
        'report_types_stats': report_types_stats
    }


def analyze_matching_fields(
    file_path: str,
    db: Session,
    sample_size: int = 5
) -> None:
    """
    Анализирует по каким полям можно сопоставлять данные.
    Показывает примеры данных из отчета терминала и БД для понимания возможных связей.
    
    Args:
        file_path: Путь к Excel файлу отчета терминала
        db: SQLAlchemy сессия базы данных
        sample_size: Количество примеров для отображения
    """
    try:
        from models.sales import Sales
        
        print("\n" + "=" * 80)
        print("🔬 АНАЛИЗ ПОЛЕЙ ДЛЯ СОПОСТАВЛЕНИЯ ДАННЫХ")
        print("=" * 80)
        
        # Парсим отчет терминала
        data = parse_terminal_report(file_path)
        transactions = data['transactions'][:sample_size]
        
        # Получаем примеры из БД Sales
        sales_records = db.query(Sales).limit(sample_size).all()
        
        print(f"\n📋 ПОЛЯ ИЗ ОТЧЕТА ТЕРМИНАЛА (примеры из {len(transactions)} транзакций):")
        print("-" * 80)
        
        if transactions:
            trans = transactions[0]
            important_fields = [
                'Дата операции', 'Время', 'Сумма операции (т)',
                'Сумма к зачислению/ списанию (т)', 'Тип операции',
                'Тип оплаты', 'Номер карты', 'Комиссия Kaspi Pay (т)'
            ]
            
            for field in important_fields:
                if field in trans:
                    print(f"  • {field}: {trans[field]}")
        
        print(f"\n📊 ПОЛЯ ИЗ БД SALES (примеры из {len(sales_records)} записей):")
        print("-" * 80)
        
        if sales_records:
            sale = sales_records[0]
            important_db_fields = [
                ('close_time', 'Время закрытия заказа'),
                ('open_time', 'Время открытия заказа'),
                ('dish_discount_sum_int', 'Сумма блюда с учетом скидок'),
                ('dish_sum_int', 'Сумма блюда без скидок'),
                ('order_id', 'ID заказа'),
                ('pay_types', 'Типы оплаты'),
                ('commission', 'Комиссия'),
                ('card_number', 'Номер карты'),
            ]
            
            for field_name, description in important_db_fields:
                value = getattr(sale, field_name, None)
                if value is not None:
                    print(f"  • {description} ({field_name}): {value}")
        
        print(f"\n🔗 ВОЗМОЖНЫЕ ПОЛЯ ДЛЯ СОПОСТАВЛЕНИЯ:")
        print("-" * 80)
        print("  1. ⏰ ВРЕМЯ:")
        print("     Терминал: 'Дата операции' + 'Время'")
        print("     БД Sales: 'close_time' или 'open_time'")
        print("     Рекомендация: Сравнивать с погрешностью ±5 минут")
        print()
        print("  2. 💰 СУММА:")
        print("     Терминал: 'Сумма операции (т)'")
        print("     БД Sales: 'dish_discount_sum_int' (сумма с учетом скидок)")
        print("     Рекомендация: Сравнивать с погрешностью ±1-2% (для точности сопоставления)")
        print()
        print("  3. 💳 ДОПОЛНИТЕЛЬНЫЕ ПОЛЯ:")
        print("     Терминал: 'Номер карты', 'Тип оплаты'")
        print("     БД Sales: 'card_number', 'pay_types'")
        print("     Рекомендация: Использовать как дополнительную проверку")
        print()
        print("  4. 📝 ТИП ОПЕРАЦИИ:")
        print("     Терминал: 'Тип операции' (Покупка, Возврат и т.д.)")
        print("     БД Sales: 'operation_type'")
        print()
        
        print(f"\n📈 СРАВНИТЕЛЬНАЯ ТАБЛИЦА:")
        print("-" * 80)
        print(f"{'Поле терминала':<35} | {'Поле БД Sales':<35}")
        print("-" * 80)
        print(f"{'Дата операции + Время':<35} | {'close_time / open_time':<35}")
        print(f"{'Сумма операции (т)':<35} | {'dish_discount_sum_int':<35}")
        print(f"{'Номер карты':<35} | {'card_number':<35}")
        print(f"{'Тип оплаты':<35} | {'pay_types':<35}")
        print(f"{'Комиссия Kaspi Pay (т)':<35} | {'commission':<35}")
        print(f"{'Тип операции':<35} | {'operation_type':<35}")
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"\n❌ Ошибка при анализе полей: {e}")
        import traceback
        traceback.print_exc()


# Пример использования
if __name__ == "__main__":
    # Тестовый запуск
    test_file = r"C:\Documents\sidework\backend\GC_backend_main_node\temp_files\sales report from terminal.xlsx"
    
    # Проверяем аргументы командной строки
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == 'inspect':
            # Режим детального просмотра
            print("🔍 РЕЖИМ ДЕТАЛЬНОГО ПРОСМОТРА ФАЙЛА\n")
            inspect_excel_file(test_file, max_rows=15)
            sys.exit(0)
        elif sys.argv[1] == 'analyze':
            # Режим анализа полей для сопоставления
            print("🔬 РЕЖИМ АНАЛИЗА ПОЛЕЙ ДЛЯ СОПОСТАВЛЕНИЯ\n")
            try:
                from database.database import SessionLocal
                db = SessionLocal()
                analyze_matching_fields(test_file, db, sample_size=3)
                db.close()
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                import traceback
                traceback.print_exc()
            sys.exit(0)
        elif sys.argv[1] == 'compare':
            # Режим сравнения с БД
            print("🔍 РЕЖИМ СРАВНЕНИЯ С БАЗОЙ ДАННЫХ\n")
            try:
                from database.database import SessionLocal
                db = SessionLocal()
                result = compare_terminal_report_with_db(
                    test_file, 
                    db,
                    time_tolerance_minutes=15,
                    amount_tolerance_percent=5.0,
                    verbose=True
                )
                db.close()
                
                print(f"\n📝 Результаты сохранены в переменной result")
                print(f"   Совпадений: {result['matched']}")
                print(f"   Не найдено: {result['not_matched']}")
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                import traceback
                traceback.print_exc()
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

🆕 НОВОЕ: АВТОМАТИЧЕСКОЕ ОПРЕДЕЛЕНИЕ ТИПА ОТЧЕТА И ПАРСИНГ ПАПКИ
--------------------------------------------------------------------

Модуль теперь поддерживает два типа отчетов терминалов:
1. Kaspi - детальная информация по операциям (37 колонок)
2. Банковские выписки (Народный Банк и др.) - упрощенный формат

Тип отчета определяется автоматически!


0a. ПАРСИНГ ВСЕЙ ПАПКИ С ОТЧЕТАМИ (рекомендуемый способ):

   from utils.terminal_report_parsing import parse_terminals_directory
   
   # Парсит все .xlsx файлы в папке, автоматически определяет типы
   result = parse_terminals_directory(
       "temp_files/terminals_report/",
       verbose=True,   # показывать детальную статистику
       date_from=13,   # с 13 числа месяца (включительно)
       date_to=18      # по 18 число месяца (включительно)
   )
   
   print(f"Обработано файлов: {result['success_files']}")
   print(f"Всего транзакций: {result['total_transactions']}")
   print(f"Общая сумма: {result['total_amount']:,.2f} тг")
   
   # Доступ к отдельным отчетам
   for report in result['reports']:
       print(f"\nФайл: {report['file_name']}")
       print(f"Тип: {report['report_type']}")
       print(f"Транзакций: {report['total_transactions']}")
   
   Возвращает:
   - total_files: количество найденных файлов
   - success_files: успешно обработано
   - failed_files: файлов с ошибками
   - total_transactions: общее количество транзакций
   - total_amount: общая сумма
   - total_commission: общая комиссия
   - reports: список распарсенных отчетов
   - failed_reports: список ошибок
   - report_types_stats: статистика по типам отчетов


0b. ОПРЕДЕЛЕНИЕ ТИПА ОТЧЕТА:

   from utils.terminal_report_parsing import detect_report_type, TerminalReportType
   
   report_type = detect_report_type("файл.xlsx")
   
   if report_type == TerminalReportType.KASPI_DETAILED:
       print("Это Kaspi отчет с детальной информацией")
   elif report_type == TerminalReportType.BANK_STATEMENT:
       print("Это банковская выписка")


0. ДЕТАЛЬНЫЙ ПРОСМОТР ФАЙЛА (для анализа структуры):
   
   from utils.terminal_report_parsing import inspect_excel_file
   
   # Показывает полную структуру файла, все колонки и примеры данных
   inspect_excel_file("файл.xlsx", max_rows=10)
   
   # Или запустить из командной строки:
   # python utils/terminal_report_parsing.py inspect
   
   
0.1. РЕЖИМЫ РАБОТЫ ИЗ КОМАНДНОЙ СТРОКИ:
   
   # Режим детального просмотра структуры файла:
   python utils/terminal_report_parsing.py inspect
   
   # Режим анализа полей для сопоставления с БД:
   python utils/terminal_report_parsing.py analyze
   
   # Режим сравнения транзакций с БД:
   python utils/terminal_report_parsing.py compare
   
   # Обычный режим (парсинг и статистика):
   python utils/terminal_report_parsing.py


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


8. АНАЛИЗ ПОЛЕЙ ДЛЯ СОПОСТАВЛЕНИЯ С БД:
   
   from utils.terminal_report_parsing import analyze_matching_fields
   from database.database import SessionLocal
   
   db = SessionLocal()
   analyze_matching_fields("файл.xlsx", db)
   # Показывает какие поля можно использовать для связи данных
   

9. СРАВНЕНИЕ ТРАНЗАКЦИЙ С БД:
   
   from utils.terminal_report_parsing import compare_terminal_report_with_db
   from database.database import SessionLocal
   
   db = SessionLocal()
   result = compare_terminal_report_with_db(
       "файл.xlsx", 
       db,
       amount_tolerance_percent=1.0,  # погрешность по сумме ±1%
       verbose=True,                   # выводить детальную статистику
       date_from=13,                   # с 13 числа месяца (включительно)
       date_to=18                      # по 18 число месяца (включительно)
   )
   
   # Поиск выполняется:
   # - По времени: день транзакции (00:00) + до 04:00 следующего дня
   #   (покрывает случаи когда чек выставили вечером, а оплатили после полуночи)
   # - По сумме: с погрешностью ±1%
   # - Несколько совпадений: выбирается лучший (по сумме, затем по времени)
   # - По дате: только транзакции с 13 по 18 число (если указаны date_from и date_to)
   
   print(f"Найдено совпадений: {result['matched']}")
   print(f"Не найдено: {result['not_matched']}")
   print(f"Процент совпадений: {result['match_percentage']:.1f}%")


10. ПОИСК КОНКРЕТНОЙ ТРАНЗАКЦИИ В БД:
   
   from utils.terminal_report_parsing import match_transaction_with_sales
   from database.database import SessionLocal
   
   db = SessionLocal()
   transaction = {
       'Дата операции': '29.09.2025',
       'Время': '14:30:00',
       'Сумма операции (т)': 15000.0
   }
   
   sales_match = match_transaction_with_sales(transaction, db)
   if sales_match:
       print(f"Найдено! Order ID: {sales_match['order_id']}")

=============================================================================

🆕 НОВЫЕ ФУНКЦИИ ДЛЯ СОХРАНЕНИЯ ОТЧЕТОВ И ЛОГОВ
--------------------------------------------------------------------

11. СОХРАНЕНИЕ ПОЛНОГО ОТЧЕТА О ВСЕХ ТРАНЗАКЦИЯХ:

   from utils.terminal_report_parsing import save_all_transactions_report
   
   # Сохраняет JSON с совпавшими и несовпавшими транзакциями
   success = save_all_transactions_report(
       matched_transactions,      # Список совпавших транзакций
       not_matched_transactions,  # Список несовпавших транзакций
       "reports/all_transactions_report.json",
       metadata={                 # Дополнительная информация
           'source_file': 'terminal_report.xlsx',
           'processing_date': '2025-01-23 15:30:00',
           'total_transactions': 150,
           'matched': 120,
           'not_matched': 30
       }
   )
   
   Структура JSON файла:
   {
     "timestamp": "2025-01-23 15:30:00",
     "summary": {
       "total_matched": 120,
       "total_not_matched": 30,
       "total_transactions": 150,
       "match_percentage": 80.0
     },
     "metadata": {...},
     "matched_transactions": [
       {
         "terminal_transaction": {...},
         "order": {...},
         "check_sales": [...],
         "payment_transaction_id": "...",
         "check_sum": 1500.0,
         "is_multi_check_order": false,
         "match_confidence": "high"
       }
     ],
     "not_matched_transactions": [...]
   }


12. СОЗДАНИЕ ЛОГ ФАЙЛА КОМИССИЙ:

   from utils.terminal_report_parsing import create_commission_log_file
   
   # Создает текстовый лог файл с информацией о записи комиссий
   commission_records = [
       {
           'order_id': 123,
           'order_iiko_id': 'abc-123-def',
           'commission_amount': 45.50,
           'previous_commission': 0.0,
           'new_commission': 45.50,
           'operation_type': 'добавление',
           'terminal_transaction': {...},
           'check_info': {...},
           'timestamp': '2025-01-23 15:30:00'
       }
   ]
   
   success = create_commission_log_file(
       "logs/commission_log_20250123.txt",
       commission_records,
       metadata={
           'source_file': 'terminal_report.xlsx',
           'total_commission_records': 1,
           'total_commission_amount': 45.50
       }
   )
   
   Структура лог файла:
   ================================================================================
   ЛОГ ЗАПИСИ КОМИССИЙ В D_ORDER
   ================================================================================
   Дата создания: 2025-01-23 15:30:00
   
   МЕТАДАННЫЕ:
   ----------------------------------------
   source_file: terminal_report.xlsx
   total_commission_records: 1
   
   ВСЕГО ЗАПИСЕЙ КОМИССИЙ: 1
   
   ЗАПИСЬ #1
   ----------------------------------------
   Order ID (d_order.id): 123
   Order iiko_id: abc-123-def
   Комиссия записана: 45.5 тг
   Предыдущая комиссия: 0.0 тг
   Новая комиссия: 45.5 тг
   Тип операции: добавление
   Транзакция терминала:
     Дата/Время: 23.01.2025 14:30:00
     Сумма: 1500.0 тг
     Адрес: Astana, Mangilik el, 50
   Чек:
     Payment transaction ID: pay-123-456
     Сумма чека: 1500.0 тг
     Позиций в чеке: 3
     Заказ с несколькими чеками: Нет
   Время записи: 2025-01-23 15:30:00
   
   СТАТИСТИКА:
   ----------------------------------------
   Всего записей: 1
   Общая сумма комиссий: 45.50 тг
   По типам операций:
     добавление: 1 записей


13. АВТОМАТИЧЕСКОЕ СОХРАНЕНИЕ ПРИ ОБРАБОТКЕ:

   from utils.terminal_report_parsing import compare_terminal_report_with_db
   from database.database import SessionLocal
   
   db = SessionLocal()
   result = compare_terminal_report_with_db(
       "terminal_report.xlsx", 
       db,
       amount_tolerance_percent=1.0,
       write_commissions=True,                    # Записывать комиссии в БД
       save_all_transactions_to="reports/all_transactions.json",  # Сохранить полный отчет
       save_commission_log_to="logs/commission_log.txt"          # Создать лог комиссий
   )
   
   # Функция автоматически:
   # 1. Обработает все транзакции
   # 2. Запишет комиссии в d_order.bank_commission
   # 3. Сохранит полный отчет в JSON
   # 4. Создаст лог файл с информацией о записи комиссий
   
   print(f"Обработано транзакций: {result['total_transactions']}")
   print(f"Совпадений найдено: {result['matched']}")
   print(f"Комиссий записано: {result['commissions_written']}")


14. ОБНОВЛЕННАЯ ФУНКЦИЯ process_and_write_commissions:

   from utils.terminal_report_parsing import process_and_write_commissions
   from database.database import SessionLocal
   
   db = SessionLocal()
   
   # Обработка с сохранением всех отчетов
   result = process_and_write_commissions(
       "terminal_report.xlsx",
       db,
       terminal_org_mapping={},  # Словарь соответствий адресов
       dry_run=False,            # Режим записи в БД
       verbose=True,             # Детальное логирование
       date_from=13,             # С 13 числа месяца
       date_to=18,               # По 18 число месяца
       save_all_transactions_to="reports/transactions_13-18.json",
       save_commission_log_to="logs/commissions_13-18.txt"
   )
   
   # Результат содержит:
   # - Статистику обработки
   # - Список совпавших транзакций
   # - Список несовпавших транзакций
   # - Записи о комиссиях для лога


=============================================================================
"""
