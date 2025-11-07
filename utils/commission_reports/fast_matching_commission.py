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


def find_matching_commissions_and_sales(session, start_date=None, end_date=None):
    """
    Выполняет SQL-запрос для поиска совпадений между комиссиями и продажами.
    Теперь включает информацию о времени заказов для выбора ближайшего.
    
    Args:
        session: сессия БД
        start_date: начальная дата для фильтрации (строка в формате 'YYYY-MM-DD')
        end_date: конечная дата для фильтрации (строка в формате 'YYYY-MM-DD')
    
    Returns:
        list: список совпадений с информацией о заказах
    """
    # Формируем условие для фильтрации по датам в таблице sales
    date_filter_sales = ""
    if start_date and end_date:
        date_filter_sales = f"AND open_date_typed >= '{start_date}' AND open_date_typed <= '{end_date}'"
    elif start_date:
        date_filter_sales = f"AND open_date_typed >= '{start_date}'"
    elif end_date:
        date_filter_sales = f"AND open_date_typed <= '{end_date}'"
    
    query = text(f"""
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
                {date_filter_sales}
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


def find_closest_order_by_time(order_data_json, sale_precheque_time, sale_open_time, transaction_time, max_time_diff_hours=24):
    """
    Находит ближайший заказ по времени из списка заказов.
    
    ПРАВИЛЬНАЯ ЛОГИКА:
    - Сравнивает transaction_time (время оплаты на терминале) со ВСЕМИ тремя временами:
      1. order_time (время создания заказа)
      2. sale_precheque_time (время предоплаты)
      3. sale_open_time (время открытия заказа)
    - Для каждого заказа берет МИНИМАЛЬНУЮ разницу из трех
    - Если минимальная разница больше max_time_diff_hours - отбрасывает заказ
    - Из оставшихся выбирает заказ с наименьшей разницей
    
    Это нужно, потому что заказ может быть:
    - Открыт (order_time)
    - Оплачен частично как предоплата (sale_precheque_time)
    - И потом через несколько дней оплачен полностью (transaction_time)
    
    Args:
        order_data_json: JSON с данными заказов
        sale_precheque_time: время precheque из sales
        sale_open_time: время open из sales
        transaction_time: время транзакции из bank_commission (КЛЮЧЕВОЕ ПОЛЕ!)
        max_time_diff_hours: максимальная допустимая разница в часах (по умолчанию 24)
    
    Returns:
        dict: ближайший заказ или None, и информация о выбранном времени
    """
    if not order_data_json:
        return None, None
    
    if not transaction_time:
        # Если нет времени транзакции, не можем сопоставить
        return None, {"error": "no_transaction_time"}
    
    max_time_diff_seconds = max_time_diff_hours * 3600
    
    # Ищем заказ с ближайшим временем к transaction_time
    closest_order = None
    min_time_diff = float('inf')
    best_time_type = None
    
    for order in order_data_json:
        order_time = order.get('time_order')
        if not order_time:
            continue
        
        # Преобразуем строку в datetime если нужно
        if isinstance(order_time, str):
            order_time = datetime.fromisoformat(order_time.replace('Z', '+00:00'))
        
        # Вычисляем разницу со ВСЕМИ тремя временами
        time_diffs = []
        
        # 1. Разница с order_time (время создания заказа)
        if order_time:
            diff_order = abs((order_time - transaction_time).total_seconds())
            time_diffs.append(('order_time', diff_order, order_time))
        
        # 2. Разница с sale_precheque_time (время предоплаты)
        if sale_precheque_time:
            diff_precheque = abs((sale_precheque_time - transaction_time).total_seconds())
            time_diffs.append(('sale_precheque_time', diff_precheque, sale_precheque_time))
        
        # 3. Разница с sale_open_time (время открытия заказа)
        if sale_open_time:
            diff_open = abs((sale_open_time - transaction_time).total_seconds())
            time_diffs.append(('sale_open_time', diff_open, sale_open_time))
        
        if not time_diffs:
            continue
        
        # Берем МИНИМАЛЬНУЮ разницу из трех
        min_diff_info = min(time_diffs, key=lambda x: x[1])
        min_diff_type, min_diff_seconds, reference_time = min_diff_info
        
        # Если минимальная разница больше максимальной - отбрасываем этот заказ
        if min_diff_seconds > max_time_diff_seconds:
            continue
        
        # Если это лучший заказ на данный момент
        if min_diff_seconds < min_time_diff:
            min_time_diff = min_diff_seconds
            closest_order = order
            best_time_type = min_diff_type
    
    if not closest_order:
        # Не нашли заказ в допустимом временном диапазоне
        return None, {
            "error": f"no_order_within_{max_time_diff_hours}_hours",
            "transaction_time": transaction_time.isoformat() if transaction_time else None,
            "checked_orders_count": len(order_data_json)
        }
    
    return closest_order, {
        "time_diff_seconds": min_time_diff,
        "time_diff_hours": round(min_time_diff / 3600, 2),
        "time_diff_type": best_time_type,
        "transaction_time": transaction_time.isoformat() if transaction_time else None,
        "order_time": closest_order.get('time_order'),
        "sale_precheque_time": sale_precheque_time.isoformat() if sale_precheque_time else None,
        "sale_open_time": sale_open_time.isoformat() if sale_open_time else None,
        "max_allowed_hours": max_time_diff_hours
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


def simulate_commission_match(match, session, max_time_diff_hours=24):
    """
    Симулирует сопоставление комиссии с заказом без записи в БД (для dry_run режима).
    Использует ту же логику, что и обычное сопоставление.
    
    Args:
        match: словарь с данными о совпадении
        session: сессия БД
        max_time_diff_hours: максимальная допустимая разница в часах (по умолчанию 24)
    
    Returns:
        dict: результат симуляции
    """
    try:
        # Проверяем, есть ли данные о заказах
        if not match['order_data']:
            return {
                "success": False, 
                "error": "No orders found for this match"
            }
        
        # Используем ту же функцию поиска ближайшего заказа
        closest_order_data, time_selection_info = find_closest_order_by_time(
            match['order_data'],
            match['sale_precheque_time'],
            match['sale_open_time'],
            match['transaction_time'],
            max_time_diff_hours=max_time_diff_hours
        )
        
        if not closest_order_data:
            error_msg = time_selection_info.get('error', 'Could not find closest order') if time_selection_info else 'Could not find closest order'
            return {
                "success": False,
                "error": error_msg,
                "time_info": time_selection_info
            }
        
        # Проверяем, есть ли уже комиссия
        was_summed = closest_order_data['bank_commission'] is not None
        current_commission = float(closest_order_data['bank_commission']) if closest_order_data['bank_commission'] else 0.0
        new_commission = float(match['commission'])
        total_commission = current_commission + new_commission
        
        return {
            "success": True,
            "order_id": closest_order_data['id'],
            "order_iiko_id": closest_order_data['iiko_id'],
            "was_summed": was_summed,
            "total_commission_amount": total_commission,
            "payment_transaction_id": match.get('payment_id'),
            "sales_amount": match.get('sales_amount'),
            "time_selection_info": time_selection_info
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def sync_commission_with_order_fast(match, session, commit=True, max_time_diff_hours=24):
    """
    Быстрое сопоставление комиссии с заказом на основе совпадения из SQL-запроса.
    Выбирает ближайший заказ по времени и записывает payment_id в cheque_additional_info.
    
    Args:
        match: словарь с данными совпадения (включает order_data)
        session: сессия БД
        commit: делать ли commit (False для batch операций)
        max_time_diff_hours: максимальная разница во времени в часах (по умолчанию 24)
    
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
        match['transaction_time'],
        max_time_diff_hours=max_time_diff_hours
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


def sync_all_commissions_fast(batch_size=100, start_date=None, end_date=None, dry_run=False, max_time_diff_hours=24):
    """
    Быстрое сопоставление всех комиссий с заказами через SQL-запрос.
    Использует batch операции для ускорения процесса.
    
    Args:
        batch_size: размер пакета для commit (по умолчанию 100)
        start_date: начальная дата для фильтрации (строка в формате 'YYYY-MM-DD')
        end_date: конечная дата для фильтрации (строка в формате 'YYYY-MM-DD')
        dry_run: если True, только поиск без записи в БД (по умолчанию False)
        max_time_diff_hours: максимальная разница во времени в часах (по умолчанию 24)
    
    Returns:
        dict: отчетность по сопоставлению
    """
    session = get_session()
    
    try:
        print("[INFO] Finding matching commissions and sales using SQL query...")
        if start_date or end_date:
            print(f"[INFO] Date filter: start={start_date or 'no limit'}, end={end_date or 'no limit'}")
        if dry_run:
            print("[INFO] DRY RUN MODE: No changes will be saved to database")
        print(f"[INFO] Max time difference: {max_time_diff_hours} hours")
        matches = find_matching_commissions_and_sales(session, start_date, end_date)
        print(f"[INFO] Found {len(matches)} potential matches")
        
        # Статистика
        stats = {
            "total_matches_found": len(matches),
            "matched_commissions": 0,
            "failed_matches": 0,
            "rejected_by_time_filter": 0,  # Отброшено из-за фильтра по времени
            "rejected_by_time_filter_amount": 0.0,
            "total_commission_amount": 0.0,
            "matched_commission_amount": 0.0,
            "failed_commission_amount": 0.0,
            "orders_updated": 0,
            "unique_orders_updated": set(),  # Уникальные ID заказов
            "summed_commissions": 0,  # Количество комиссий, которые были суммированы с существующими
            "matched_transactions": [],
            "failed_transactions": [],
            "orders_with_commission_list": []
        }
        
        # Обрабатываем каждое совпадение БЕЗ commit (batch операция)
        batch_counter = 0
        successful_updates = 0
        
        # Отслеживаем уже использованные комиссии и payment_transaction_id
        used_commission_ids = set()  # Комиссии, которые уже были сопоставлены
        used_payment_transaction_ids = set()  # payment_transaction_id, которые уже были использованы
        
        for idx, match in enumerate(matches, 1):
            commission_id = match['commission_id']
            payment_id = match['payment_id']
            commission_amount = match['commission']
            
            # Пропускаем комиссию, если она уже была использована
            if commission_id in used_commission_ids:
                continue
            
            # Пропускаем payment_transaction_id, если он уже был использован
            if payment_id and payment_id in used_payment_transaction_ids:
                continue
            
            stats["total_commission_amount"] += commission_amount
            
            # Передаем commit=False для batch операций (и dry_run для режима без записи)
            if dry_run:
                # В режиме dry_run просто симулируем успешное сопоставление
                result = simulate_commission_match(match, session, max_time_diff_hours=max_time_diff_hours)
            else:
                result = sync_commission_with_order_fast(match, session, commit=False, max_time_diff_hours=max_time_diff_hours)
            
            if result["success"]:
                # Помечаем комиссию и payment_transaction_id как использованные
                used_commission_ids.add(commission_id)
                if payment_id:
                    used_payment_transaction_ids.add(payment_id)
                
                stats["matched_commissions"] += 1
                stats["matched_commission_amount"] += commission_amount
                successful_updates += 1
                batch_counter += 1
                
                order_id = result["order_id"]
                
                # Учитываем суммирование комиссий
                if result.get("was_summed", False):
                    stats["summed_commissions"] += 1
                
                # Отслеживаем уникальные заказы (считаем только один раз на заказ)
                if order_id not in stats["unique_orders_updated"]:
                    stats["unique_orders_updated"].add(order_id)
                    stats["orders_updated"] += 1
                
                stats["matched_transactions"].append({
                    "commission_id": match['commission_id'],
                    "amount": match['commission_amount'],
                    "commission": commission_amount,
                    "organization_id": match['organization_id'],
                    "time_transaction": match['transaction_time'].isoformat() if match['transaction_time'] else None,
                    "sale_precheque_time": match['sale_precheque_time'].isoformat() if match['sale_precheque_time'] else None,
                    "sale_open_time": match['sale_open_time'].isoformat() if match['sale_open_time'] else None,
                    "order_id": order_id,
                    "order_iiko_id": result["order_iiko_id"],
                    "was_summed": result.get("was_summed", False),
                    "total_commission_amount": result.get("total_commission_amount", commission_amount),
                    "payment_transaction_id": result.get("payment_transaction_id"),
                    "sales_amount": result.get("sales_amount"),
                    "time_selection_info": result.get("time_selection_info")
                })
                
                # Добавляем заказ в список только один раз (при первом добавлении комиссии)
                if order_id not in [o["order_id"] for o in stats["orders_with_commission_list"]]:
                    stats["orders_with_commission_list"].append({
                        "order_id": order_id,
                        "order_iiko_id": result["order_iiko_id"],
                        "commission": commission_amount
                    })
                
                # Делаем commit каждые batch_size операций (если не dry_run)
                if not dry_run and batch_counter >= batch_size:
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
                # Проверяем, была ли ошибка из-за фильтра по времени
                error = result.get("error", "")
                if "no_order_within" in error or "no_transaction_time" in error:
                    stats["rejected_by_time_filter"] += 1
                    stats["rejected_by_time_filter_amount"] += commission_amount
                
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
        
        # Финальный commit для оставшихся записей (если не dry_run)
        if not dry_run and batch_counter > 0:
            try:
                session.commit()
                print(f"[INFO] Final commit: all {len(matches)} matches processed")
            except Exception as e:
                print(f"[ERROR] Final commit failed: {str(e)}")
                session.rollback()
        
        # Проверяем несопоставленные комиссии (которые не попали в SQL-запрос)
        # Применяем фильтр по датам, если указан
        query_all_commissions = session.query(BankCommission).filter(BankCommission.order_id.is_(None))
        
        # Если указаны даты, то учитываем только комиссии в указанном диапазоне
        # Для этого нужно проверить связанные sales по датам
        if start_date or end_date:
            # Получаем ID комиссий из sales в нужном диапазоне дат
            date_filter_for_commissions = "WHERE payment_transaction_id IS NOT NULL"
            if start_date and end_date:
                date_filter_for_commissions += f" AND open_date_typed >= '{start_date}' AND open_date_typed <= '{end_date}'"
            elif start_date:
                date_filter_for_commissions += f" AND open_date_typed >= '{start_date}'"
            elif end_date:
                date_filter_for_commissions += f" AND open_date_typed <= '{end_date}'"
            
            # Получаем все комиссии, связанные с sales в указанном диапазоне дат
            query_commissions_in_date_range = text(f"""
                SELECT DISTINCT c.id
                FROM public.bank_commissions c
                JOIN (
                    SELECT DISTINCT organization_id, SUM(dish_discount_sum_int) as amount
                    FROM public.sales
                    {date_filter_for_commissions}
                    GROUP BY organization_id, payment_transaction_id
                ) s ON c.organization_id = s.organization_id AND c.amount = s.amount
                WHERE c.order_id IS NULL
            """)
            result = session.execute(query_commissions_in_date_range)
            commission_ids_in_range = {row[0] for row in result.fetchall()}
            
            # Фильтруем только комиссии в нужном диапазоне дат
            all_commissions = [c for c in query_all_commissions.all() if c.id in commission_ids_in_range]
        else:
            all_commissions = query_all_commissions.all()
        
        matched_commission_ids = {m['commission_id'] for m in matches}
        unmatched_commissions = [c for c in all_commissions if c.id not in matched_commission_ids]
        
        stats["unmatched_by_sql"] = len(unmatched_commissions)
        stats["unmatched_commission_amount"] = sum(float(c.bank_commission or 0) for c in unmatched_commissions)
        
        # Сохраняем детали несопоставленных комиссий
        stats["unmatched_commissions_details"] = [
            {
                "commission_id": c.id,
                "amount": float(c.amount or 0),
                "commission": float(c.bank_commission or 0),
                "organization_id": c.organization_id,
                "time_transaction": c.time_transaction.isoformat() if c.time_transaction else None,
                "source": c.source
            }
            for c in unmatched_commissions[:100]  # Первые 100 для экономии памяти
        ]
        
        print(f"[INFO] Sync completed: {stats['matched_commissions']} matched, {stats['failed_matches']} failed ({stats.get('rejected_by_time_filter', 0)} rejected by time filter), {stats['unmatched_by_sql']} unmatched")
        
        return stats
        
    except Exception as e:
        print(f"[ERROR] Sync failed: {str(e)}")
        session.rollback()
        raise
    finally:
        session.close()


def generate_commission_report_fast(batch_size=100, start_date=None, end_date=None, dry_run=False, max_time_diff_hours=24):
    """
    Генерирует быстрый отчет по сопоставлению комиссий с заказами.
    
    Args:
        batch_size: размер пакета для commit (по умолчанию 100)
        start_date: начальная дата для фильтрации (строка в формате 'YYYY-MM-DD')
        end_date: конечная дата для фильтрации (строка в формате 'YYYY-MM-DD')
        dry_run: если True, только поиск без записи в БД (по умолчанию False)
        max_time_diff_hours: максимальная разница во времени в часах (по умолчанию 24)
    
    Returns:
        dict: полный отчет
    """
    import time
    
    start_time = time.time()
    stats = sync_all_commissions_fast(
        batch_size=batch_size, 
        start_date=start_date, 
        end_date=end_date, 
        dry_run=dry_run,
        max_time_diff_hours=max_time_diff_hours
    )
    elapsed_time = time.time() - start_time
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "elapsed_time_seconds": round(elapsed_time, 2),
        "batch_size": batch_size,
        "start_date": start_date,
        "end_date": end_date,
        "dry_run": dry_run,
        "max_time_diff_hours": max_time_diff_hours,
        "summary": {
            "total_matches_found": stats["total_matches_found"],
            "matched_commissions": stats["matched_commissions"],
            "failed_matches": stats["failed_matches"],
            "rejected_by_time_filter": stats.get("rejected_by_time_filter", 0),
            "unmatched_by_sql": stats.get("unmatched_by_sql", 0),
            "summed_commissions": stats["summed_commissions"],
            "match_percentage": (stats["matched_commissions"] / stats["total_matches_found"] * 100) if stats["total_matches_found"] > 0 else 0,
            "total_commission_amount": stats["total_commission_amount"],
            "matched_commission_amount": stats["matched_commission_amount"],
            "failed_commission_amount": stats["failed_commission_amount"],
            "rejected_by_time_filter_amount": stats.get("rejected_by_time_filter_amount", 0.0),
            "unmatched_commission_amount": stats.get("unmatched_commission_amount", 0.0),
            "orders_updated": stats["orders_updated"],
        },
        "details": {
            "matched_transactions": stats["matched_transactions"],
            "failed_transactions": stats["failed_transactions"],
            "orders_with_commission": stats["orders_with_commission_list"],
            "unmatched_commissions": stats.get("unmatched_commissions_details", [])
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

