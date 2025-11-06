"""
Скрипт для создания отчета о прибылях и убытках (P&L)
Отчет показывает финансовые показатели по организациям и категориям
"""
import sys
import io
import os

# Настройка кодировки для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from sqlalchemy import create_engine, and_, func
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import pandas as pd
import config
from models.transaction import Transaction
from models.sales import Sales
from models.organization import Organization
from models.d_order import DOrder

# Подключение к БД
DATABASE_URL = config.DATABASE_URL
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def analyze_account_hierarchy(db):
    """
    Анализирует структуру account_hierarchy для понимания категорий
    """
    print("Анализируем структуру account_hierarchy...")
    
    # Получаем уникальные значения account_hierarchy_top
    top_hierarchies = db.query(
        Transaction.account_hierarchy_top
    ).distinct().filter(
        Transaction.account_hierarchy_top.isnot(None)
    ).all()
    
    print(f"\nНайдено категорий верхнего уровня: {len(top_hierarchies)}")
    for item in top_hierarchies[:20]:  # Показываем первые 20
        print(f"  - {item[0]}")
    
    # Получаем unique сочетания top, second и third
    hierarchies = db.query(
        Transaction.account_hierarchy_top,
        Transaction.account_hierarchy_second,
        Transaction.account_hierarchy_third
    ).distinct().filter(
        Transaction.account_hierarchy_top.isnot(None)
    ).limit(50).all()
    
    print(f"\nПримеры иерархии (первые 50):")
    for hier in hierarchies:
        parts = [p for p in hier if p]
        if parts:
            print(f"  {' > '.join(parts)}")
    
    return hierarchies


def get_organizations(db):
    """Получает список всех активных организаций"""
    return db.query(Organization).filter(Organization.is_active == True).all()


def get_additional_revenue_by_organization(db, organization_id, start_date, end_date):
    """
    Получает дополнительную выручку из транзакций по организации
    """
    additional_revenue = float(db.query(func.sum(Transaction.sum_resigned)).filter(
        and_(
            Transaction.organization_id == organization_id,
            Transaction.account_name == 'Задолженность перед поставщиками',
            Transaction.contr_account_type == 'INCOME',
            Transaction.date_typed >= start_date,
            Transaction.date_typed <= end_date
        )
    ).scalar() or 0)
    
    return additional_revenue


def get_revenue_by_organization(db, organization_id, start_date, end_date):
    """
    Получает выручку по организации из таблицы sales
    Разделяет на Кухня и Бар
    Учитывает скидки согласно SQL запросу
    """
    # Выручка Кухня (с учетом скидки)
    kitchen_query = db.query(
        func.sum(Sales.full_sum).label('full_sum'),
        func.sum(Sales.discount_without_vat).label('discount')
    ).filter(
        and_(
            Sales.organization_id == organization_id,
            Sales.open_date_typed >= start_date,
            Sales.open_date_typed < end_date,
            Sales.cooking_place_type == 'Кухня'
        )
    ).first()
    
    kitchen_revenue = float(kitchen_query.full_sum or 0) - float(kitchen_query.discount or 0)
    
    # Выручка Бар (не Кухня, с учетом скидки)
    bar_query = db.query(
        func.sum(Sales.full_sum).label('full_sum'),
        func.sum(Sales.discount_without_vat).label('discount')
    ).filter(
        and_(
            Sales.organization_id == organization_id,
            Sales.open_date_typed >= start_date,
            Sales.open_date_typed < end_date,
            Sales.cooking_place_type != 'Кухня',
            Sales.cooking_place_type.isnot(None)
        )
    ).first()
    
    bar_revenue = float(bar_query.full_sum or 0) - float(bar_query.discount or 0)
    
    # Дополнительная выручка
    additional_revenue = get_additional_revenue_by_organization(db, organization_id, start_date, end_date)
    
    return kitchen_revenue, bar_revenue, additional_revenue


def get_cost_of_goods_by_organization(db, organization_id, start_date, end_date):
    """
    Получает себестоимость продуктов по организации из таблицы sales
    Разделяет на Кухня и Бар
    """
    # Себестоимость Кухня
    kitchen_cost_query = db.query(
        func.sum(Sales.product_cost_base_product_cost).label('product_cost')
    ).filter(
        and_(
            Sales.organization_id == organization_id,
            Sales.open_date_typed >= start_date,
            Sales.open_date_typed < end_date,
            Sales.cooking_place_type == 'Кухня',
            Sales.product_cost_base_product_cost.isnot(None)
        )
    ).first()
    
    kitchen_cost = float(kitchen_cost_query.product_cost or 0)
    
    # Себестоимость Бар (не Кухня)
    bar_cost_query = db.query(
        func.sum(Sales.product_cost_base_product_cost).label('product_cost')
    ).filter(
        and_(
            Sales.organization_id == organization_id,
            Sales.open_date_typed >= start_date,
            Sales.open_date_typed < end_date,
            Sales.cooking_place_type != 'Кухня',
            Sales.cooking_place_type.isnot(None),
            Sales.product_cost_base_product_cost.isnot(None)
        )
    ).first()
    
    bar_cost = float(bar_cost_query.product_cost or 0)
    
    return kitchen_cost, bar_cost


def get_bank_commission_by_organization(db, organization_id, start_date, end_date):
    """
    Получает сумму банковских комиссий по организации из d_orders
    """
    commission = db.query(
        func.sum(DOrder.bank_commission)
    ).filter(
        and_(
            DOrder.organization_id == organization_id,
            DOrder.time_order >= start_date,
            DOrder.time_order < end_date,
            DOrder.bank_commission.isnot(None)
        )
    ).scalar() or 0
    
    return float(commission)


def get_transactions_by_hierarchy(db, organization_id, start_date, end_date):
    """
    Получает суммы по транзакциям, сгруппированные по иерархии account_hierarchy
    Возвращает словарь где ключ - полный путь категории, значение - сумма
    Добавляет все уровни иерархии для правильного отображения в отчете
    """
    if organization_id:
        transactions_dict = {}
        
        # Получаем все уникальные комбинации иерархии с суммами
        results = db.query(
            Transaction.account_hierarchy_top,
            Transaction.account_hierarchy_second,
            Transaction.account_hierarchy_third,
            func.sum(func.coalesce(Transaction.amount_out, Transaction.amount_in, 0)).label('total')
        ).filter(
            and_(
                Transaction.organization_id == organization_id,
                Transaction.date_time_typed >= start_date,
                Transaction.date_time_typed < end_date,
                Transaction.account_hierarchy_top.isnot(None),
                Transaction.account_hierarchy_top != ''
            )
        ).group_by(
            Transaction.account_hierarchy_top,
            Transaction.account_hierarchy_second,
            Transaction.account_hierarchy_third
        ).all()
        
        # Формируем полные пути категорий и суммируем
        for row in results:
            parts = []
            if row.account_hierarchy_top:
                parts.append(row.account_hierarchy_top)
            if row.account_hierarchy_second:
                parts.append(row.account_hierarchy_second)
            if row.account_hierarchy_third:
                parts.append(row.account_hierarchy_third)
            
            if parts:
                total = abs(float(row.total or 0))
                if total != 0:
                    # Сохраняем все уровни иерархии отдельно
                    
                    # Уровень 1
                    if len(parts) >= 1 and parts[0]:
                        transactions_dict[parts[0]] = transactions_dict.get(parts[0], 0) + total
                    
                    # Уровень 2 (если есть)
                    if len(parts) >= 2 and parts[1]:
                        full_path_2 = ' > '.join(parts[:2])
                        transactions_dict[full_path_2] = transactions_dict.get(full_path_2, 0) + total
                    
                    # Уровень 3 (если есть)
                    if len(parts) >= 3 and parts[2]:
                        full_path_3 = ' > '.join(parts)
                        transactions_dict[full_path_3] = transactions_dict.get(full_path_3, 0) + total
        
        return transactions_dict
    else:
        return {}


def get_transactions_sum_by_category(db, organization_id, start_date, end_date):
    """
    Получает суммы по категориям из account_hierarchy_full
    Возвращает словарь: {category: sum_resigned}
    """
    results = db.query(
        Transaction.account_hierarchy_full,
        func.sum(Transaction.sum_resigned).label('total')
    ).filter(
        and_(
            Transaction.organization_id == organization_id,
            Transaction.date_time_typed >= start_date,
            Transaction.date_time_typed < end_date,
            Transaction.account_hierarchy_full.isnot(None),
            Transaction.account_hierarchy_full != ''
        )
    ).group_by(
        Transaction.account_hierarchy_full
    ).all()
    
    return {row.account_hierarchy_full: float(row.total or 0) for row in results}


def create_profit_loss_report(start_date='2025-10-13 00:00:00', end_date='2025-10-19 00:00:00', output_file=None):
    """
    Создает отчет о прибылях и убытках
    
    Args:
        start_date: Начальная дата фильтра
        end_date: Конечная дата фильтра
        output_file: Имя файла для сохранения
    """
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("СОЗДАНИЕ ОТЧЕТА О ПРИБЫЛЯХ И УБЫТКАХ")
        print("=" * 80)
        print()
        
        # Преобразуем строки в datetime если нужно
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
        
        print(f"Период: с {start_date} по {end_date}")
        print()
        
        # Получаем все организации
        print("Получаем список организаций...")
        organizations = get_organizations(db)
        print(f"Найдено организаций: {len(organizations)}")
        for org in organizations:
            print(f"  - {org.name} (ID: {org.id})")
        
        # Собираем данные для каждой организации
        print()
        print("Собираем данные по организациям...")
        
        # Получаем ВСЕ уникальные категории из account_hierarchy_full, исключая ненужные
        all_categories = db.query(
            Transaction.account_hierarchy_full
        ).distinct().filter(
            and_(
                Transaction.account_hierarchy_full.isnot(None),
                Transaction.account_hierarchy_full != '',
                ~Transaction.account_hierarchy_full.startswith('Денежные средства'),
                ~Transaction.account_hierarchy_full.startswith('Кухня'),
                ~Transaction.account_hierarchy_full.startswith('Бар')
            )
        ).all()
        
        all_categories_list = [row.account_hierarchy_full for row in all_categories]
        
        # Добавляем специальные категории
        all_categories_list.append('bank_commission')
        all_categories_list.append('Выручка > Кухня')
        all_categories_list.append('Выручка > Бар')
        all_categories_list.append('Выручка > Дополнительная')
        all_categories_list.append('discount')
        
        print(f"\nНайдено категорий: {len(all_categories_list)}")
        
        # Инициализируем report_data
        report_data = {}
        for category in all_categories_list:
            report_data[category] = {}
            for org in organizations:
                report_data[category][org.name] = 0
        
        # Заполняем данные для каждой организации
        for org in organizations:
            print(f"\nОбрабатываем организацию: {org.name}")
            
            # Получаем суммы по категориям из transactions
            transactions = get_transactions_sum_by_category(db, org.id, start_date, end_date)
            for category, amount in transactions.items():
                if category in report_data:
                    report_data[category][org.name] = amount
                    print(f"  {category}: {amount:.2f}")
            
            # Получаем bank_commission из d_orders
            bank_commission_query = db.query(
                func.sum(DOrder.bank_commission)
            ).filter(
                and_(
                    DOrder.organization_id == org.id,
                    DOrder.time_order >= start_date,
                    DOrder.time_order < end_date,
                    DOrder.bank_commission.isnot(None)
                )
            ).scalar()
            report_data['bank_commission'][org.name] = float(bank_commission_query or 0)
            print(f"  bank_commission: {report_data['bank_commission'][org.name]:.2f}")
            
            # Получаем выручку и скидки из sales по Кухне
            kitchen_revenue_query = db.query(
                func.sum(Sales.full_sum - Sales.discount_without_vat).label('revenue')
            ).filter(
                and_(
                    Sales.organization_id == org.id,
                    Sales.open_date_typed >= start_date,
                    Sales.open_date_typed < end_date,
                    Sales.cooking_place_type == 'Кухня'
                )
            ).scalar()
            report_data['Выручка > Кухня'][org.name] = float(kitchen_revenue_query or 0)
            
            # Получаем выручку из sales по Бару
            bar_revenue_query = db.query(
                func.sum(Sales.full_sum - Sales.discount_without_vat).label('revenue')
            ).filter(
                and_(
                    Sales.organization_id == org.id,
                    Sales.open_date_typed >= start_date,
                    Sales.open_date_typed < end_date,
                    Sales.cooking_place_type != 'Кухня',
                    Sales.cooking_place_type.isnot(None)
                )
            ).scalar()
            report_data['Выручка > Бар'][org.name] = float(bar_revenue_query or 0)
            
            # Получаем дополнительную выручку из транзакций
            additional_revenue = get_additional_revenue_by_organization(db, org.id, start_date, end_date)
            report_data['Выручка > Дополнительная'][org.name] = additional_revenue
            print(f"  Дополнительная выручка: {additional_revenue:.2f}")
            
            # Получаем discount из d_orders (сумма скидок)
            discount_query = db.query(
                func.sum(DOrder.discount)
            ).filter(
                and_(
                    DOrder.organization_id == org.id,
                    DOrder.time_order >= start_date,
                    DOrder.time_order < end_date,
                    DOrder.discount.isnot(None)
                )
            ).scalar()
            report_data['discount'][org.name] = float(discount_query or 0)
            print(f"  discount: {report_data['discount'][org.name]:.2f}")
        
        # Формируем финальный список категорий
        all_categories = sorted(all_categories_list)
        
        print("\n" + "=" * 80)
        print("ИТОГОВЫЙ СПИСОК КАТЕГОРИЙ ДЛЯ EXCEL:")
        print("=" * 80)
        for i, cat in enumerate(all_categories, 1):
            print(f"{i}. {cat}")
        print("=" * 80)
        print(f"Всего категорий: {len(all_categories)}")
        
        # Создаем DataFrame
        print()
        print("Создаем Excel файл...")
        
        # Подготовка данных для сводной таблицы
        data_rows = []
        for category in all_categories:
            row = {'Категория': category}
            for org in organizations:
                row[org.name] = report_data[category][org.name]
            data_rows.append(row)
        
        df = pd.DataFrame(data_rows)
        
        # Генерируем имя файла если не указано
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            date_range = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
            output_file = f"profit_loss_report_{date_range}_{timestamp}.xlsx"
        
        # Создаем папку reports если её нет
        reports_dir = "reports"
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
        
        # Полный путь к файлу
        full_output_path = os.path.join(reports_dir, output_file)
        
        # Сохраняем в Excel
        with pd.ExcelWriter(full_output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Отчет П&У', index=False)
            
            # Получаем workbook и worksheet для форматирования
            workbook = writer.book
            worksheet = writer.sheets['Отчет П&У']
            
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
                
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        print()
        print("=" * 80)
        print("ОТЧЕТ СОЗДАН УСПЕШНО")
        print("=" * 80)
        print(f"Файл сохранен: {full_output_path}")
        print(f"Организаций: {len(organizations)}")
        print(f"Категорий: {len(all_categories)}")
        print()
        
    except Exception as e:
        print(f"Ошибка при создании отчета: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Создание отчета о прибылях и убытках')
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
        help='Имя выходного файла'
    )
    parser.add_argument(
        '--analyze',
        action='store_true',
        help='Только проанализировать структуру данных'
    )
    
    args = parser.parse_args()
    
    db = SessionLocal()
    
    if args.analyze:
        analyze_account_hierarchy(db)
    else:
        create_profit_loss_report(args.start, args.end, args.output)
    
    db.close()
