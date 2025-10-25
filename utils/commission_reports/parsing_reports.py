"""
Парсер отчетов с комиссиями терминалов оплаты

Этот модуль предоставляет функции для парсинга PDF и Excel файлов 
с отчетами терминалов оплаты и нормализации данных в единый формат.

Основные функции:
-----------------
- scan_reports_folder(folder_path) - сканирует папку и находит PDF и Excel файлы
- parse_file(file_path, file_type) - парсит файл используя существующие парсеры проекта
- normalize_transaction_data(raw_data) - нормализует данные в единый формат

Использует существующие парсеры:
- utils.pdf_terminal_report_parsing - для PDF файлов
- utils.terminal_report_parsing - для Excel файлов

Пример использования:
--------------------
    from utils.commission_reports.parsing_reports import (
        scan_reports_folder, 
        parse_file, 
        normalize_transaction_data
    )
    
    # Сканируем папку
    files = scan_reports_folder("reports/")
    
    # Парсим все файлы
    all_data = []
    for pdf_file in files['pdf_reports']:
        data = parse_file(pdf_file, 'pdf')
        all_data.extend(data)
    
    for xlsx_file in files['xlsx_reports']:
        data = parse_file(xlsx_file, 'xlsx')
        all_data.extend(data)
    
    # Нормализуем данные
    normalized = normalize_transaction_data(all_data)
    
    # Результат: массив словарей с полями:
    # - date: дата транзакции
    # - amount: сумма транзакции
    # - terminal_address: адрес терминала
    # - commission: комиссия
    # - file_path: путь к файлу
    # - transaction: исходные данные
"""

import os
from typing import Dict, List, Any
import traceback
from datetime import datetime


def scan_reports_folder(folder_path: str) -> Dict[str, List[str]]:
    """
    Сканирует папку и возвращает списки PDF и XLSX файлов.
    
    Args:
        folder_path: путь к папке с отчетами
        
    Returns:
        словарь с ключами 'pdf_reports' и 'xlsx_reports'
    """
    pdf_reports = []
    xlsx_reports = []
    
    if not os.path.exists(folder_path):
        return {"pdf_reports": pdf_reports, "xlsx_reports": xlsx_reports}

    for file in os.listdir(folder_path):
        if 'terminals_report_pdf' in folder_path:
            # В папке PDF только PDF файлы
            if file.endswith('.pdf'):
                pdf_reports.append(os.path.join(folder_path, file))
        else:
            # В обычной папке PDF и Excel файлы
            if file.endswith('.xlsx') or file.endswith('.XLSX'):
                xlsx_reports.append(os.path.join(folder_path, file))

    return {"pdf_reports": pdf_reports, "xlsx_reports": xlsx_reports}
    

def parse_file(file_path: str, file_type: str) -> List[Dict[str, Any]]:
    """
    Парсит файл и извлекает данные таблиц.
    Использует существующие парсеры из проекта.
    
    Args:
        file_path: путь к файлу
        file_type: тип файла ('pdf' или 'xlsx')
        
    Returns:
        массив словарей с данными из таблиц
    """
    data = []
    
    try:
        if file_type.lower() == 'pdf':
            # Используем существующий PDF парсер
            from utils.pdf_terminal_report_parsing import parse_pdf_terminal_report
            
            report_data = parse_pdf_terminal_report(file_path, verbose=False)
            
            # Извлекаем транзакции и добавляем file_path
            for transaction in report_data.get('transactions', []):
                transaction['file_path'] = file_path
                data.append(transaction)
        
        elif file_type.lower() in ['xlsx', 'xls']:
            # Используем существующий Excel парсер
            from utils.terminal_report_parsing import parse_terminal_report
            
            report_data = parse_terminal_report(file_path)
            
            # Извлекаем транзакции и добавляем file_path
            for transaction in report_data.get('transactions', []):
                transaction['file_path'] = file_path
                data.append(transaction)
    
    except Exception as e:
        print(f"Ошибка при парсинге файла {file_path}: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return data


def normalize_transaction_data(raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Нормализует данные транзакций в единый формат.
    
    Args:
        raw_data: массив словарей с сырыми данными
        
    Returns:
        массив нормализованных словарей
    """
    normalized_data = []
    errors = []
    
    for transaction in raw_data:
        try:
            normalized_transaction = {
                "date": None,
                "amount": None,
                "terminal_address": None,
                "commission": None,
                "file_path": transaction.get('file_path', ''),
                "transaction": transaction
            }
            
            # Извлекаем дату и время - пробуем разные поля
            date_fields = [
                'Дата операции', 'Дата и время транзакции', 'Дата', 'date',
                'Транзакция\nкүні / Дата\nтранзакции', 'Дата транзакции',
                'Транзакция күні / Дата транзакции'
            ]
            
            # Также ищем отдельно время
            time_fields = [
                'Время', 'Время операции', 'Время транзакции', 'time'
            ]
            
            date_str = None
            time_str = None
            
            # Ищем дату
            for field in date_fields:
                if field in transaction and transaction[field]:
                    date_str = str(transaction[field])
                    break
            
            # Ищем время
            for field in time_fields:
                if field in transaction and transaction[field]:
                    time_str = str(transaction[field])
                    break
            
            # Преобразуем в строку формата YYYY-MM-DD HH:MM:SS
            if date_str:
                try:
                    # Если дата уже содержит время (например, "15.10.2025 19:04:27")
                    if ' ' in date_str and ':' in date_str:
                        # Формат: DD.MM.YYYY HH:MM:SS -> YYYY-MM-DD HH:MM:SS
                        date_part, time_part = date_str.split(' ', 1)
                        day, month, year = date_part.split('.')
                        normalized_transaction["date"] = f"{year}-{month.zfill(2)}-{day.zfill(2)} {time_part}"
                    
                    # Если дата в формате DD.MM.YYYY
                    elif '.' in date_str and len(date_str.split('.')) == 3:
                        day, month, year = date_str.split('.')
                        date_formatted = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        
                        # Добавляем время если найдено
                        if time_str and ':' in time_str:
                            time_parts = time_str.split(':')
                            if len(time_parts) >= 2:
                                hour = time_parts[0].zfill(2)
                                minute = time_parts[1].zfill(2)
                                second = time_parts[2].zfill(2) if len(time_parts) > 2 else "00"
                                normalized_transaction["date"] = f"{date_formatted} {hour}:{minute}:{second}"
                            else:
                                normalized_transaction["date"] = f"{date_formatted} 00:00:00"
                        else:
                            normalized_transaction["date"] = f"{date_formatted} 00:00:00"
                    
                    # Если дата в формате YYYY-MM-DD
                    elif '-' in date_str and len(date_str.split('-')) == 3:
                        date_formatted = date_str
                        
                        # Добавляем время если найдено
                        if time_str and ':' in time_str:
                            time_parts = time_str.split(':')
                            if len(time_parts) >= 2:
                                hour = time_parts[0].zfill(2)
                                minute = time_parts[1].zfill(2)
                                second = time_parts[2].zfill(2) if len(time_parts) > 2 else "00"
                                normalized_transaction["date"] = f"{date_formatted} {hour}:{minute}:{second}"
                            else:
                                normalized_transaction["date"] = f"{date_formatted} 00:00:00"
                        else:
                            normalized_transaction["date"] = f"{date_formatted} 00:00:00"
                    
                    # Если дата в формате ISO (2025-10-15T19:04:27Z)
                    elif 'T' in date_str:
                        date_part = date_str.split('T')[0]
                        time_part = date_str.split('T')[1].rstrip('Z')
                        normalized_transaction["date"] = f"{date_part} {time_part}"
                    
                    else:
                        # Если формат не распознан, сохраняем как есть
                        normalized_transaction["date"] = date_str
                    
                except Exception as e:
                    # Если не удалось распарсить, сохраняем как строку
                    normalized_transaction["date"] = date_str
                    print(f"⚠️ Не удалось распарсить дату '{date_str}': {e}")
            else:
                normalized_transaction["date"] = None
            
            # Извлекаем сумму - пробуем разные поля
            amount_fields = [
                'Сумма операции (т)', 'Сумма транзакции', 'Сумма', 
                'amount', 'Сумма операции', 'Сумма к зачислению/ списанию (т)',
                'Сумма транзакции в валюте транзакции', 'Сумма\nтранзакции',
                'Сумма транзакции в валюте транзакции'
            ]
            for field in amount_fields:
                if field in transaction and transaction[field]:
                    try:
                        amount = float(transaction[field])
                        normalized_transaction["amount"] = amount
                        break
                    except (ValueError, TypeError):
                        # Пробуем извлечь число из строки
                        try:
                            clean_value = ''.join(c for c in str(transaction[field]) if c.isdigit() or c in '.,')
                            if clean_value:
                                normalized_transaction["amount"] = float(clean_value.replace(',', '.'))
                                break
                        except:
                            pass
            
            # Извлекаем адрес терминала - пробуем разные поля
            address_fields = [
                'Адрес точки продаж', 'Адрес торговой точки', 'Адрес', 
                'terminal_address', 'Адрес\nторговой точки', 'Адрес\nточки продаж',
                'Транзакция\nмекенжайы /\nАдрес\nтранзакции', 'Адрес транзакции',
                'Транзакция мекенжайы / Адрес транзакции',
                'Адрес\nустановки\nустройства', 'Адрес установки устройства',
                'Адрес установки', 'Адрес устройства'
            ]
            for field in address_fields:
                if field in transaction and transaction[field]:
                    normalized_transaction["terminal_address"] = str(transaction[field])
                    break
            
            # Извлекаем комиссию - пробуем разные поля
            commission_fields = [
                'Комиссия за операции (т)', 'Комиссия Kaspi Pay (т)', 
                'Комиссия', 'commission', 'Комиссия за операции по карте (т)',
                'Комиссия за обеспечение платежа (т)', 'Комиссия Kaspi Travel (т)',
                'Общая комиссия банка', 'Общая\nкомиссия\nбанка',
                'Сумма комиссии', 'Комиссия банка'
            ]
            total_commission = 0.0
            for field in commission_fields:
                if field in transaction and transaction[field]:
                    try:
                        commission = float(transaction[field])
                        total_commission += abs(commission)  # Берем по модулю
                    except (ValueError, TypeError):
                        try:
                            clean_value = ''.join(c for c in str(transaction[field]) if c.isdigit() or c in '.,')
                            if clean_value:
                                commission = float(clean_value.replace(',', '.'))
                                total_commission += abs(commission)
                        except:
                            pass
            
            if total_commission > 0:
                normalized_transaction["commission"] = total_commission
            
            # Если комиссия не найдена, но есть сумма операции и сумма к зачислению
            if normalized_transaction["commission"] is None:
                amount = normalized_transaction.get("amount")
                if amount:
                    # Пробуем найти сумму к зачислению
                    credit_fields = [
                        'Сумма к зачислению/ списанию (т)', 'Сумма к зачислению', 
                        'Сумма к\nзачислению', 'Сумма\nк зачислению'
                    ]
                    for field in credit_fields:
                        if field in transaction and transaction[field]:
                            try:
                                credit_amount = float(transaction[field])
                                commission = amount - credit_amount
                                if commission != 0:
                                    normalized_transaction["commission"] = abs(commission)
                                break
                            except (ValueError, TypeError):
                                pass
            
            normalized_data.append(normalized_transaction)
            
        except Exception as e:
            error_info = {
                "transaction": transaction,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            errors.append(error_info)
    
    # Выводим ошибки
    if errors:
        print("Ошибки при нормализации данных:")
        for i, error in enumerate(errors, 1):
            print(f"Ошибка {i}: {error['error']}")
            print(f"Данные: {error['transaction']}")
            print("-" * 50)
    
    return normalized_data

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

def create_bank_commission(transactions: list[dict]) -> bool:
    """
    Создает комиссии в базе данных.
    """
    from database.database import SessionLocal
    from models.bank_commission import BankCommission
    from models.organization import Organization
    session = SessionLocal()
    for transaction in transactions:
        if transaction.get('commission') is None:
            print(f"   ⚠️ Комиссия не найдена в транзакции")
            print(transaction)
            continue
        department_code = get_department_code_by_terminal(transaction['terminal_address'])
        organization_id = None
        if department_code:
            organization = session.query(Organization).filter(Organization.code == department_code).first()
            if organization:
                organization_id = organization.id
        
        date_and_time = datetime.strptime(transaction['date'], '%Y-%m-%d %H:%M:%S')
        bank_commission = BankCommission(
            amount=transaction['amount'],
            bank_commission=transaction['commission'],
            organization_id=organization_id,
            time_transaction=date_and_time,
            source=transaction['file_path'],
        )
        session.add(bank_commission)
    session.commit()
    session.close()