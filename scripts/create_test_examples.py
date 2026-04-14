"""
Скрипт для создания тестовых примеров запросов на создание документов
"""
import sys
import os
import json
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import SessionLocal
from models.organization import Organization
from models.store import Store
from models.item import Item
from models.conception import Conception
from models.supplier import Supplier
from models.account import Account

def create_test_examples():
    db = SessionLocal()
    try:
        # Получаем данные
        org = db.query(Organization).first()
        store = db.query(Store).first()
        items = db.query(Item).limit(3).all()
        conception = db.query(Conception).filter(
            (Conception.name == "ГК 9 Премьера") | (Conception.code == "13")
        ).first()
        supplier = db.query(Supplier).first()
        account = db.query(Account).first()
        
        if not org:
            print("❌ Ошибка: Нет организаций в БД")
            return
        
        if not items:
            print("❌ Ошибка: Нет товаров в БД")
            return
        
        examples = {}
        
        # Пример 1: Приходная накладная (INCOMING_INVOICE)
        if store and conception and supplier:
            examples["incoming_invoice"] = {
                "document_type": "INCOMING_INVOICE",
                "document_number": None,  # Будет сгенерирован автоматически
                "date": datetime.now().strftime("%d.%m.%Y"),
                "date_incoming": datetime.now().strftime("%d.%m.%Y"),
                "organization_id": org.id,
                "store_id": store.id,
                "conception_id": conception.id,  # Будет заменено на захардкоженную "ГК 9 Премьера"
                "supplier_id": supplier.id,
                "invoice": "TEST-INV-001",
                "comment": "Тестовая приходная накладная",
                "items": [
                    {
                        "item_id": items[0].id,
                        "quantity": 10.0,
                        "price": 100.0,
                        "amount": 1000.0
                    },
                    {
                        "item_id": items[1].id if len(items) > 1 else items[0].id,
                        "quantity": 5.0,
                        "price": 200.0,
                        "amount": 1000.0
                    }
                ]
            }
        else:
            examples["incoming_invoice"] = {
                "note": "⚠️ Требуется синхронизация: склады, концепции, поставщики",
                "document_type": "INCOMING_INVOICE",
                "organization_id": org.id,
                "items": [
                    {
                        "item_id": items[0].id,
                        "quantity": 10.0,
                        "price": 100.0,
                        "amount": 1000.0
                    }
                ]
            }
        
        # Пример 2: Расходная накладная (OUTGOING_INVOICE)
        if store and account:
            examples["outgoing_invoice"] = {
                "document_type": "OUTGOING_INVOICE",
                "document_number": None,  # Будет сгенерирован автоматически
                "date": datetime.now().strftime("%d.%m.%Y"),
                "date_incoming": datetime.now().strftime("%d.%m.%Y"),
                "organization_id": org.id,
                "default_store_id": store.id,
                "account_id": account.id,
                "comment": "Тестовая расходная накладная",
                "items": [
                    {
                        "item_id": items[0].id,
                        "quantity": 5.0,
                        "price": 100.0,
                        "amount": 500.0
                    }
                ]
            }
        else:
            examples["outgoing_invoice"] = {
                "note": "⚠️ Требуется синхронизация: склады, счета",
                "document_type": "OUTGOING_INVOICE",
                "organization_id": org.id,
                "items": [
                    {
                        "item_id": items[0].id,
                        "quantity": 5.0,
                        "price": 100.0,
                        "amount": 500.0
                    }
                ]
            }
        
        # Пример 3: Акт списания (WRITEOFF)
        if store and account:
            examples["writeoff"] = {
                "date_incoming": datetime.now().strftime("%Y-%m-%d"),
                "organization_id": org.id,
                "store_id": store.id,
                "account_id": account.id,
                "status": "NEW",
                "comment": "Тестовый акт списания",
                "items": [
                    {
                        "item_id": items[0].id,
                        "amount": 2.0,
                        "cost": 200.0
                    }
                ]
            }
        else:
            examples["writeoff"] = {
                "note": "⚠️ Требуется синхронизация: склады, счета",
                "organization_id": org.id,
                "items": [
                    {
                        "item_id": items[0].id,
                        "amount": 2.0,
                        "cost": 200.0
                    }
                ]
            }
        
        # Выводим примеры
        print("=" * 80)
        print("ТЕСТОВЫЕ ПРИМЕРЫ ЗАПРОСОВ ДЛЯ СОЗДАНИЯ ДОКУМЕНТОВ")
        print("=" * 80)
        print("\n📋 Используемые данные:")
        print(f"  Организация: ID={org.id}, name={org.name}")
        if store:
            print(f"  Склад: ID={store.id}, name={store.name}")
        if conception:
            print(f"  Концепция: ID={conception.id}, name={conception.name}, code={conception.code}")
        if supplier:
            print(f"  Поставщик: ID={supplier.id}, name={supplier.name}")
        if account:
            print(f"  Счет: ID={account.id}, name={account.name}, code={account.code}")
        print(f"  Товары: {len(items)} шт.")
        for i, item in enumerate(items, 1):
            print(f"    {i}. ID={item.id}, name={item.name}")
        
        print("\n" + "=" * 80)
        print("1. ПРИХОДНАЯ НАКЛАДНАЯ (INCOMING_INVOICE)")
        print("=" * 80)
        print("POST /warehouse/documents")
        print(json.dumps(examples["incoming_invoice"], indent=2, ensure_ascii=False))
        
        print("\n" + "=" * 80)
        print("2. РАСХОДНАЯ НАКЛАДНАЯ (OUTGOING_INVOICE)")
        print("=" * 80)
        print("POST /warehouse/documents")
        print(json.dumps(examples["outgoing_invoice"], indent=2, ensure_ascii=False))
        
        print("\n" + "=" * 80)
        print("3. АКТ СПИСАНИЯ (WRITEOFF)")
        print("=" * 80)
        print("POST /warehouse/writeoff-documents")
        print(json.dumps(examples["writeoff"], indent=2, ensure_ascii=False))
        
        # Сохраняем в файл
        output_file = os.path.join(os.path.dirname(__file__), "test_examples.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(examples, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n✅ Примеры сохранены в файл: {output_file}")
        
    finally:
        db.close()

if __name__ == "__main__":
    create_test_examples()

