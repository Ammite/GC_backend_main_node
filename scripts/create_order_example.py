"""
Скрипт для создания примера запроса на создание заказа
"""
import sys
import os
import json

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import SessionLocal
from models.user import User
from models.employees import Employees
from models.item import Item
from models.tables import Table
from models.organization import Organization
import random

def create_order_example():
    db = SessionLocal()
    try:
        print("=" * 80)
        print("ПОИСК ДАННЫХ ДЛЯ СОЗДАНИЯ ПРИМЕРА ЗАКАЗА")
        print("=" * 80)
        
        # Ищем пользователя с id=10
        user = db.query(User).filter(User.id == 10).first()
        if not user:
            print("❌ Пользователь с ID=10 не найден в таблице users")
            print("\nДоступные пользователи:")
            users = db.query(User).limit(10).all()
            for u in users:
                print(f"  ID: {u.id}, name: {u.name}, login: {u.login}, iiko_id: {u.iiko_id}")
            return
        
        print(f"\n✅ Найден пользователь:")
        print(f"  ID: {user.id}")
        print(f"  name: {user.name}")
        print(f"  login: {user.login}")
        print(f"  iiko_id: {user.iiko_id}")
        
        # Ищем соответствующего сотрудника (employee) по iiko_id
        waiter = None
        if user.iiko_id:
            waiter = db.query(Employees).filter(Employees.iiko_id == user.iiko_id).first()
        
        if not waiter:
            print("\n⚠️ Сотрудник (employee) с таким iiko_id не найден")
            print("Попробуем найти любого сотрудника...")
            waiter = db.query(Employees).first()
            if waiter:
                print(f"  Используем случайного сотрудника: ID={waiter.id}, name={waiter.name}")
            else:
                print("❌ Сотрудники не найдены в БД")
                return
        else:
            print(f"\n✅ Найден сотрудник (официант):")
            print(f"  ID: {waiter.id}")
            print(f"  name: {waiter.name}")
            print(f"  iiko_id: {waiter.iiko_id}")
        
        # Ищем два случайных товара
        items = db.query(Item).filter(Item.deleted == False).all()
        if not items:
            print("\n❌ Товары не найдены в БД")
            return
        
        if len(items) < 2:
            print(f"\n⚠️ Найдено только {len(items)} товар(ов), используем все доступные")
            selected_items = items
        else:
            selected_items = random.sample(items, 2)
        
        print(f"\n✅ Найдено товаров: {len(items)}")
        print(f"Выбрано {len(selected_items)} случайных товара для примера:")
        for item in selected_items:
            print(f"  ID: {item.id}, name: {item.name}, price: {item.price}")
        
        # Ищем стол (опционально)
        table = db.query(Table).filter(Table.is_deleted == False).first()
        if table:
            print(f"\n✅ Найден стол:")
            print(f"  ID: {table.id}, number: {table.number}, name: {table.name}")
        else:
            print("\n⚠️ Столы не найдены (tableId будет null в запросе)")
        
        # Ищем организацию (опционально)
        org = db.query(Organization).filter(Organization.is_active == True).first()
        if org:
            print(f"\n✅ Найдена организация:")
            print(f"  ID: {org.id}, name: {org.name}")
        else:
            print("\n⚠️ Организации не найдены (organizationId будет null в запросе)")
        
        # Формируем пример запроса
        print("\n" + "=" * 80)
        print("ПРИМЕР ЗАПРОСА ДЛЯ СОЗДАНИЯ ЗАКАЗА")
        print("=" * 80)
        
        order_request = {
            "waiterId": waiter.id,
            "guests": 2,
            "items": []
        }
        
        if org:
            order_request["organizationId"] = org.id
        
        if table:
            order_request["tableId"] = table.id
        
        # Добавляем товары
        for item in selected_items:
            amount = round(random.uniform(1.0, 3.0), 1)  # Случайное количество от 1 до 3
            price = float(item.price)
            total_sum = round(amount * price, 2)
            
            order_request["items"].append({
                "productId": item.id,
                "amount": amount,
                "price": price,
                "sum": total_sum,
                "comment": None
            })
        
        if order_request.get("comment") is None:
            order_request["comment"] = "Тестовый заказ"
        
        # Выводим JSON
        print("\n```json")
        print(json.dumps(order_request, ensure_ascii=False, indent=2))
        print("```")
        
        # Выводим curl пример
        print("\n" + "=" * 80)
        print("ПРИМЕР CURL ЗАПРОСА")
        print("=" * 80)
        print("\n```bash")
        json_str = json.dumps(order_request, ensure_ascii=False)
        print(f'curl -X POST "http://localhost:8000/orders" \\')
        print(f'  -H "Content-Type: application/json" \\')
        print(f'  -H "Authorization: Bearer YOUR_TOKEN" \\')
        print(f'  -d \'{json_str}\'')
        print("```")
        
        print("\n" + "=" * 80)
        print("ИНФОРМАЦИЯ О ДАННЫХ")
        print("=" * 80)
        print(f"\nПользователь (users): ID={user.id}, name={user.name}")
        print(f"Официант (employees): ID={waiter.id}, name={waiter.name}")
        if org:
            print(f"Организация: ID={org.id}, name={org.name}")
        if table:
            print(f"Стол: ID={table.id}, number={table.number}")
        print(f"\nТовары в заказе:")
        for i, item in enumerate(selected_items, 1):
            order_item = order_request["items"][i-1]
            print(f"  {i}. ID={item.id}, name={item.name}, amount={order_item['amount']}, price={order_item['price']}, sum={order_item['sum']}")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    create_order_example()
