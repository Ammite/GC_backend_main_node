'''
Задача этого модуля - сопоставить комиссии из отчета терминала с заказами в БД.

Создаем функцию которая будет находить по сумме, времени и адресу нужную транзакцию в БД.

Алгоритм работы:
1. Функция получает сумму, время и organization_id.
2. Ищем в БД в таблице sales по полям:
    - precheque_time с фильтром на время от вчерашнего дня с 12:00 до 12:00 следующего дня.
    - organization_id.
3. Получаем список транзакций по этим фильтрам. 
4. Группируем список транзакций по payment_transaction_id. Это id транзакции внутри бд.
5. Сравниваем сумму транзакции с суммой чека.
6. Если сумма транзакции совпадает с суммой чека, то это нужная нам транзакция.
7. Если сумма транзакции не совпадает с суммой чека, то ищем по discount в таблице d_order с учетом фильтров времени и organization_id.
8. Возвращаем список подходящих транзакций. 


Следующая функция будет сопоставлять транзакции с заказами в БД.

1. Функция получает список подходящих транзакций.
2. Оцениваем какая транзакция лучше всего подходит по сумме, времени и organization_id.
3. Возвращаем лучшую транзакцию.

Следующая функция будет сопоставлять транзакции с заказами в БД.

1. Получаем транзакцию из предыдущей функции.
2. Находим заказ в бд в таблице d_order по полю iiko_id полученную из sales (поле order_id).
3. Суммируем комиссию с уже существующей в таблице d_order.bank_commission (если заказ уже имеет комиссию).
4. Записываем в таблице для текущей транзакции bank_commission order_id и order_iiko_id этого d_order. (тем самым мы связываем транзакцию у которой комиссия записана с заказом)


Нужно чтобы все эти функции записывали отчетность. 
Мне нужно записывать:
    - Количество транзакций из bank_commissions.
    - Количество транзакций из bank_commissions которые не были сопоставлены с заказами.
    - Количество транзакций из bank_commissions которые были сопоставлены с заказами.

    - Общая сумма комиссий из bank_commissions.
    - Общая сумма комиссий из bank_commissions которые не были сопоставлены с заказами.
    - Общая сумма комиссий из bank_commissions которые были сопоставлены с заказами.

    - Количество заказов, которым была записана комиссия.
    - Общая сумма комиссий, записанная в заказы.
    - Количество комиссий, которые были суммированы с уже существующими.

    - Список транзакций из bank_commissions которые не были сопоставлены с заказами.
    - Список транзакций из bank_commissions которые были сопоставлены с заказами.
    - Список заказов, которым была записана комиссия.

'''

from sqlalchemy.orm import sessionmaker
from sqlalchemy import and_, func, desc
from database.database import engine
from models.bank_commission import BankCommission
from models.sales import Sales
from models.d_order import DOrder
from datetime import datetime, timedelta
from decimal import Decimal
import json

# Глобальные переменные для отслеживания использования транзакций
# Структура: {payment_transaction_id: {"sales_list": [sales], "total_amount": float, "used": bool, "organization_id": int, "precheque_time": datetime, "opentime": datetime, "closetime": datetime}}
not_used_transactions = {}
used_transactions = {}


def get_session():
    """Создает сессию для работы с БД"""
    Session = sessionmaker(bind=engine)
    return Session()


def initialize_transaction_tracker(session):
    """
    Инициализирует трекер транзакций для всех payment_transaction_id.
    Собирает все distinct(payment_transaction_id) и группирует по ним sales.
    """
    global not_used_transactions, used_transactions
    not_used_transactions = {}
    used_transactions = {}
    
    # Получаем все уникальные payment_transaction_id
    distinct_transaction_ids = session.query(Sales.payment_transaction_id).filter(
        Sales.payment_transaction_id.isnot(None)
    ).distinct().all()
    
    for (transaction_id,) in distinct_transaction_ids:
        # Получаем все sales для этого payment_transaction_id
        sales_list = session.query(Sales).filter(
            Sales.payment_transaction_id == transaction_id
        ).all()
        
        if sales_list:
            # Суммируем dish_discount_sum_int
            total_amount = sum(float(sale.dish_discount_sum_int or 0) for sale in sales_list)
            
            # Берем organization_id и precheque_time из первой записи
            representative_sale = sales_list[0]
            
            transaction_data = {
                "sales_list": sales_list,
                "total_amount": total_amount,
                "used": False,
                "organization_id": representative_sale.organization_id,
                "precheque_time": representative_sale.precheque_time,  # Может быть None
                "opentime": representative_sale.open_time,  # Может быть None
                "closetime": representative_sale.close_time  # Может быть None
            }
            
            # Добавляем в словарь неиспользованных транзакций
            not_used_transactions[transaction_id] = transaction_data


def mark_transaction_as_used(transaction_id):
    """
    Помечает транзакцию как использованную.
    Перемещает её из not_used_transactions в used_transactions.
    
    Args:
        transaction_id: ID транзакции
    """
    global not_used_transactions, used_transactions
    
    if transaction_id in not_used_transactions:
        # Помечаем как использованную
        transaction_data = not_used_transactions[transaction_id]
        transaction_data["used"] = True
        
        # Перемещаем в словарь использованных
        used_transactions[transaction_id] = transaction_data
        
        # Удаляем из словаря неиспользованных
        del not_used_transactions[transaction_id]


def get_transaction_tracker_stats():
    """
    Возвращает статистику по использованию транзакций.
    
    Returns:
        dict: статистика использования
    """
    global not_used_transactions, used_transactions
    
    total_transactions = len(not_used_transactions) + len(used_transactions)
    used_count = len(used_transactions)
    not_used_count = len(not_used_transactions)
    
    return {
        "total_transactions": total_transactions,
        "used_transactions": used_count,
        "not_used_transactions": not_used_count,
        "not_used_transactions_data": not_used_transactions,
        "used_transactions_data": used_transactions
    }


def find_transactions_by_amount_time_org(amount, transaction_time, organization_id, session):
    """
    Находит транзакции в словаре not_used_transactions по сумме, времени и organization_id.
    
    Args:
        amount: сумма транзакции
        transaction_time: время транзакции
        organization_id: ID организации
        session: сессия БД (не используется в новой логике)
    
    Returns:
        list: список подходящих групп транзакций с суммированными суммами
    """
    global not_used_transactions
    
    # Определяем временной диапазон (от вчерашнего дня с 12:00 до 12:00 следующего дня)
    transaction_date = transaction_time.date()
    start_time = datetime.combine(transaction_date - timedelta(days=1), datetime.min.time().replace(hour=12))
    end_time = datetime.combine(transaction_date + timedelta(days=1), datetime.min.time().replace(hour=12))
    
    matching_transaction_groups = []
    
    # Ищем в словаре неиспользованных транзакций
    for transaction_id, transaction_data in not_used_transactions.items():
        # Проверяем временной диапазон по любому из полей времени (precheque_time OR opentime OR closetime)
        precheque_time = transaction_data["precheque_time"]
        opentime = transaction_data["opentime"]
        closetime = transaction_data["closetime"]
        
        # Проверяем, есть ли хотя бы одно время в нужном диапазоне
        time_in_range = False
        if precheque_time and (start_time <= precheque_time <= end_time):
            time_in_range = True
        elif opentime and (start_time <= opentime <= end_time):
            time_in_range = True
        elif closetime and (start_time <= closetime <= end_time):
            time_in_range = True
            
        if not time_in_range:
            continue
            
        # Проверяем organization_id если указан
        if organization_id is not None and transaction_data["organization_id"] != organization_id:
            continue
        
        # Проверяем сумму
        total_amount = transaction_data["total_amount"]
        if abs(total_amount - float(amount)) < 1:  # Учитываем погрешность округления
            matching_transaction_groups.append({
                'transaction_id': transaction_id,
                'total_amount': total_amount,
                'sales_list': transaction_data["sales_list"],
                'representative_sale': transaction_data["sales_list"][0]  # Берем первую запись как представителя группы
            })
        else:
            # Если не совпадает, ищем по discount в d_order
            order_ids = [sale.order_id for sale in transaction_data["sales_list"] if sale.order_id]
            if order_ids:
                if organization_id is not None:
                    # Если organization_id указан, ищем только в этой организации
                    orders = session.query(DOrder).filter(
                        and_(
                            DOrder.iiko_id.in_(order_ids),
                            DOrder.organization_id == organization_id,
                            DOrder.time_order >= start_time,
                            DOrder.time_order <= end_time
                        )
                    ).all()
                else:
                    # Если organization_id не указан, ищем по всем организациям
                    orders = session.query(DOrder).filter(
                        and_(
                            DOrder.iiko_id.in_(order_ids),
                            DOrder.time_order >= start_time,
                            DOrder.time_order <= end_time
                        )
                    ).all()
                
                for order in orders:
                    if order.discount and abs(float(order.discount) - float(amount)) < 0.01:
                        matching_transaction_groups.append({
                            'transaction_id': transaction_id,
                            'total_amount': total_amount,
                            'sales_list': transaction_data["sales_list"],
                            'representative_sale': transaction_data["sales_list"][0]  # Берем первую запись как представителя группы
                        })
                        break
    
    return matching_transaction_groups


def find_best_matching_transaction(transaction_groups, amount, transaction_time, organization_id):
    """
    Находит лучшую группу транзакций из списка по сумме, времени и organization_id.
    
    Args:
        transaction_groups: список групп транзакций с суммированными суммами
        amount: сумма для сравнения
        transaction_time: время для сравнения
        organization_id: ID организации
    
    Returns:
        dict: лучшая группа транзакций или None
    """
    if not transaction_groups:
        return None
    
    best_group = None
    best_score = float('inf')
    
    for group in transaction_groups:
        score = 0
        
        # Оценка по сумме (используем суммированную сумму группы)
        group_amount = group['total_amount']
        amount_diff = abs(group_amount - float(amount))
        score += amount_diff

        order_id = group['representative_sale'].order_id
        
        
        # Оценка по времени (используем представителя группы)
        representative_sale = group['representative_sale']
        if representative_sale.precheque_time:
            time_diff = abs((representative_sale.precheque_time - transaction_time).total_seconds())
            score += time_diff / 3600  # Конвертируем в часы
        
        # Оценка по organization_id (должен совпадать, если organization_id указан)
        if organization_id is not None and representative_sale.organization_id != organization_id:
            continue
            score += 100000  # Большой штраф за несовпадение организации
        
        if score < best_score:
            best_score = score
            best_group = group
    
    return best_group


def sync_commission_with_order(bank_commission_id, session):
    """
    Сопоставляет комиссию с заказом и записывает данные в БД.
    
    Args:
        bank_commission_id: ID комиссии в таблице bank_commissions
        session: сессия БД
    
    Returns:
        dict: результат операции
    """
    # Получаем комиссию из БД
    commission = session.query(BankCommission).filter(BankCommission.id == bank_commission_id).first()
    if not commission:
        return {"success": False, "error": "Commission not found"}
    
    # Ищем подходящие группы транзакций
    # print(f"[INFO] Searching for matching transactions for commission {bank_commission_id} with amount {commission.amount}")
    transaction_groups = find_transactions_by_amount_time_org(
        commission.amount, 
        commission.time_transaction, 
        commission.organization_id, 
        session
    )
    
    if not transaction_groups:
        return {"success": False, "error": "No matching transactions found"}
    
    # Находим лучшую группу транзакций
    # print(f"[INFO] Found {len(transaction_groups)} transaction groups")
    best_group = find_best_matching_transaction(
        transaction_groups, 
        commission.amount, 
        commission.time_transaction, 
        commission.organization_id
    )
    # print(f"[INFO] Best group: found")
    if not best_group:
        return {"success": False, "error": "No suitable transaction found"}
    
    # Используем представителя группы для поиска заказа
    representative_sale = best_group['representative_sale']
    transaction_id = best_group['transaction_id']
    
    order = session.query(DOrder).filter(
        DOrder.iiko_id == representative_sale.order_id
    ).first()
    
    if not order:
        return {"success": False, "error": "Order not found"}
    
    try:
        # Проверяем, что комиссия еще не была сопоставлена
        if commission.order_id:
            return {"success": False, "error": f"Commission {commission.id} already has order_id {commission.order_id}"}
        
        # Суммируем комиссию с уже существующей (если есть)
        current_commission = float(order.bank_commission or 0)
        commission_amount = float(commission.bank_commission or 0)
        total_commission = current_commission + commission_amount
        
        # Записываем суммарную комиссию в заказ
        order.bank_commission = total_commission
        
        # Обновляем связь в таблице комиссий
        commission.order_id = order.id
        commission.order_iiko_id = order.iiko_id
        
        # Помечаем транзакцию как использованную
        mark_transaction_as_used(transaction_id)
        
        session.commit()
        # print(f"[INFO] Commission {commission.id} successfully matched with order {order.id}")
        
        return {
            "success": True, 
            "order_id": order.id,
            "order_iiko_id": order.iiko_id,
            "commission_amount": commission_amount,
            "total_commission_amount": total_commission,
            "was_summed": current_commission > 0,
            "transaction_id": transaction_id
        }
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}


def sync_all_commissions_with_orders():
    """
    Сопоставляет все комиссии с заказами и возвращает отчетность.
    
    Returns:
        dict: отчетность по сопоставлению
    """
    session = get_session()
    
    try:
        # Инициализируем трекер транзакций
        print("[INFO] Initializing transaction tracker...")
        initialize_transaction_tracker(session)
        tracker_stats = get_transaction_tracker_stats()
        print(f"[INFO] Tracker initialized: {tracker_stats['total_transactions']} transactions found")
        
        # Получаем все комиссии
        all_commissions = session.query(BankCommission).all()
        
        # Статистика
        stats = {
            "total_commissions": len(all_commissions),
            "matched_commissions": 0,
            "unmatched_commissions": 0,
            "total_commission_amount": 0.0,
            "matched_commission_amount": 0.0,
            "unmatched_commission_amount": 0.0,
            "orders_with_commission": 0,
            "total_commission_in_orders": 0.0,
            "summed_commissions": 0,  # Количество комиссий, которые были суммированы
            "matched_transactions": [],
            "unmatched_transactions": [],
            "orders_with_commission_list": []
        }
        
        # Обрабатываем каждую комиссию
        limit = len(all_commissions)
        counter = 1
        for commission in all_commissions:
            commission_amount = float(commission.bank_commission or 0)
            stats["total_commission_amount"] += commission_amount

            # print(f"[INFO] {counter}/{limit}")
            # print(f"[INFO] Processing commission {commission.id} with amount {commission_amount}")
            result = sync_commission_with_order(commission.id, session)
            
            if result["success"]:
                stats["matched_commissions"] += 1
                stats["matched_commission_amount"] += commission_amount
                
                # Учитываем суммирование комиссий
                if result.get("was_summed", False):
                    stats["summed_commissions"] += 1
                else:
                    # Считаем заказ только если это первая комиссия для него
                    stats["orders_with_commission"] += 1
                
                # Общая сумма комиссий в заказах - это суммарная комиссия после суммирования
                stats["total_commission_in_orders"] += result.get("total_commission_amount", commission_amount)
                
                stats["matched_transactions"].append({
                    "commission_id": commission.id,
                    "amount": float(commission.amount or 0),
                    "commission": commission_amount,
                    "organization_id": commission.organization_id,
                    "time_transaction": commission.time_transaction.isoformat() if commission.time_transaction else None,
                    "order_id": result["order_id"],
                    "order_iiko_id": result["order_iiko_id"],
                    "was_summed": result.get("was_summed", False),
                    "total_commission_amount": result.get("total_commission_amount", commission_amount),
                    "transaction_id": result.get("transaction_id")
                })
                
                # Добавляем заказ в список только если это первая комиссия для него
                if not result.get("was_summed", False):
                    stats["orders_with_commission_list"].append({
                        "order_id": result["order_id"],
                        "order_iiko_id": result["order_iiko_id"],
                        "commission": commission_amount
                    })
            else:
                stats["unmatched_commissions"] += 1
                stats["unmatched_commission_amount"] += commission_amount
                
                stats["unmatched_transactions"].append({
                    "commission_id": commission.id,
                    "amount": float(commission.amount or 0),
                    "commission": commission_amount,
                    "organization_id": commission.organization_id,
                    "time_transaction": commission.time_transaction.isoformat() if commission.time_transaction else None,
                    "error": result["error"]
                })
            counter += 1
        
        # Добавляем статистику по трекеру
        final_tracker_stats = get_transaction_tracker_stats()
        stats["transaction_tracker"] = final_tracker_stats
        
        return stats
        
    finally:
        session.close()


def generate_commission_report():
    """
    Генерирует отчет по сопоставлению комиссий с заказами.
    
    Returns:
        dict: полный отчет
    """
    stats = sync_all_commissions_with_orders()
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_commissions": stats["total_commissions"],
            "matched_commissions": stats["matched_commissions"],
            "unmatched_commissions": stats["unmatched_commissions"],
            "summed_commissions": stats["summed_commissions"],
            "match_percentage": (stats["matched_commissions"] / stats["total_commissions"] * 100) if stats["total_commissions"] > 0 else 0,
            "total_commission_amount": stats["total_commission_amount"],
            "matched_commission_amount": stats["matched_commission_amount"],
            "unmatched_commission_amount": stats["unmatched_commission_amount"],
            "orders_with_commission": stats["orders_with_commission"],
            "total_commission_in_orders": stats["total_commission_in_orders"]
        },
        "transaction_tracker": stats.get("transaction_tracker", {}),
        "details": {
            "matched_transactions": stats["matched_transactions"],
            "unmatched_transactions": stats["unmatched_transactions"],
            "orders_with_commission": stats["orders_with_commission_list"]
        }
    }
    
    return report