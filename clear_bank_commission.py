#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для очистки полей bank_commission в таблице d_order и связей в bank_commission

Этот скрипт:
1. Обнуляет все значения поля bank_commission в таблице d_order
2. Очищает поля order_id и order_iiko_id в таблице bank_commission

Полезно для тестирования или сброса данных перед повторным парсингом.

Использование:
    python clear_bank_commission.py
"""

from database.database import SessionLocal
from models.d_order import DOrder
from models.bank_commission import BankCommission
import sys


def clear_bank_commission(dry_run=True):
    """
    Очищает поля bank_commission в таблице d_order и связи в bank_commission
    
    Args:
        dry_run: Если True, только показывает что будет сделано, не изменяет данные
    """
    session = SessionLocal()
    
    try:
        # Получаем все записи с непустым bank_commission в d_order
        orders_with_commission = session.query(DOrder).filter(
            DOrder.bank_commission.isnot(None),
            DOrder.bank_commission != 0
        ).all()
        
        # Получаем все записи с непустыми связями в bank_commission
        commissions_with_links = session.query(BankCommission).filter(
            BankCommission.order_id.isnot(None)
        ).all()
        
        total_orders_count = len(orders_with_commission)
        total_commissions_count = len(commissions_with_links)
        
        if total_orders_count == 0 and total_commissions_count == 0:
            print("[OK] No records with filled bank_commission fields or links")
            return
        
        print(f"[INFO] Found {total_orders_count} orders with filled bank_commission field")
        print(f"[INFO] Found {total_commissions_count} commissions with order links")
        
        if dry_run:
            print("\n[PREVIEW] PREVIEW MODE (dry_run=True) - changes will NOT be applied")
            
            if total_orders_count > 0:
                print("\nExamples of orders that will be cleared:")
                # Показываем первые 5 записей заказов
                for i, order in enumerate(orders_with_commission[:5]):
                    print(f"  {i+1}. Order ID: {order.id}, iiko_id: {order.iiko_id}, bank_commission: {order.bank_commission}")
                
                if total_orders_count > 5:
                    print(f"  ... and {total_orders_count - 5} more orders")
            
            if total_commissions_count > 0:
                print("\nExamples of commission links that will be cleared:")
                # Показываем первые 5 записей комиссий
                for i, commission in enumerate(commissions_with_links[:5]):
                    print(f"  {i+1}. Commission ID: {commission.id}, order_id: {commission.order_id}, order_iiko_id: {commission.order_iiko_id}")
                
                if total_commissions_count > 5:
                    print(f"  ... and {total_commissions_count - 5} more commission links")
            
            print(f"\n[INFO] To apply changes run:")
            print(f"   python clear_bank_commission.py --apply")
            
        else:
            print("\n[WARNING] APPLY MODE (dry_run=False) - changes WILL be applied")
            
            # Подтверждение от пользователя
            total_records = total_orders_count + total_commissions_count
            confirm = input(f"\n[CONFIRM] Are you sure you want to clear {total_orders_count} orders and {total_commissions_count} commission links? (yes/no): ")
            
            if confirm.lower() not in ['yes', 'y']:
                print("[CANCELLED] Operation cancelled by user")
                return
            
            # Очищаем bank_commission в заказах
            if total_orders_count > 0:
                updated_orders_count = session.query(DOrder).filter(
                    DOrder.bank_commission.isnot(None),
                    DOrder.bank_commission != 0
                ).update({DOrder.bank_commission: None})
                print(f"[SUCCESS] Cleared bank_commission for {updated_orders_count} orders")
            
            # Очищаем связи в bank_commission
            if total_commissions_count > 0:
                updated_commissions_count = session.query(BankCommission).filter(
                    BankCommission.order_id.isnot(None)
                ).update({
                    BankCommission.order_id: None,
                    BankCommission.order_iiko_id: None
                })
                print(f"[SUCCESS] Cleared order links for {updated_commissions_count} commissions")
            
            session.commit()
            
            # Проверяем результат
            remaining_orders = session.query(DOrder).filter(
                DOrder.bank_commission.isnot(None),
                DOrder.bank_commission != 0
            ).count()
            
            remaining_commissions = session.query(BankCommission).filter(
                BankCommission.order_id.isnot(None)
            ).count()
            
            print(f"[INFO] Remaining orders with bank_commission: {remaining_orders}")
            print(f"[INFO] Remaining commissions with order links: {remaining_commissions}")
    
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        session.rollback()
        raise
    
    finally:
        session.close()


def show_statistics():
    """Показывает статистику по полям bank_commission в обеих таблицах"""
    session = SessionLocal()
    
    try:
        # Статистика по заказам
        total_orders = session.query(DOrder).count()
        orders_with_commission = session.query(DOrder).filter(
            DOrder.bank_commission.isnot(None),
            DOrder.bank_commission != 0
        ).count()
        orders_with_null_commission = session.query(DOrder).filter(
            DOrder.bank_commission.is_(None)
        ).count()
        orders_with_zero_commission = session.query(DOrder).filter(
            DOrder.bank_commission == 0
        ).count()
        
        # Статистика по комиссиям
        total_commissions = session.query(BankCommission).count()
        commissions_with_links = session.query(BankCommission).filter(
            BankCommission.order_id.isnot(None)
        ).count()
        commissions_without_links = session.query(BankCommission).filter(
            BankCommission.order_id.is_(None)
        ).count()
        
        print("[INFO] BANK COMMISSION STATISTICS")
        print("=" * 60)
        print("ORDERS TABLE (d_order):")
        print(f"  Total orders: {total_orders}")
        print(f"  With commission: {orders_with_commission}")
        print(f"  With NULL commission: {orders_with_null_commission}")
        print(f"  With zero commission: {orders_with_zero_commission}")
        print()
        print("COMMISSIONS TABLE (bank_commission):")
        print(f"  Total commissions: {total_commissions}")
        print(f"  With order links: {commissions_with_links}")
        print(f"  Without order links: {commissions_without_links}")
        print("=" * 60)
        
        if orders_with_commission > 0:
            # Показываем примеры заказов с комиссиями
            print("\nExamples of orders with commission:")
            examples = session.query(DOrder).filter(
                DOrder.bank_commission.isnot(None),
                DOrder.bank_commission != 0
            ).limit(3).all()
            
            for i, order in enumerate(examples, 1):
                print(f"  {i}. Order ID: {order.id}, iiko_id: {order.iiko_id}, bank_commission: {order.bank_commission}")
        
        if commissions_with_links > 0:
            # Показываем примеры комиссий со связями
            print("\nExamples of commissions with order links:")
            examples = session.query(BankCommission).filter(
                BankCommission.order_id.isnot(None)
            ).limit(3).all()
            
            for i, commission in enumerate(examples, 1):
                print(f"  {i}. Commission ID: {commission.id}, order_id: {commission.order_id}, order_iiko_id: {commission.order_iiko_id}")
    
    finally:
        session.close()


if __name__ == "__main__":
    print("[INFO] BANK COMMISSION CLEAR SCRIPT")
    print("=" * 50)
    
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1:
        if sys.argv[1] == '--apply':
            print("[WARNING] ATTENTION: Data cleanup will be performed!")
            clear_bank_commission(dry_run=False)
        elif sys.argv[1] == '--stats':
            show_statistics()
        elif sys.argv[1] == '--help':
            print("\nUsage:")
            print("  python clear_bank_commission.py           # Preview (no changes)")
            print("  python clear_bank_commission.py --apply   # Apply changes")
            print("  python clear_bank_commission.py --stats   # Show statistics")
            print("  python clear_bank_commission.py --help     # This help")
            print("\nThis script will:")
            print("  1. Clear bank_commission field in d_order table")
            print("  2. Clear order_id and order_iiko_id fields in bank_commission table")
        else:
            print(f"[ERROR] Unknown argument: {sys.argv[1]}")
            print("Use --help for help")
    else:
        # По умолчанию - режим просмотра
        show_statistics()
        print()
        clear_bank_commission(dry_run=True)
