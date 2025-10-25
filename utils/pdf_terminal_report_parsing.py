# -*- coding: utf-8 -*-
"""
Парсер PDF отчетов от терминала оплаты (БЦК, Kaspi и др.)

Этот модуль предоставляет функции для чтения и парсинга PDF файлов 
с выгрузками от терминала оплаты с поддержкой записи в БД.

Основные функции:
-----------------
- inspect_pdf_file(file_path) - детальный просмотр структуры PDF для анализа
- parse_pdf_terminal_report(file_path) - полный парсинг PDF отчета
- convert_pdf_to_excel(file_path, output_path) - конвертация PDF в Excel
- parse_pdf_directory(directory_path) - парсинг всех PDF в папке
- compare_pdf_with_db(pdf_path, db) - парсинг PDF и сопоставление с БД
- process_pdf_directory_with_db(directory_path, db) - обработка папки с записью в БД

Требования:
-----------
- pdfplumber >= 0.11.0  (установить: pip install pdfplumber)
- pandas >= 2.2.3
- openpyxl >= 3.1.5

Установка:
----------
pip install pdfplumber

Примеры использования:
--------------------
    # 1. Парсим PDF напрямую
    from utils.pdf_terminal_report_parsing import parse_pdf_terminal_report
    data = parse_pdf_terminal_report("выписка.pdf")
    print(f"Всего транзакций: {data['total_transactions']}")
    
    # 2. Парсим PDF и сопоставляем с БД
    from utils.pdf_terminal_report_parsing import compare_pdf_with_db
    from database.database import SessionLocal
    
    db = SessionLocal()
    result = compare_pdf_with_db(
        "выписка.pdf", 
        db,
        amount_tolerance_percent=2.0,
        write_commissions=True,
        dry_run=False
    )
    print(f"Найдено совпадений: {result['matched']}")
    db.close()
    
    # 3. Обработка папки с PDF
    from utils.pdf_terminal_report_parsing import process_pdf_directory_with_db
    result = process_pdf_directory_with_db(
        "temp_files/terminals_report_pdf",
        db,
        date_from=13,
        date_to=18,
        write_commissions=True
    )
    
    # 4. Конвертация в Excel (для совместимости)
    from utils.pdf_terminal_report_parsing import convert_pdf_to_excel
    from utils.terminal_report_parsing import parse_terminal_report
    
    convert_pdf_to_excel("выписка.pdf", "выписка.xlsx")
    data = parse_terminal_report("выписка.xlsx")

CLI скрипт:
-----------
    # Используйте process_pdf_commissions.py для удобной работы из командной строки
    python process_pdf_commissions.py --pdf-file "выписка.pdf" --dry-run
    python process_pdf_commissions.py --pdf-directory "temp_files/terminals_report_pdf" --write-commissions
"""

import os
import sys
from typing import Dict, List, Optional, Any
import pandas as pd
from datetime import datetime

# Настройка кодировки для Windows
if sys.platform == 'win32':
    import codecs
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def check_pdfplumber_installed() -> bool:
    """
    Проверяет, установлена ли библиотека pdfplumber.
    
    Returns:
        True если установлена, False если нет
    """
    try:
        import pdfplumber
        return True
    except ImportError:
        return False


def install_pdfplumber_instructions():
    """
    Выводит инструкции по установке pdfplumber.
    """
    print("\n" + "=" * 80)
    print("⚠️ ТРЕБУЕТСЯ УСТАНОВКА БИБЛИОТЕКИ pdfplumber")
    print("=" * 80)
    print("\nДля работы с PDF файлами необходимо установить библиотеку pdfplumber.")
    print("\n📦 Установка:")
    print("   pip install pdfplumber")
    print("\nИли добавьте в requirements.txt:")
    print("   pdfplumber==0.11.0")
    print("\nИ выполните:")
    print("   pip install -r requirements.txt")
    print("\n" + "=" * 80)


def inspect_pdf_file(file_path: str, max_pages: int = 3) -> None:
    """
    Детально отображает структуру и содержимое PDF файла для анализа.
    
    Args:
        file_path: Путь к PDF файлу
        max_pages: Максимальное количество страниц для отображения (по умолчанию 3)
    """
    if not check_pdfplumber_installed():
        install_pdfplumber_instructions()
        return
    
    import pdfplumber
    
    if not os.path.exists(file_path):
        print(f"❌ Файл не найден: {file_path}")
        return
    
    print("=" * 80)
    print("📋 ДЕТАЛЬНЫЙ ПРОСМОТР PDF ФАЙЛА")
    print("=" * 80)
    print(f"\n📁 Файл: {file_path}")
    
    try:
        with pdfplumber.open(file_path) as pdf:
            print(f"\n📊 Информация о файле:")
            print(f"   Страниц: {len(pdf.pages)}")
            
            if pdf.metadata:
                print(f"\n📄 Метаданные:")
                for key, value in pdf.metadata.items():
                    if value:
                        print(f"   {key}: {value}")
            
            # Обрабатываем каждую страницу
            for page_num, page in enumerate(pdf.pages[:max_pages], 1):
                print(f"\n{'='*80}")
                print(f"📄 СТРАНИЦА {page_num}")
                print('='*80)
                
                # Извлекаем текст
                text = page.extract_text()
                if text:
                    print(f"\n📝 Текст (первые 1000 символов):")
                    print("-" * 80)
                    print(text[:1000])
                    if len(text) > 1000:
                        print(f"\n... (всего {len(text)} символов)")
                
                # Извлекаем таблицы
                tables = page.extract_tables()
                if tables:
                    print(f"\n📊 Найдено таблиц: {len(tables)}")
                    
                    for table_idx, table in enumerate(tables, 1):
                        print(f"\n   Таблица #{table_idx}:")
                        print(f"   Размер: {len(table)} строк × {len(table[0]) if table else 0} колонок")
                        
                        # Показываем заголовки и первые строки
                        if table:
                            print(f"\n   Заголовки (первая строка):")
                            headers = table[0]
                            for col_idx, header in enumerate(headers[:10], 1):  # Первые 10 колонок
                                if header:
                                    print(f"      {col_idx}. {header}")
                            
                            print(f"\n   Примеры данных (первые 3 строки):")
                            for row_idx, row in enumerate(table[1:4], 1):
                                print(f"\n      Строка {row_idx}:")
                                for col_idx, cell in enumerate(row[:10], 1):  # Первые 10 колонок
                                    if cell and str(cell).strip():
                                        print(f"         Колонка {col_idx}: {cell}")
        
        print(f"\n{'='*80}")
        print("✅ ПРОСМОТР ЗАВЕРШЕН")
        print('='*80)
        
    except Exception as e:
        print(f"\n❌ Ошибка при чтении PDF: {e}")
        import traceback
        traceback.print_exc()


def extract_tables_from_pdf(file_path: str) -> List[pd.DataFrame]:
    """
    Извлекает все таблицы из PDF файла.
    
    Args:
        file_path: Путь к PDF файлу
        
    Returns:
        Список pandas DataFrame с таблицами из PDF
    """
    if not check_pdfplumber_installed():
        install_pdfplumber_instructions()
        return []
    
    import pdfplumber
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    
    all_tables = []
    
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        # Преобразуем в DataFrame
                        df = pd.DataFrame(table[1:], columns=table[0])
                        all_tables.append(df)
        
        return all_tables
        
    except Exception as e:
        raise Exception(f"Ошибка при извлечении таблиц из PDF: {str(e)}")


def convert_pdf_to_excel(
    pdf_path: str,
    excel_path: Optional[str] = None,
    verbose: bool = True
) -> str:
    """
    Конвертирует PDF отчет в Excel файл.
    После конвертации можно использовать существующий парсер terminal_report_parsing.py
    
    Args:
        pdf_path: Путь к PDF файлу
        excel_path: Путь для сохранения Excel (если None, создается автоматически)
        verbose: Выводить ли информацию о процессе
        
    Returns:
        Путь к созданному Excel файлу
    """
    if not check_pdfplumber_installed():
        install_pdfplumber_instructions()
        raise ImportError("Библиотека pdfplumber не установлена")
    
    import pdfplumber
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Файл не найден: {pdf_path}")
    
    # Генерируем имя для Excel файла
    if excel_path is None:
        excel_path = pdf_path.rsplit('.', 1)[0] + '.xlsx'
    
    if verbose:
        print(f"\n{'='*80}")
        print(f"🔄 КОНВЕРТАЦИЯ PDF → EXCEL")
        print('='*80)
        print(f"\nИсходный файл: {pdf_path}")
        print(f"Выходной файл: {excel_path}")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Создаем Excel writer
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                
                # Обрабатываем каждую страницу
                for page_num, page in enumerate(pdf.pages, 1):
                    if verbose:
                        print(f"\n📄 Обработка страницы {page_num}/{len(pdf.pages)}...")
                    
                    # Извлекаем таблицы
                    tables = page.extract_tables()
                    
                    if tables:
                        for table_idx, table in enumerate(tables, 1):
                            if table:
                                # Преобразуем в DataFrame
                                df = pd.DataFrame(table[1:], columns=table[0])
                                
                                # Очищаем пустые строки
                                df = df.dropna(how='all')
                                
                                # Название листа
                                sheet_name = f"Page{page_num}_Table{table_idx}"
                                if len(sheet_name) > 31:  # Excel ограничение на длину имени листа
                                    sheet_name = f"P{page_num}_T{table_idx}"
                                
                                # Записываем в Excel
                                df.to_excel(writer, sheet_name=sheet_name, index=False)
                                
                                if verbose:
                                    print(f"   ✅ Таблица {table_idx}: {len(df)} строк × {len(df.columns)} колонок → {sheet_name}")
        
        if verbose:
            print(f"\n{'='*80}")
            print(f"✅ КОНВЕРТАЦИЯ ЗАВЕРШЕНА")
            print(f"   Файл сохранен: {excel_path}")
            print('='*80)
        
        return excel_path
        
    except Exception as e:
        raise Exception(f"Ошибка при конвертации PDF в Excel: {str(e)}")


def _normalize_bck_transaction(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Нормализует транзакцию из БЦК формата в стандартный формат.
    
    БЦК формат имеет колонки вроде:
    - "Дата транзакции"  
    - "Сумма транзакции в валюте транзакции"
    - "Сумма комиссии"
    """
    normalized = {}
    
    
    # Извлекаем дату и время из "Дата транзакции"
    date_str = transaction.get('Транзакция\nкүні / Дата\nтранзакции') or transaction.get('Дата транзакции')
    
    if date_str and isinstance(date_str, str):
        # Убираем все переносы строк и лишние пробелы
        date_str = date_str.replace('\n', '').replace(' ', '').strip()
        
        # Формат: 2025-10-15T19:04:27Z
        try:
            if 'T' in date_str:
                date_part, time_part = date_str.split('T')
                time_part = time_part.rstrip('Z')
                
                # Преобразуем дату в DD.MM.YYYY
                if '-' in date_part:
                    year, month, day = date_part.split('-')
                    normalized['Дата операции'] = f"{day}.{month}.{year}"
                
                # Время уже в правильном формате HH:MM:SS
                if ':' in time_part:
                    normalized['Время'] = time_part
        except:
            pass
    
    # Адрес терминала - ищем в разных возможных полях
    address = None
    
    # Сначала пробуем точные совпадения
    exact_keys = [
        'Құрылғыны орнату\nмекенжайы / Адрес\nустановки\nустройства',
        'Құрылғыны\nорнату\nмекенжайы /\nАдрес\nустановки\nустройства',
        'Адрес установки устройства',
        'Транзакция\nмекенжайы /\nАдрес\nтранзакции',
        'Адрес транзакции'
    ]
    
    for key in exact_keys:
        if transaction.get(key):
            address = transaction.get(key)
            break
    
    # Если не нашли точным совпадением, ищем по частичному совпадению
    if not address:
        for key, value in transaction.items():
            if value and ('установки' in key.lower() and 'устройства' in key.lower()):
                address = value
                break
    
    if address:
        # Очищаем адрес от переносов строк и лишних пробелов
        address_clean = str(address).replace('\n', ' ').replace('\r', '').strip()
        # Убираем множественные пробелы
        address_clean = ' '.join(address_clean.split())
        normalized['Адрес установки устройства'] = address_clean
        print(f"   ✅ Найден адрес: {address_clean}")
    else:
        print(f"   ❌ Адрес не найден")
    
    # Сумма транзакции - ищем по ключевым словам
    amount_str = None
    for key, value in transaction.items():
        if value and ('Сумма транзакции' in key or 'сумма транзакции' in key.lower()):
            amount_str = value
            break
    
    if amount_str:
        try:
            # Удаляем пробелы и запятые, преобразуем в число
            amount_clean = str(amount_str).replace(' ', '').replace(',', '').replace('\n', '')
            normalized['Сумма операции (т)'] = float(amount_clean)
        except:
            pass
    
    # Комиссия - ищем в разных полях, приоритет числовым значениям
    commission_found = False
    
    # Сначала ищем в полях с числовыми значениями
    commission_fields = [
        'Комиссия\nсомасы /\nСумма\nкомиссии',
        'Сумма комиссии',
        'Комиссия сомасы / Сумма комиссии',
        'Бөліп төлеу үшін\nбанк комиссиясы /\nСумма комиссии\nбанка за рассрочку',
        'Кэшбэк үшін банк\nкомиссиясының\nсомасы / Сумма\nкомиссии банка за\nкэшбек'
    ]
    
    for field in commission_fields:
        if field in transaction and transaction[field]:
            try:
                commission_clean = str(transaction[field]).strip().replace('\n', '').replace('\r', '').replace(' ', '').replace(',', '')
                if commission_clean and commission_clean.replace('.', '').replace('-', '').isdigit():
                    normalized['Общая комиссия банка'] = abs(float(commission_clean))
                    commission_found = True
                    break
            except:
                pass
    
    # Если не нашли в числовых полях, пробуем "Общая комиссия банка"
    if not commission_found:
        commission_str = None
        for key, value in transaction.items():
            if value and ('Общая\nкомиссия\nбанка' in key or 'Общая комиссия банка' in key):
                commission_str = value
                break
        
        if commission_str:
            try:
                commission_clean = str(commission_str).strip().replace('\n', '').replace('\r', '').replace(' ', '').replace(',', '')
                if commission_clean and commission_clean.replace('.', '').replace('-', '').isdigit():
                    normalized['Общая комиссия банка'] = abs(float(commission_clean))
                else:
                    print(f"   ⚠️ Поле 'Общая комиссия банка' содержит не числовое значение: {commission_str}")
            except Exception as e:
                print(f"   ⚠️ Ошибка парсинга 'Общая комиссия банка' в нормализации: {commission_str} - {e}")
    
    # Номер карты
    card_number = transaction.get('Карта нөмірі /\nНомер карты') or transaction.get('Номер карты')
    if card_number:
        normalized['Номер карты'] = str(card_number)
    
    # Тип операции
    operation_type = (transaction.get('Транзакция\nатауы /\nНаименование\nтранзакции') or
                     transaction.get('Наименование транзакции'))
    if operation_type:
        normalized['Тип операции'] = 'Покупка'  # По умолчанию
        normalized['Тип оплаты'] = str(operation_type)
    
    return normalized


def parse_pdf_terminal_report(file_path: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Парсит PDF отчет терминала напрямую в список транзакций.
    
    Args:
        file_path: Путь к PDF файлу
        verbose: Выводить ли детальную информацию
        
    Returns:
        Словарь с распарсенными данными (такой же как у parse_terminal_report)
    """
    if not check_pdfplumber_installed():
        install_pdfplumber_instructions()
        raise ImportError("Библиотека pdfplumber не установлена")
    
    import pdfplumber
    
    if verbose:
        print(f"\n{'='*80}")
        print(f"📄 ПАРСИНГ PDF: {os.path.basename(file_path)}")
        print('='*80)
    
    try:
        transactions = []
        all_tables_data = []
        
        with pdfplumber.open(file_path) as pdf:
            if verbose:
                print(f"\n📊 Страниц в PDF: {len(pdf.pages)}")
            
            # Извлекаем таблицы со всех страниц
            for page_num, page in enumerate(pdf.pages, 1):
                if verbose:
                    print(f"\n📄 Обработка страницы {page_num}...")
                
                tables = page.extract_tables()
                
                for table_idx, table in enumerate(tables, 1):
                    if table and len(table) > 1:
                        # Преобразуем в DataFrame
                        df = pd.DataFrame(table[1:], columns=table[0])
                        
                        # Очищаем пустые строки
                        df = df.dropna(how='all')
                        
                        if len(df) > 0:
                            all_tables_data.append(df)
                            
                            if verbose:
                                print(f"   Таблица {table_idx}: {len(df)} строк × {len(df.columns)} колонок")
        
        if not all_tables_data:
            raise Exception("Не найдено таблиц с данными в PDF")
        
        # Объединяем все таблицы
        if len(all_tables_data) > 1:
            df_combined = pd.concat(all_tables_data, ignore_index=True)
        else:
            df_combined = all_tables_data[0]
        
        if verbose:
            print(f"\n✅ Всего строк данных: {len(df_combined)}")
            print(f"   Колонки: {list(df_combined.columns)}")
        
        # Определяем тип отчета по колонкам
        columns_str = ' '.join([str(col) for col in df_combined.columns])
        
        if 'Дата и время' in columns_str and 'транзакции' in columns_str:
            report_type = "bank_statement"
        elif 'Дата операции' in columns_str and 'Время' in columns_str:
            report_type = "kaspi_detailed"
        elif 'Дата транзакции' in columns_str or 'Сумма транзакции' in columns_str:
            report_type = "bank_statement_bck"  # БЦК формат
        else:
            report_type = "unknown"
        
        if verbose:
            print(f"\n📋 Тип отчета: {report_type}")
        
        # Преобразуем в список транзакций
        for idx, row in df_combined.iterrows():
            transaction = {}
            for col in df_combined.columns:
                value = row[col]
                # Преобразуем NaN в None
                if pd.isna(value):
                    transaction[col] = None
                # Преобразуем Timestamp в строку
                elif isinstance(value, pd.Timestamp):
                    transaction[col] = value.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    transaction[col] = value
            
            # Простая нормализация для БЦК формата
            if report_type == "bank_statement_bck":
                normalized = _normalize_bck_transaction(transaction)
            else:
                # Для других форматов используем встроенную нормализацию
                try:
                    from utils.terminal_report_parsing import normalize_transaction_fields
                    normalized = normalize_transaction_fields(transaction, report_type)
                except:
                    # Если не можем импортировать, используем транзакцию как есть
                    normalized = transaction
            
            # Добавляем только если есть сумма
            if normalized.get('Сумма операции (т)') or normalized.get('Сумма транзакции'):
                # Добавляем адрес из таблицы для каждой транзакции
                # Ищем адрес в разных возможных полях
                address = (normalized.get('Адрес установки устройства') or 
                          normalized.get('Адрес точки продаж') or 
                          normalized.get('Адрес транзакции'))
                
                # print(f"\n📍 Отладка адреса для транзакции:")
                # print(f"   'Адрес установки устройства': {normalized.get('Адрес установки устройства')}")
                # print(f"   'Адрес точки продаж': {normalized.get('Адрес точки продаж')}")
                # print(f"   'Адрес транзакции': {normalized.get('Адрес транзакции')}")
                # print(f"   Найденный адрес: {address}")
                
                if address and str(address).strip():
                    normalized['terminal_address'] = str(address).strip()
                    print(f"   ✅ Добавлен terminal_address: {normalized['terminal_address']}")
                else:
                    print(f"   ❌ Адрес не найден или пустой")
                
                transactions.append(normalized)
        
        # Подсчитываем итоги
        total_amount = 0.0
        total_commission = 0.0
        
        for trans in transactions:
            amount = trans.get('Сумма операции (т)', 0)
            if amount:
                try:
                    total_amount += float(amount)
                except:
                    pass
            
            # Комиссия - используем ТОЛЬКО "Общая комиссия банка" если есть
            total_commission_value = trans.get('Общая комиссия банка')
            if total_commission_value:
                try:
                    # Триммим и убираем переносы строк и лишние пробелы
                    commission_clean = str(total_commission_value).strip().replace('\n', '').replace('\r', '').replace(' ', '')
                    if commission_clean:
                        total_commission = abs(float(commission_clean))
                        continue
                except Exception as e:
                    if verbose:
                        print(f"   ⚠️ Ошибка парсинга 'Общая комиссия банка': {total_commission_value} - {e}")
            else:
                if verbose:
                    print(f"   ⚠️ Поле 'Общая комиссия банка' не найдено в транзакции")
        
        if verbose:
            print(f"\n💰 Статистика:")
            print(f"   Транзакций: {len(transactions)}")
            print(f"   Общая сумма: {total_amount:,.2f} тг")
            print(f"   Комиссия: {total_commission:,.2f} тг")
        
        return {
            'file_path': file_path,
            'source_type': 'pdf',
            'report_type': report_type,
            'metadata': {'report_type': report_type},
            'total_transactions': len(transactions),
            'total_amount': total_amount,
            'total_to_credit': total_amount - total_commission,
            'total_commission': total_commission,
            'transactions': transactions,
            'summary': {
                'columns': list(df_combined.columns),
                'first_transaction': transactions[0] if transactions else None,
                'last_transaction': transactions[-1] if transactions else None,
            }
        }
        
    except Exception as e:
        raise Exception(f"Ошибка при парсинге PDF: {str(e)}")


def parse_pdf_directory(
    directory_path: str,
    file_pattern: str = "*.pdf",
    verbose: bool = True,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None
) -> Dict[str, Any]:
    """
    Парсит все PDF отчеты терминалов из указанной папки.
    
    Args:
        directory_path: Путь к папке с PDF отчетами
        file_pattern: Шаблон для поиска файлов (по умолчанию "*.pdf")
        verbose: Выводить ли детальную информацию
        date_from: Начальный день месяца для фильтрации (включительно)
        date_to: Конечный день месяца для фильтрации (включительно)
        
    Returns:
        Словарь с результатами
    """
    if not check_pdfplumber_installed():
        install_pdfplumber_instructions()
        raise ImportError("Библиотека pdfplumber не установлена")
    
    import glob
    
    if not os.path.exists(directory_path):
        raise FileNotFoundError(f"Папка не найдена: {directory_path}")
    
    # Ищем все PDF файлы
    search_pattern = os.path.join(directory_path, file_pattern)
    files = glob.glob(search_pattern)
    
    if verbose:
        print("\n" + "=" * 80)
        print("📂 ПАРСИНГ ПАПКИ С PDF ОТЧЕТАМИ ТЕРМИНАЛОВ")
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
    
    for idx, pdf_path in enumerate(files, 1):
        file_name = os.path.basename(pdf_path)
        
        if verbose:
            print(f"\n{'='*80}")
            print(f"📄 Файл {idx}/{len(files)}: {file_name}")
            print('='*80)
        
        try:
            # Парсим PDF напрямую
            report_data = parse_pdf_terminal_report(pdf_path, verbose=False)
            
            # Фильтруем по датам если нужно
            if date_from is not None or date_to is not None:
                from utils.terminal_report_parsing import parse_terminals_directory
                # Используем логику фильтрации из существующей функции
                # (копируем логику фильтрации)
                original_count = len(report_data['transactions'])
                filtered_transactions = []
                
                for transaction in report_data['transactions']:
                    date_str = transaction.get('Дата операции')
                    if date_str:
                        try:
                            if isinstance(date_str, str):
                                parts = date_str.split('.')
                                if len(parts) == 3:
                                    day = int(parts[0])
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
                            pass
                
                report_data['transactions'] = filtered_transactions
                report_data['total_transactions'] = len(filtered_transactions)
                
                if verbose and original_count != len(filtered_transactions):
                    print(f"\n   📅 Применена фильтрация:")
                    print(f"      До: {original_count} транзакций")
                    print(f"      После: {len(filtered_transactions)} транзакций")
            
            # Добавляем информацию об источнике
            report_data['source_type'] = 'pdf'
            report_data['original_file'] = pdf_path
            report_data['file_name'] = file_name
            
            reports.append(report_data)
            
            # Обновляем статистику
            total_transactions += report_data['total_transactions']
            total_amount += report_data['total_amount']
            total_commission += report_data['total_commission']
            
            if verbose:
                print(f"\n✅ Успешно обработан")
                print(f"   Транзакций: {report_data['total_transactions']}")
                print(f"   Сумма: {report_data['total_amount']:,.2f} тг")
        
        except Exception as e:
            failed_reports.append({
                'file_name': file_name,
                'file_path': pdf_path,
                'error': str(e)
            })
            
            if verbose:
                print(f"\n❌ Ошибка: {e}")
    
    # Финальная статистика
    if verbose:
        print("\n" + "=" * 80)
        print("📊 ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 80)
        print(f"\n📁 Файлы:")
        print(f"   Всего: {len(files)}")
        print(f"   ✅ Успешно: {len(reports)}")
        print(f"   ❌ Ошибок: {len(failed_reports)}")
        
        print(f"\n💰 Транзакции:")
        print(f"   Всего: {total_transactions}")
        print(f"   Сумма: {total_amount:,.2f} тг")
        print(f"   Комиссия: {total_commission:,.2f} тг")
        
        if failed_reports:
            print(f"\n❌ Ошибки:")
            for failed in failed_reports:
                print(f"   • {failed['file_name']}: {failed['error']}")
        
        print("\n" + "=" * 80)
    
    return {
        'total_files': len(files),
        'success_files': len(reports),
        'failed_files': len(failed_reports),
        'total_transactions': total_transactions,
        'total_amount': total_amount,
        'total_commission': total_commission,
        'reports': reports,
        'failed_reports': failed_reports
    }


def compare_pdf_with_db(
    pdf_path: str,
    db,
    amount_tolerance_percent: float = 2.0,
    write_commissions: bool = False,
    verbose: bool = True,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    save_not_matched_to: Optional[str] = None,
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Парсит PDF и сопоставляет транзакции с БД напрямую (БЕЗ создания Excel).
    Использует обновленный маппинг терминалов с поддержкой всех вариантов адресов.
    
    Args:
        pdf_path: Путь к PDF файлу
        db: SQLAlchemy сессия базы данных
        amount_tolerance_percent: Погрешность по сумме в процентах (по умолчанию 2.0%)
        write_commissions: Записывать ли комиссии в БД (по умолчанию False)
        verbose: Детальное логирование (по умолчанию True)
        date_from: Начальный день месяца для фильтрации (включительно), например 13
        date_to: Конечный день месяца для фильтрации (включительно), например 18
        save_not_matched_to: Путь к JSON файлу для несовпавших транзакций (опционально)
        dry_run: Режим тестирования без записи в БД (по умолчанию True)
        
    Returns:
        Словарь с результатами сопоставления:
        {
            'total_transactions': int,           # Всего транзакций в PDF
            'matched': int,                      # Найдено совпадений в БД
            'not_matched': int,                  # Не найдено в БД
            'match_percentage': float,           # Процент совпадений
            'commissions_written': int,          # Записано комиссий (если write_commissions=True)
            'matched_transactions': list,        # Список совпавших транзакций
            'not_matched_transactions': list,    # Список несовпавших транзакций
        }
    """
    from utils.terminal_report_parsing import (
        match_transaction_with_order,
        calculate_commission,
        update_order_commission,
        save_not_matched_transactions
    )
    
    if verbose:
        print("\n" + "=" * 80)
        print("🔍 СОПОСТАВЛЕНИЕ PDF С БД")
        print("=" * 80)
        
        if dry_run:
            print("\n⚠️  РЕЖИМ ТЕСТИРОВАНИЯ (dry_run=True) - изменения НЕ будут записаны в БД")
        else:
            print("\n✅ РЕЖИМ ЗАПИСИ (dry_run=False) - изменения БУДУТ записаны в БД")
    
    # 1. Парсим PDF
    data = parse_pdf_terminal_report(pdf_path, verbose=verbose)
    transactions = data['transactions']
    
    # 2. Фильтруем по датам если нужно
    if date_from is not None or date_to is not None:
        filtered_transactions = []
        for transaction in transactions:
            date_str = transaction.get('Дата операции')
            if date_str:
                try:
                    if isinstance(date_str, str):
                        parts = date_str.split('.')
                        if len(parts) == 3:
                            day = int(parts[0])
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
                    pass
        
        if verbose:
            print(f"\n📅 Применен фильтр по датам: {date_from if date_from else 1} - {date_to if date_to else 31} число")
            print(f"   До фильтрации: {len(transactions)} транзакций")
            print(f"   После фильтрации: {len(filtered_transactions)} транзакций")
        
        transactions = filtered_transactions
    
    if verbose:
        print(f"\n📊 Параметры поиска:")
        print(f"  - Погрешность по сумме: ±{amount_tolerance_percent}%")
        print(f"  - Запись комиссий: {'ДА' if write_commissions else 'НЕТ'}")
        print(f"\n⏳ Обработка {len(transactions)} транзакций...")
    
    # 3. Сопоставляем с БД
    matched_transactions = []
    not_matched_transactions = []
    commissions_written = 0
    used_payment_transactions = set()  # Для отслеживания уже обработанных чеков
    
    for idx, transaction in enumerate(transactions, 1):
        if not verbose and idx % 10 == 0:
            print(f"  Обработано {idx}/{len(transactions)} транзакций...")
        
        # Ищем соответствующий заказ
        match = match_transaction_with_order(
            transaction,
            db,
            time_tolerance_minutes=15,  # не используется
            amount_tolerance_percent=amount_tolerance_percent,
            verbose_logging=verbose,
            transaction_num=idx,
            used_payment_transactions=used_payment_transactions
        )
        
        if match:
            # Добавляем payment_transaction_id в использованные
            payment_id = match.get('payment_transaction_id')
            if payment_id:
                used_payment_transactions.add(payment_id)
            
            matched_transactions.append({
                'terminal_transaction': transaction,
                'order': match['order'],
                'check_sales': match['check_sales'],
                'payment_transaction_id': payment_id,
                'check_sum': match['check_sum'],
                'is_multi_check_order': match.get('is_multi_check_order', False),
                'order_checks_count': match.get('order_checks_count', 1),
                'match_confidence': match['match_confidence']
            })
            
            # Записываем комиссию если нужно (только если не dry_run)
            if write_commissions and not dry_run:
                commission = calculate_commission(transaction)
                if commission > 0:
                    order = match['order']
                    is_multi_check = match.get('is_multi_check_order', False)
                    
                    if is_multi_check:
                        # Заказ с несколькими чеками - СУММИРУЕМ
                        existing_commission = float(order.bank_commission or 0)
                        total_commission = existing_commission + commission
                        
                        success = update_order_commission(order.id, total_commission, db)
                        if success:
                            commissions_written += 1
                    else:
                        # Заказ с одним чеком - просто записываем
                        success = update_order_commission(order.id, commission, db)
                        if success:
                            commissions_written += 1
        else:
            not_matched_transactions.append(transaction)
    
    # 4. Подсчитываем статистику
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
    }
    
    if verbose:
        print("\n" + "=" * 80)
        print("📈 СТАТИСТИКА СОПОСТАВЛЕНИЯ")
        print("=" * 80)
        print(f"\n✅ Найдено совпадений: {matched} ({match_percentage:.1f}%)")
        print(f"❌ Не найдено: {not_matched} ({100 - match_percentage:.1f}%)")
        print(f"📊 Всего транзакций: {total}")
        
        if write_commissions:
            print(f"\n💾 Записано комиссий: {commissions_written}")
        
        print(f"\n💰 Финансовая статистика:")
        print(f"  - Сумма операций: {data['total_amount']:,.2f} тг")
        print(f"  - Комиссия: {data['total_commission']:,.2f} тг")
    
    # 5. Сохраняем несовпавшие если нужно
    if save_not_matched_to and not_matched_transactions:
        metadata = {
            'source_file': pdf_path,
            'source_type': 'pdf',
            'processing_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_transactions': total,
            'matched': matched,
            'not_matched': not_matched,
            'match_percentage': match_percentage,
            'parameters': {
                'amount_tolerance_percent': amount_tolerance_percent,
                'date_from': date_from,
                'date_to': date_to
            }
        }
        
        save_not_matched_transactions(
            not_matched_transactions,
            save_not_matched_to,
            metadata
        )
        
        if verbose:
            print(f"\n💾 Несовпавшие транзакции сохранены в: {save_not_matched_to}")
    
    return result


def process_pdf_directory_with_db(
    directory_path: str,
    db,
    amount_tolerance_percent: float = 2.0,
    write_commissions: bool = False,
    verbose: bool = True,
    date_from: Optional[int] = None,
    date_to: Optional[int] = None,
    save_not_matched_to: Optional[str] = None,
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Парсит все PDF из папки и сопоставляет с БД.
    
    Args:
        directory_path: Путь к папке с PDF
        db: SQLAlchemy сессия
        amount_tolerance_percent: Погрешность по сумме
        write_commissions: Записывать ли комиссии
        verbose: Детальное логирование
        date_from: С какого числа
        date_to: По какое число
        save_not_matched_to: Путь для сохранения несовпавших
        
    Returns:
        Сводная статистика по всем файлам
    """
    import glob
    
    if verbose:
        print("\n" + "=" * 80)
        print("🔍 ОБРАБОТКА ПАПКИ С PDF + СОПОСТАВЛЕНИЕ С БД")
        print("=" * 80)
    
    files = glob.glob(os.path.join(directory_path, "*.pdf"))
    
    if verbose:
        print(f"\n📁 Папка: {directory_path}")
        print(f"📊 Найдено PDF файлов: {len(files)}")
        if date_from or date_to:
            print(f"📅 Фильтр: {date_from or 1} - {date_to or 31} число")
        print()
    
    total_matched = 0
    total_not_matched = 0
    total_commissions_written = 0
    all_not_matched = []
    file_results = []
    
    for idx, pdf_path in enumerate(files, 1):
        file_name = os.path.basename(pdf_path)
        
        if verbose:
            print(f"\n{'='*80}")
            print(f"📄 Файл {idx}/{len(files)}: {file_name}")
            print('='*80)
        
        try:
            result = compare_pdf_with_db(
                pdf_path,
                db,
                amount_tolerance_percent=amount_tolerance_percent,
                write_commissions=write_commissions,
                verbose=verbose,
                date_from=date_from,
                date_to=date_to,
                save_not_matched_to=None,  # не сохраняем для каждого файла
                dry_run=dry_run
            )
            
            total_matched += result['matched']
            total_not_matched += result['not_matched']
            total_commissions_written += result['commissions_written']
            all_not_matched.extend(result['not_matched_transactions'])
            
            file_results.append({
                'file_name': file_name,
                'result': result
            })
            
        except Exception as e:
            if verbose:
                print(f"\n❌ Ошибка при обработке файла: {e}")
    
    # Итоговая статистика
    if verbose:
        print("\n" + "=" * 80)
        print("📊 ИТОГОВАЯ СТАТИСТИКА ПО ВСЕМ ФАЙЛАМ")
        print("=" * 80)
        print(f"\n✅ Всего найдено в БД: {total_matched}")
        print(f"❌ Всего не найдено: {total_not_matched}")
        
        if total_matched + total_not_matched > 0:
            match_percent = (total_matched / (total_matched + total_not_matched)) * 100
            print(f"📊 Процент совпадений: {match_percent:.1f}%")
        
        if write_commissions:
            print(f"\n💾 Всего записано комиссий: {total_commissions_written}")
    
    # Сохраняем все несовпавшие
    if save_not_matched_to and all_not_matched:
        from utils.terminal_report_parsing import save_not_matched_transactions
        
        metadata = {
            'source_directory': directory_path,
            'source_type': 'pdf_directory',
            'total_files': len(files),
            'processing_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_matched': total_matched,
            'total_not_matched': total_not_matched,
            'parameters': {
                'amount_tolerance_percent': amount_tolerance_percent,
                'date_from': date_from,
                'date_to': date_to
            }
        }
        
        save_not_matched_transactions(all_not_matched, save_not_matched_to, metadata)
        
        if verbose:
            print(f"\n💾 Несовпавшие транзакции сохранены: {save_not_matched_to}")
    
    return {
        'total_files': len(files),
        'total_matched': total_matched,
        'total_not_matched': total_not_matched,
        'total_commissions_written': total_commissions_written,
        'file_results': file_results,
        'all_not_matched_transactions': all_not_matched
    }


# Пример использования
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'inspect':
            # Режим просмотра PDF
            test_file = r"temp_files\terminals_report_pdf\БЦК Выписка POS с 2025-10-13 по 2025-10-19 (1).pdf"
            if len(sys.argv) > 2:
                test_file = sys.argv[2]
            
            print("🔍 РЕЖИМ ПРОСМОТРА PDF ФАЙЛА\n")
            inspect_pdf_file(test_file, max_pages=2)
            sys.exit(0)
        
        elif sys.argv[1] == 'convert':
            # Режим конвертации
            test_file = r"temp_files\terminals_report_pdf\БЦК Выписка POS с 2025-10-13 по 2025-10-19 (1).pdf"
            if len(sys.argv) > 2:
                test_file = sys.argv[2]
            
            print("🔄 РЕЖИМ КОНВЕРТАЦИИ PDF → EXCEL\n")
            excel_path = convert_pdf_to_excel(test_file, verbose=True)
            print(f"\n✅ Готово! Файл: {excel_path}")
            sys.exit(0)
        
        elif sys.argv[1] == 'parse':
            # Режим полного парсинга
            test_file = r"temp_files\terminals_report_pdf\БЦК Выписка POS с 2025-10-13 по 2025-10-19 (1).pdf"
            if len(sys.argv) > 2:
                test_file = sys.argv[2]
            
            print("📋 РЕЖИМ ПАРСИНГА PDF\n")
            data = parse_pdf_terminal_report(test_file, verbose=True)
            
            print(f"\n✅ Результат:")
            print(f"   Транзакций: {data['total_transactions']}")
            print(f"   Сумма: {data['total_amount']:,.2f} тг")
            print(f"   Комиссия: {data['total_commission']:,.2f} тг")
            sys.exit(0)
        
        elif sys.argv[1] == 'directory':
            # Режим парсинга папки
            test_dir = r"temp_files\terminals_report_pdf"
            if len(sys.argv) > 2:
                test_dir = sys.argv[2]
            
            print("📂 РЕЖИМ ПАРСИНГА ПАПКИ С PDF\n")
            result = parse_pdf_directory(test_dir, verbose=True)
            
            print(f"\n✅ Итого:")
            print(f"   Файлов обработано: {result['success_files']}/{result['total_files']}")
            print(f"   Транзакций: {result['total_transactions']}")
            print(f"   Сумма: {result['total_amount']:,.2f} тг")
            sys.exit(0)
    
    # По умолчанию - справка
    print("=" * 80)
    print("PDF ПАРСЕР ОТЧЕТОВ ТЕРМИНАЛОВ")
    print("=" * 80)
    print("\nИспользование:")
    print("  python utils/pdf_terminal_report_parsing.py inspect [файл.pdf]")
    print("  python utils/pdf_terminal_report_parsing.py convert [файл.pdf]")
    print("  python utils/pdf_terminal_report_parsing.py parse [файл.pdf]")
    print("  python utils/pdf_terminal_report_parsing.py directory [папка]")
    print("\nПримеры:")
    print('  python utils/pdf_terminal_report_parsing.py inspect "выписка.pdf"')
    print('  python utils/pdf_terminal_report_parsing.py directory temp_files/terminals_report_pdf')
    print("\n" + "=" * 80)

