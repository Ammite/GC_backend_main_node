"""
Скрипт для удаления дубликатов из таблицы sales
Оставляет только первую запись из каждой группы дубликатов
"""

import sys
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime
from database.database import get_db, engine
from models import Sales

def normalize_value_for_key(value):
    """Нормализует значение для использования в уникальном ключе"""
    if value is None:
        return None
    
    # Datetime преобразуем в ISO строку без микросекунд
    if isinstance(value, datetime):
        return value.replace(microsecond=0, tzinfo=None).isoformat()
    
    # Числовые значения
    if isinstance(value, (int, float)):
        if isinstance(value, int) or value == int(value):
            return int(value)
        return round(float(value), 2)
    
    # Decimal из SQLAlchemy
    from decimal import Decimal
    if isinstance(value, Decimal):
        float_val = float(value)
        if float_val == int(float_val):
            return int(float_val)
        return round(float_val, 2)
    
    # Все остальное возвращаем как есть
    return value


def create_sale_unique_key(sale):
    """
    Создает уникальный ключ для продажи из ВСЕХ значимых полей
    (кроме id, created_at, updated_at, is_active, commission)
    """
    # Список полей для ИСКЛЮЧЕНИЯ из ключа
    exclude_fields = {'id', 'created_at', 'updated_at', 'is_active', 'commission'}
    
    # Получаем все поля модели Sales
    all_fields = [column.name for column in Sales.__table__.columns if column.name not in exclude_fields]
    
    # Создаем tuple из нормализованных значений ВСЕХ полей
    key_values = []
    for field in sorted(all_fields):  # sorted для стабильного порядка
        value = getattr(sale, field, None)
        normalized_value = normalize_value_for_key(value)
        key_values.append(normalized_value)
    
    return tuple(key_values)


def remove_duplicates(db: Session, batch_size: int = 1000, dry_run: bool = True):
    """
    Удаляет дубликаты из таблицы sales
    
    Args:
        db: Сессия базы данных
        batch_size: Размер пакета для обработки
        dry_run: Если True, только показывает что будет удалено, не удаляет
    """
    exclude_fields = {'id', 'created_at', 'updated_at', 'is_active', 'commission'}
    total_fields = len([c.name for c in Sales.__table__.columns if c.name not in exclude_fields])
    
    print(f"{'[DRY RUN] ' if dry_run else ''}Начало поиска дубликатов...")
    print(f"Используется {total_fields} полей для определения уникальности")
    
    # Получаем общее количество записей
    total_count = db.query(Sales).count()
    print(f"Всего записей в таблице sales: {total_count}")
    
    # Обрабатываем записи пакетами
    offset = 0
    unique_keys = {}  # key -> первая запись с этим ключом
    duplicates_to_delete = []
    
    while True:
        # Получаем пакет записей
        sales_batch = db.query(Sales).order_by(Sales.id).offset(offset).limit(batch_size).all()
        
        if not sales_batch:
            break
        
        print(f"Обработка записей {offset + 1} - {offset + len(sales_batch)}...")
        
        for sale in sales_batch:
            key = create_sale_unique_key(sale)
            
            if key in unique_keys:
                # Это дубликат - помечаем для удаления
                duplicates_to_delete.append(sale.id)
            else:
                # Это первая запись с таким ключом - сохраняем
                unique_keys[key] = sale.id
        
        offset += batch_size
    
    print(f"\nНайдено уникальных записей: {len(unique_keys)}")
    print(f"Найдено дубликатов: {len(duplicates_to_delete)}")
    
    if len(duplicates_to_delete) == 0:
        print("Дубликаты не найдены!")
        return
    
    if dry_run:
        print("\n[DRY RUN] Это был тестовый запуск. Для реального удаления запустите скрипт с параметром --delete")
        print(f"[DRY RUN] Будет удалено {len(duplicates_to_delete)} дубликатов")
        
        # Показываем примеры дубликатов
        print("\nПримеры дубликатов (первые 10):")
        for dup_id in duplicates_to_delete[:10]:
            sale = db.query(Sales).filter(Sales.id == dup_id).first()
            if sale:
                print(f"  ID: {sale.id}, item_sale_event_id: {sale.item_sale_event_id}, "
                      f"order_id: {sale.order_id}, dish_id: {sale.dish_id}, "
                      f"open_time: {sale.open_time}")
    else:
        print(f"\nУдаление {len(duplicates_to_delete)} дубликатов...")
        
        # Удаляем дубликаты пакетами
        deleted = 0
        batch_delete_size = 500
        
        for i in range(0, len(duplicates_to_delete), batch_delete_size):
            batch = duplicates_to_delete[i:i + batch_delete_size]
            db.query(Sales).filter(Sales.id.in_(batch)).delete(synchronize_session=False)
            db.commit()
            deleted += len(batch)
            print(f"Удалено {deleted} из {len(duplicates_to_delete)}...")
        
        print(f"\n✓ Успешно удалено {deleted} дубликатов!")
        
        # Проверяем результат
        final_count = db.query(Sales).count()
        print(f"Записей осталось: {final_count}")
        print(f"Удалено: {total_count - final_count}")


if __name__ == "__main__":
    # Проверяем аргументы командной строки
    dry_run = "--delete" not in sys.argv
    
    if dry_run:
        print("=" * 80)
        print("РЕЖИМ ТЕСТОВОГО ЗАПУСКА (DRY RUN)")
        print("Скрипт только покажет что будет удалено, но не удалит данные")
        print("Для реального удаления запустите: python remove_sales_duplicates.py --delete")
        print("=" * 80)
        print()
    else:
        print("=" * 80)
        print("⚠️  ВНИМАНИЕ! РЕЖИМ УДАЛЕНИЯ АКТИВИРОВАН!")
        print("Дубликаты будут удалены из базы данных!")
        print("=" * 80)
        print()
        response = input("Вы уверены? Введите 'YES' для продолжения: ")
        if response != "YES":
            print("Отменено пользователем.")
            sys.exit(0)
    
    # Создаем сессию
    db = next(get_db())
    
    try:
        remove_duplicates(db, batch_size=1000, dry_run=dry_run)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

