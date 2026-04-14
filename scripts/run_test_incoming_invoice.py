"""
Прямое выполнение тестового запроса на создание приходной накладной
"""
import sys
import os
import asyncio
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import SessionLocal
from services.warehouse.invoice_service import create_incoming_invoice_in_iiko
from schemas.warehouse import CreateWarehouseDocumentRequest, WarehouseDocumentItemRequest
from models.store import Store
from models.item import Item
from models.supplier import Supplier

async def run_test():
    db = SessionLocal()
    try:
        print("=" * 80)
        print("ТЕСТОВЫЙ ЗАПРОС: СОЗДАНИЕ ПРИХОДНОЙ НАКЛАДНОЙ")
        print("=" * 80)
        
        # Проверяем данные
        org_id = 8
        print(f"\n📋 Организация ID: {org_id}")
        
        # Склады
        stores = db.query(Store).all()
        if not stores:
            print("❌ Ошибка: Нет складов в БД. Необходимо синхронизировать через POST /sync/stores")
            print("   Или создайте склад вручную в БД")
            return
        
        store = stores[0]
        print(f"🏪 Склад: ID={store.id}, name={store.name}")
        
        # Товары
        items = db.query(Item).limit(2).all()
        if not items:
            print("❌ Ошибка: Нет товаров в БД")
            return
        
        item1 = items[0]
        print(f"📦 Товар 1: ID={item1.id}, name={item1.name}")
        if len(items) > 1:
            item2 = items[1]
            print(f"📦 Товар 2: ID={item2.id}, name={item2.name}")
        
        # Поставщики (опционально)
        supplier = db.query(Supplier).first()
        if supplier:
            print(f"🚚 Поставщик: ID={supplier.id}, name={supplier.name}")
        
        # Создаем запрос
        items_data = [
            WarehouseDocumentItemRequest(
                item_id=item1.id,
                quantity=10.0,
                price=100.0,
                amount=1000.0
            )
        ]
        
        if len(items) > 1:
            items_data.append(
                WarehouseDocumentItemRequest(
                    item_id=item2.id,
                    quantity=5.0,
                    price=200.0,
                    amount=1000.0
                )
            )
        
        document_data = CreateWarehouseDocumentRequest(
            document_type="INCOMING_INVOICE",
            date=datetime.now().strftime("%d.%m.%Y"),
            date_incoming=datetime.now().strftime("%d.%m.%Y"),
            organization_id=org_id,
            store_id=store.id,
            supplier_id=supplier.id if supplier else None,
            invoice="TEST-INV-001",
            comment="Тестовая приходная накладная для организации Премьера (ID=8)",
            items=items_data
        )
        
        print("\n" + "=" * 80)
        print("ВЫПОЛНЕНИЕ ЗАПРОСА...")
        print("=" * 80)
        
        # Выполняем запрос
        result = await create_incoming_invoice_in_iiko(
            db=db,
            document_data=document_data,
            user_id=1  # Тестовый user_id
        )
        
        print("\n" + "=" * 80)
        print("РЕЗУЛЬТАТ:")
        print("=" * 80)
        print(f"Success: {result.get('success')}")
        print(f"Message: {result.get('message')}")
        if result.get('iiko_id'):
            print(f"iiko_id: {result.get('iiko_id')}")
        if result.get('document_id'):
            print(f"document_id: {result.get('document_id')}")
        
        if result.get('success'):
            print("\n✅ Документ успешно создан!")
        else:
            print("\n❌ Ошибка при создании документа")
            print(f"   {result.get('message')}")
        
    except Exception as e:
        print(f"\n❌ Исключение: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_test())

