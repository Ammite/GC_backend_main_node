"""
Синхронизация складов и создание тестового запроса
"""
import sys
import os
import json
import asyncio
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import SessionLocal
from services.warehouse.balance_service import sync_stores_from_iiko
from models.store import Store
from models.item import Item
from models.supplier import Supplier

async def sync_and_create_test():
    db = SessionLocal()
    try:
        print("🔄 Синхронизация складов...")
        result = await sync_stores_from_iiko(db)
        print(f"✅ {result.get('message', 'Синхронизация завершена')}")
        
        # Проверяем склады
        stores = db.query(Store).all()
        print(f"\n🏪 Найдено складов: {len(stores)}")
        if stores:
            for store in stores[:5]:
                print(f"  ID: {store.id}, name: {store.name}")
            store_id = stores[0].id
        else:
            print("❌ Склады не найдены после синхронизации")
            return
        
        # Проверяем поставщиков
        suppliers = db.query(Supplier).all()
        print(f"\n🚚 Найдено поставщиков: {len(suppliers)}")
        supplier_id = None
        if suppliers:
            for supplier in suppliers[:3]:
                print(f"  ID: {supplier.id}, name: {supplier.name}")
            supplier_id = suppliers[0].id
        else:
            print("⚠️ Поставщики не найдены (можно синхронизировать через POST /sync/suppliers)")
        
        # Товары
        items = db.query(Item).limit(3).all()
        if not items:
            print("❌ Товары не найдены")
            return
        
        # Создаем тестовый запрос
        test_request = {
            "document_type": "INCOMING_INVOICE",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "date_incoming": datetime.now().strftime("%d.%m.%Y"),
            "organization_id": 8,
            "store_id": store_id,
            "invoice": "TEST-INV-001",
            "comment": "Тестовая приходная накладная для организации Премьера",
            "items": [
                {
                    "item_id": items[0].id,
                    "quantity": 10.0,
                    "price": 100.0,
                    "amount": 1000.0
                }
            ]
        }
        
        if supplier_id:
            test_request["supplier_id"] = supplier_id
        
        print("\n" + "=" * 80)
        print("ТЕСТОВЫЙ ЗАПРОС ДЛЯ ПРИХОДНОЙ НАКЛАДНОЙ")
        print("=" * 80)
        print(f"POST /warehouse/documents")
        print(json.dumps(test_request, indent=2, ensure_ascii=False))
        
        # Сохраняем в файл
        output_file = os.path.join(os.path.dirname(__file__), "test_request_org_8.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(test_request, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Запрос сохранен в: {output_file}")
        print("\n💡 Для выполнения запроса используйте:")
        print(f"   curl -X POST 'http://localhost:8000/warehouse/documents' \\")
        print(f"     -H 'Content-Type: application/json' \\")
        print(f"     -H 'Authorization: Bearer YOUR_TOKEN' \\")
        print(f"     -d @{output_file}")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(sync_and_create_test())

