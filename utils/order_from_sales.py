"""
Утилита для создания заказов (d_orders и t_orders) из записей таблицы sales.

Этот модуль преобразует данные из таблицы sales (отчеты из iiko) 
в структурированные заказы в таблицах d_orders и t_orders.

ВАЖНО: Структура данных в sales:
- Каждая запись sales = одно проданное блюдо (не весь заказ!)
- Если в заказе 3 блюда → 3 записи в sales с одинаковым order_id
- У sales НЕТ уникального ID для позиций:
  * item_sale_event_id - это НЕ iiko_id
  * item_sale_event_id может повторяться
- Поэтому TOrder создаются БЕЗ iiko_id (будет NULL)

Логика работы:
1. Группируем все sales по order_id
2. Для каждого уникального order_id создаем ОДИН заказ в d_orders
3. Для каждой записи sales создаем позицию в t_orders
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal

from models.sales import Sales
from models.d_order import DOrder
from models.t_order import TOrder
from models.item import Item
from models.organization import Organization
from models.order_types import OrderType


class OrderFromSalesConverter:
    """Класс для конвертации записей Sales в Orders"""
    
    def __init__(self, db: Session):
        self.db = db
        self.stats = {
            "processed_orders": 0,
            "created_orders": 0,
            "updated_orders": 0,
            "created_items": 0,
            "skipped_sales": 0,
            "errors": []
        }
    
    def convert_all_sales(self) -> Dict:
        """
        Конвертирует все записи из таблицы sales в заказы.
        
        Returns:
            Dict: Статистика выполнения
        """
        print("🔄 Начинаем конвертацию sales -> orders...")
        
        # Получаем все уникальные order_id из sales
        unique_order_ids = self.db.query(Sales.order_id)\
            .filter(Sales.order_id.isnot(None))\
            .distinct()\
            .all()
        
        total_orders = len(unique_order_ids)
        print(f"📊 Найдено уникальных заказов: {total_orders}")
        
        for idx, (order_id,) in enumerate(unique_order_ids, 1):
            if idx % 10 == 0 or idx == total_orders:
                print(f"   Обработано: {idx}/{total_orders} заказов...")
            
            try:
                self._process_order(order_id)
            except Exception as e:
                error_msg = f"Ошибка при обработке заказа {order_id}: {str(e)}"
                print(f"❌ {error_msg}")
                self.stats["errors"].append(error_msg)
        
        self.db.commit()
        self._print_stats()
        return self.stats
    
    def convert_sales_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> Dict:
        """
        Конвертирует записи sales за указанный период.
        
        Args:
            start_date: Начало периода
            end_date: Конец периода
            
        Returns:
            Dict: Статистика выполнения
        """
        print(f"🔄 Конвертация заказов с {start_date} по {end_date}...")
        
        unique_order_ids = self.db.query(Sales.order_id)\
            .filter(
                Sales.order_id.isnot(None),
                Sales.open_time >= start_date,
                Sales.open_time <= end_date
            )\
            .distinct()\
            .all()
        
        total_orders = len(unique_order_ids)
        print(f"📊 Найдено заказов за период: {total_orders}")
        
        for idx, (order_id,) in enumerate(unique_order_ids, 1):
            if idx % 10 == 0 or idx == total_orders:
                print(f"   Обработано: {idx}/{total_orders} заказов...")
            
            try:
                self._process_order(order_id)
            except Exception as e:
                error_msg = f"Ошибка при обработке заказа {order_id}: {str(e)}"
                print(f"❌ {error_msg}")
                self.stats["errors"].append(error_msg)
        
        self.db.commit()
        self._print_stats()
        return self.stats
    
    def _process_order(self, order_id: str) -> None:
        """
        Обрабатывает один заказ: создает или обновляет записи в d_orders и t_orders.
        
        Args:
            order_id: ID заказа из iiko
        """
        # Получаем все записи sales для этого заказа
        sales_records = self.db.query(Sales)\
            .filter(Sales.order_id == order_id)\
            .order_by(Sales.open_time)\
            .all()
        
        if not sales_records:
            self.stats["skipped_sales"] += 1
            return
        
        # Берем первую запись для получения общей информации о заказе
        first_sale = sales_records[0]
        
        # Проверяем, существует ли уже заказ
        existing_order = self.db.query(DOrder)\
            .filter(DOrder.iiko_id == order_id)\
            .first()
        
        if existing_order:
            # Обновляем существующий заказ
            order = self._update_order(existing_order, sales_records)
            self.stats["updated_orders"] += 1
        else:
            # Создаем новый заказ
            order = self._create_order(first_sale, sales_records)
            self.db.add(order)
            self.db.flush()  # Получаем ID для связи с t_orders
            self.stats["created_orders"] += 1
        
        # Обрабатываем позиции заказа
        self._process_order_items(order, sales_records)
        
        self.stats["processed_orders"] += 1
    
    def _create_order(self, first_sale: Sales, sales_records: List[Sales]) -> DOrder:
        """
        Создает новую запись заказа в d_orders.
        
        Args:
            first_sale: Первая запись продажи для получения общей информации
            sales_records: Все записи продаж для этого заказа
            
        Returns:
            DOrder: Созданный заказ
        """
        # Получаем или создаем organization
        organization_id = self._get_or_create_organization(first_sale)
        
        # Получаем или создаем order_type
        order_type_id = self._get_or_create_order_type(first_sale)
        
        # Рассчитываем общую сумму заказа
        total_sum = sum(
            sale.dish_sum_int or Decimal(0) 
            for sale in sales_records
        )
        
        # Рассчитываем общую скидку
        total_discount = sum(
            sale.dish_discount_sum_int or Decimal(0) 
            for sale in sales_records
        )
        
        # Создаем заказ
        order = DOrder(
            iiko_id=first_sale.order_id,
            organization_id=organization_id,
            external_number=first_sale.external_number,
            phone=first_sale.delivery_phone,
            guest_count=first_sale.guest_num or 0,
            tab_name=first_sale.table_num if first_sale.table_num else None,
            order_type_id=order_type_id,
            sum_order=total_sum,
            state_order=first_sale.order_deleted or "completed",
            discount=total_discount,
            service=None,  # Можно добавить, если есть данные
            bank_commission=None,  # Можно добавить, если есть данные
            time_order=first_sale.open_time or datetime.now(),
            deleted=first_sale.order_deleted == "DELETED",
            
            # JSON поля с детальной информацией
            customer=self._extract_customer_info(first_sale),
            payments=self._extract_payments_info(sales_records),
            discounts_info=self._extract_discounts_info(sales_records),
            external_data=self._extract_external_data(first_sale),
        )
        
        return order
    
    def _update_order(
        self, 
        existing_order: DOrder, 
        sales_records: List[Sales]
    ) -> DOrder:
        """
        Обновляет существующий заказ новой информацией из sales.
        
        Args:
            existing_order: Существующий заказ
            sales_records: Записи продаж для обновления
            
        Returns:
            DOrder: Обновленный заказ
        """
        first_sale = sales_records[0]
        
        # Обновляем основные поля, если они не были заполнены
        if not existing_order.phone and first_sale.delivery_phone:
            existing_order.phone = first_sale.delivery_phone
        
        if not existing_order.guest_count and first_sale.guest_num:
            existing_order.guest_count = first_sale.guest_num
        
        # Пересчитываем суммы
        total_sum = sum(
            sale.dish_sum_int or Decimal(0) 
            for sale in sales_records
        )
        total_discount = sum(
            sale.dish_discount_sum_int or Decimal(0) 
            for sale in sales_records
        )
        
        existing_order.sum_order = total_sum
        existing_order.discount = total_discount
        
        # Обновляем JSON поля
        if not existing_order.customer:
            existing_order.customer = self._extract_customer_info(first_sale)
        
        if not existing_order.payments:
            existing_order.payments = self._extract_payments_info(sales_records)
        
        return existing_order
    
    def _process_order_items(
        self, 
        order: DOrder, 
        sales_records: List[Sales]
    ) -> None:
        """
        Создает позиции заказа в t_orders.
        
        ВАЖНО: Каждая запись sales = одна позиция в заказе (одно блюдо).
        У sales НЕТ уникального ID, поэтому мы не используем iiko_id для t_orders.
        
        Args:
            order: Заказ
            sales_records: Записи продаж (каждая = одно блюдо в заказе)
        """
        # При обновлении заказа удаляем старые позиции, чтобы избежать дубликатов
        existing_items = self.db.query(TOrder)\
            .filter(TOrder.order_id == order.id)\
            .all()
        
        # Если позиции уже есть, пропускаем создание (заказ уже был обработан)
        if existing_items:
            return
        
        for sale in sales_records:
            # Пропускаем записи без блюда
            if not sale.dish_id:
                self.stats["skipped_sales"] += 1
                continue
            
            # Ищем товар по iiko_id
            item = self.db.query(Item)\
                .filter(Item.iiko_id == sale.dish_id)\
                .first()
            
            if not item:
                # Если товар не найден, создаем базовую запись
                item = self._create_item_from_sale(sale)
                self.db.add(item)
                self.db.flush()
            
            # Создаем позицию заказа
            # ВАЖНО: НЕ используем item_sale_event_id как iiko_id, 
            # т.к. он не уникальный!
            order_item = TOrder(
                iiko_id=None,  # У sales нет уникального ID для позиций
                item_id=item.id,
                order_id=order.id,
                count_order=sale.dish_amount_int or 1,
                time_order=sale.open_time or datetime.now(),
                comment_order=sale.order_comment
            )
            self.db.add(order_item)
            self.stats["created_items"] += 1
    
    def _get_or_create_organization(self, sale: Sales) -> Optional[int]:
        """Получает или создает организацию из sales."""
        if not sale.organization_id:
            return None
        
        return sale.organization_id
    
    def _get_or_create_order_type(self, sale: Sales) -> Optional[int]:
        """
        Получает или создает тип заказа.
        
        Args:
            sale: Запись продажи
            
        Returns:
            Optional[int]: ID типа заказа или None
        """
        # Если нет информации о типе заказа - возвращаем None
        if not sale.order_type_id and not sale.order_type:
            return None
        
        # Определяем iiko_id и name для order_type
        iiko_id = sale.order_type_id or f"unknown_{sale.order_type}"
        name = sale.order_type or "Неизвестный тип"
        
        # Ищем существующий тип заказа по iiko_id
        order_type = self.db.query(OrderType)\
            .filter(OrderType.iiko_id == iiko_id)\
            .first()
        
        if order_type:
            return order_type.id
        
        # Создаем новый тип заказа
        # Модель OrderType имеет поля: id, iiko_id, name, is_deleted
        new_order_type = OrderType(
            iiko_id=iiko_id,
            name=name,
            is_deleted=False  # По умолчанию не удалено
        )
        self.db.add(new_order_type)
        self.db.flush()
        
        return new_order_type.id
    
    def _create_item_from_sale(self, sale: Sales) -> Item:
        """
        Создает базовую запись товара из данных sales.
        
        Args:
            sale: Запись продажи
            
        Returns:
            Item: Созданный товар
        """
        item = Item(
            iiko_id=sale.dish_id,
            name=sale.dish_name or "Неизвестное блюдо",
            code=sale.dish_code,
            price=sale.dish_sum_int or Decimal(0),
            organization_id=sale.organization_id,
            data_source="sales_import",
            description=sale.dish_full_name,
            measure_unit=sale.dish_measure_unit,
            type=sale.dish_type,
        )
        
        return item
    
    def _extract_customer_info(self, sale: Sales) -> Optional[Dict]:
        """Извлекает информацию о клиенте из sales."""
        if not any([
            sale.delivery_customer_name,
            sale.delivery_customer_phone,
            sale.delivery_customer_email
        ]):
            return None
        
        return {
            "name": sale.delivery_customer_name,
            "phone": sale.delivery_customer_phone,
            "email": sale.delivery_customer_email,
            "comment": sale.delivery_customer_comment,
            "card_number": sale.delivery_customer_card_number,
            "card_type": sale.delivery_customer_card_type,
        }
    
    def _extract_payments_info(self, sales_records: List[Sales]) -> Optional[List[Dict]]:
        """Извлекает информацию о платежах."""
        payments = []
        
        for sale in sales_records:
            if sale.pay_types and sale.dish_sum_int:
                payment = {
                    "type": sale.pay_types,
                    "sum": float(sale.dish_sum_int),
                    "is_print_cheque": sale.pay_types_is_print_cheque,
                    "voucher_num": sale.pay_types_voucher_num,
                }
                payments.append(payment)
        
        return payments if payments else None
    
    def _extract_discounts_info(self, sales_records: List[Sales]) -> Optional[List[Dict]]:
        """Извлекает информацию о скидках."""
        discounts = []
        
        for sale in sales_records:
            if sale.discount_sum and sale.discount_sum > 0:
                discount = {
                    "type": sale.order_discount_type,
                    "sum": float(sale.discount_sum),
                    "percent": float(sale.discount_percent) if sale.discount_percent else None,
                    "guest_card": sale.order_discount_guest_card,
                }
                discounts.append(discount)
        
        return discounts if discounts else None
    
    def _extract_external_data(self, sale: Sales) -> Optional[Dict]:
        """Извлекает дополнительные данные о заказе."""
        external_data = {}
        
        # Информация о доставке
        if sale.delivery_is_delivery:
            external_data["delivery"] = {
                "is_delivery": sale.delivery_is_delivery,
                "address": sale.delivery_address,
                "city": sale.delivery_city,
                "street": sale.delivery_street,
                "courier": sale.delivery_courier,
                "courier_id": sale.delivery_courier_id,
                "expected_time": sale.delivery_expected_time.isoformat() if sale.delivery_expected_time else None,
                "actual_time": sale.delivery_actual_time.isoformat() if sale.delivery_actual_time else None,
            }
        
        # Информация о терминале и сессии
        if sale.session_id or sale.cash_register_name:
            external_data["terminal"] = {
                "session_id": sale.session_id,
                "session_num": sale.session_num,
                "cash_register": sale.cash_register_name,
                "cash_register_number": sale.cash_register_name_number,
            }
        
        # Информация об официанте
        if sale.waiter_name:
            external_data["waiter"] = {
                "name": sale.waiter_name,
                "id": sale.waiter_name_id,
            }
        
        # Информация о кассире
        if sale.cashier:
            external_data["cashier"] = {
                "name": sale.cashier,
                "id": sale.cashier_id,
            }
        
        return external_data if external_data else None
    
    def _print_stats(self) -> None:
        """Выводит статистику выполнения."""
        print("\n" + "="*60)
        print("📊 СТАТИСТИКА КОНВЕРТАЦИИ")
        print("="*60)
        print(f"✅ Обработано заказов:      {self.stats['processed_orders']}")
        print(f"🆕 Создано новых заказов:   {self.stats['created_orders']}")
        print(f"♻️  Обновлено заказов:       {self.stats['updated_orders']}")
        print(f"📦 Создано позиций:         {self.stats['created_items']}")
        print(f"⏭️  Пропущено записей:       {self.stats['skipped_sales']}")
        
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
    end_date: Optional[datetime] = None
) -> Dict:
    """
    Основная функция для конвертации sales в orders.
    
    Args:
        db: Сессия базы данных
        start_date: Начальная дата (опционально)
        end_date: Конечная дата (опционально)
        
    Returns:
        Dict: Статистика выполнения
        
    Example:
        from database.database import get_db
        from utils.order_from_sales import convert_sales_to_orders
        
        db = next(get_db())
        stats = convert_sales_to_orders(db)
        
        # Или за период:
        from datetime import datetime
        stats = convert_sales_to_orders(
            db,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31)
        )
    """
    converter = OrderFromSalesConverter(db)
    
    if start_date and end_date:
        return converter.convert_sales_by_date_range(start_date, end_date)
    else:
        return converter.convert_all_sales()


# Вспомогательная функция для использования из командной строки
if __name__ == "__main__":
    from database.database import SessionLocal
    
    print("🚀 Запуск конвертации Sales -> Orders")
    print("="*60)
    
    db = SessionLocal()
    try:
        stats = convert_sales_to_orders(db)
        print(f"\n✅ Конвертация завершена успешно!")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {str(e)}")
        db.rollback()
    finally:
        db.close()

