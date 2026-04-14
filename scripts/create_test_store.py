"""
Создание тестового склада для организации 8
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import SessionLocal
from models.store import Store
from models.organization import Organization

def create_test_store():
    db = SessionLocal()
    try:
        # Проверяем организацию
        org = db.query(Organization).filter(Organization.id == 8).first()
        if not org:
            print("❌ Организация с ID=8 не найдена")
            return
        
        print(f"✅ Организация: ID={org.id}, name={org.name}")
        
        # Проверяем, есть ли уже склады
        existing_stores = db.query(Store).all()
        if existing_stores:
            print(f"\n🏪 Уже есть склады ({len(existing_stores)} шт.):")
            for store in existing_stores:
                print(f"  ID: {store.id}, name: {store.name}, iiko_id: {store.iiko_id}")
            print("\n✅ Используем существующий склад")
            return existing_stores[0].id
        
        # Создаем тестовый склад
        test_store = Store(
            iiko_id="test-store-001",
            name="Тестовый склад",
            code="TEST-001",
            organization_id=org.id,
            is_active=True
        )
        
        db.add(test_store)
        db.commit()
        db.refresh(test_store)
        
        print(f"\n✅ Создан тестовый склад:")
        print(f"  ID: {test_store.id}")
        print(f"  name: {test_store.name}")
        print(f"  iiko_id: {test_store.iiko_id}")
        print(f"  organization_id: {test_store.organization_id}")
        
        return test_store.id
        
    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    store_id = create_test_store()
    if store_id:
        print(f"\n💡 Store ID для использования: {store_id}")

