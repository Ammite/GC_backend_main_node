"""
Скрипт для удаления дубликатов из таблицы sales по комбинации полей:
item_sale_event_id + payment_transaction_id

Для каждой уникальной комбинации этих полей оставляет только ПЕРВУЮ запись (с минимальным ID),
остальные дубликаты удаляет.

Использование:
    python remove_sales_duplicates_by_id.py                    # Dry-run (только показать)
    python remove_sales_duplicates_by_id.py --delete           # Удалить дубликаты
    python remove_sales_duplicates_by_id.py --start-date 2025-10-01 --end-date 2025-10-31 --delete
"""

import sys
import argparse
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Set
from sqlalchemy import and_
from sqlalchemy.orm import Session

from database.database import SessionLocal
from models.sales import Sales


def fetch_sales_with_fields(
    db: Session,
    start_date: str = None,
    end_date: str = None,
    org_id: int = None
) -> List[Sales]:
    """
    Получить все записи sales с непустыми item_sale_event_id и payment_transaction_id
    
    Args:
        db: Сессия БД
        start_date: Дата начала периода (YYYY-MM-DD)
        end_date: Дата конца периода (YYYY-MM-DD)
        org_id: ID организации
        
    Returns:
        Список записей Sales
    """
    query = db.query(Sales).filter(
        Sales.item_sale_event_id.isnot(None),
        Sales.payment_transaction_id.isnot(None)
    )
    
    filters = []
    
    if start_date:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        filters.append(Sales.open_date_typed >= start_dt.date())
    
    if end_date:
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        filters.append(Sales.open_date_typed <= end_dt.date())
    
    if org_id:
        filters.append(Sales.organization_id == org_id)
    
    if filters:
        query = query.filter(and_(*filters))
    
    # Сортировка по id для стабильного порядка
    query = query.order_by(Sales.id)
    
    print(f"Загрузка данных из БД...")
    records = query.all()
    print(f"Загружено {len(records)} записей с item_sale_event_id и payment_transaction_id")
    
    return records


def find_duplicates_by_fields(records: List[Sales]) -> Dict[tuple, List[int]]:
    """
    Найти дубликаты по комбинации item_sale_event_id + payment_transaction_id
    
    Args:
        records: Список записей Sales
        
    Returns:
        Словарь {(item_sale_event_id, payment_transaction_id): [список ID для удаления]}
    """
    print(f"\nПоиск дубликатов по комбинации item_sale_event_id + payment_transaction_id...")
    
    # Группируем ID записей по комбинации полей
    grouped: Dict[tuple, List[int]] = defaultdict(list)
    
    for idx, record in enumerate(records):
        if idx > 0 and idx % 10000 == 0:
            print(f"Обработано {idx}/{len(records)} записей...")
        
        # Создаем ключ из комбинации двух полей
        key = (record.item_sale_event_id, record.payment_transaction_id)
        grouped[key].append(record.id)
    
    # Определяем какие ID нужно удалить (все кроме первого в каждой группе)
    duplicates_to_delete: Dict[tuple, List[int]] = {}
    total_duplicates = 0
    
    for key, ids_list in grouped.items():
        if len(ids_list) > 1:
            # Оставляем первый ID (минимальный), остальные в список на удаление
            ids_to_delete = sorted(ids_list)[1:]  # Все кроме первого
            duplicates_to_delete[key] = ids_to_delete
            total_duplicates += len(ids_to_delete)
    
    print(f"\nНайдено {len(duplicates_to_delete)} групп дубликатов")
    print(f"Всего дубликатов для удаления: {total_duplicates}")
    
    return duplicates_to_delete


def delete_duplicates_batch(db: Session, ids_to_delete: List[int], batch_size: int = 500):
    """
    Удалить дубликаты из БД пакетами
    
    Args:
        db: Сессия БД
        ids_to_delete: Список ID для удаления
        batch_size: Размер пакета для удаления
    """
    total = len(ids_to_delete)
    if total == 0:
        print("Нет дубликатов для удаления")
        return
    
    print(f"\nУдаление {total} дубликатов из БД...")
    
    deleted = 0
    for i in range(0, total, batch_size):
        batch = ids_to_delete[i:i + batch_size]
        
        try:
            db.query(Sales).filter(Sales.id.in_(batch)).delete(synchronize_session=False)
            db.commit()
            deleted += len(batch)
            print(f"Удалено {deleted}/{total} записей... ({deleted/total*100:.1f}%)")
        except Exception as e:
            print(f"Ошибка при удалении пакета: {e}")
            db.rollback()
            continue
    
    print(f"\n✓ Удаление завершено! Удалено {deleted} дубликатов")


def print_summary(duplicates: Dict[tuple, List[int]], dry_run: bool = True):
    """
    Вывести сводку по дубликатам
    
    Args:
        duplicates: Словарь с дубликатами
        dry_run: Режим dry-run
    """
    print("\n" + "="*80)
    print("СВОДКА ПО ДУБЛИКАТАМ (item_sale_event_id + payment_transaction_id)")
    print("="*80)
    
    total_duplicates = sum(len(ids) for ids in duplicates.values())
    
    print(f"Найдено групп с дубликатами: {len(duplicates)}")
    print(f"Всего дубликатов для удаления: {total_duplicates}")
    
    if duplicates:
        # Топ-10 групп с наибольшим количеством дубликатов
        sorted_dupes = sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True)
        
        print("\nТоп-10 групп с наибольшим количеством дубликатов:")
        for idx, (key, ids_list) in enumerate(sorted_dupes[:10], 1):
            event_id, payment_id = key
            print(f"{idx}. item_sale_event_id: {event_id}")
            print(f"   payment_transaction_id: {payment_id}")
            print(f"   Всего записей: {len(ids_list) + 1} (будет удалено: {len(ids_list)})")
            print(f"   ID для удаления: {ids_list[:5]}{'...' if len(ids_list) > 5 else ''}")
        
        if len(duplicates) > 10:
            print(f"\n... и еще {len(duplicates) - 10} групп дубликатов")
        
        # Статистика
        group_sizes = [len(ids) for ids in duplicates.values()]
        print(f"\nСтатистика:")
        print(f"  Минимум дубликатов в группе: {min(group_sizes)}")
        print(f"  Максимум дубликатов в группе: {max(group_sizes)}")
        print(f"  Среднее количество дубликатов: {sum(group_sizes) / len(group_sizes):.2f}")
    
    if dry_run:
        print("\n" + "="*80)
        print("⚠️  РЕЖИМ DRY-RUN: Дубликаты НЕ будут удалены")
        print("Для реального удаления запустите скрипт с флагом --delete")
        print("="*80)
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Удаление дубликатов в таблице sales по комбинации item_sale_event_id + payment_transaction_id',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python remove_sales_duplicates_by_id.py                                    # Dry-run
  python remove_sales_duplicates_by_id.py --delete                          # Удалить все дубликаты
  python remove_sales_duplicates_by_id.py --start-date 2025-10-01 --delete # За период
        """
    )
    
    parser.add_argument(
        '--start-date',
        type=str,
        help='Дата начала периода (формат: YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--end-date',
        type=str,
        help='Дата конца периода (формат: YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--org-id',
        type=int,
        help='ID организации для фильтрации'
    )
    
    parser.add_argument(
        '--delete',
        action='store_true',
        help='Удалить найденные дубликаты (без этого флага только показывает)'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=500,
        help='Размер пакета для удаления (по умолчанию: 500)'
    )
    
    args = parser.parse_args()
    
    dry_run = not args.delete
    
    # Информация о параметрах запуска
    print("="*80)
    print("СКРИПТ УДАЛЕНИЯ ДУБЛИКАТОВ")
    print("ПО КОМБИНАЦИИ: item_sale_event_id + payment_transaction_id")
    print("="*80)
    print(f"Дата начала: {args.start_date or 'не указана (все данные)'}")
    print(f"Дата конца: {args.end_date or 'не указана (все данные)'}")
    print(f"ID организации: {args.org_id or 'не указан (все организации)'}")
    print(f"Режим: {'DRY-RUN (только показать)' if dry_run else 'УДАЛЕНИЕ ДУБЛИКАТОВ ⚠️'}")
    print(f"Размер пакета: {args.batch_size}")
    print("="*80 + "\n")
    
    if not dry_run:
        print("⚠️  ВНИМАНИЕ! Вы собираетесь УДАЛИТЬ дубликаты из базы данных!")
        print("Для каждой комбинации (item_sale_event_id + payment_transaction_id)")
        print("будет оставлена только ПЕРВАЯ запись (с минимальным ID)")
        print()
        response = input("Продолжить? Введите 'YES' для подтверждения: ")
        if response != "YES":
            print("Отменено пользователем.")
            sys.exit(0)
        print()
    
    start_time = datetime.now()
    
    # Создание сессии БД
    db = SessionLocal()
    
    try:
        # Загрузка данных
        records = fetch_sales_with_fields(
            db,
            start_date=args.start_date,
            end_date=args.end_date,
            org_id=args.org_id
        )
        
        if not records:
            print("Записей не найдено по заданным фильтрам")
            return
        
        # Поиск дубликатов
        duplicates = find_duplicates_by_fields(records)
        
        if not duplicates:
            print("\n✓ Дубликаты не найдены!")
            return
        
        # Вывод сводки
        print_summary(duplicates, dry_run)
        
        # Удаление дубликатов
        if not dry_run:
            # Собираем все ID для удаления в один список
            all_ids_to_delete = []
            for ids_list in duplicates.values():
                all_ids_to_delete.extend(ids_list)
            
            # Удаляем
            delete_duplicates_batch(db, all_ids_to_delete, args.batch_size)
            
            # Проверяем результат
            remaining_count = db.query(Sales).filter(
                Sales.item_sale_event_id.isnot(None),
                Sales.payment_transaction_id.isnot(None)
            ).count()
            print(f"\nЗаписей с обоими полями осталось: {remaining_count}")
            print(f"Было удалено: {len(all_ids_to_delete)} записей")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"\nВремя выполнения: {duration:.2f} секунд")
    print("Скрипт завершен!")


if __name__ == "__main__":
    main()

