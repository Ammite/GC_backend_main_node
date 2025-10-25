"""
Скрипт для экспорта данных из d_orders и sales в Excel
С фильтрацией по датам и типам карт
"""
import sys
import io

# Настройка кодировки для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import pandas as pd
import config
from models.d_order import DOrder
from models.sales import Sales

# Подключение к БД
DATABASE_URL = config.DATABASE_URL
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def export_to_excel(start_date='2025-10-13 00:00:00', end_date='2025-10-19 00:00:00', output_file=None):
    """
    Экспортирует данные из d_orders и sales в Excel
    
    Args:
        start_date: Начальная дата фильтра (строка или datetime)
        end_date: Конечная дата фильтра (строка или datetime)
        output_file: Имя файла для сохранения (по умолчанию генерируется автоматически)
    """
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("ЭКСПОРТ ДАННЫХ ИЗ D_ORDERS И SALES В EXCEL")
        print("=" * 80)
        print()
        
        # Преобразуем строки в datetime если нужно
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
        
        print(f"Период: с {start_date} по {end_date}")
        print()
        
        # Список исключаемых типов карт
        excluded_card_types = [
            '(нет карты)',
            'Glovo Интеграция Безнал',
            'Wolt Интеграция Безнал',
            'Yandex Интеграция Безнал',
            'Оплата онлайн стартер',
            'KASPI QR'
        ]
        
        print("Выполняем запрос к базе данных...")
        
        # Выполняем JOIN запрос
        query = db.query(
            DOrder.iiko_id.label('iiko_id'),
            DOrder.time_order.label('time_order'),
            Sales.dish_name.label('dish_name'),
            DOrder.discount.label('price'),
            DOrder.bank_commission.label('bank_commission'),
            Sales.card_type_name.label('card_type_name'),
            Sales.conception.label('conception')
        ).join(
            Sales,
            DOrder.iiko_id == Sales.order_id
        ).filter(
            and_(
                DOrder.time_order >= start_date,
                DOrder.time_order < end_date,
                Sales.dish_amount_int != 0,
                DOrder.bank_commission.is_(None),  # Только записи без комиссии
                Sales.card_type_name.notin_(excluded_card_types)
            )
        ).order_by(DOrder.iiko_id.asc())  # Сортировка по iiko_id
        
        # Получаем результаты
        results = query.all()
        
        print(f"Найдено записей: {len(results)}")
        print()
        
        if not results:
            print("⚠ Данные не найдены для указанных критериев!")
            return
        
        # Преобразуем в DataFrame
        print("Создаем DataFrame...")
        data = []
        for row in results:
            data.append({
                'iiko_id': row.iiko_id,
                'Время заказа': row.time_order,
                'Название блюда': row.dish_name,
                'Цена': row.price,
                'Комиссия банка': row.bank_commission,
                'Тип карты': row.card_type_name,
                'Концепция': row.conception
            })
        
        df = pd.DataFrame(data)
        
        # Форматируем даты
        if 'Время заказа' in df.columns:
            df['Время заказа'] = pd.to_datetime(df['Время заказа'])
        
        # Генерируем имя файла если не указано
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            date_range = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
            output_file = f"orders_sales_export_{date_range}_{timestamp}.xlsx"
        
        # Сохраняем в Excel
        print(f"Сохраняем в файл: {output_file}")
        
        # Используем openpyxl для поддержки русского языка
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Данные', index=False)
            
            # Получаем workbook и worksheet для форматирования
            workbook = writer.book
            worksheet = writer.sheets['Данные']
            
            # Автоматически настраиваем ширину столбцов
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if cell.value:
                            cell_length = len(str(cell.value))
                            if cell_length > max_length:
                                max_length = cell_length
                    except:
                        pass
                
                adjusted_width = min(max_length + 2, 50)  # Максимум 50 символов
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        print()
        print("=" * 80)
        print("СТАТИСТИКА:")
        print("=" * 80)
        print(f"Всего записей экспортировано: {len(df)}")
        print(f"Период: {start_date.date()} - {end_date.date()}")
        
        # Дополнительная статистика
        if len(df) > 0:
            print()
            print("Распределение по типам карт:")
            card_type_stats = df['Тип карты'].value_counts()
            for card_type, count in card_type_stats.items():
                print(f"  - {card_type}: {count}")
            
            print()
            print("Распределение по концепциям:")
            conception_stats = df['Концепция'].value_counts()
            for conception, count in conception_stats.items():
                print(f"  - {conception}: {count}")
            
            # Статистика по комиссиям
            if 'Комиссия банка' in df.columns:
                total_commission = df['Комиссия банка'].sum()
                records_with_commission = df['Комиссия банка'].notna().sum()
                records_without_commission = df['Комиссия банка'].isna().sum()
                
                print()
                print("Статистика по комиссиям:")
                print(f"  - Записей с комиссией: {records_with_commission}")
                print(f"  - Записей без комиссии: {records_without_commission}")
                if total_commission:
                    print(f"  - Общая сумма комиссий: {total_commission:.2f}")
        
        print()
        print(f"✓ Данные успешно экспортированы в файл: {output_file}")
        print()
        
    except Exception as e:
        print(f"Ошибка при экспорте данных: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def get_distinct_card_types(start_date='2025-10-13 00:00:00', end_date='2025-10-19 00:00:00'):
    """
    Получает список всех уникальных типов карт за период
    """
    db = SessionLocal()
    
    try:
        # Преобразуем строки в datetime
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
        
        query = db.query(Sales.card_type_name).distinct().join(
            DOrder,
            Sales.order_id == DOrder.iiko_id
        ).filter(
            and_(
                DOrder.time_order >= start_date,
                DOrder.time_order < end_date,
                Sales.dish_amount_int != 0
            )
        )
        
        card_types = [row.card_type_name for row in query.all() if row.card_type_name]
        
        print("Уникальные типы карт в данных:")
        for card_type in sorted(card_types):
            print(f"  - {card_type}")
        
        return card_types
        
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Экспорт данных из d_orders и sales в Excel')
    parser.add_argument(
        '--start',
        type=str,
        default='2025-10-13 00:00:00',
        help='Начальная дата (формат: YYYY-MM-DD HH:MM:SS)'
    )
    parser.add_argument(
        '--end',
        type=str,
        default='2025-10-19 00:00:00',
        help='Конечная дата (формат: YYYY-MM-DD HH:MM:SS)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Имя выходного файла (по умолчанию генерируется автоматически)'
    )
    parser.add_argument(
        '--show-card-types',
        action='store_true',
        help='Показать все уникальные типы карт и выйти'
    )
    
    args = parser.parse_args()
    
    if args.show_card_types:
        get_distinct_card_types(args.start, args.end)
    else:
        export_to_excel(args.start, args.end, args.output)

