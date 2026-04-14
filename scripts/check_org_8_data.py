"""
Проверка данных для организации ID=8
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import SessionLocal
from models.organization import Organization
from models.store import Store
from models.item import Item
from models.account import Account

def check_org_8():
    db = SessionLocal()
    try:
        org = db.query(Organization).filter(Organization.id == 8).first()
        if not org:
            print("❌ Организация с ID=8 не найдена")
            return
        
        print(f"✅ Организация: ID={org.id}, name={org.name}, iiko_id={org.iiko_id}")
        
        # Склады
        stores = db.query(Store).all()
        print(f"\n🏪 Склады (всего: {len(stores)}):")
        if stores:
            for store in stores[:10]:
                print(f"  ID: {store.id}, name: {store.name}, iiko_id: {store.iiko_id}")
        else:
            print("  Нет складов")
        
        # Товары
        items = db.query(Item).filter(Item.organization_id == 8).limit(10).all()
        print(f"\n📦 Товары для организации {org.id} (найдено: {len(items)}):")
        if items:
            for item in items:
                print(f"  ID: {item.id}, name: {item.name}, iiko_id: {item.iiko_id}")
        else:
            # Если нет товаров для этой организации, показываем любые товары
            items = db.query(Item).limit(10).all()
            print(f"  Товаров для организации {org.id} нет, показываем любые товары:")
            for item in items:
                print(f"  ID: {item.id}, name: {item.name}, iiko_id: {item.iiko_id}")
        
        # Счета
        accounts = db.query(Account).limit(5).all()
        print(f"\n💰 Счета:")
        if accounts:
            for account in accounts:
                print(f"  ID: {account.id}, name: {account.name}, code: {account.code}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_org_8()

