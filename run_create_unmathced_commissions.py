'''
Скрипт для работы с несопоставленными комиссиями.

Функции:
1. create_orders_from_unmatched_commissions() - создает d_order для bank_commission без order_id
2. delete_created_orders_and_clear_links() - удаляет созданные заказы и очищает связи
'''

from sqlalchemy.orm import sessionmaker
from sqlalchemy import and_, func
from database.database import engine
from models.bank_commission import BankCommission
from models.d_order import DOrder
from datetime import datetime
import json


def get_session():
    """Создает сессию для работы с БД"""
    Session = sessionmaker(bind=engine)
    return Session()


def create_orders_from_unmatched_commissions():
    """
    Создает d_order для всех bank_commission, у которых нет order_id.
    
    Returns:
        dict: отчет о созданных заказах
    """
    session = get_session()
    
    try:
        # Получаем все комиссии без order_id
        unmatched_commissions = session.query(BankCommission).filter(
            BankCommission.order_id.is_(None)
        ).all()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_unmatched_commissions": len(unmatched_commissions),
            "created_orders": 0,
            "failed_creations": 0,
            "created_orders_details": [],
            "failed_creations_details": []
        }
        
        print(f"[INFO] Found {len(unmatched_commissions)} unmatched commissions")
        
        for commission in unmatched_commissions:
            try:
                # Создаем новый заказ на основе комиссии
                new_order = DOrder(
                    iiko_id=f"COMMISSION_{commission.id}",  # Уникальный ID на основе комиссии
                    organization_id=commission.organization_id,
                    time_order=commission.time_transaction,
                    bank_commission=commission.bank_commission,
                    discount=commission.amount,
                    # Дополнительные поля можно заполнить по необходимости
                    external_number="created_from_commission"
                )
                
                session.add(new_order)
                session.flush()  # Получаем ID нового заказа
                
                # Обновляем связь в комиссии
                commission.order_id = new_order.id
                commission.order_iiko_id = new_order.iiko_id
                
                session.commit()
                
                report["created_orders"] += 1
                report["created_orders_details"].append({
                    "commission_id": commission.id,
                    "order_id": new_order.id,
                    "order_iiko_id": new_order.iiko_id,
                    "amount": float(commission.amount or 0),
                    "commission": float(commission.bank_commission or 0),
                    "organization_id": commission.organization_id,
                    "time_transaction": commission.time_transaction.isoformat() if commission.time_transaction else None
                })
                
                print(f"[SUCCESS] Created order {new_order.id} for commission {commission.id}")
                
            except Exception as e:
                session.rollback()
                report["failed_creations"] += 1
                report["failed_creations_details"].append({
                    "commission_id": commission.id,
                    "error": str(e),
                    "amount": float(commission.amount or 0),
                    "commission": float(commission.bank_commission or 0)
                })
                print(f"[ERROR] Failed to create order for commission {commission.id}: {str(e)}")
        
        return report
        
    finally:
        session.close()


def delete_created_orders_and_clear_links():
    """
    Удаляет заказы, созданные из комиссий (с iiko_id начинающимся с 'COMMISSION_'),
    и очищает связи в bank_commission.
    
    Returns:
        dict: отчет об удалении
    """
    session = get_session()
    
    try:
        # Находим все заказы, созданные из комиссий
        created_orders = session.query(DOrder).filter(
            DOrder.iiko_id.like('COMMISSION_%')
        ).all()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_created_orders": len(created_orders),
            "deleted_orders": 0,
            "cleared_commissions": 0,
            "failed_deletions": 0,
            "deleted_orders_details": [],
            "failed_deletions_details": []
        }
        
        print(f"[INFO] Found {len(created_orders)} orders created from commissions")
        
        for order in created_orders:
            try:
                # Находим связанные комиссии
                related_commissions = session.query(BankCommission).filter(
                    BankCommission.order_id == order.id
                ).all()
                
                # Очищаем связи в комиссиях
                for commission in related_commissions:
                    commission.order_id = None
                    commission.order_iiko_id = None
                    report["cleared_commissions"] += 1
                
                # Удаляем заказ
                session.delete(order)
                session.commit()
                
                report["deleted_orders"] += 1
                report["deleted_orders_details"].append({
                    "order_id": order.id,
                    "order_iiko_id": order.iiko_id,
                    "amount": float(order.discount or 0),
                    "commission": float(order.bank_commission or 0),
                    "organization_id": order.organization_id,
                    "related_commissions_count": len(related_commissions)
                })
                
                print(f"[SUCCESS] Deleted order {order.id} and cleared {len(related_commissions)} commission links")
                
            except Exception as e:
                session.rollback()
                report["failed_deletions"] += 1
                report["failed_deletions_details"].append({
                    "order_id": order.id,
                    "order_iiko_id": order.iiko_id,
                    "error": str(e)
                })
                print(f"[ERROR] Failed to delete order {order.id}: {str(e)}")
        
        return report
        
    finally:
        session.close()


def get_unmatched_commissions_stats():
    """
    Возвращает статистику по несопоставленным комиссиям.
    
    Returns:
        dict: статистика
    """
    session = get_session()
    
    try:
        # Общая статистика
        total_commissions = session.query(BankCommission).count()
        matched_commissions = session.query(BankCommission).filter(
            BankCommission.order_id.isnot(None)
        ).count()
        unmatched_commissions = session.query(BankCommission).filter(
            BankCommission.order_id.is_(None)
        ).count()
        
        # Статистика по суммам
        total_amount = session.query(BankCommission).with_entities(
            func.sum(BankCommission.amount)
        ).scalar() or 0
        
        matched_amount = session.query(BankCommission).filter(
            BankCommission.order_id.isnot(None)
        ).with_entities(
            func.sum(BankCommission.amount)
        ).scalar() or 0
        
        unmatched_amount = session.query(BankCommission).filter(
            BankCommission.order_id.is_(None)
        ).with_entities(
            func.sum(BankCommission.amount)
        ).scalar() or 0
        
        # Статистика по созданным заказам
        created_orders_count = session.query(DOrder).filter(
            DOrder.iiko_id.like('COMMISSION_%')
        ).count()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_commissions": total_commissions,
            "matched_commissions": matched_commissions,
            "unmatched_commissions": unmatched_commissions,
            "match_percentage": (matched_commissions / total_commissions * 100) if total_commissions > 0 else 0,
            "total_amount": float(total_amount),
            "matched_amount": float(matched_amount),
            "unmatched_amount": float(unmatched_amount),
            "created_orders_count": created_orders_count
        }
        
    finally:
        session.close()


def json_serializer(obj):
    """Сериализатор для JSON"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python create_unmatched_commissions.py create    - Create orders from unmatched commissions")
        print("  python create_unmatched_commissions.py delete    - Delete created orders and clear links")
        print("  python create_unmatched_commissions.py stats     - Show statistics")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "create":
        print("[INFO] Creating orders from unmatched commissions...")
        report = create_orders_from_unmatched_commissions()
        
        # Сохраняем отчет
        filename = f"temp_files/created_orders_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=json_serializer)
        
        print(f"[INFO] Report saved to {filename}")
        print(f"[SUMMARY] Created {report['created_orders']} orders, failed {report['failed_creations']}")
        
    elif command == "delete":
        print("[INFO] Deleting created orders and clearing links...")
        report = delete_created_orders_and_clear_links()
        
        # Сохраняем отчет
        filename = f"temp_files/deleted_orders_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=json_serializer)
        
        print(f"[INFO] Report saved to {filename}")
        print(f"[SUMMARY] Deleted {report['deleted_orders']} orders, cleared {report['cleared_commissions']} commission links")
        
    elif command == "stats":
        print("[INFO] Getting statistics...")
        stats = get_unmatched_commissions_stats()
        
        print(f"[STATS] Total commissions: {stats['total_commissions']}")
        print(f"[STATS] Matched: {stats['matched_commissions']} ({stats['match_percentage']:.1f}%)")
        print(f"[STATS] Unmatched: {stats['unmatched_commissions']}")
        print(f"[STATS] Created orders: {stats['created_orders_count']}")
        print(f"[STATS] Total amount: {stats['total_amount']:.2f}")
        print(f"[STATS] Unmatched amount: {stats['unmatched_amount']:.2f}")
        
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
