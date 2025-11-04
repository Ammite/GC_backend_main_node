'''
Быстрый модуль для сопоставления комиссий с заказами через SQL-запрос.

Преимущества перед matching_commission_w_sales_n_orders.py:
- Использует один SQL-запрос вместо множества запросов к БД
- Группировка и JOIN выполняются на уровне БД, что намного быстрее
- Меньше нагрузка на Python-логику
- Batch операции (commit каждые N записей)

Алгоритм:
1. Выполняем SQL-запрос, который группирует sales по payment_transaction_id и джойнит с bank_commissions
2. Для каждого совпадения:
   - Берем transaction_time из bank_commission
   - Сравниваем с precheque_time и open_time из sales
   - Выбираем самое близкое время
   - По выбранному времени находим соответствующий заказ
3. Обновляем связи в БД (batch операции)
4. Записываем payment_id в d_order.cheque_additional_info
5. Собираем подробную статистику по операциям
'''

from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from database.database import engine
from models.bank_commission import BankCommission
from models.d_order import DOrder
from datetime import datetime
import json


def get_session():
    """Создает сессию для работы с БД"""
    Session = sessionmaker(bind=engine)
    return Session()


def find_matching_commissions_and_sales(session):
    """
    Выполняет SQL-запрос для поиска совпадений между комиссиями и продажами.
    Теперь включает информацию о времени заказов для выбора ближайшего.
    
    Args:
        session: сессия БД
    
    Returns:
        list: список совпадений с информацией о заказах
    """
    query = text("""
        SELECT
            s.payment_id, 
            s.amount as sales_amount, 
            c.amount as commission_amount, 
            c.bank_commission as commission, 
            s.precheque_time as sale_precheque_time,
            s.open_time as sale_open_time,
            c.time_transaction as transaction_time, 
            s.organization_id, 
            s.order_ids,
            c.id as commission_id, 
            s.sales_ids,
            o.order_data
        FROM (
            SELECT 
                payment_transaction_id as payment_id, 
                SUM(dish_discount_sum_int) as amount, 
                MAX(precheque_time) as precheque_time,
                MAX(open_time) as open_time,
                MAX(organization_id) as organization_id, 
                STRING_AGG(id::text, ', ' ORDER BY id) as sales_ids,
                STRING_AGG(DISTINCT(order_id), ', ' ORDER BY order_id) as order_ids
            FROM 
                public.sales
            WHERE
                payment_transaction_id IS NOT NULL
            GROUP BY 
                payment_transaction_id
        ) s
        JOIN 
            public.bank_commissions c 
        ON
            s.amount = c.amount 
            AND s.organization_id = c.organization_id
            AND c.order_id IS NULL
        LEFT JOIN LATERAL (
            SELECT 
                json_agg(
                    json_build_object(
                        'id', d.id,
                        'iiko_id', d.iiko_id,
                        'time_order', d.time_order,
                        'bank_commission', d.bank_commission,
                        'cheque_additional_info', d.cheque_additional_info
                    )
                ) as order_data
            FROM 
                public.d_orders d
            WHERE 
                d.iiko_id = ANY(string_to_array(s.order_ids, ', '))
                and c.time_transaction >= '2025-10-1 00:00:00'
                and c.time_transaction < '2025-10-20 23:59:59'
                and c.bank_commission is not null
                and c.source = 'temp_files/terminals_report/ИП Амиржан Каспий.xlsx'
        ) o ON true
        ORDER BY s.payment_id ASC
    """)
    
    result = session.execute(query)
    rows = result.fetchall()
    
    # Преобразуем результат в список словарей
    matches = []
    for row in rows:
        matches.append({
            'payment_id': row[0],
            'sales_amount': float(row[1]) if row[1] else 0.0,
            'commission_amount': float(row[2]) if row[2] else 0.0,
            'commission': float(row[3]) if row[3] else 0.0,
            'sale_precheque_time': row[4],
            'sale_open_time': row[5],
            'transaction_time': row[6],
            'organization_id': row[7],
            'order_ids': row[8],  # Строка с order_id через запятую
            'commission_id': row[9],
            'sales_ids': row[10],
            'order_data': row[11]  # JSON с данными заказов
        })
    
    return matches


def find_closest_order_by_time(order_data_json, sale_precheque_time, sale_open_time, transaction_time):
    """
    Находит ближайший заказ по времени из списка заказов.
    Сравнивает transaction_time с precheque_time и open_time из sales,
    выбирает самое близкое время и находит заказ по нему.
    
    Args:
        order_data_json: JSON с данными заказов
        sale_precheque_time: время precheque из sales
        sale_open_time: время open из sales
        transaction_time: время транзакции из bank_commission
    
    Returns:
        dict: ближайший заказ или None, и информация о выбранном времени
    """
    if not order_data_json:
        return None, None
    
    if not transaction_time:
        # Если нет времени транзакции, берем первый заказ
        return order_data_json[0], "no_transaction_time"
    
    # Сравниваем transaction_time с precheque_time и open_time
    # Выбираем самое близкое
    best_reference_time = None
    best_time_type = None
    min_diff_to_transaction = float('inf')
    
    if sale_precheque_time:
        diff = abs((transaction_time - sale_precheque_time).total_seconds())
        if diff < min_diff_to_transaction:
            min_diff_to_transaction = diff
            best_reference_time = sale_precheque_time
            best_time_type = "precheque_time"
    
    if sale_open_time:
        diff = abs((transaction_time - sale_open_time).total_seconds())
        if diff < min_diff_to_transaction:
            min_diff_to_transaction = diff
            best_reference_time = sale_open_time
            best_time_type = "open_time"
    
    # Если не нашли подходящее время, используем transaction_time
    if not best_reference_time:
        best_reference_time = transaction_time
        best_time_type = "transaction_time_fallback"
    
    # Теперь находим заказ с ближайшим временем к выбранному reference_time
    closest_order = None
    min_time_diff = float('inf')
    
    for order in order_data_json:
        order_time = order.get('time_order')
        if not order_time:
            continue
        
        # Преобразуем строку в datetime если нужно
        if isinstance(order_time, str):
            order_time = datetime.fromisoformat(order_time.replace('Z', '+00:00'))
        
        # Вычисляем разницу во времени
        time_diff = abs((order_time - best_reference_time).total_seconds())
        
        if time_diff < min_time_diff:
            min_time_diff = time_diff
            closest_order = order
    
    result_order = closest_order if closest_order else (order_data_json[0] if order_data_json else None)
    
    return result_order, {
        "used_time_type": best_time_type,
        "reference_time": best_reference_time.isoformat() if best_reference_time else None,
        "time_diff_to_order": min_time_diff if closest_order else None
    }


def update_cheque_additional_info(current_info, payment_id):
    """
    Обновляет cheque_additional_info, добавляя payment_id.
    
    Args:
        current_info: текущее значение cheque_additional_info (может быть JSON, строкой или None)
        payment_id: payment_transaction_id для добавления
    
    Returns:
        str: обновленный JSON
    """
    try:
        if current_info:
            # Пытаемся распарсить как JSON
            if isinstance(current_info, str):
                info_dict = json.loads(current_info)
            elif isinstance(current_info, dict):
                info_dict = current_info
            else:
                info_dict = {}
        else:
            info_dict = {}
        
        # Добавляем или обновляем payment_ids
        if 'payment_ids' not in info_dict:
            info_dict['payment_ids'] = []
        
        if payment_id not in info_dict['payment_ids']:
            info_dict['payment_ids'].append(payment_id)
        
        return json.dumps(info_dict, ensure_ascii=False)
    except:
        # Если не удалось распарсить, создаем новый JSON
        return json.dumps({'payment_ids': [payment_id]}, ensure_ascii=False)


def sync_commission_with_order_fast(match, session, commit=True):
    """
    Быстрое сопоставление комиссии с заказом на основе совпадения из SQL-запроса.
    Выбирает ближайший заказ по времени и записывает payment_id в cheque_additional_info.
    
    Args:
        match: словарь с данными совпадения (включает order_data)
        session: сессия БД
        commit: делать ли commit (False для batch операций)
    
    Returns:
        dict: результат операции
    """
    commission_id = match['commission_id']
    order_data_json = match['order_data']
    payment_id = match['payment_id']
    
    # Получаем комиссию
    commission = session.query(BankCommission).filter(BankCommission.id == commission_id).first()
    if not commission:
        return {"success": False, "error": "Commission not found"}
    
    # Проверяем, что комиссия еще не была сопоставлена
    if commission.order_id:
        return {"success": False, "error": f"Commission {commission.id} already has order_id {commission.order_id}"}
    
    # Проверяем наличие заказов
    if not order_data_json:
        return {"success": False, "error": "No orders found in order_data"}
    
    # Находим ближайший заказ по времени
    closest_order_data, time_selection_info = find_closest_order_by_time(
        order_data_json,
        match['sale_precheque_time'],
        match['sale_open_time'],
        match['transaction_time']
    )
    
    if not closest_order_data:
        return {"success": False, "error": "Could not find closest order"}
    
    # Получаем заказ из БД
    order = session.query(DOrder).filter(DOrder.id == closest_order_data['id']).first()
    
    if not order:
        return {"success": False, "error": f"Order not found for id: {closest_order_data['id']}"}
    
    try:
        # Суммируем комиссию с уже существующей (если есть)
        current_commission = float(order.bank_commission or 0)
        commission_amount = float(commission.bank_commission or 0)
        total_commission = current_commission + commission_amount
        
        # Записываем суммарную комиссию в заказ
        order.bank_commission = total_commission
        
        # Обновляем cheque_additional_info с payment_id
        order.cheque_additional_info = update_cheque_additional_info(
            order.cheque_additional_info,
            payment_id
        )
        
        # Обновляем связь в таблице комиссий
        commission.order_id = order.id
        commission.order_iiko_id = order.iiko_id
        
        # Коммитим если требуется (для batch операций commit=False)
        if commit:
            session.commit()
        
        return {
            "success": True, 
            "order_id": order.id,
            "order_iiko_id": order.iiko_id,
            "commission_amount": commission_amount,
            "total_commission_amount": total_commission,
            "was_summed": current_commission > 0,
            "payment_transaction_id": payment_id,
            "sales_amount": match['sales_amount'],
            "commission_amount_from_match": match['commission_amount'],
            "time_selection_info": time_selection_info  # Информация о том, какое время использовалось для выбора
        }
    except Exception as e:
        if commit:
            session.rollback()
        return {"success": False, "error": str(e)}


def sync_all_commissions_fast(batch_size=100):
    """
    Быстрое сопоставление всех комиссий с заказами через SQL-запрос.
    Использует batch операции для ускорения процесса.
    
    Args:
        batch_size: размер пакета для commit (по умолчанию 100)
    
    Returns:
        dict: отчетность по сопоставлению
    """
    session = get_session()
    
    try:
        print("[INFO] Finding matching commissions and sales using SQL query...")
        matches = find_matching_commissions_and_sales(session)
        print(f"[INFO] Found {len(matches)} potential matches")
        
        # Статистика
        stats = {
            "total_matches_found": len(matches),
            "matched_commissions": 0,
            "failed_matches": 0,
            "total_commission_amount": 0.0,
            "matched_commission_amount": 0.0,
            "failed_commission_amount": 0.0,
            "orders_updated": 0,
            "summed_commissions": 0,  # Количество комиссий, которые были суммированы с существующими
            "matched_transactions": [],
            "failed_transactions": [],
            "orders_with_commission_list": []
        }
        
        # Обрабатываем каждое совпадение БЕЗ commit (batch операция)
        batch_counter = 0
        successful_updates = 0
        
        for idx, match in enumerate(matches, 1):
            commission_amount = match['commission']
            stats["total_commission_amount"] += commission_amount
            
            # Передаем commit=False для batch операций
            result = sync_commission_with_order_fast(match, session, commit=False)
            
            if result["success"]:
                stats["matched_commissions"] += 1
                stats["matched_commission_amount"] += commission_amount
                successful_updates += 1
                batch_counter += 1
                
                # Учитываем суммирование комиссий
                if result.get("was_summed", False):
                    stats["summed_commissions"] += 1
                else:
                    # Считаем заказ только если это первая комиссия для него
                    stats["orders_updated"] += 1
                
                stats["matched_transactions"].append({
                    "commission_id": match['commission_id'],
                    "amount": match['commission_amount'],
                    "commission": commission_amount,
                    "organization_id": match['organization_id'],
                    "time_transaction": match['transaction_time'].isoformat() if match['transaction_time'] else None,
                    "sale_precheque_time": match['sale_precheque_time'].isoformat() if match['sale_precheque_time'] else None,
                    "sale_open_time": match['sale_open_time'].isoformat() if match['sale_open_time'] else None,
                    "order_id": result["order_id"],
                    "order_iiko_id": result["order_iiko_id"],
                    "was_summed": result.get("was_summed", False),
                    "total_commission_amount": result.get("total_commission_amount", commission_amount),
                    "payment_transaction_id": result.get("payment_transaction_id"),
                    "sales_amount": result.get("sales_amount"),
                    "time_selection_info": result.get("time_selection_info")
                })
                
                # Добавляем заказ в список только если это первая комиссия для него
                if not result.get("was_summed", False):
                    stats["orders_with_commission_list"].append({
                        "order_id": result["order_id"],
                        "order_iiko_id": result["order_iiko_id"],
                        "commission": commission_amount
                    })
                
                # Делаем commit каждые batch_size операций
                if batch_counter >= batch_size:
                    try:
                        session.commit()
                        print(f"[INFO] Batch commit: processed {idx}/{len(matches)} matches, {successful_updates} successful")
                        batch_counter = 0
                    except Exception as e:
                        print(f"[ERROR] Batch commit failed: {str(e)}")
                        session.rollback()
                        batch_counter = 0
                        # Продолжаем обработку
            else:
                stats["failed_matches"] += 1
                stats["failed_commission_amount"] += commission_amount
                
                stats["failed_transactions"].append({
                    "commission_id": match['commission_id'],
                    "amount": match['commission_amount'],
                    "commission": commission_amount,
                    "organization_id": match['organization_id'],
                    "time_transaction": match['transaction_time'].isoformat() if match['transaction_time'] else None,
                    "error": result["error"]
                })
        
        # Финальный commit для оставшихся записей
        if batch_counter > 0:
            try:
                session.commit()
                print(f"[INFO] Final commit: all {len(matches)} matches processed")
            except Exception as e:
                print(f"[ERROR] Final commit failed: {str(e)}")
                session.rollback()
        
        # Проверяем несопоставленные комиссии (которые не попали в SQL-запрос)
        all_commissions = session.query(BankCommission).filter(BankCommission.order_id.is_(None)).all()
        matched_commission_ids = {m['commission_id'] for m in matches}
        unmatched_commissions = [c for c in all_commissions if c.id not in matched_commission_ids]
        
        stats["unmatched_by_sql"] = len(unmatched_commissions)
        stats["unmatched_commission_amount"] = sum(float(c.bank_commission or 0) for c in unmatched_commissions)
        
        print(f"[INFO] Sync completed: {stats['matched_commissions']} matched, {stats['failed_matches']} failed, {stats['unmatched_by_sql']} unmatched")
        
        return stats
        
    except Exception as e:
        print(f"[ERROR] Sync failed: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()


def generate_commission_report_fast(batch_size=100):
    """
    Генерирует быстрый отчет по сопоставлению комиссий с заказами.
    
    Args:
        batch_size: размер пакета для commit (по умолчанию 100)
    
    Returns:
        dict: полный отчет
    """
    import time
    
    start_time = time.time()
    stats = sync_all_commissions_fast(batch_size=batch_size)
    elapsed_time = time.time() - start_time
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "elapsed_time_seconds": round(elapsed_time, 2),
        "batch_size": batch_size,
        "summary": {
            "total_matches_found": stats["total_matches_found"],
            "matched_commissions": stats["matched_commissions"],
            "failed_matches": stats["failed_matches"],
            "unmatched_by_sql": stats.get("unmatched_by_sql", 0),
            "summed_commissions": stats["summed_commissions"],
            "match_percentage": (stats["matched_commissions"] / stats["total_matches_found"] * 100) if stats["total_matches_found"] > 0 else 0,
            "total_commission_amount": stats["total_commission_amount"],
            "matched_commission_amount": stats["matched_commission_amount"],
            "failed_commission_amount": stats["failed_commission_amount"],
            "unmatched_commission_amount": stats.get("unmatched_commission_amount", 0.0),
            "orders_updated": stats["orders_updated"],
        },
        "details": {
            "matched_transactions": stats["matched_transactions"],
            "failed_transactions": stats["failed_transactions"],
            "orders_with_commission": stats["orders_with_commission_list"]
        }
    }
    
    return report


def export_report_to_json(report, filename="commission_report_fast.json"):
    """
    Экспортирует отчет в JSON-файл.
    
    Args:
        report: отчет для экспорта
        filename: имя файла
    """
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[INFO] Report exported to {filename}")


if __name__ == "__main__":
    """
    Пример использования модуля.
    """
    print("=" * 80)
    print("FAST COMMISSION MATCHING - START")
    print("=" * 80)
    print("\nОсобенности:")
    print("✓ Один SQL-запрос для поиска совпадений")
    print("✓ Batch операции (commit каждые 100 записей)")
    print("✓ Выбор ближайшего заказа: сравнивает transaction_time с precheque_time и open_time")
    print("✓ Запись payment_id в cheque_additional_info")
    print()
    
    # Генерируем отчет с batch_size=100 (можно изменить)
    report = generate_commission_report_fast(batch_size=100)
    
    # Выводим основную статистику
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Elapsed time:                   {report['elapsed_time_seconds']:.2f} seconds")
    print(f"Batch size:                     {report['batch_size']}")
    print(f"\nTotal matches found by SQL:     {report['summary']['total_matches_found']}")
    print(f"Successfully matched:           {report['summary']['matched_commissions']}")
    print(f"Failed to match:                {report['summary']['failed_matches']}")
    print(f"Unmatched by SQL:               {report['summary']['unmatched_by_sql']}")
    print(f"Summed with existing:           {report['summary']['summed_commissions']}")
    print(f"Match percentage:               {report['summary']['match_percentage']:.2f}%")
    print(f"\nTotal commission amount:        {report['summary']['total_commission_amount']:.2f}")
    print(f"Matched commission amount:      {report['summary']['matched_commission_amount']:.2f}")
    print(f"Failed commission amount:       {report['summary']['failed_commission_amount']:.2f}")
    print(f"Unmatched commission amount:    {report['summary']['unmatched_commission_amount']:.2f}")
    print(f"\nOrders updated:                 {report['summary']['orders_updated']}")
    
    # Экспортируем отчет
    export_report_to_json(report)
    
    print("\n" + "=" * 80)
    print("FAST COMMISSION MATCHING - COMPLETE")
    print("=" * 80)

