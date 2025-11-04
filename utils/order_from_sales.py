"""
Утилита для создания заказов (d_orders) из записей таблицы sales.

Этот модуль преобразует данные из таблицы sales (отчеты из iiko) 
в структурированные заказы в таблице d_orders.

ОПТИМИЗИРОВАННАЯ ВЕРСИЯ:
- Один SQL-запрос с GROUP BY для получения всех данных
- Batch операции (commit каждые 100 заказов)
- Суммирование dish_sum_int и dish_discount_sum_int на уровне БД
- JOIN с order_types для получения типов заказов
- Минимальная нагрузка на Python

Логика работы:
1. Один SQL-запрос группирует все sales по order_id и суммирует суммы
2. Batch создание заказов в d_orders (по 100 штук)
3. t_orders не создаются (можно добавить отдельным запуском)
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal
import json

from models.d_order import DOrder
from database.database import engine


class OrderFromSalesConverter:
    """Оптимизированный класс для конвертации записей Sales в Orders"""
    
    def __init__(self, db: Session):
        self.db = db
        self.stats = {
            "processed_orders": 0,
            "created_orders": 0,
            "updated_orders": 0,
            "skipped_orders": 0,
            "errors": []
        }
    
    def convert_all_sales(self, batch_size: int = 100) -> Dict:
        """
        Конвертирует все записи из таблицы sales в заказы.
        Использует один SQL-запрос и batch операции.
        
        Args:
            batch_size: Размер пакета для commit (по умолчанию 100)
        
        Returns:
            Dict: Статистика выполнения
        """
        print("🔄 Начинаем оптимизированную конвертацию sales -> orders...")
        print(f"   Batch size: {batch_size}")
        
        # Получаем агрегированные данные одним запросом
        grouped_sales = self._get_grouped_sales_data()
        
        total_orders = len(grouped_sales)
        print(f"📊 Найдено уникальных заказов: {total_orders}")
        
        # Batch обработка
        batch_counter = 0
        for idx, sale_data in enumerate(grouped_sales, 1):
            if idx % 10 == 0 or idx == total_orders:
                print(f"   Обработано: {idx}/{total_orders} заказов...")
            
            try:
                self._create_or_update_order(sale_data)
                batch_counter += 1
                
                # Commit каждые batch_size записей
                if batch_counter >= batch_size:
                    self.db.commit()
                    batch_counter = 0
                    
            except Exception as e:
                error_msg = f"Ошибка при обработке заказа {sale_data.get('order_id')}: {str(e)}"
                print(f"❌ {error_msg}")
                self.stats["errors"].append(error_msg)
                self.db.rollback()
                batch_counter = 0
        
        # Финальный commit для оставшихся записей
        if batch_counter > 0:
            self.db.commit()
        
        self._print_stats()
        return self.stats
    
    def convert_sales_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime,
        batch_size: int = 100
    ) -> Dict:
        """
        Конвертирует записи sales за указанный период.
        Использует один SQL-запрос и batch операции.
        
        Args:
            start_date: Начало периода
            end_date: Конец периода
            batch_size: Размер пакета для commit (по умолчанию 100)
            
        Returns:
            Dict: Статистика выполнения
        """
        print(f"🔄 Оптимизированная конвертация заказов с {start_date} по {end_date}...")
        print(f"   Batch size: {batch_size}")
        
        # Получаем агрегированные данные за период одним запросом
        grouped_sales = self._get_grouped_sales_data(start_date, end_date)
        
        total_orders = len(grouped_sales)
        print(f"📊 Найдено заказов за период: {total_orders}")
        
        # Batch обработка
        batch_counter = 0
        for idx, sale_data in enumerate(grouped_sales, 1):
            if idx % 10 == 0 or idx == total_orders:
                print(f"   Обработано: {idx}/{total_orders} заказов...")
            
            try:
                self._create_or_update_order(sale_data)
                batch_counter += 1
                
                # Commit каждые batch_size записей
                if batch_counter >= batch_size:
                    self.db.commit()
                    batch_counter = 0
                    
            except Exception as e:
                error_msg = f"Ошибка при обработке заказа {sale_data.get('order_id')}: {str(e)}"
                print(f"❌ {error_msg}")
                self.stats["errors"].append(error_msg)
                self.db.rollback()
                batch_counter = 0
        
        # Финальный commit для оставшихся записей
        if batch_counter > 0:
            self.db.commit()
        
        self._print_stats()
        return self.stats
    
    def _get_grouped_sales_data(
        self, 
        start_date: Optional[datetime] = None, 
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Получает агрегированные данные о продажах одним SQL-запросом.
        Группирует по order_id, суммирует суммы, джойнит с order_types.
        
        Args:
            start_date: Начало периода (опционально)
            end_date: Конец периода (опционально)
        
        Returns:
            List[Dict]: Список агрегированных заказов
        """
        # Базовый запрос с группировкой и суммированием
        date_filter = ""
        if start_date and end_date:
            date_filter = f"AND s.open_time >= '{start_date.isoformat()}' AND s.open_time <= '{end_date.isoformat()}'"
        
        query = text(f"""
            SELECT 
                s.order_id,
                MAX(s.external_number) as external_number,
                MAX(s.delivery_phone) as phone,
                MAX(s.guest_num) as guest_count,
                MAX(s.table_num) as tab_name,
                SUM(s.dish_sum_int) as sum_order,
                SUM(s.dish_discount_sum_int) as discount,
                MAX(s.open_time) as time_order,
                MAX(s.order_deleted) as state_order,
                MAX(s.organization_id) as organization_id,
                MAX(s.order_type_id) as order_type_iiko_id,
                ot.id as order_type_id,
                ot.name as order_type_name,
                -- JSON агрегации для детальной информации
                json_agg(
                    DISTINCT jsonb_build_object(
                        'customer_name', s.delivery_customer_name,
                        'customer_phone', s.delivery_customer_phone,
                        'customer_email', s.delivery_customer_email,
                        'customer_comment', s.delivery_customer_comment,
                        'customer_card_number', s.delivery_customer_card_number,
                        'customer_card_type', s.delivery_customer_card_type
                    )
                ) FILTER (WHERE s.delivery_customer_name IS NOT NULL OR s.delivery_customer_phone IS NOT NULL) as customer_data,
                json_agg(
                    DISTINCT jsonb_build_object(
                        'pay_type', s.pay_types,
                        'sum', s.dish_sum_int,
                        'is_print_cheque', s.pay_types_is_print_cheque,
                        'voucher_num', s.pay_types_voucher_num
                    )
                ) FILTER (WHERE s.pay_types IS NOT NULL) as payments_data,
                json_agg(
                    DISTINCT jsonb_build_object(
                        'discount_type', s.order_discount_type,
                        'discount_sum', s.discount_sum,
                        'discount_percent', s.discount_percent,
                        'guest_card', s.order_discount_guest_card
                    )
                ) FILTER (WHERE s.discount_sum IS NOT NULL AND s.discount_sum > 0) as discounts_data,
                json_build_object(
                    'delivery', json_agg(
                        DISTINCT jsonb_build_object(
                            'is_delivery', s.delivery_is_delivery,
                            'address', s.delivery_address,
                            'city', s.delivery_city,
                            'street', s.delivery_street,
                            'courier', s.delivery_courier,
                            'courier_id', s.delivery_courier_id,
                            'expected_time', s.delivery_expected_time,
                            'actual_time', s.delivery_actual_time
                        )
                    ) FILTER (WHERE s.delivery_is_delivery IS NOT NULL),
                    'terminal', json_agg(
                        DISTINCT jsonb_build_object(
                            'session_id', s.session_id,
                            'session_num', s.session_num,
                            'cash_register', s.cash_register_name,
                            'cash_register_number', s.cash_register_name_number
                        )
                    ) FILTER (WHERE s.session_id IS NOT NULL OR s.cash_register_name IS NOT NULL),
                    'waiter', json_agg(
                        DISTINCT jsonb_build_object(
                            'name', s.waiter_name,
                            'id', s.waiter_name_id
                        )
                    ) FILTER (WHERE s.waiter_name IS NOT NULL),
                    'cashier', json_agg(
                        DISTINCT jsonb_build_object(
                            'name', s.cashier,
                            'id', s.cashier_id
                        )
                    ) FILTER (WHERE s.cashier IS NOT NULL)
                ) as external_data
            FROM 
                public.sales s
            LEFT JOIN 
                public.order_types ot ON s.order_type_id = ot.iiko_id
            WHERE 
                s.order_id IS NOT NULL
                {date_filter}
            GROUP BY 
                s.order_id, ot.id, ot.name
            ORDER BY 
                s.order_id ASC
        """)
        
        result = self.db.execute(query)
        rows = result.fetchall()
        
        # Преобразуем результат в список словарей
        grouped_sales = []
        for row in rows:
            grouped_sales.append({
                'order_id': row[0],
                'external_number': row[1],
                'phone': row[2],
                'guest_count': row[3] or 0,
                'tab_name': row[4],
                'sum_order': float(row[5]) if row[5] else 0.0,
                'discount': float(row[6]) if row[6] else 0.0,
                'time_order': row[7],
                'state_order': row[8] or "completed",
                'organization_id': row[9],
                'order_type_iiko_id': row[10],
                'order_type_id': row[11],
                'order_type_name': row[12],
                'customer_data': row[13],
                'payments_data': row[14],
                'discounts_data': row[15],
                'external_data': row[16]
            })
        
        return grouped_sales
    
    def _create_or_update_order(self, sale_data: Dict) -> None:
        """
        Создает или обновляет заказ на основе агрегированных данных из SQL-запроса.
        
        Args:
            sale_data: Словарь с агрегированными данными заказа
        """
        order_id = sale_data['order_id']
        
        # Проверяем, существует ли уже заказ
        existing_order = self.db.query(DOrder)\
            .filter(DOrder.iiko_id == order_id)\
            .first()
        
        if existing_order:
            # return
            # Обновляем существующий заказ
            self._update_existing_order(existing_order, sale_data)
            self.stats["updated_orders"] += 1
        else:
            # Создаем новый заказ
            new_order = self._create_new_order(sale_data)
            self.db.add(new_order)
            self.stats["created_orders"] += 1
        
        self.stats["processed_orders"] += 1
    
    def _create_new_order(self, sale_data: Dict) -> DOrder:
        """
        Создает новый заказ из агрегированных данных.
        
        Args:
            sale_data: Словарь с агрегированными данными
            
        Returns:
            DOrder: Новый заказ
        """
        # Обрабатываем customer_data
        customer_info = None
        if sale_data['customer_data']:
            customer_list = sale_data['customer_data']
            if customer_list and len(customer_list) > 0:
                customer_info = customer_list[0]
        
        # Обрабатываем payments_data
        payments_info = sale_data['payments_data'] if sale_data['payments_data'] else None
        
        # Обрабатываем discounts_data
        discounts_info = sale_data['discounts_data'] if sale_data['discounts_data'] else None
        
        # Обрабатываем external_data
        external_data = sale_data['external_data'] if sale_data['external_data'] else None
        
        # Создаем заказ
        order = DOrder(
            iiko_id=sale_data['order_id'],
            organization_id=sale_data['organization_id'],
            external_number=sale_data['external_number'],
            phone=sale_data['phone'],
            guest_count=sale_data['guest_count'],
            tab_name=sale_data['tab_name'],
            order_type_id=sale_data['order_type_id'],
            sum_order=Decimal(str(sale_data['sum_order'])),
            state_order=sale_data['state_order'],
            discount=Decimal(str(sale_data['discount'])),
            service=None,
            bank_commission=None,
            time_order=sale_data['time_order'] or datetime.now(),
            deleted=sale_data['state_order'] == "DELETED",
            
            # JSON поля
            customer=json.dumps(customer_info) if customer_info else None,
            payments=json.dumps(payments_info) if payments_info else None,
            discounts_info=json.dumps(discounts_info) if discounts_info else None,
            external_data=json.dumps(external_data) if external_data else None,
        )
        
        return order
    
    def _update_existing_order(self, existing_order: DOrder, sale_data: Dict) -> None:
        """
        Обновляет существующий заказ новыми данными.
        
        Args:
            existing_order: Существующий заказ
            sale_data: Агрегированные данные для обновления
        """
        # Обновляем основные поля, если они не были заполнены
        if not existing_order.phone and sale_data['phone']:
            existing_order.phone = sale_data['phone']
        
        if not existing_order.guest_count and sale_data['guest_count']:
            existing_order.guest_count = sale_data['guest_count']
        
        if not existing_order.external_number and sale_data['external_number']:
            existing_order.external_number = sale_data['external_number']
        
        # Обновляем суммы (всегда, т.к. они могли измениться)
        existing_order.sum_order = Decimal(str(sale_data['sum_order']))
        existing_order.discount = Decimal(str(sale_data['discount']))
        
        # Обновляем order_type_id если есть
        if sale_data['order_type_id'] and not existing_order.order_type_id:
            existing_order.order_type_id = sale_data['order_type_id']
        
        # Обновляем JSON поля, если они не были заполнены
        if not existing_order.customer and sale_data['customer_data']:
            customer_list = sale_data['customer_data']
            if customer_list and len(customer_list) > 0:
                existing_order.customer = json.dumps(customer_list[0])
        
        if not existing_order.payments and sale_data['payments_data']:
            existing_order.payments = json.dumps(sale_data['payments_data'])
        
        if not existing_order.discounts_info and sale_data['discounts_data']:
            existing_order.discounts_info = json.dumps(sale_data['discounts_data'])
        
        if not existing_order.external_data and sale_data['external_data']:
            existing_order.external_data = json.dumps(sale_data['external_data'])
    
    
    def _print_stats(self) -> None:
        """Выводит статистику выполнения."""
        print("\n" + "="*60)
        print("📊 СТАТИСТИКА ОПТИМИЗИРОВАННОЙ КОНВЕРТАЦИИ")
        print("="*60)
        print(f"✅ Обработано заказов:      {self.stats['processed_orders']}")
        print(f"🆕 Создано новых заказов:   {self.stats['created_orders']}")
        print(f"♻️  Обновлено заказов:       {self.stats['updated_orders']}")
        print(f"⏭️  Пропущено заказов:       {self.stats['skipped_orders']}")
        
        if self.stats["errors"]:
            print(f"\n❌ Ошибок: {len(self.stats['errors'])}")
            for error in self.stats["errors"][:5]:  # Показываем первые 5 ошибок
                print(f"   - {error}")
            if len(self.stats["errors"]) > 5:
                print(f"   ... и еще {len(self.stats['errors']) - 5} ошибок")
        else:
            print("\n✨ Конвертация завершена без ошибок!")
        
        print("="*60 + "\n")


def convert_sales_to_orders(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    batch_size: int = 100
) -> Dict:
    """
    ОПТИМИЗИРОВАННАЯ функция для конвертации sales в orders.
    
    Использует один SQL-запрос с GROUP BY для агрегации данных и batch операции.
    
    Args:
        db: Сессия базы данных
        start_date: Начальная дата (опционально)
        end_date: Конечная дата (опционально)
        batch_size: Размер пакета для commit (по умолчанию 100)
        
    Returns:
        Dict: Статистика выполнения
        
    Example:
        from database.database import get_db
        from utils.order_from_sales import convert_sales_to_orders
        
        db = next(get_db())
        stats = convert_sales_to_orders(db, batch_size=100)
        
        # Или за период:
        from datetime import datetime
        stats = convert_sales_to_orders(
            db,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            batch_size=100
        )
    """
    converter = OrderFromSalesConverter(db)
    
    if start_date and end_date:
        return converter.convert_sales_by_date_range(start_date, end_date, batch_size)
    else:
        return converter.convert_all_sales(batch_size)


# Вспомогательная функция для использования из командной строки
if __name__ == "__main__":
    import time
    from database.database import SessionLocal
    
    print("=" * 80)
    print("ОПТИМИЗИРОВАННАЯ КОНВЕРТАЦИЯ SALES -> ORDERS")
    print("=" * 80)
    print("\nОсобенности:")
    print("✓ Один SQL-запрос с GROUP BY для получения всех данных")
    print("✓ Batch операции (commit каждые 100 записей)")
    print("✓ Суммирование dish_sum_int и dish_discount_sum_int на уровне БД")
    print("✓ JOIN с order_types для получения типов заказов")
    print("✓ JSON агрегация для customer, payments, discounts, external_data")
    print("✓ Создаются только d_orders (t_orders можно создать отдельно)")
    print()
    
    db = SessionLocal()
    start_time = time.time()
    
    try:
        stats = convert_sales_to_orders(db, batch_size=100)
        elapsed_time = time.time() - start_time
        
        print("\n" + "=" * 80)
        print("ИТОГОВАЯ СТАТИСТИКА")
        print("=" * 80)
        print(f"⏱️  Время выполнения:        {elapsed_time:.2f} секунд")
        print(f"✅ Обработано заказов:      {stats['processed_orders']}")
        print(f"🆕 Создано заказов:         {stats['created_orders']}")
        print(f"♻️  Обновлено заказов:       {stats['updated_orders']}")
        print(f"⏭️  Пропущено заказов:       {stats['skipped_orders']}")
        
        if stats['errors']:
            print(f"\n❌ Ошибок: {len(stats['errors'])}")
        else:
            print("\n✨ Конвертация завершена без ошибок!")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

