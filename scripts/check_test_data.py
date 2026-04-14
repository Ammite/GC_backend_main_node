"""
Скрипт для проверки данных в БД для создания тестового примера документов
"""
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import SessionLocal
from models.organization import Organization
from models.store import Store
from models.item import Item
from models.conception import Conception
from models.supplier import Supplier
from models.account import Account

def check_data():
    db = SessionLocal()
    try:
        print("=" * 80)
        print("ДАННЫЕ ДЛЯ СОЗДАНИЯ ТЕСТОВОГО ДОКУМЕНТА")
        print("=" * 80)
        
        # Организации
        print("\n📋 ОРГАНИЗАЦИИ:")
        organizations = db.query(Organization).limit(5).all()
        if organizations:
            for org in organizations:
                print(f"  ID: {org.id}, iiko_id: {org.iiko_id}, name: {org.name}")
        else:
            print("  Нет организаций")
        
        # Склады
        print("\n🏪 СКЛАДЫ:")
        stores = db.query(Store).limit(5).all()
        if stores:
            for store in stores:
                print(f"  ID: {store.id}, iiko_id: {store.iiko_id}, name: {store.name}, code: {store.code}")
        else:
            print("  Нет складов")
        
        # Концепции
        print("\n💼 КОНЦЕПЦИИ:")
        conceptions = db.query(Conception).limit(5).all()
        if conceptions:
            for conception in conceptions:
                print(f"  ID: {conception.id}, iiko_id: {conception.iiko_id}, name: {conception.name}, code: {conception.code}")
        else:
            print("  Нет концепций")
        
        # Поставщики
        print("\n🚚 ПОСТАВЩИКИ:")
        suppliers = db.query(Supplier).limit(5).all()
        if suppliers:
            for supplier in suppliers:
                print(f"  ID: {supplier.id}, iiko_id: {supplier.iiko_id}, name: {supplier.name}, code: {supplier.code}")
        else:
            print("  Нет поставщиков")
        
        # Счета
        print("\n💰 СЧЕТА:")
        accounts = db.query(Account).limit(5).all()
        if accounts:
            for account in accounts:
                print(f"  ID: {account.id}, iiko_id: {account.iiko_id}, name: {account.name}, code: {account.code}")
        else:
            print("  Нет счетов")
        
        # Товары
        print("\n📦 ТОВАРЫ:")
        items = db.query(Item).limit(10).all()
        if items:
            for item in items:
                print(f"  ID: {item.id}, iiko_id: {item.iiko_id}, name: {item.name}")
        else:
            print("  Нет товаров")
        
        print("\n" + "=" * 80)
        print("РЕКОМЕНДУЕМЫЕ ДАННЫЕ ДЛЯ ТЕСТОВОГО ПРИМЕРА:")
        print("=" * 80)
        
        if organizations and stores and items:
            org = organizations[0]
            store = stores[0]
            item1 = items[0] if len(items) > 0 else None
            item2 = items[1] if len(items) > 1 else None
            
            print(f"\nОрганизация ID: {org.id}")
            print(f"Склад ID: {store.id}")
            if item1:
                print(f"Товар 1 ID: {item1.id}")
            if item2:
                print(f"Товар 2 ID: {item2.id}")
            
            if conceptions:
                conception = conceptions[0]
                print(f"Концепция ID: {conception.id} (name: {conception.name}, code: {conception.code})")
            
            if suppliers:
                supplier = suppliers[0]
                print(f"Поставщик ID: {supplier.id} (name: {supplier.name})")
            
            if accounts:
                account = accounts[0]
                print(f"Счет ID: {account.id} (name: {account.name}, code: {account.code})")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_data()

