"""
Создание тестовой концепции "ГК 9 Премьера" с кодом "13"
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import SessionLocal
from models.conception import Conception
from models.organization import Organization

def create_test_conception():
    db = SessionLocal()
    try:
        # Проверяем, есть ли уже концепция
        conception = db.query(Conception).filter(
            (Conception.name == "ГК 9 Премьера") | (Conception.code == "13")
        ).first()
        
        if conception:
            print(f"✅ Концепция уже существует:")
            print(f"  ID: {conception.id}")
            print(f"  name: {conception.name}")
            print(f"  code: {conception.code}")
            print(f"  iiko_id: {conception.iiko_id}")
            return conception.id
        
        # Проверяем организацию 8
        org = db.query(Organization).filter(Organization.id == 8).first()
        if not org:
            print("❌ Организация с ID=8 не найдена")
            return
        
        # Создаем тестовую концепцию
        test_conception = Conception(
            iiko_id="test-conception-001",
            name="ГК 9 Премьера",
            code="13",
            organization_id=org.id,
            is_active=True
        )
        
        db.add(test_conception)
        db.commit()
        db.refresh(test_conception)
        
        print(f"✅ Создана тестовая концепция:")
        print(f"  ID: {test_conception.id}")
        print(f"  name: {test_conception.name}")
        print(f"  code: {test_conception.code}")
        print(f"  iiko_id: {test_conception.iiko_id}")
        print(f"  organization_id: {test_conception.organization_id}")
        
        return test_conception.id
        
    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    conception_id = create_test_conception()
    if conception_id:
        print(f"\n💡 Conception ID для использования: {conception_id}")

