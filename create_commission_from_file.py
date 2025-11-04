'''
Создание банковских комиссий из одного файла с фильтрацией по датам
'''

import sys
import os
from datetime import datetime
from utils.commission_reports.parsing_reports import parse_file, normalize_transaction_data, create_bank_commission

# Настройка кодировки для Windows консоли
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def create_commissions_from_single_file(
    file_path: str,
    start_date: str = None,
    end_date: str = None
):
    """
    Создает банковские комиссии из одного файла с фильтрацией по датам.
    
    Args:
        file_path: путь к файлу (Excel или PDF)
        start_date: начальная дата в формате 'YYYY-MM-DD' или 'DD.MM.YYYY' (опционально)
        end_date: конечная дата в формате 'YYYY-MM-DD' или 'DD.MM.YYYY' (опционально)
    """
    print("=" * 80)
    print("СОЗДАНИЕ БАНКОВСКИХ КОМИССИЙ ИЗ ФАЙЛА")
    print("=" * 80)
    print(f"Файл: {file_path}")
    
    # Проверяем существование файла
    if not os.path.exists(file_path):
        print(f"[!] Ошибка: Файл не найден: {file_path}")
        return
    
    # Определяем тип файла
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext in ['.xlsx', '.xls']:
        file_type = 'xlsx'
    elif file_ext == '.pdf':
        file_type = 'pdf'
    else:
        print(f"[!] Ошибка: Неподдерживаемый формат файла: {file_ext}")
        return
    
    print(f"Тип файла: {file_type.upper()}")
    
    # Парсим даты если указаны
    start_datetime = None
    end_datetime = None
    
    if start_date:
        try:
            # Пробуем разные форматы
            if '.' in start_date:
                start_datetime = datetime.strptime(start_date, '%d.%m.%Y')
            else:
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            print(f"Начальная дата: {start_datetime.strftime('%d.%m.%Y')}")
        except ValueError:
            print(f"[!] Ошибка: Неверный формат начальной даты. Используйте 'YYYY-MM-DD' или 'DD.MM.YYYY'")
            return
    
    if end_date:
        try:
            # Пробуем разные форматы
            if '.' in end_date:
                end_datetime = datetime.strptime(end_date, '%d.%m.%Y')
            else:
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
            # Устанавливаем время на конец дня
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
            print(f"Конечная дата: {end_datetime.strftime('%d.%m.%Y')}")
        except ValueError:
            print(f"[!] Ошибка: Неверный формат конечной даты. Используйте 'YYYY-MM-DD' или 'DD.MM.YYYY'")
            return
    
    if not start_date and not end_date:
        print("Период: Все даты")
    
    print("-" * 80)
    
    # Парсим файл
    print("\n[*] Шаг 1: Парсинг файла...")
    raw_transactions = parse_file(file_path, file_type)
    print(f"[+] Найдено транзакций в файле: {len(raw_transactions)}")
    
    if not raw_transactions:
        print("[!] Транзакции не найдены в файле")
        return
    
    # Нормализуем данные
    print("\n[*] Шаг 2: Нормализация данных...")
    normalized_transactions = normalize_transaction_data(raw_transactions)
    print(f"[+] Нормализовано транзакций: {len(normalized_transactions)}")
    
    # Фильтруем по датам
    filtered_transactions = []
    
    if start_datetime or end_datetime:
        print("\n[*] Шаг 3: Фильтрация по датам...")
        
        for t in normalized_transactions:
            if t.get('date'):
                try:
                    # Парсим дату транзакции
                    if isinstance(t['date'], str):
                        trans_datetime = datetime.strptime(t['date'], '%Y-%m-%d %H:%M:%S')
                    else:
                        trans_datetime = t['date']
                    
                    # Проверяем вхождение в диапазон
                    if start_datetime and trans_datetime < start_datetime:
                        continue
                    if end_datetime and trans_datetime > end_datetime:
                        continue
                    
                    filtered_transactions.append(t)
                except Exception as e:
                    print(f"[!] Ошибка парсинга даты '{t['date']}': {e}")
                    continue
        
        print(f"[+] Транзакций после фильтрации: {len(filtered_transactions)}")
    else:
        filtered_transactions = normalized_transactions
        print("\n[*] Шаг 3: Фильтрация по датам пропущена (не указаны даты)")
    
    if not filtered_transactions:
        print("[!] Нет транзакций в указанном диапазоне дат")
        return
    
    # Фильтруем транзакции с комиссией
    transactions_with_commission = [
        t for t in filtered_transactions 
        if t.get('commission') is not None and t['commission'] != 0
    ]
    
    print(f"\n[*] Транзакций с комиссией: {len(transactions_with_commission)}")
    
    if not transactions_with_commission:
        print("[!] Нет транзакций с комиссией в указанном диапазоне")
        return
    
    # Статистика
    positive_count = sum(1 for t in transactions_with_commission if t['commission'] > 0)
    negative_count = sum(1 for t in transactions_with_commission if t['commission'] < 0)
    positive_sum = sum(t['commission'] for t in transactions_with_commission if t['commission'] > 0)
    negative_sum = sum(t['commission'] for t in transactions_with_commission if t['commission'] < 0)
    total_sum = positive_sum + negative_sum
    
    print("\n" + "=" * 80)
    print("СТАТИСТИКА ПЕРЕД ЗАПИСЬЮ В БД:")
    print("=" * 80)
    print(f"Транзакций с комиссией: {len(transactions_with_commission)}")
    print(f"  - Положительных (+): {positive_count} шт, сумма: +{positive_sum:.2f} тг")
    print(f"  - Отрицательных (-): {negative_count} шт, сумма: {negative_sum:.2f} тг")
    print(f"  - ИТОГО: {total_sum:.2f} тг")
    print("=" * 80)
    
    # Подтверждение
    print("\n[?] Создать комиссии в базе данных?")
    print("    Введите 'да' или 'yes' для подтверждения, или любой другой ввод для отмены:")
    confirmation = input(">>> ").strip().lower()
    
    if confirmation not in ['да', 'yes', 'y']:
        print("[!] Отменено пользователем")
        return
    
    # Создаем комиссии в БД
    print("\n[*] Шаг 4: Создание комиссий в базе данных...")
    try:
        create_bank_commission(transactions_with_commission)
        print(f"[+] Успешно создано {len(transactions_with_commission)} комиссий в БД!")
    except Exception as e:
        print(f"[!] Ошибка при создании комиссий: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 80)
    print("✓ ГОТОВО!")
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Создание банковских комиссий из одного файла с фильтрацией по датам'
    )
    parser.add_argument(
        'file_path',
        nargs='?',
        default="temp_files/terminals_report/Sales_Report_01.09.2025 - 25.10.2025 (1).xlsx",
        help='Путь к файлу (Excel или PDF)'
    )
    parser.add_argument(
        '--start-date',
        '-s',
        type=str,
        help='Начальная дата (формат: YYYY-MM-DD или DD.MM.YYYY)'
    )
    parser.add_argument(
        '--end-date',
        '-e',
        type=str,
        help='Конечная дата (формат: YYYY-MM-DD или DD.MM.YYYY)'
    )
    parser.add_argument(
        '--no-confirm',
        action='store_true',
        help='Не запрашивать подтверждение перед созданием комиссий'
    )
    
    args = parser.parse_args()
    
    # Если указан флаг --no-confirm, пропускаем подтверждение
    if args.no_confirm:
        # Временно подменяем функцию подтверждения
        original_function = create_commissions_from_single_file
        
        def wrapper(file_path, start_date=None, end_date=None):
            # Перехватываем подтверждение
            import builtins
            original_input = builtins.input
            builtins.input = lambda x: 'да'
            
            try:
                result = original_function(file_path, start_date, end_date)
            finally:
                builtins.input = original_input
            
            return result
        
        wrapper(args.file_path, args.start_date, args.end_date)
    else:
        create_commissions_from_single_file(
            file_path=args.file_path,
            start_date=args.start_date,
            end_date=args.end_date
        )

