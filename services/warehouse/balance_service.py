"""
Сервис для получения и обработки остатков товаров
"""
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from models.item import Item
from models.store import Store
from models.conception import Conception
from models.supplier import Supplier
from models.organization import Organization
from models.department import Department
from services.iiko.iiko_service import IikoService

logger = logging.getLogger(__name__)

iiko_service = IikoService()


async def sync_stores_from_iiko(db: Session) -> Dict[str, Any]:
    """
    Синхронизация складов из iiko API
    
    Returns:
        Словарь с результатом синхронизации
    """
    try:
        stores_data = await iiko_service.get_server_stores()
        
        if not stores_data:
            logger.warning("Не удалось получить склады из iiko API")
            return {
                "success": False,
                "message": "Не удалось получить склады из iiko API",
                "synced": 0
            }
        
        if len(stores_data) == 0:
            logger.warning("Получен пустой список складов из iiko API")
            return {
                "success": False,
                "message": "Получен пустой список складов из iiko API",
                "synced": 0
            }
        
        logger.info(f"Получено складов из iiko API: {len(stores_data)}")

        # Карта Department.iiko_id → Organization.id (резолв через org.department_id)
        dept_to_org: Dict[str, int] = {}
        for d in db.query(Department).all():
            o = db.query(Organization).filter(Organization.department_id == d.id).first()
            if o:
                dept_to_org[d.iiko_id] = o.id

        synced_count = 0
        org_linked_count = 0

        for store_data in stores_data:
            iiko_id = store_data.get("id") or store_data.get("storeId")
            name = store_data.get("name") or store_data.get("storeName")
            code = store_data.get("code") or store_data.get("storeCode")
            parent_id = store_data.get("parent_id") or store_data.get("parentId")
            organization_id = dept_to_org.get(parent_id) if parent_id else None

            if not iiko_id:
                logger.warning(f"Пропущен склад без iiko_id: {store_data}")
                continue

            existing_store = db.query(Store).filter(
                Store.iiko_id == iiko_id
            ).first()

            if existing_store:
                existing_store.name = name or existing_store.name
                existing_store.code = code or existing_store.code
                if organization_id and existing_store.organization_id != organization_id:
                    existing_store.organization_id = organization_id
                    org_linked_count += 1
                existing_store.updated_at = datetime.now()
            else:
                new_store = Store(
                    iiko_id=iiko_id,
                    name=name or f"Склад {iiko_id}",
                    code=code,
                    organization_id=organization_id,
                )
                if organization_id:
                    org_linked_count += 1
                db.add(new_store)

            synced_count += 1

        db.commit()

        logger.info(f"Синхронизировано складов: {synced_count}, привязано к org: {org_linked_count}")
        
        return {
            "success": True,
            "message": f"Синхронизировано складов: {synced_count}",
            "synced": synced_count
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка синхронизации складов: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Ошибка синхронизации складов: {str(e)}",
            "synced": 0
        }


async def get_balance_stores(
    db: Session,
    timestamp: Optional[str] = None,
    organization_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Получить остатки товаров по складам с группировкой
    
    Args:
        db: сессия БД
        timestamp: Дата и время в формате ISO (например, "2025-12-27T12:20:00")
        organization_id: ID организации для фильтрации (опционально)
    
    Returns:
        Список словарей с остатками по складам:
        [
            {
                "store": "название склада",
                "sum": 2400.0,
                "products": [
                    {
                        "item": "название товара",
                        "amount": 2.0,
                        "sum": 2400.0
                    }
                ]
            }
        ]
    """
    try:
        # Синхронизируем склады перед получением остатков
        await sync_stores_from_iiko(db)
        
        # Получаем остатки из iiko API
        balance_data = await iiko_service.get_server_balance_stores(timestamp=timestamp)
        
        if not balance_data:
            logger.warning("Не удалось получить остатки из iiko API")
            return []
        
        # Получаем все склады из БД для маппинга
        stores_map = {}
        stores_query = db.query(Store)
        if organization_id:
            stores_query = stores_query.join(Organization).filter(
                Organization.id == organization_id
            )
        
        for store in stores_query.all():
            stores_map[store.iiko_id] = store.name
        
        # Получаем все товары из БД для маппинга
        items_map = {}
        items_query = db.query(Item)
        if organization_id:
            items_query = items_query.filter(Item.organization_id == organization_id)
        
        for item in items_query.all():
            items_map[item.iiko_id] = item.name
        
        # Группируем остатки по складам
        stores_balance = {}
        
        for balance_item in balance_data:
            store_iiko_id = balance_item.get("store")
            product_iiko_id = balance_item.get("product")
            amount = balance_item.get("amount", 0.0)
            sum_value = balance_item.get("sum", 0.0)
            
            if not store_iiko_id:
                continue
            
            # Получаем название склада
            store_name = stores_map.get(store_iiko_id)
            if not store_name:
                # Если склад не найден в БД, используем iiko_id
                store_name = store_iiko_id
                # Пробуем получить из API
                stores_data = await iiko_service.get_server_stores()
                if stores_data:
                    for store_data in stores_data:
                        if (store_data.get("id") == store_iiko_id or 
                            store_data.get("storeId") == store_iiko_id):
                            store_name = store_data.get("name") or store_data.get("storeName") or store_iiko_id
                            break
            
            # Получаем название товара
            item_name = items_map.get(product_iiko_id)
            if not item_name:
                # Если товар не найден, используем iiko_id
                item_name = product_iiko_id or "Неизвестный товар"
            
            # Инициализируем склад в словаре, если его еще нет
            if store_name not in stores_balance:
                stores_balance[store_name] = {
                    "store": store_name,
                    "sum": 0.0,
                    "products": []
                }
            
            # Добавляем товар к складу
            stores_balance[store_name]["products"].append({
                "item": item_name,
                "amount": float(amount),
                "sum": float(sum_value)
            })
            
            # Увеличиваем общую сумму склада
            stores_balance[store_name]["sum"] += float(sum_value)
        
        # Преобразуем словарь в список
        result = list(stores_balance.values())
        
        logger.info(f"Получено остатков по {len(result)} складам")
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка получения остатков: {e}", exc_info=True)
        return []


async def sync_conceptions_from_iiko(db: Session) -> Dict[str, Any]:
    """
    Синхронизация концепций из iiko API
    
    Returns:
        Словарь с результатом синхронизации
    """
    try:
        conceptions_data = await iiko_service.get_server_conceptions()
        
        if not conceptions_data:
            logger.warning("Не удалось получить концепции из iiko API")
            return {
                "success": False,
                "message": "Не удалось получить концепции из iiko API",
                "synced": 0
            }
        
        synced_count = 0
        
        for conception_data in conceptions_data:
            iiko_id = conception_data.get("id") or conception_data.get("conceptionId")
            name = conception_data.get("name") or conception_data.get("conceptionName")
            code = conception_data.get("code") or conception_data.get("conceptionCode")
            
            if not iiko_id:
                logger.warning(f"Пропущена концепция без iiko_id: {conception_data}")
                continue
            
            # Ищем существующую концепцию
            existing_conception = db.query(Conception).filter(
                Conception.iiko_id == iiko_id
            ).first()
            
            if existing_conception:
                # Обновляем данные
                existing_conception.name = name or existing_conception.name
                existing_conception.code = code or existing_conception.code
                existing_conception.updated_at = datetime.now()
            else:
                # Создаем новую концепцию
                new_conception = Conception(
                    iiko_id=iiko_id,
                    name=name or f"Концепция {iiko_id}",
                    code=code
                )
                db.add(new_conception)
            
            synced_count += 1
        
        db.commit()
        
        logger.info(f"Синхронизировано концепций: {synced_count}")
        
        return {
            "success": True,
            "message": f"Синхронизировано концепций: {synced_count}",
            "synced": synced_count
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка синхронизации концепций: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Ошибка синхронизации концепций: {str(e)}",
            "synced": 0
        }


async def sync_suppliers_from_iiko(db: Session) -> Dict[str, Any]:
    """
    Синхронизация поставщиков из iiko API
    
    Returns:
        Словарь с результатом синхронизации
    """
    try:
        suppliers_data = await iiko_service.get_server_suppliers()
        
        if not suppliers_data:
            logger.warning("Не удалось получить поставщиков из iiko API")
            return {
                "success": False,
                "message": "Не удалось получить поставщиков из iiko API",
                "synced": 0
            }
        
        synced_count = 0
        
        for supplier_data in suppliers_data:
            iiko_id = supplier_data.get("id") or supplier_data.get("supplierId")
            name = supplier_data.get("name") or supplier_data.get("supplierName")
            code = supplier_data.get("code") or supplier_data.get("supplierCode")
            
            if not iiko_id:
                logger.warning(f"Пропущен поставщик без iiko_id: {supplier_data}")
                continue
            
            # Ищем существующего поставщика
            existing_supplier = db.query(Supplier).filter(
                Supplier.iiko_id == iiko_id
            ).first()
            
            if existing_supplier:
                # Обновляем данные
                existing_supplier.name = name or existing_supplier.name
                existing_supplier.code = code or existing_supplier.code
                existing_supplier.updated_at = datetime.now()
            else:
                # Создаем нового поставщика
                new_supplier = Supplier(
                    iiko_id=iiko_id,
                    name=name or f"Поставщик {iiko_id}",
                    code=code
                )
                db.add(new_supplier)
            
            synced_count += 1
        
        db.commit()
        
        logger.info(f"Синхронизировано поставщиков: {synced_count}")
        
        return {
            "success": True,
            "message": f"Синхронизировано поставщиков: {synced_count}",
            "synced": synced_count
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка синхронизации поставщиков: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Ошибка синхронизации поставщиков: {str(e)}",
            "synced": 0
        }

