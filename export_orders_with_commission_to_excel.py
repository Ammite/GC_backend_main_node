"""
Скрипт для экспорта данных заказов с комиссиями в Excel
Выполняет группировку по iiko_id и агрегацию данных из d_orders и sales
"""
import sys
import io
import os

# Настройка кодировки для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from sqlalchemy import create_engine, and_, func, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import pandas as pd
import config
from models.d_order import DOrder
from models.sales import Sales
from models.organization import Organization

# Подключение к БД
DATABASE_URL = config.DATABASE_URL
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def export_orders_with_commission_to_excel(start_date='2025-10-13 00:00:00', end_date='2025-10-19 00:00:00', output_file=None):
    """
    Экспортирует данные заказов с комиссиями в Excel с группировкой по iiko_id
    
    Args:
        start_date: Начальная дата фильтра (строка или datetime)
        end_date: Конечная дата фильтра (строка или datetime)
        output_file: Имя файла для сохранения (по умолчанию генерируется автоматически)
    """
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("ЭКСПОРТ ЗАКАЗОВ С КОМИССИЯМИ В EXCEL")
        print("=" * 80)
        print()
        
        # Преобразуем строки в datetime если нужно
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
        
        print(f"Период: с {start_date} по {end_date}")
        print()
        
        print("Выполняем запрос к базе данных...")
        
        # Выполняем запрос с группировкой по iiko_id
        query = db.query(
            DOrder.iiko_id.label('iiko_id'),
            func.max(DOrder.time_order).label('time_order'),
            func.max(DOrder.discount).label('price'),
            func.max(DOrder.bank_commission).label('bank_commission'),
            func.min(Sales.card_type_name).label('card_type_name'),
            func.min(Sales.conception).label('conception'),
            func.string_agg(Sales.dish_name, text("', ' ORDER BY dish_name")).label('dish_list')  # Для PostgreSQL
        ).join(
            Sales,
            DOrder.iiko_id == Sales.order_id
        ).filter(
            and_(
                DOrder.time_order >= start_date,
                DOrder.time_order < end_date,
                DOrder.discount != 0  # Только заказы с ненулевой скидкой
            )
        ).group_by(
            DOrder.iiko_id
        ).order_by(
            DOrder.iiko_id.asc()
        )
        
        # Получаем результаты
        results = query.all()
        
        print(f"Найдено заказов: {len(results)}")
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
                'Цена (скидка)': row.price,
                'Комиссия банка': row.bank_commission,
                'Тип карты': row.card_type_name,
                'Концепция': row.conception,
                'Список блюд': row.dish_list
            })
        
        df = pd.DataFrame(data)
        
        # Форматируем даты
        if 'Время заказа' in df.columns:
            df['Время заказа'] = pd.to_datetime(df['Время заказа'])
        
        # Генерируем имя файла если не указано
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            date_range = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
            output_file = f"orders_with_commission_{date_range}_{timestamp}.xlsx"
        
        # Создаем папку reports если её нет
        reports_dir = "reports"
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
            print(f"Создана папка: {reports_dir}")
        
        # Полный путь к файлу
        full_output_path = os.path.join(reports_dir, output_file)
        
        # Сохраняем в Excel
        print(f"Сохраняем в файл: {full_output_path}")
        
        # Используем openpyxl для поддержки русского языка
        with pd.ExcelWriter(full_output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Заказы с комиссиями', index=False)
            
            # Получаем workbook и worksheet для форматирования
            workbook = writer.book
            worksheet = writer.sheets['Заказы с комиссиями']
            
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
                
                # Специальная настройка для разных столбцов
                if column_letter == 'G':  # Список блюд
                    adjusted_width = min(max_length + 2, 100)  # Максимум 100 символов для списка блюд
                else:
                    adjusted_width = min(max_length + 2, 50)  # Максимум 50 символов для остальных
                
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        print()
        print("=" * 80)
        print("СТАТИСТИКА:")
        print("=" * 80)
        print(f"Всего заказов экспортировано: {len(df)}")
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
                print(f"  - Заказов с комиссией: {records_with_commission}")
                print(f"  - Заказов без комиссии: {records_without_commission}")
                if total_commission:
                    print(f"  - Общая сумма комиссий: {total_commission:.2f}")
            
            # Статистика по ценам
            if 'Цена (скидка)' in df.columns:
                total_price = df['Цена (скидка)'].sum()
                avg_price = df['Цена (скидка)'].mean()
                min_price = df['Цена (скидка)'].min()
                max_price = df['Цена (скидка)'].max()
                
                print()
                print("Статистика по ценам (скидкам):")
                print(f"  - Общая сумма: {total_price:.2f}")
                print(f"  - Средняя цена: {avg_price:.2f}")
                print(f"  - Минимальная цена: {min_price:.2f}")
                print(f"  - Максимальная цена: {max_price:.2f}")
        
        print()
        print(f"✓ Данные успешно экспортированы в файл: {full_output_path}")
        print()
        
        # Создаем дополнительную таблицу с комиссиями
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        create_commission_table(start_date, end_date, timestamp)
        
    except Exception as e:
        print(f"Ошибка при экспорте данных: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def create_commission_table(start_date, end_date, timestamp):
    """
    Создает дополнительную таблицу с данными по комиссиям
    """
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("СОЗДАНИЕ ТАБЛИЦЫ КОМИССИЙ")
        print("=" * 80)
        print()
        
        print("Выполняем запрос к базе данных для таблицы комиссий...")
        
        # Выполняем запрос для таблицы комиссий
        query = db.query(
            DOrder.iiko_id.label('iiko_id'),
            DOrder.time_order.label('time_order'),
            DOrder.discount.label('price'),
            DOrder.bank_commission.label('bank_commission'),
            Organization.name.label('organization_name')
        ).join(
            Organization,
            DOrder.organization_id == Organization.id
        ).filter(
            and_(
                DOrder.time_order >= start_date,
                DOrder.time_order < end_date,
                DOrder.discount != 0,
                DOrder.iiko_id.like('COMMISSION_%')
            )
        ).order_by(
            DOrder.iiko_id.asc()
        )
        
        # Получаем результаты
        results = query.all()
        
        print(f"Найдено записей комиссий: {len(results)}")
        print()
        
        if not results:
            print("⚠ Данные комиссий не найдены для указанных критериев!")
            return
        
        # Преобразуем в DataFrame
        print("Создаем DataFrame для таблицы комиссий...")
        data = []
        for row in results:
            data.append({
                'iiko_id': row.iiko_id,
                'Время заказа': row.time_order,
                'Цена (скидка)': row.price,
                'Комиссия банка': row.bank_commission,
                'Название организации': row.organization_name
            })
        
        df_commission = pd.DataFrame(data)
        
        # Форматируем даты
        if 'Время заказа' in df_commission.columns:
            df_commission['Время заказа'] = pd.to_datetime(df_commission['Время заказа'])
        
        # Генерируем имя файла для таблицы комиссий
        date_range = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
        commission_output_file = f"commission_table_{date_range}_{timestamp}.xlsx"
        
        # Создаем папку reports если её нет
        reports_dir = "reports"
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
        
        # Полный путь к файлу
        full_commission_path = os.path.join(reports_dir, commission_output_file)
        
        # Сохраняем в Excel
        print(f"Сохраняем таблицу комиссий в файл: {full_commission_path}")
        
        # Используем openpyxl для поддержки русского языка
        with pd.ExcelWriter(full_commission_path, engine='openpyxl') as writer:
            df_commission.to_excel(writer, sheet_name='Комиссии', index=False)
            
            # Получаем workbook и worksheet для форматирования
            workbook = writer.book
            worksheet = writer.sheets['Комиссии']
            
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
        print("СТАТИСТИКА ТАБЛИЦЫ КОМИССИЙ:")
        print("=" * 80)
        print(f"Всего записей комиссий экспортировано: {len(df_commission)}")
        print(f"Период: {start_date.date()} - {end_date.date()}")
        
        # Дополнительная статистика по комиссиям
        if len(df_commission) > 0:
            print()
            print("Распределение по организациям:")
            org_stats = df_commission['Название организации'].value_counts()
            for org_name, count in org_stats.items():
                print(f"  - {org_name}: {count}")
            
            # Статистика по комиссиям
            if 'Комиссия банка' in df_commission.columns:
                total_commission = df_commission['Комиссия банка'].sum()
                records_with_commission = df_commission['Комиссия банка'].notna().sum()
                records_without_commission = df_commission['Комиссия банка'].isna().sum()
                
                print()
                print("Статистика по комиссиям:")
                print(f"  - Записей с комиссией: {records_with_commission}")
                print(f"  - Записей без комиссии: {records_without_commission}")
                if total_commission:
                    print(f"  - Общая сумма комиссий: {total_commission:.2f}")
            
            # Статистика по ценам
            if 'Цена (скидка)' in df_commission.columns:
                total_price = df_commission['Цена (скидка)'].sum()
                avg_price = df_commission['Цена (скидка)'].mean()
                min_price = df_commission['Цена (скидка)'].min()
                max_price = df_commission['Цена (скидка)'].max()
                
                print()
                print("Статистика по ценам (скидкам):")
                print(f"  - Общая сумма: {total_price:.2f}")
                print(f"  - Средняя цена: {avg_price:.2f}")
                print(f"  - Минимальная цена: {min_price:.2f}")
                print(f"  - Максимальная цена: {max_price:.2f}")
        
        print()
        print(f"✓ Таблица комиссий успешно экспортирована в файл: {full_commission_path}")
        print()
        
    except Exception as e:
        print(f"Ошибка при создании таблицы комиссий: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def get_orders_summary(start_date='2025-10-13 00:00:00', end_date='2025-10-19 00:00:00'):
    """
    Получает краткую сводку по заказам за период
    """
    db = SessionLocal()
    
    try:
        # Преобразуем строки в datetime
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
        
        print("=" * 80)
        print("СВОДКА ПО ЗАКАЗАМ")
        print("=" * 80)
        print(f"Период: с {start_date} по {end_date}")
        print()
        
        # Общее количество заказов
        total_orders = db.query(DOrder).filter(
            and_(
                DOrder.time_order >= start_date,
                DOrder.time_order < end_date
            )
        ).count()
        
        # Заказы с ненулевой скидкой
        orders_with_discount = db.query(DOrder).filter(
            and_(
                DOrder.time_order >= start_date,
                DOrder.time_order < end_date,
                DOrder.discount != 0
            )
        ).count()
        
        # Заказы с комиссией
        orders_with_commission = db.query(DOrder).filter(
            and_(
                DOrder.time_order >= start_date,
                DOrder.time_order < end_date,
                DOrder.bank_commission.isnot(None)
            )
        ).count()
        
        print(f"Всего заказов: {total_orders}")
        print(f"Заказов с ненулевой скидкой: {orders_with_discount}")
        print(f"Заказов с комиссией: {orders_with_commission}")
        print()
        
        # Статистика по типам карт
        card_types_query = db.query(Sales.card_type_name).distinct().join(
            DOrder,
            Sales.order_id == DOrder.iiko_id
        ).filter(
            and_(
                DOrder.time_order >= start_date,
                DOrder.time_order < end_date,
                DOrder.discount != 0
            )
        )
        
        card_types = [row.card_type_name for row in card_types_query.all() if row.card_type_name]
        
        print("Типы карт в заказах с ненулевой скидкой:")
        for card_type in sorted(card_types):
            print(f"  - {card_type}")
        
        return {
            'total_orders': total_orders,
            'orders_with_discount': orders_with_discount,
            'orders_with_commission': orders_with_commission,
            'card_types': card_types
        }
        
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Экспорт заказов с комиссиями в Excel')
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
        '--summary',
        action='store_true',
        help='Показать только сводку по заказам и выйти'
    )
    
    args = parser.parse_args()
    
    if args.summary:
        get_orders_summary(args.start, args.end)
    else:
        export_orders_with_commission_to_excel(args.start, args.end, args.output)
