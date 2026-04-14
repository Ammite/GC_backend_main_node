"""
Синхронизация данных с iiko API
Содержит функции для синхронизации данных из iiko API с локальной базой данных
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .iiko_service import iiko_service
from .iiko_parser import iiko_parser
from database.database import get_db
from models import (
    Organization,
    Category,
    Item,
    Modifier,
    ItemModifier,
    Employees,
    Roles,
    Shift,
    Table,
    Terminal,
    ProductGroup,
    MenuCategory,
    AttendanceType,
    RestaurantSection,
    TerminalGroup,
    Transaction,
    Sales,
    Account,
    UserSalary,
    User,
    WarehouseDocument,
    WarehouseDocumentItem,
    Income,
    Expense,
    PaymentType,
)
from services.transactions_and_statistics.daily_aggregates_service import (
    recalculate_daily_metrics_for_date,
    recalculate_daily_employee_metrics_for_date,
)
from services.employees.employees_service import create_users_for_all_employees

logger = logging.getLogger(__name__)


def _get_all_organization_ids(db: Session) -> List[int]:
    """Получить список ID всех активных организаций."""
    orgs = db.query(Organization.id).filter(Organization.is_active == True).all()  # noqa: E712
    return [org.id for org in orgs]


def _recalculate_metrics_for_date(
    db: Session,
    metric_date: date,
    context: str = "sync"
) -> None:
    """
    Пересчитать дневные метрики за конкретную дату:
    глобально (organization_id=None) + по каждой организации отдельно.
    """
    org_ids = _get_all_organization_ids(db)

    # Глобальный пересчёт (без фильтра по организации)
    try:
        recalculate_daily_metrics_for_date(db, metric_date)
        logger.debug(f"Пересчитаны глобальные дневные метрики за {metric_date} ({context})")
    except Exception as agg_err:
        logger.error(f"Ошибка пересчёта глобальных дневных метрик за {metric_date} ({context}): {agg_err}")

    try:
        recalculate_daily_employee_metrics_for_date(db, metric_date)
        logger.debug(f"Пересчитаны глобальные метрики по сотрудникам за {metric_date} ({context})")
    except Exception as emp_err:
        logger.error(f"Ошибка пересчёта глобальных метрик по сотрудникам за {metric_date} ({context}): {emp_err}")

    # Пересчёт по каждой организации
    for org_id in org_ids:
        try:
            recalculate_daily_metrics_for_date(db, metric_date, org_id)
        except Exception as agg_err:
            logger.error(f"Ошибка пересчёта дневных метрик за {metric_date} org_id={org_id} ({context}): {agg_err}")

        try:
            recalculate_daily_employee_metrics_for_date(db, metric_date, org_id)
        except Exception as emp_err:
            logger.error(f"Ошибка пересчёта метрик по сотрудникам за {metric_date} org_id={org_id} ({context}): {emp_err}")


def _recalculate_metrics_for_date_range(
    db: Session,
    from_date: Optional[datetime],
    to_date: Optional[datetime],
    context: str = "sync"
) -> None:
    """
    Вспомогательная функция для пересчета дневных метрик за диапазон дат.
    Пересчитывает глобально + по каждой организации.

    Args:
        db: сессия БД
        from_date: начало периода
        to_date: конец периода
        context: контекст вызова для логирования
    """
    if not from_date or not to_date:
        return

    try:
        # Определяем диапазон дат
        start_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0).date()
        end_date = to_date.replace(hour=0, minute=0, second=0, microsecond=0).date()

        # Пересчитываем метрики для каждого дня в диапазоне
        current_date = start_date
        while current_date <= end_date:
            _recalculate_metrics_for_date(db, current_date, context)
            current_date += timedelta(days=1)
    except Exception as e:
        logger.error(f"Ошибка при пересчёте метрик за диапазон ({context}): {e}")


class IikoSync:
    """Класс для синхронизации данных с iiko API"""
    
    def __init__(self):
        self.service = iiko_service
        self.parser = iiko_parser
    
    async def sync_organizations(self, db: Session) -> Dict[str, int]:
        """Синхронизация организаций"""
        try:
            # Получаем данные только из Cloud API
            data = await self.service.get_cloud_organizations()
            
            if not data:
                logger.warning("Не удалось получить данные организаций")
                return {"created": 0, "updated": 0, "errors": 0}
            
            # Парсим данные
            parsed_data = self.parser.parse_organizations(data)
            
            created = 0
            updated = 0
            errors = 0
            
            for org_data in parsed_data:
                try:
                    cloud_id = org_data["iiko_id"]

                    # Проверяем существование: сначала по iiko_id, потом по iiko_id_cloud
                    existing_org = db.query(Organization).filter(
                        Organization.iiko_id == cloud_id
                    ).first()

                    if not existing_org:
                        existing_org = db.query(Organization).filter(
                            Organization.iiko_id_cloud == cloud_id
                        ).first()

                    if existing_org:
                        # Обновляем существующую.
                        # Не перезаписываем iiko_id (server UUID) — он в Cloud-ответе
                        # отсутствует и приходит из отдельного source.
                        # `code` теперь обновляется: Cloud API /api/1/organizations
                        # возвращает правильный code, совпадающий с department code
                        # в Server API (по которому идёт JOIN с sales.department_code).
                        for key, value in org_data.items():
                            if key not in ["created_at", "iiko_id"]:
                                setattr(existing_org, key, value)
                        # Если iiko_id_cloud ещё не заполнен, записываем cloud UUID
                        if not existing_org.iiko_id_cloud:
                            existing_org.iiko_id_cloud = cloud_id
                        existing_org.updated_at = datetime.now()
                        updated += 1
                    else:
                        # Создаем новую
                        new_org = Organization(**org_data)
                        db.add(new_org)
                        created += 1
                    
                    # Коммитим каждую запись отдельно
                    db.commit()
                    
                except Exception as e:
                    logger.error(f"Ошибка синхронизации организации {org_data.get('name')}: {e}")
                    db.rollback()  # Откатываем транзакцию при ошибке
                    errors += 1
            logger.info(f"Синхронизация организаций завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации организаций: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}
    
    async def sync_cloud_org_ids(self, db: Session) -> Dict[str, int]:
        """
        Синхронизация iiko_id_cloud для организаций.
        Берёт список организаций из Cloud API и матчит по имени с локальными записями.
        """
        try:
            cloud_orgs = await self.service.get_cloud_organizations()
            if not cloud_orgs:
                logger.warning("Не удалось получить организации из Cloud API")
                return {"updated": 0, "errors": 0}

            updated = 0
            errors = 0

            for cloud_org in cloud_orgs:
                cloud_id = cloud_org.get("id")
                name = cloud_org.get("name", "").strip()
                if not cloud_id or not name:
                    continue

                local_org = db.query(Organization).filter(
                    Organization.name == name
                ).first()

                if local_org:
                    local_org.iiko_id_cloud = cloud_id
                    updated += 1
                    logger.info(f"Org '{name}': iiko_id_cloud = {cloud_id}")
                else:
                    logger.warning(f"Cloud орг '{name}' ({cloud_id}) не найдена локально по имени")

            db.commit()
            logger.info(f"Синхронизация Cloud org IDs завершена: обновлено {updated}, ошибок {errors}")
            return {"updated": updated, "errors": errors}

        except Exception as e:
            logger.error(f"Ошибка синхронизации Cloud org IDs: {e}", exc_info=True)
            db.rollback()
            return {"updated": 0, "errors": 1}

    async def sync_menu(self, db: Session, organization_id: Optional[str] = None) -> Dict[str, int]:
        """Синхронизация меню только из Server API
        Синхронизирует:
        1. Категории продуктов (MenuCategory)
        2. Группы товаров (ProductGroup)
        3. Товары (Item)
        4. Модификаторы товаров (Modifier)
        """
        try:
            logger.info("Запуск синхронизации меню из Server API")
            
            # 1. Синхронизируем категории продуктов
            menu_categories_result = await self.sync_menu_categories(db)
            
            # 2. Синхронизируем группы товаров
            product_groups_result = await self.sync_product_groups(db)
            
            # 3. Синхронизируем товары из Server API
            items_result = await self.sync_items_server(db)
            
            # 4. Синхронизируем модификаторы (они парсятся вместе с товарами)
            # Модификаторы уже синхронизированы в sync_items_server
            
            total_created = (
                menu_categories_result.get("created", 0) + 
                product_groups_result.get("created", 0) + 
                items_result.get("created", 0)
            )
            total_updated = (
                menu_categories_result.get("updated", 0) + 
                product_groups_result.get("updated", 0) + 
                items_result.get("updated", 0)
            )
            total_errors = (
                menu_categories_result.get("errors", 0) + 
                product_groups_result.get("errors", 0) + 
                items_result.get("errors", 0)
            )
            
            logger.info(f"Синхронизация меню завершена: создано {total_created}, обновлено {total_updated}, ошибок {total_errors}")
            return {
                "menu_categories": menu_categories_result,
                "product_groups": product_groups_result,
                "items": items_result,
                "total_created": total_created,
                "total_updated": total_updated,
                "total_errors": total_errors
            }
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации меню: {e}")
            db.rollback()
            return {"menu_categories": 0, "product_groups": 0, "items": 0, "errors": 1}
    
    async def _sync_categories(self, db: Session, categories_data: List[Dict[Any, Any]]) -> Dict[str, int]:
        """Синхронизация категорий"""
        created = 0
        updated = 0
        errors = 0
        
        for cat_data in categories_data:
            try:
                existing_cat = db.query(Category).filter(
                    Category.iiko_id == cat_data["iiko_id"]
                ).first()
                
                if existing_cat:
                    for key, value in cat_data.items():
                        if key not in ["created_at"]:
                            setattr(existing_cat, key, value)
                    existing_cat.updated_at = datetime.now()
                    updated += 1
                else:
                    new_cat = Category(**cat_data)
                    db.add(new_cat)
                    created += 1
                    
            except Exception as e:
                logger.error(f"Ошибка синхронизации категории {cat_data.get('name')}: {e}")
                errors += 1
        
        return {"created": created, "updated": updated, "errors": errors}
    
    async def _sync_items(self, db: Session, items_data: List[Dict[Any, Any]]) -> Dict[str, int]:
        """Синхронизация блюд"""
        created = 0
        updated = 0
        errors = 0
        
        for item_data in items_data:
            try:
                existing_item = db.query(Item).filter(
                    Item.iiko_id == item_data["iiko_id"]
                ).first()
                
                if existing_item:
                    for key, value in item_data.items():
                        if key not in ["created_at"]:
                            setattr(existing_item, key, value)
                    existing_item.updated_at = datetime.now()
                    updated += 1
                else:
                    new_item = Item(**item_data)
                    db.add(new_item)
                    created += 1
                    
            except Exception as e:
                logger.error(f"Ошибка синхронизации блюда {item_data.get('name')}: {e}")
                errors += 1
        
        return {"created": created, "updated": updated, "errors": errors}

    async def sync_items_cloud(self, db: Session, organization_id: int = None) -> Dict[str, int]:
        """Синхронизация товаров из Cloud API для конкретной организации или всех организаций"""
        try:
            if organization_id:
                logger.info(f"Запуск синхронизации товаров Cloud API для организации {organization_id}")
                # Получаем данные из Cloud API для конкретной организации
                cloud_data = await self.service.get_cloud_menu(organization_id)
                if not cloud_data:
                    logger.warning(f"Нет данных Cloud API для организации {organization_id}")
                    return {"created": 0, "updated": 0, "errors": 0}
                
                # Парсим данные с привязкой к организации
                parsed_items = self.parser.parse_items_cloud(cloud_data, organization_id)
            else:
                logger.info("Запуск синхронизации товаров Cloud API для всех организаций")
                # Получаем все организации
                organizations = await self.service.get_organizations()
                if not organizations:
                    logger.warning("Нет организаций для синхронизации")
                    return {"created": 0, "updated": 0, "errors": 0}
                
                parsed_items = []
                # Для каждой организации получаем товары
                for org in organizations:
                    org_id = org.get("id")
                    if org_id:
                        # Получаем внутренний ID организации из базы
                        db_org = db.query(Organization).filter(Organization.iiko_id == org_id).first()
                        if db_org:
                            cloud_data = await self.service.get_cloud_menu(org_id)
                            if cloud_data:
                                # Парсим данные с привязкой к внутреннему ID организации
                                org_items = self.parser.parse_items_cloud(cloud_data, db_org.id)
                                parsed_items.extend(org_items)
            
            created = 0
            updated = 0
            errors = 0
            
            for item_data in parsed_items:
                try:
                    # Ищем существующий товар только по iiko_id (он уникальный)
                    existing_item = db.query(Item).filter(
                        Item.iiko_id == item_data["iiko_id"]
                    ).first()
                    
                    if existing_item:
                        # Товар уже существует - обновляем его
                        # Проверяем, если data_source отличается, ставим is_duplicate = True
                        if existing_item.data_source != item_data["data_source"]:
                            item_data["is_duplicate"] = True
                        
                        # Обновляем все поля
                        for key, value in item_data.items():
                            if key not in ["created_at"]:
                                setattr(existing_item, key, value)
                        existing_item.updated_at = datetime.now()
                        updated += 1
                    else:
                        # Создаем новый товар
                        new_item = Item(**item_data)
                        db.add(new_item)
                        created += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации товара Cloud {item_data.get('name')}: {e}")
                    errors += 1
            
            db.commit()
            logger.info(f"Синхронизация товаров Cloud API завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации товаров Cloud API: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}

    async def sync_items_server(self, db: Session) -> Dict[str, int]:
        """Синхронизация товаров и их модификаторов из Server API"""
        try:
            logger.info("Запуск синхронизации товаров Server API")
            
            # Получаем данные из Server API
            server_data = await self.service.get_server_menu()
            if not server_data:
                logger.warning("Нет данных Server API")
                return {"created": 0, "updated": 0, "errors": 0, "modifiers_created": 0}
            
            # Парсим данные
            parsed_items = self.parser.parse_items_server(server_data)
            
            created = 0
            updated = 0
            errors = 0
            modifiers_created = 0
            
            for item_data in parsed_items:
                try:
                    item_iiko_id = item_data["iiko_id"]
                    
                    # Связываем с категорией по category_server (iiko_id категории)
                    category_iiko_id = item_data.get("category_server")
                    if category_iiko_id:
                        menu_category = db.query(MenuCategory).filter(
                            MenuCategory.iiko_id == category_iiko_id
                        ).first()
                        if menu_category:
                            item_data["menu_category_id"] = menu_category.id
                    
                    # Связываем с группой товаров по parent (iiko_id группы)
                    parent_iiko_id = item_data.get("parent")
                    if parent_iiko_id:
                        product_group = db.query(ProductGroup).filter(
                            ProductGroup.iiko_id == parent_iiko_id
                        ).first()
                        if product_group:
                            item_data["product_group_id"] = product_group.id
                    
                    # Ищем существующий товар по iiko_id
                    existing_item = db.query(Item).filter(
                        Item.iiko_id == item_iiko_id
                    ).first()
                    
                    if existing_item:
                        # Товар уже существует - обновляем его
                        # Проверяем, если data_source отличается, ставим is_duplicate = True
                        if existing_item.data_source != item_data["data_source"]:
                            item_data["is_duplicate"] = True
                        
                        # Обновляем все поля
                        for key, value in item_data.items():
                            if key not in ["created_at"]:
                                setattr(existing_item, key, value)
                        existing_item.updated_at = datetime.now()
                        updated += 1
                    else:
                        # Создаем новый товар
                        new_item = Item(**item_data)
                        db.add(new_item)
                        db.flush()  # Чтобы получить ID товара для модификаторов
                        existing_item = new_item
                        created += 1
                    
                    # Синхронизируем модификаторы товара, если они есть
                    # Получаем исходные данные товара из server_data
                    original_item = next((item for item in server_data if item.get("id") == item_iiko_id), None)
                    if original_item and original_item.get("modifiers"):
                        modifiers_data = original_item.get("modifiers", [])
                        parsed_modifiers = self.parser.parse_item_modifiers(modifiers_data, item_iiko_id)
                        
                        # Удаляем старые связи товар-модификатор
                        db.query(ItemModifier).filter(ItemModifier.item_id == existing_item.id).delete()
                        
                        # Создаем/обновляем модификаторы и связи
                        for mod_data in parsed_modifiers:
                            modifier_iiko_id = mod_data["iiko_id"]
                            
                            # Ищем или создаем сам модификатор
                            modifier = db.query(Modifier).filter(
                                Modifier.iiko_id == modifier_iiko_id
                            ).first()
                            
                            if not modifier:
                                # Создаем новый модификатор
                                modifier = Modifier(
                                    iiko_id=modifier_iiko_id,
                                    deleted=False
                                )
                                db.add(modifier)
                                db.flush()  # Чтобы получить ID
                            
                            # Создаем связь товар-модификатор с параметрами
                            item_modifier = ItemModifier(
                                item_id=existing_item.id,
                                modifier_id=modifier.id,
                                parent_modifier_iiko_id=mod_data.get("parent_modifier_iiko_id"),
                                deleted=mod_data.get("deleted", False),
                                default_amount=mod_data.get("default_amount", 0),
                                free_of_charge_amount=mod_data.get("free_of_charge_amount", 0),
                                minimum_amount=mod_data.get("minimum_amount", 0),
                                maximum_amount=mod_data.get("maximum_amount", 0),
                                hide_if_default_amount=mod_data.get("hide_if_default_amount", False),
                                child_modifiers_have_min_max_restrictions=mod_data.get("child_modifiers_have_min_max_restrictions", False),
                                splittable=mod_data.get("splittable", False)
                            )
                            db.add(item_modifier)
                            modifiers_created += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации товара Server {item_data.get('name')}: {e}")
                    db.rollback()
                    errors += 1
            
            # После синхронизации всех товаров и модификаторов, связываем parent_id модификаторов
            await self._link_modifier_parents(db)
            
            db.commit()
            logger.info(f"Синхронизация товаров Server API завершена: создано {created}, обновлено {updated}, модификаторов создано {modifiers_created}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors, "modifiers_created": modifiers_created}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации товаров Server API: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1, "modifiers_created": 0}
    
    async def _link_modifier_parents(self, db: Session):
        """Связывает ItemModifier с их родителями по parent_modifier_iiko_id"""
        try:
            # Получаем все связи товар-модификатор с parent_modifier_iiko_id
            item_modifiers_with_parents = db.query(ItemModifier).filter(
                ItemModifier.parent_modifier_iiko_id.isnot(None)
            ).all()
            
            for item_modifier in item_modifiers_with_parents:
                # Находим родительскую связь в рамках того же товара
                # Сначала находим модификатор с нужным iiko_id
                parent_modifier = db.query(Modifier).filter(
                    Modifier.iiko_id == item_modifier.parent_modifier_iiko_id
                ).first()
                
                if parent_modifier:
                    # Находим связь этого модификатора с тем же товаром
                    parent_item_modifier = db.query(ItemModifier).filter(
                        ItemModifier.item_id == item_modifier.item_id,
                        ItemModifier.modifier_id == parent_modifier.id
                    ).first()
                    
                    if parent_item_modifier:
                        item_modifier.parent_item_modifier_id = parent_item_modifier.id
            
            logger.info(f"Связано {len(item_modifiers_with_parents)} связей товар-модификатор с родителями")
        except Exception as e:
            logger.error(f"Ошибка связывания связей товар-модификатор с родителями: {e}")
    
    async def sync_menu_categories(self, db: Session) -> Dict[str, int]:
        """Синхронизация категорий продуктов из Server API"""
        try:
            logger.info("Запуск синхронизации категорий продуктов")
            
            # Получаем данные из Server API
            categories_data = await self.service.get_server_product_categories()
            if not categories_data:
                logger.warning("Нет данных категорий продуктов")
                return {"created": 0, "updated": 0, "errors": 0}
            
            # Парсим данные
            parsed_categories = self.parser.parse_product_categories(categories_data)
            
            created = 0
            updated = 0
            errors = 0
            
            for cat_data in parsed_categories:
                try:
                    # Ищем существующую категорию по iiko_id
                    existing_cat = db.query(MenuCategory).filter(
                        MenuCategory.iiko_id == cat_data["iiko_id"]
                    ).first()
                    
                    if existing_cat:
                        # Обновляем существующую категорию
                        for key, value in cat_data.items():
                            if key not in ["created_at"]:
                                setattr(existing_cat, key, value)
                        existing_cat.updated_at = datetime.now()
                        updated += 1
                    else:
                        # Создаем новую категорию
                        new_cat = MenuCategory(**cat_data)
                        db.add(new_cat)
                        created += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации категории {cat_data.get('name')}: {e}")
                    errors += 1
            
            db.commit()
            logger.info(f"Синхронизация категорий продуктов завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации категорий продуктов: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}
    
    async def sync_product_groups(self, db: Session) -> Dict[str, int]:
        """Синхронизация групп товаров из Server API"""
        try:
            logger.info("Запуск синхронизации групп товаров")
            
            # Получаем данные из Server API
            groups_data = await self.service.get_server_product_groups()
            if not groups_data:
                logger.warning("Нет данных групп товаров")
                return {"created": 0, "updated": 0, "errors": 0}
            
            # Парсим данные
            parsed_groups = self.parser.parse_product_groups(groups_data)
            
            created = 0
            updated = 0
            errors = 0
            
            for group_data in parsed_groups:
                try:
                    # Ищем существующую группу по iiko_id
                    existing_group = db.query(ProductGroup).filter(
                        ProductGroup.iiko_id == group_data["iiko_id"]
                    ).first()
                    
                    if existing_group:
                        # Обновляем существующую группу
                        for key, value in group_data.items():
                            if key not in ["created_at"]:
                                setattr(existing_group, key, value)
                        existing_group.updated_at = datetime.now()
                        updated += 1
                    else:
                        # Создаем новую группу
                        new_group = ProductGroup(**group_data)
                        db.add(new_group)
                        created += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации группы товаров {group_data.get('name')}: {e}")
                    errors += 1
            
            # После создания всех групп, связываем parent_id
            await self._link_product_group_parents(db)
            
            db.commit()
            logger.info(f"Синхронизация групп товаров завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации групп товаров: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}
    
    async def _link_product_group_parents(self, db: Session):
        """Связывает группы товаров с их родителями по parent_iiko_id"""
        try:
            # Получаем все группы с parent_iiko_id
            groups_with_parents = db.query(ProductGroup).filter(
                ProductGroup.parent_iiko_id.isnot(None)
            ).all()
            
            for group in groups_with_parents:
                # Находим родительскую группу по iiko_id
                parent_group = db.query(ProductGroup).filter(
                    ProductGroup.iiko_id == group.parent_iiko_id
                ).first()
                
                if parent_group:
                    group.parent_id = parent_group.id
            
            logger.info(f"Связано {len(groups_with_parents)} групп товаров с родителями")
        except Exception as e:
            logger.error(f"Ошибка связывания групп товаров с родителями: {e}")
    
    async def _sync_modifiers(self, db: Session, modifiers_data: List[Dict[Any, Any]]) -> Dict[str, int]:
        """Синхронизация модификаторов"""
        created = 0
        updated = 0
        errors = 0
        
        for modifier_data in modifiers_data:
            try:
                existing_modifier = db.query(Modifier).filter(
                    Modifier.iiko_id == modifier_data["iiko_id"]
                ).first()
                
                if existing_modifier:
                    for key, value in modifier_data.items():
                        if key not in ["created_at"]:
                            setattr(existing_modifier, key, value)
                    existing_modifier.updated_at = datetime.now()
                    updated += 1
                else:
                    new_modifier = Modifier(**modifier_data)
                    db.add(new_modifier)
                    created += 1
                    
            except Exception as e:
                logger.error(f"Ошибка синхронизации модификатора {modifier_data.get('name')}: {e}")
                errors += 1
        
        return {"created": created, "updated": updated, "errors": errors}
    
    async def sync_employees(self, db: Session, organization_id: Optional[str] = None) -> Dict[str, int]:
        """Синхронизация сотрудников"""
        try:
            # Получаем данные сотрудников
            employees_data = await self.service.get_employees(organization_id)
            
            if not employees_data:
                logger.warning("Не удалось получить данные сотрудников")
                return {"created": 0, "updated": 0, "errors": 0}
            
            # Парсим данные
            parsed_data = self.parser.parse_employees(employees_data)
            
            created = 0
            updated = 0
            errors = 0
            
            for emp_data in parsed_data:
                try:
                    # Проверяем, является ли сотрудник уволенным (по слову "уволен" в имени)
                    name = emp_data.get("name", "")
                    if name and "уволен" in name.lower():
                        emp_data["deleted"] = True
                        logger.info(f"Сотрудник {name} помечен как уволенный")
                    
                    existing_emp = db.query(Employees).filter(
                        Employees.iiko_id == emp_data["iiko_id"]
                    ).first()

                    # Если по iiko_id не нашли — ищем по code (iiko_id мог измениться)
                    old_iiko_id = None
                    if not existing_emp and emp_data.get("code"):
                        existing_emp = db.query(Employees).filter(
                            Employees.code == emp_data["code"],
                            Employees.deleted == False,  # noqa: E712
                        ).first()
                        if existing_emp and existing_emp.iiko_id != emp_data["iiko_id"]:
                            old_iiko_id = existing_emp.iiko_id
                            logger.info(
                                f"iiko_id сотрудника {emp_data.get('name')} изменился: "
                                f"{old_iiko_id} → {emp_data['iiko_id']}"
                            )

                    # Обрабатываем связи с ролями
                    main_role_iiko_id = emp_data.pop("main_role_iiko_id", None)
                    roles_iiko_ids = emp_data.pop("roles_iiko_ids", [])
                    
                    # Находим главную роль по iiko_id
                    main_role_id = None
                    if main_role_iiko_id:
                        main_role = db.query(Roles).filter(Roles.iiko_id == main_role_iiko_id).first()
                        if main_role:
                            main_role_id = main_role.id
                    
                    # Находим все роли по iiko_id
                    roles_ids = []
                    for role_iiko_id in roles_iiko_ids:
                        role = db.query(Roles).filter(Roles.iiko_id == role_iiko_id).first()
                        if role:
                            roles_ids.append(role.id)
                    
                    # Добавляем найденные ID ролей в данные
                    emp_data["main_role_id"] = main_role_id
                    emp_data["roles_id"] = roles_ids
                    
                    # Убираем поля, которые не должны обновляться
                    emp_data.pop("created_at", None)
                    
                    if existing_emp:
                        # Если iiko_id изменился — обновляем связанного User
                        if old_iiko_id:
                            linked_user = db.query(User).filter(User.iiko_id == old_iiko_id).first()
                            if linked_user:
                                linked_user.iiko_id = emp_data["iiko_id"]
                                logger.info(
                                    f"Обновлён iiko_id у User {linked_user.id} ({linked_user.login}): "
                                    f"{old_iiko_id} → {emp_data['iiko_id']}"
                                )

                        for key, value in emp_data.items():
                            setattr(existing_emp, key, value)
                        existing_emp.updated_at = datetime.now()
                        updated += 1
                    else:
                        emp_data["created_at"] = datetime.now()
                        emp_data["updated_at"] = datetime.now()
                        new_emp = Employees(**emp_data)
                        db.add(new_emp)
                        created += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации сотрудника {emp_data.get('name', 'Unknown')}: {e}")
                    db.rollback()  # Откатываем транзакцию при ошибке
                    errors += 1
            
            db.commit()
            logger.info(f"Синхронизация сотрудников завершена: создано {created}, обновлено {updated}, ошибок {errors}")

            # Автоматически создаём User для новых сотрудников без учётной записи
            try:
                new_users = create_users_for_all_employees(db)
                if new_users:
                    logger.info(f"Автоматически создано {len(new_users)} пользователей для новых сотрудников")
            except Exception as e:
                logger.error(f"Ошибка автосоздания пользователей: {e}")

            return {"created": created, "updated": updated, "errors": errors}

        except Exception as e:
            logger.error(f"Ошибка синхронизации сотрудников: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}

    async def sync_roles(self, db: Session) -> Dict[str, int]:
        """Синхронизация ролей"""
        try:
            roles_data = await self.service.get_roles()
            
            if not roles_data:
                logger.warning("Не удалось получить данные ролей")
                return {"created": 0, "updated": 0, "errors": 0}
            
            parsed_data = self.parser.parse_roles(roles_data)
            
            created = 0
            updated = 0
            errors = 0
            
            for role_data in parsed_data:
                try:
                    existing_role = db.query(Roles).filter(
                        Roles.iiko_id == role_data["iiko_id"]
                    ).first()
                    
                    if existing_role:
                        for key, value in role_data.items():
                            setattr(existing_role, key, value)
                        updated += 1
                    else:
                        new_role = Roles(**role_data)
                        db.add(new_role)
                        created += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации роли {role_data.get('name')}: {e}")
                    errors += 1
            
            db.commit()
            logger.info(f"Синхронизация ролей завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации ролей: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}
    
    async def sync_attendance_types(self, db: Session) -> Dict[str, int]:
        """Синхронизация типов явок из Server API"""
        try:
            raw_data = await self.service.get_attendance_types()

            if not raw_data:
                logger.warning("Не удалось получить данные типов явок")
                return {"created": 0, "updated": 0, "errors": 0}

            created = 0
            updated = 0
            errors = 0

            for item in raw_data:
                try:
                    iiko_id = item.get("id")
                    if not iiko_id:
                        continue

                    name = item.get("name") or ""
                    code = item.get("code") or name
                    is_deleted = item.get("isDeleted", False)

                    existing = db.query(AttendanceType).filter(
                        AttendanceType.iiko_id == iiko_id
                    ).first()

                    if existing:
                        existing.name = name
                        existing.code = code
                        existing.status = not is_deleted
                        existing.updated_at = datetime.now()
                        updated += 1
                    else:
                        new_type = AttendanceType(
                            iiko_id=iiko_id,
                            code=code,
                            name=name,
                            status=not is_deleted,
                        )
                        db.add(new_type)
                        created += 1

                except Exception as e:
                    logger.error(f"Ошибка синхронизации типа явки: {e}")
                    errors += 1

            db.commit()
            logger.info(f"Синхронизация типов явок завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors}

        except Exception as e:
            logger.error(f"Ошибка синхронизации типов явок: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}

    async def sync_restaurant_sections(self, db: Session, organization_id: Optional[str] = None) -> Dict[str, int]:
        """Синхронизация секций ресторана"""
        try:
            sections_data = await self.service.get_restaurant_sections(organization_id)
            
            if not sections_data:
                logger.warning("Не удалось получить данные секций ресторана")
                return {"created": 0, "updated": 0, "errors": 0}
            
            parsed_data = self.parser.parse_restaurant_sections(sections_data)
            
            created = 0
            updated = 0
            errors = 0
            
            for section_data in parsed_data:
                try:
                    # Находим терминальную группу по iiko_id
                    terminal_group_iiko_id = section_data.get("terminal_group_iiko_id")
                    terminal_group = None
                    if terminal_group_iiko_id:
                        terminal_group = db.query(TerminalGroup).filter(
                            TerminalGroup.iiko_id == terminal_group_iiko_id
                        ).first()
                    
                    if not terminal_group:
                        logger.warning(f"Не найдена терминальная группа с iiko_id {terminal_group_iiko_id} для секции {section_data.get('iiko_id')}")
                        errors += 1
                        continue
                    
                    # Ищем существующую секцию по iiko_id
                    existing_section = db.query(RestaurantSection).filter(
                        RestaurantSection.iiko_id == section_data["iiko_id"]
                    ).first()
                    
                    if existing_section:
                        # Обновляем существующую секцию
                        existing_section.name = section_data.get("name", "")
                        existing_section.terminal_group_id = terminal_group.id
                        existing_section.updated_at = datetime.now()
                        updated += 1
                    else:
                        # Создаем новую секцию
                        new_section = RestaurantSection(
                            iiko_id=section_data["iiko_id"],
                            name=section_data.get("name", ""),
                            terminal_group_id=terminal_group.id,
                            created_at=datetime.now(),
                            updated_at=datetime.now()
                        )
                        db.add(new_section)
                        created += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации секции {section_data.get('name')}: {e}")
                    errors += 1
            
            db.commit()
            logger.info(f"Синхронизация секций ресторана завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации секций ресторана: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}

    async def sync_tables(self, db: Session, organization_id: Optional[str] = None, skip_sections_sync: bool = False) -> Dict[str, int]:
        """Синхронизация столов"""
        try:
            # Сначала синхронизируем секции, чтобы они существовали
            if not skip_sections_sync:
                await self.sync_restaurant_sections(db, organization_id)
            
            tables_data = await self.service.get_tables(organization_id)
            
            if not tables_data:
                logger.warning("Не удалось получить данные столов")
                return {"created": 0, "updated": 0, "errors": 0}
            
            parsed_data = self.parser.parse_tables(tables_data)
            
            created = 0
            updated = 0
            errors = 0
            
            for table_data in parsed_data:
                try:
                    # Находим секцию по section_iiko_id
                    section_iiko_id = table_data.get("section_iiko_id")
                    section = None
                    if section_iiko_id:
                        section = db.query(RestaurantSection).filter(
                            RestaurantSection.iiko_id == section_iiko_id
                        ).first()
                    
                    if not section:
                        logger.warning(f"Не найдена секция с iiko_id {section_iiko_id} для стола {table_data.get('iiko_id')}")
                        errors += 1
                        continue
                    
                    # Удаляем section_iiko_id из данных и добавляем section_id
                    table_data.pop("section_iiko_id", None)
                    table_data["section_id"] = section.id

                    # Поиск существующего стола: сначала по составному ключу
                    # (section_id, number) — он стабилен даже если iiko переприсвоит
                    # uuid'ы. Это предотвращает накопление дублей-призраков.
                    # Fallback'и на случай, если несколько столов с одним номером
                    # в одной секции (теоретически возможно) или если ключ не нашёлся:
                    # → по pos_id (id в RMS-базе, более стабильный, чем cloud-id)
                    # → по iiko_id (старое поведение)
                    existing_table = None
                    table_number = table_data.get("number")
                    if table_number is not None:
                        existing_table = db.query(Table).filter(
                            Table.section_id == section.id,
                            Table.number == table_number,
                        ).first()
                    if not existing_table and table_data.get("pos_id"):
                        existing_table = db.query(Table).filter(
                            Table.pos_id == table_data["pos_id"]
                        ).first()
                    if not existing_table:
                        existing_table = db.query(Table).filter(
                            Table.iiko_id == table_data["iiko_id"]
                        ).first()

                    if existing_table:
                        # Обновляем существующий стол (включая is_deleted=False,
                        # чтобы стол, ошибочно помеченный удалённым, ожил)
                        for key, value in table_data.items():
                            if key not in ["created_at"]:
                                setattr(existing_table, key, value)
                        existing_table.is_deleted = False
                        existing_table.updated_at = datetime.now()
                        updated += 1
                    else:
                        # Создаем новый стол
                        new_table = Table(**table_data)
                        db.add(new_table)
                        created += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации стола {table_data.get('name')}: {e}")
                    errors += 1
            
            db.commit()
            logger.info(f"Синхронизация столов завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации столов: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}
    
    async def sync_terminal_groups(self, db: Session, organization_id: Optional[str] = None) -> Dict[str, int]:
        """Синхронизация групп терминалов"""
        try:
            terminal_groups_data = await self.service.get_terminal_groups(organization_id)
            
            if not terminal_groups_data:
                logger.warning("Не удалось получить данные групп терминалов")
                return {"created": 0, "updated": 0, "errors": 0}
            
            parsed_data = self.parser.parse_terminal_groups(terminal_groups_data)
            
            created = 0
            updated = 0
            errors = 0
            
            for group_data in parsed_data:
                try:
                    # Находим организацию по iiko_id
                    org_iiko_id = group_data.get("organization_id")
                    organization = None
                    if org_iiko_id:
                        organization = db.query(Organization).filter(
                            Organization.iiko_id == org_iiko_id
                        ).first()
                    
                    # Убираем organization_id из данных, так как это iiko_id
                    group_data_clean = {k: v for k, v in group_data.items() if k != "organization_id"}
                    
                    existing_group = db.query(TerminalGroup).filter(
                        TerminalGroup.iiko_id == group_data["iiko_id"]
                    ).first()
                    
                    if existing_group:
                        for key, value in group_data_clean.items():
                            if key not in ["created_at"]:
                                setattr(existing_group, key, value)
                        if organization:
                            existing_group.organization_id = organization.id
                        existing_group.updated_at = datetime.now()
                        updated += 1
                    else:
                        new_group = TerminalGroup(iiko_id=group_data["iiko_id"], name=group_data["name"])
                        if organization:
                            new_group.organization_id = organization.id
                        db.add(new_group)
                        created += 1
                    
                    # Коммитим каждую запись отдельно
                    db.commit()
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации группы терминалов {group_data.get('iiko_id')}: {e}")
                    db.rollback()  # Откатываем транзакцию при ошибке
                    errors += 1
            
            logger.info(f"Синхронизация групп терминалов завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации групп терминалов: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}

    async def sync_terminals(self, db: Session, organization_id: Optional[str] = None) -> Dict[str, int]:
        """Синхронизация терминалов"""
        try:
            terminals_data = await self.service.get_terminals(organization_id)
            
            if not terminals_data:
                logger.warning("Не удалось получить данные терминалов")
                return {"created": 0, "updated": 0, "errors": 0}
            
            parsed_data = self.parser.parse_terminals(terminals_data)
            
            created = 0
            updated = 0
            errors = 0
            
            for terminal_data in parsed_data:
                try:
                    # Находим организацию по iiko_id
                    org_iiko_id = terminal_data.get("organization_id")
                    organization = None
                    if org_iiko_id:
                        organization = db.query(Organization).filter(
                            Organization.iiko_id == org_iiko_id
                        ).first()
                    
                    # Убираем organization_id из данных, так как это iiko_id
                    terminal_data_clean = {k: v for k, v in terminal_data.items() if k != "organization_id"}
                    
                    existing_terminal = db.query(Terminal).filter(
                        Terminal.iiko_id == terminal_data["iiko_id"]
                    ).first()
                    
                    if existing_terminal:
                        for key, value in terminal_data_clean.items():
                            if key not in ["created_at"]:
                                setattr(existing_terminal, key, value)
                        if organization:
                            existing_terminal.organization_id = organization.id
                        existing_terminal.updated_at = datetime.now()
                        updated += 1
                    else:
                        new_terminal = Terminal(**terminal_data_clean)
                        if organization:
                            new_terminal.organization_id = organization.id
                        db.add(new_terminal)
                        created += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации терминала {terminal_data.get('name')}: {e}")
                    db.rollback()  # Откатываем транзакцию при ошибке
                    errors += 1
            
            db.commit()
            logger.info(f"Синхронизация терминалов завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации терминалов: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}
    
    async def sync_payment_types(self, db: Session) -> Dict[str, int]:
        """Синхронизация видов оплат из ДВУХ источников.

        1) Cloud `/api/1/payment_types` — primary, ~6 видов с полной схемой
           (paymentTypeKind, terminalGroups, combinable, paymentProcessingType).
        2) Server `/resto/api/v2/entities/list?rootType=PaymentType` — secondary,
           ~43 вида с минимальной схемой. Достраивается эвристиками.

        Мердж по iiko_id: Cloud приоритетнее (полная схема), Server дополняет.

        Для Server-only видов с именами вроде «Каспий банк ИП Шаяхметов»
        выполняется фильтр по юр.лицу: вид доступен только тем организациям,
        которые принадлежат соответствующему JurPerson из corporate tree.
        Остальные Server-only виды без указания юр.лица — доступны для всех.
        """
        try:
            from models.department import Department

            # 1. Cloud организации
            orgs = db.query(Organization).filter(
                Organization.iiko_id_cloud.isnot(None)
            ).all()
            org_cloud_ids = [org.iiko_id_cloud for org in orgs]
            if not org_cloud_ids:
                logger.warning("Нет организаций с iiko_id_cloud для sync_payment_types")
                return {"created": 0, "updated": 0, "errors": 0}

            # 2. Cloud данные (primary)
            cloud_raw = await self.service.get_payment_types(org_cloud_ids)
            cloud_parsed = self.parser.parse_payment_types(cloud_raw) if cloud_raw else []
            logger.info(f"sync_payment_types: Cloud вернул {len(cloud_parsed)} видов")

            # 3. Server данные (secondary)
            server_raw = await self.service.get_server_payment_types()
            server_parsed = self.parser.parse_server_payment_types(server_raw) if server_raw else []
            logger.info(f"sync_payment_types: Server вернул {len(server_parsed)} видов")

            # 4. JurPersons из corporate tree
            jur_persons = await self.service.get_server_jur_persons() or []
            # Маппинг: name → jur_person iiko_id
            jp_name_to_id = {jp['name']: jp['id'] for jp in jur_persons if jp.get('name') and jp.get('id')}
            logger.info(f"sync_payment_types: JurPersons {jp_name_to_id}")

            # 5. Маппинг: jur_person iiko_id → список cloud uuid'ов организаций
            # организация → department.parent_id (это и есть JurPerson uuid)
            jp_to_org_ids: Dict[str, List[str]] = {}
            org_with_dept = (
                db.query(Organization, Department)
                .join(Department, Department.id == Organization.department_id)
                .filter(Organization.iiko_id_cloud.isnot(None))
                .all()
            )
            for org, dept in org_with_dept:
                if dept.parent_id:
                    jp_to_org_ids.setdefault(dept.parent_id, []).append(org.iiko_id_cloud)
            logger.info(f"sync_payment_types: jp_to_org_ids = {jp_to_org_ids}")

            # 6. Мердж: Cloud primary, Server fallback по iiko_id
            merged: Dict[str, Dict] = {}
            for pt in cloud_parsed:
                pt.pop('jur_person_hint', None)
                merged[pt['iiko_id']] = pt
            for pt in server_parsed:
                if pt['iiko_id'] in merged:
                    # Cloud уже есть — пропускаем (полная схема приоритетна)
                    continue
                # Server-only: рассчитываем organization_iiko_ids по jur_person
                hint = pt.pop('jur_person_hint', None)
                if hint and hint in jp_name_to_id:
                    jp_id = jp_name_to_id[hint]
                    pt['organization_iiko_ids'] = jp_to_org_ids.get(jp_id, [])
                else:
                    # Без указания юр.лица → доступен для ВСЕХ организаций
                    pt['organization_iiko_ids'] = None
                merged[pt['iiko_id']] = pt

            logger.info(f"sync_payment_types: после мерджа {len(merged)} видов")

            # 7. Upsert
            created = updated = errors = 0
            for pt_data in merged.values():
                try:
                    existing = db.query(PaymentType).filter(
                        PaymentType.iiko_id == pt_data["iiko_id"]
                    ).first()
                    if existing:
                        for key, value in pt_data.items():
                            if key not in ["created_at"]:
                                setattr(existing, key, value)
                        existing.updated_at = datetime.now()
                        updated += 1
                    else:
                        pt_data["created_at"] = datetime.now()
                        pt_data["updated_at"] = datetime.now()
                        new_pt = PaymentType(**pt_data)
                        db.add(new_pt)
                        created += 1
                except Exception as e:
                    logger.error(f"Ошибка sync_payment_types для {pt_data.get('iiko_id')}: {e}")
                    errors += 1

            db.commit()
            logger.info(
                f"sync_payment_types: создано {created}, обновлено {updated}, "
                f"ошибок {errors} (cloud={len(cloud_parsed)}, server={len(server_parsed)}, "
                f"merged={len(merged)})"
            )
            return {"created": created, "updated": updated, "errors": errors}

        except Exception as e:
            logger.error(f"Ошибка sync_payment_types: {e}", exc_info=True)
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}

    async def sync_all(self, db: Session, organization_id: Optional[str] = None) -> Dict[str, Any]:
        """Полная синхронизация всех данных"""
        logger.info("Начало полной синхронизации данных с iiko API")
        
        results = {}
        
        try:
            # Синхронизируем организации
            results["organizations"] = await self.sync_organizations(db)
            
            # Синхронизируем меню
            results["menu"] = await self.sync_menu(db, organization_id)
            
            # Синхронизируем сотрудников
            results["employees"] = await self.sync_employees(db, organization_id)
            
            # Синхронизируем роли
            results["roles"] = await self.sync_roles(db)
            
            # Синхронизируем терминалы (нужны для секций)
            results["terminals"] = await self.sync_terminals(db, organization_id)
            
            # Синхронизируем секции ресторана (нужны для столов)
            results["restaurant_sections"] = await self.sync_restaurant_sections(db, organization_id)
            
            # Синхронизируем столы (зависят от секций)
            results["tables"] = await self.sync_tables(db, organization_id)

            # Синхронизируем типы явок
            results["attendance_types"] = await self.sync_attendance_types(db)

            # Синхронизируем виды оплат
            results["payment_types"] = await self.sync_payment_types(db)

            logger.info("Полная синхронизация данных завершена успешно")
            return results
            
        except Exception as e:
            logger.error(f"Ошибка полной синхронизации: {e}")
            return {"error": str(e)}
    
    def _find_existing_transaction(self, db: Session, trans_data: Dict[str, Any]) -> Optional[Transaction]:
        """Поиск существующей транзакции по составному ключу"""
        # Вариант 1: order_id + product_id + date_time + amount
        if trans_data.get("order_id") and trans_data.get("product_id") and trans_data.get("date_time") and trans_data.get("amount"):
            existing = db.query(Transaction).filter(
                Transaction.order_id == trans_data["order_id"],
                Transaction.product_id == trans_data["product_id"],
                Transaction.date_time == trans_data["date_time"],
                Transaction.amount == trans_data["amount"]
            ).first()
            if existing:
                return existing
        
        # Вариант 2: order_num + product_id + date_time + amount
        if trans_data.get("order_num") and trans_data.get("product_id") and trans_data.get("date_time") and trans_data.get("amount"):
            existing = db.query(Transaction).filter(
                Transaction.order_num == trans_data["order_num"],
                Transaction.product_id == trans_data["product_id"],
                Transaction.date_time == trans_data["date_time"],
                Transaction.amount == trans_data["amount"]
            ).first()
            if existing:
                return existing
        
        # Вариант 3: document + product_id + date_time + amount
        if trans_data.get("document") and trans_data.get("product_id") and trans_data.get("date_time") and trans_data.get("amount"):
            existing = db.query(Transaction).filter(
                Transaction.document == trans_data["document"],
                Transaction.product_id == trans_data["product_id"],
                Transaction.date_time == trans_data["date_time"],
                Transaction.amount == trans_data["amount"]
            ).first()
            if existing:
                return existing
        
        # Вариант 4: order_id + date_time + amount (если product_id отсутствует)
        if trans_data.get("order_id") and trans_data.get("date_time") and trans_data.get("amount"):
            existing = db.query(Transaction).filter(
                Transaction.order_id == trans_data["order_id"],
                Transaction.date_time == trans_data["date_time"],
                Transaction.amount == trans_data["amount"]
            ).first()
            if existing:
                return existing
        
        # Вариант 5: order_num + date_time + amount (если product_id отсутствует)
        if trans_data.get("order_num") and trans_data.get("date_time") and trans_data.get("amount"):
            existing = db.query(Transaction).filter(
                Transaction.order_num == trans_data["order_num"],
                Transaction.date_time == trans_data["date_time"],
                Transaction.amount == trans_data["amount"]
            ).first()
            if existing:
                return existing
        
        return None

    async def sync_transactions(self, db: Session, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None, skip_metrics_recalculation: bool = False) -> Dict[str, int]:
        """Синхронизация транзакций с удалением записей за день (from_date) перед записью"""
        try:
            if not from_date or not to_date:
                logger.warning("Не указаны даты для синхронизации транзакций")
                return {"created": 0, "updated": 0, "errors": 0, "deleted": 0}
            
            # Нормализуем дату (убираем время, оставляем только дату)
            day_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_date_end = day_date + timedelta(days=1)
            
            logger.info(f"Синхронизация транзакций за {day_date.date()}")
            
            # Удаляем записи за этот день (по левой границе from_date)
            deleted = db.query(Transaction).filter(
                Transaction.date_typed >= day_date,
                Transaction.date_typed < day_date_end
            ).delete(synchronize_session=False)
            
            if deleted > 0:
                logger.debug(f"Удалено {deleted} транзакций за {day_date.date()}")
            
            # Получаем данные транзакций за день
            transactions_data = await self.service.get_transactions(from_date, to_date)
            
            if not transactions_data:
                logger.warning("Не удалось получить данные транзакций")
                db.commit()
                # Пересчитываем дневные агрегаты для всего диапазона даже если данных нет (могли быть удалены)
                _recalculate_metrics_for_date_range(db, from_date, to_date, "sync_transactions (нет данных)")
                return {"created": 0, "updated": 0, "errors": 0, "deleted": deleted}
            
            parsed_data = self.parser.parse_transactions(transactions_data)
            
            if not parsed_data:
                logger.warning("Нет данных для синхронизации транзакций")
                db.commit()
                # Пересчитываем дневные агрегаты для всего диапазона даже если данных нет (могли быть удалены)
                _recalculate_metrics_for_date_range(db, from_date, to_date, "sync_transactions (нет данных)")
                return {"created": 0, "updated": 0, "errors": 0, "deleted": deleted}
            
            # Предзагружаем организации для маппинга по department_code.
            # При дублях кодов (legacy от старой iiko) предпочитаем «настоящую» —
            # ту, у которой заполнен iiko_id_cloud. См. детальный комментарий
            # в sync_sales выше.
            # TODO: добавить колонку Transaction.department_id, чтобы маппить
            # точно по uuid (как в sync_sales) — сейчас в модели её нет.
            all_orgs = db.query(Organization).all()
            _org_by_code_obj: Dict[str, Organization] = {}
            for o in all_orgs:
                if not o.code:
                    continue
                cur = _org_by_code_obj.get(o.code)
                if cur is None:
                    _org_by_code_obj[o.code] = o
                elif o.iiko_id_cloud and not cur.iiko_id_cloud:
                    _org_by_code_obj[o.code] = o
            org_by_code: Dict[str, int] = {k: v.id for k, v in _org_by_code_obj.items()}

            # Подготавливаем данные для bulk insert
            now = datetime.now()
            bulk_data = []
            for trans_data in parsed_data:
                try:
                    # Ищем организацию по Department.Code
                    department_code = trans_data.get("department_code")
                    organization_id = org_by_code.get(department_code) if department_code else None
                    
                    # Подготавливаем данные для bulk insert
                    bulk_item = dict(trans_data)
                    bulk_item["organization_id"] = organization_id
                    bulk_item.pop("created_at", None)
                    bulk_item["created_at"] = now
                    bulk_item["updated_at"] = now
                    bulk_data.append(bulk_item)
                except Exception as e:
                    logger.error(f"Ошибка подготовки транзакции order_id={trans_data.get('order_id', 'Unknown')}, order_num={trans_data.get('order_num', 'Unknown')}: {e}")
            
            # Bulk insert с batch commits (каждые 5000 записей)
            created = 0
            errors = 0
            batch_size = 5000
            
            for i in range(0, len(bulk_data), batch_size):
                batch = bulk_data[i:i + batch_size]
                try:
                    db.bulk_insert_mappings(Transaction, batch)
                    db.commit()
                    created += len(batch)
                    logger.debug(f"Вставлено {len(batch)} транзакций (всего {created}/{len(bulk_data)})")
                except Exception as e:
                    logger.error(f"Ошибка bulk insert транзакций (batch {i//batch_size + 1}): {e}")
                    db.rollback()
                    # Пробуем вставить по одной записи из батча для определения проблемных
                    for item in batch:
                        try:
                            db.bulk_insert_mappings(Transaction, [item])
                            db.commit()
                            created += 1
                        except Exception as item_error:
                            logger.error(f"Ошибка вставки транзакции order_id={item.get('order_id', 'Unknown')}, order_num={item.get('order_num', 'Unknown')}: {item_error}")
                            errors += 1
                            db.rollback()
            
            # Пересчитываем дневные агрегаты для всех дней, затронутых синхронизацией
            if not skip_metrics_recalculation:
                dates_to_recalculate = set()
                if bulk_data:
                    for trans_data in bulk_data:
                        date_typed = trans_data.get("date_typed")
                        if date_typed:
                            if isinstance(date_typed, datetime):
                                dates_to_recalculate.add(date_typed.date())
                            elif isinstance(date_typed, date):
                                dates_to_recalculate.add(date_typed)
                            elif isinstance(date_typed, str):
                                try:
                                    if 'T' in date_typed or '+' in date_typed or 'Z' in date_typed:
                                        date_obj = datetime.fromisoformat(date_typed.replace('Z', '+00:00')).date()
                                    else:
                                        date_obj = datetime.strptime(date_typed, '%Y-%m-%d').date()
                                    dates_to_recalculate.add(date_obj)
                                except (ValueError, AttributeError):
                                    pass
                else:
                    dates_to_recalculate.add(day_date.date())

                for recalc_date in dates_to_recalculate:
                    _recalculate_metrics_for_date(db, recalc_date, "sync_transactions")

            logger.info(f"Синхронизация транзакций завершена: создано {created}, удалено {deleted}, ошибок {errors}")
            return {"created": created, "updated": 0, "errors": errors, "deleted": deleted}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации транзакций: {e}")
            db.rollback()
            if not skip_metrics_recalculation:
                _recalculate_metrics_for_date_range(db, from_date, to_date, "sync_transactions (ошибка)")
            return {"created": 0, "updated": 0, "errors": 1, "deleted": 0}

    def _normalize_value_for_key(self, value: Any) -> Any:
        """Нормализует значение для использования в уникальном ключе"""
        if value is None:
            return None
        
        # Datetime преобразуем в ISO строку без микросекунд
        if isinstance(value, datetime):
            return value.replace(microsecond=0, tzinfo=None).isoformat()
        
        # Строку datetime тоже нормализуем
        if isinstance(value, str):
            # Пытаемся распарсить как datetime и нормализовать
            try:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return dt.replace(microsecond=0, tzinfo=None).isoformat()
            except:
                # Если не datetime, возвращаем как есть
                return value
        
        # Числовые значения
        if isinstance(value, (int, float)):
            if isinstance(value, int) or value == int(value):
                return int(value)
            return round(float(value), 2)
        
        # Decimal из SQLAlchemy
        from decimal import Decimal
        if isinstance(value, Decimal):
            float_val = float(value)
            if float_val == int(float_val):
                return int(float_val)
            return round(float_val, 2)
        
        # Все остальное возвращаем как есть
        return value
    
    def _create_sale_unique_key(self, sale_data: Dict[str, Any]) -> tuple:
        """
        Создает уникальный ключ для продажи из ВСЕХ значимых полей
        (кроме id, created_at, updated_at, is_active, commission)
        """
        # Список полей для ИСКЛЮЧЕНИЯ из ключа
        exclude_fields = {'id', 'created_at', 'updated_at', 'is_active', 'commission'}
        
        # Получаем все поля модели Sales
        all_fields = [column.name for column in Sales.__table__.columns if column.name not in exclude_fields]
        
        # Создаем tuple из нормализованных значений ВСЕХ полей
        key_values = []
        for field in sorted(all_fields):  # sorted для стабильного порядка
            value = sale_data.get(field)
            normalized_value = self._normalize_value_for_key(value)
            key_values.append(normalized_value)
        
        return tuple(key_values)

    async def sync_sales(self, db: Session, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None, skip_metrics_recalculation: bool = False) -> Dict[str, int]:
        """Синхронизация продаж с удалением записей за день (from_date) перед записью"""
        try:
            if not from_date or not to_date:
                logger.warning("Не указаны даты для синхронизации продаж")
                return {"created": 0, "updated": 0, "errors": 0, "deleted": 0}
            
            # Нормализуем дату (убираем время, оставляем только дату)
            day_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0).date()
            day_date_end = day_date + timedelta(days=1)
            
            logger.info(f"Синхронизация продаж за {day_date}")
            
            # Удаляем записи за этот день (по левой границе from_date)
            # Для Sales используем open_date_typed (Date поле)
            deleted = db.query(Sales).filter(
                Sales.open_date_typed >= day_date,
                Sales.open_date_typed < day_date_end
            ).delete(synchronize_session=False)
            
            if deleted > 0:
                logger.debug(f"Удалено {deleted} продаж за {day_date}")
            
            # Получаем данные продаж за день
            sales_data = await self.service.get_sales(from_date, to_date)
            
            if not sales_data:
                logger.warning("Не удалось получить данные продаж")
                db.commit()
                # Пересчитываем дневные агрегаты для всего диапазона даже если данных нет (могли быть удалены)
                _recalculate_metrics_for_date_range(db, from_date, to_date, "sync_sales (нет данных)")
                return {"created": 0, "updated": 0, "errors": 0, "deleted": deleted}
            
            parsed_data = self.parser.parse_sales(sales_data)
            
            if not parsed_data:
                logger.warning("Нет данных для синхронизации продаж")
                db.commit()
                # Пересчитываем дневные агрегаты для всего диапазона даже если данных нет (могли быть удалены)
                _recalculate_metrics_for_date_range(db, from_date, to_date, "sync_sales (нет данных)")
                return {"created": 0, "updated": 0, "errors": 0, "deleted": deleted}
            
            # Предзагружаем все организации одним запросом, строим два маппинга:
            #   1) org_by_iiko_id  — точный маппинг по uuid департамента (Department.Id),
            #      без дублей в принципе; используем как primary.
            #   2) org_by_code     — fallback по department_code. При дублях кодов
            #      (последствия миграции iiko: остались legacy-записи с такими же
            #      кодами, что и текущие организации) предпочитаем «настоящую»
            #      организацию — ту, у которой заполнен `iiko_id_cloud` (значит,
            #      она реально есть в Cloud API на сейчас).
            all_orgs = db.query(Organization).all()
            org_by_iiko_id: Dict[str, int] = {
                o.iiko_id: o.id for o in all_orgs if o.iiko_id
            }
            _org_by_code_obj: Dict[str, Organization] = {}
            for o in all_orgs:
                if not o.code:
                    continue
                cur = _org_by_code_obj.get(o.code)
                if cur is None:
                    _org_by_code_obj[o.code] = o
                elif o.iiko_id_cloud and not cur.iiko_id_cloud:
                    # Перезаписываем: новая организация «настоящая», старая — legacy
                    _org_by_code_obj[o.code] = o
            org_by_code: Dict[str, int] = {k: v.id for k, v in _org_by_code_obj.items()}

            # Подготавливаем данные для bulk insert
            now = datetime.now()
            bulk_data = []
            for sale_data in parsed_data:
                try:
                    # Ищем организацию: сначала по точному department_id, потом по code
                    organization_id = None
                    department_id = sale_data.get("department_id")
                    if department_id:
                        organization_id = org_by_iiko_id.get(department_id)
                    if organization_id is None:
                        department_code = sale_data.get("department_code")
                        if department_code:
                            organization_id = org_by_code.get(department_code)
                    
                    # Подготавливаем данные для bulk insert
                    bulk_item = dict(sale_data)
                    bulk_item["organization_id"] = organization_id
                    bulk_item.pop("created_at", None)
                    bulk_item["created_at"] = now
                    bulk_item["updated_at"] = now
                    bulk_data.append(bulk_item)
                except Exception as e:
                    logger.error(f"Ошибка подготовки продажи {sale_data.get('item_sale_event_id', 'Unknown')}: {e}")
            
            # Bulk insert с batch commits (каждые 1000 записей)
            created = 0
            errors = 0
            batch_size = 1000
            
            for i in range(0, len(bulk_data), batch_size):
                batch = bulk_data[i:i + batch_size]
                try:
                    db.bulk_insert_mappings(Sales, batch)
                    db.commit()
                    created += len(batch)
                    logger.debug(f"Вставлено {len(batch)} продаж (всего {created}/{len(bulk_data)})")
                except Exception as e:
                    logger.error(f"Ошибка bulk insert продаж (batch {i//batch_size + 1}): {e}")
                    db.rollback()
                    # Пробуем вставить по одной записи из батча для определения проблемных
                    for item in batch:
                        try:
                            db.bulk_insert_mappings(Sales, [item])
                            db.commit()
                            created += 1
                        except Exception as item_error:
                            logger.error(f"Ошибка вставки продажи item_sale_event_id={item.get('item_sale_event_id', 'Unknown')}: {item_error}")
                            errors += 1
                            db.rollback()
            
            # Пересчитываем дневные агрегаты для всех дней, затронутых синхронизацией
            if not skip_metrics_recalculation:
                dates_to_recalculate = set()
                if bulk_data:
                    for sale_data in bulk_data:
                        open_date_typed = sale_data.get("open_date_typed")
                        if open_date_typed:
                            if isinstance(open_date_typed, datetime):
                                dates_to_recalculate.add(open_date_typed.date())
                            elif isinstance(open_date_typed, date):
                                dates_to_recalculate.add(open_date_typed)
                            elif isinstance(open_date_typed, str):
                                try:
                                    if 'T' in open_date_typed or '+' in open_date_typed or 'Z' in open_date_typed:
                                        date_obj = datetime.fromisoformat(open_date_typed.replace('Z', '+00:00')).date()
                                    else:
                                        date_obj = datetime.strptime(open_date_typed, '%Y-%m-%d').date()
                                    dates_to_recalculate.add(date_obj)
                                except (ValueError, AttributeError):
                                    pass
                else:
                    dates_to_recalculate.add(day_date)

                for recalc_date in dates_to_recalculate:
                    _recalculate_metrics_for_date(db, recalc_date, "sync_sales")

            logger.info(f"Синхронизация продаж завершена: создано {created}, удалено {deleted}, ошибок {errors}")
            return {"created": created, "updated": 0, "errors": errors, "deleted": deleted}

        except Exception as e:
            logger.error(f"Ошибка синхронизации продаж: {e}")
            db.rollback()
            if not skip_metrics_recalculation:
                _recalculate_metrics_for_date_range(db, from_date, to_date, "sync_sales (ошибка)")
            return {"created": 0, "updated": 0, "errors": 1, "deleted": 0}

    async def sync_accounts(self, db: Session) -> Dict[str, int]:
        """Синхронизация счетов (accounts) из Server API"""
        try:
            accounts_data = await self.service.get_accounts()
            
            if not accounts_data:
                logger.warning("Не удалось получить данные счетов")
                return {"created": 0, "updated": 0, "errors": 0}
            
            parsed_data = self.parser.parse_accounts(accounts_data)
            
            created = 0
            updated = 0
            errors = 0
            
            for account_data in parsed_data:
                try:
                    existing_account = db.query(Account).filter(
                        Account.iiko_id == account_data["iiko_id"]
                    ).first()
                    
                    if existing_account:
                        # Обновляем существующий счет
                        for key, value in account_data.items():
                            if key not in ["created_at"]:
                                setattr(existing_account, key, value)
                        existing_account.updated_at = datetime.now()
                        updated += 1
                    else:
                        # Создаем новый счет
                        account_data["created_at"] = datetime.now()
                        account_data["updated_at"] = datetime.now()
                        new_account = Account(**account_data)
                        db.add(new_account)
                        created += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации счета {account_data.get('name')}: {e}")
                    errors += 1
            
            db.commit()
            logger.info(f"Синхронизация счетов завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации счетов: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}

    async def sync_salaries(self, db: Session) -> Dict[str, int]:
        """Синхронизация окладов сотрудников из Server API"""
        try:
            salaries_data = await self.service.get_salaries()
            
            if not salaries_data:
                logger.warning("Не удалось получить данные окладов")
                return {"created": 0, "updated": 0, "errors": 0}
            
            parsed_data = self.parser.parse_salaries(salaries_data)
            
            created = 0
            updated = 0
            errors = 0
            
            for salary_data in parsed_data:
                try:
                    # Находим сотрудника по iiko_id
                    employee_iiko_id = salary_data.get("employee_iiko_id")
                    employee = None
                    if employee_iiko_id:
                        employee = db.query(Employees).filter(
                            Employees.iiko_id == employee_iiko_id
                        ).first()
                    
                    if not employee:
                        logger.warning(f"Не найден сотрудник с iiko_id {employee_iiko_id} для оклада")
                        errors += 1
                        continue
                    
                    # Парсим даты
                    from datetime import datetime
                    date_from = datetime.fromisoformat(salary_data.get("date_from").replace('Z', '+00:00')) if salary_data.get("date_from") else None
                    date_to = datetime.fromisoformat(salary_data.get("date_to").replace('Z', '+00:00')) if salary_data.get("date_to") else None
                    salary_amount = float(salary_data.get("salary")) if salary_data.get("salary") else 0.0
                    
                    if not date_from or not date_to:
                        logger.warning(f"Некорректные даты для оклада сотрудника {employee.name}")
                        errors += 1
                        continue
                    
                    # Проверяем существует ли уже такая запись (по 4 полям)
                    existing_salary = db.query(UserSalary).filter(
                        UserSalary.employee_id == employee.id,
                        UserSalary.date_from == date_from,
                        UserSalary.date_to == date_to,
                        UserSalary.salary == salary_amount
                    ).first()
                    
                    if existing_salary:
                        # Запись уже существует, обновляем updated_at
                        existing_salary.updated_at = datetime.now()
                        updated += 1
                    else:
                        # Создаем новую запись
                        new_salary = UserSalary(
                            employee_id=employee.id,
                            salary=salary_amount,
                            date_from=date_from,
                            date_to=date_to,
                            created_at=datetime.now(),
                            updated_at=datetime.now()
                        )
                        db.add(new_salary)
                        created += 1
                        
                except Exception as e:
                    db.rollback()
                    logger.error(f"Ошибка синхронизации оклада для сотрудника {salary_data.get('employee_iiko_id')}: {e}")
                    errors += 1

            db.commit()
            logger.info(f"Синхронизация окладов завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации окладов: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}

    async def sync_shifts(
        self, 
        db: Session, 
        date_from: Optional[datetime] = None, 
        date_to: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Синхронизация смен сотрудников из iiko Server API
        
        Args:
            db: Сессия базы данных
            date_from: Дата начала периода (по умолчанию 30 дней назад)
            date_to: Дата конца периода (по умолчанию сегодня)
        
        Returns:
            Словарь с результатами синхронизации: {"created": int, "updated": int, "errors": int}
        """
        try:
            # Если даты не указаны, используем последние 30 дней
            if not date_from:
                date_from = datetime.now() - timedelta(days=30)
            if not date_to:
                date_to = datetime.now()
            
            date_from_str = date_from.strftime("%Y-%m-%d")
            date_to_str = date_to.strftime("%Y-%m-%d")
            
            logger.info(f"Синхронизация смен с {date_from_str} по {date_to_str}")
            
            # Получаем данные смен из iiko
            shifts_data = await self.service.get_server_shifts(
                date_from=date_from_str,
                date_to=date_to_str
            )
            
            if not shifts_data:
                logger.warning("Не удалось получить данные смен")
                return {"created": 0, "updated": 0, "errors": 0}
            
            # Парсим данные
            parsed_data = self.parser.parse_shifts(shifts_data)
            
            created = 0
            updated = 0
            errors = 0
            
            for shift_data in parsed_data:
                try:
                    iiko_id = shift_data.get("iiko_id")
                    if not iiko_id:
                        logger.warning("Смена без iiko_id, пропускаем")
                        errors += 1
                        continue
                    
                    # Находим сотрудника по iiko_id
                    employee_iiko_id = shift_data.get("employee_iiko_id")
                    employee = None
                    if employee_iiko_id:
                        employee = db.query(Employees).filter(
                            Employees.iiko_id == employee_iiko_id
                        ).first()
                    
                    if not employee:
                        logger.warning(f"Не найден сотрудник с iiko_id {employee_iiko_id} для смены {iiko_id}")
                        errors += 1
                        continue
                    
                    # Находим тип посещаемости
                    attendance_type_iiko_id = shift_data.get("attendance_type_iiko_id")
                    attendance_type = None
                    if attendance_type_iiko_id:
                        attendance_type = db.query(AttendanceType).filter(
                            AttendanceType.iiko_id == attendance_type_iiko_id
                        ).first()
                    
                    # Находим пользователя (если указан)
                    user_iiko_id = shift_data.get("user_iiko_id")
                    user = None
                    if user_iiko_id:
                        user = db.query(User).filter(User.iiko_id == user_iiko_id).first()
                    
                    # Проверяем существующую смену
                    existing_shift = db.query(Shift).filter(
                        Shift.iiko_id == iiko_id
                    ).first()
                    
                    if existing_shift:
                        # Обновляем существующую смену
                        existing_shift.start_time = shift_data.get("start_time")
                        existing_shift.end_time = shift_data.get("end_time")
                        existing_shift.employee_id = employee.id
                        if attendance_type:
                            existing_shift.attendance_type_id = attendance_type.id
                        if user:
                            existing_shift.user_id = user.id
                        existing_shift.updated_at = datetime.now()
                        updated += 1
                    else:
                        # Создаем новую смену
                        new_shift = Shift(
                            iiko_id=iiko_id,
                            start_time=shift_data.get("start_time"),
                            end_time=shift_data.get("end_time"),
                            employee_id=employee.id,
                            attendance_type_id=attendance_type.id if attendance_type else None,
                            user_id=user.id if user else None,
                            created_at=datetime.now(),
                            updated_at=datetime.now()
                        )
                        db.add(new_shift)
                        created += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации смены {shift_data.get('iiko_id')}: {e}")
                    errors += 1
            
            db.commit()
            logger.info(f"Синхронизация смен завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации смен: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}
        
    async def sync_by_modification_date(self, db: Session, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Синхронизация по дате изменения транзакций.
        Получает транзакции, измененные за период, извлекает даты транзакций и запускает полную синхронизацию по этим датам + за сегодня.
        """
        try:
            if not from_date or not to_date:
                logger.warning("Не указаны даты для синхронизации по дате изменения")
                return {
                    "transactions": {"created": 0, "updated": 0, "errors": 0, "deleted": 0},
                    "sales": {"created": 0, "updated": 0, "errors": 0, "deleted": 0},
                    "dates_synced": []
                }
            
            logger.info(f"Запуск синхронизации по дате изменения с {from_date.strftime('%Y-%m-%d')} по {to_date.strftime('%Y-%m-%d')}")
            
            # Получаем транзакции, измененные за период
            modified_transactions_data = await self.service.get_transactions_by_modification_date(from_date, to_date)
            
            if not modified_transactions_data:
                logger.warning("Не удалось получить транзакции, измененные за период")
                # Все равно запускаем синхронизацию за сегодня
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                tomorrow = today + timedelta(days=1)
                
                transactions_result = await self.sync_transactions(db, today, tomorrow)
                sales_result = await self.sync_sales(db, today, tomorrow)
                
                return {
                    "transactions": transactions_result,
                    "sales": sales_result,
                    "dates_synced": [today.date()]
                }
            
            # Парсим транзакции для извлечения дат
            parsed_transactions = self.parser.parse_transactions(modified_transactions_data)
            
            # Извлекаем уникальные даты создания транзакций (DateTime.DateTyped -> date_typed)
            # Это даты, за которые нужно синхронизировать транзакции
            unique_transaction_dates = set()
            for transaction in parsed_transactions:
                date_typed = transaction.get("date_typed")
                if date_typed:
                    # Если это строка, преобразуем в date
                    if isinstance(date_typed, str):
                        try:
                            # Пробуем разные форматы
                            if 'T' in date_typed or '+' in date_typed or 'Z' in date_typed:
                                # ISO формат с временем
                                date_obj = datetime.fromisoformat(date_typed.replace('Z', '+00:00')).date()
                            else:
                                # Просто дата YYYY-MM-DD
                                date_obj = datetime.strptime(date_typed, '%Y-%m-%d').date()
                            unique_transaction_dates.add(date_obj)
                        except (ValueError, AttributeError) as e:
                            logger.warning(f"Не удалось распарсить дату транзакции: {date_typed}, ошибка: {e}")
                    elif isinstance(date_typed, (datetime, date)):
                        if isinstance(date_typed, datetime):
                            unique_transaction_dates.add(date_typed.date())
                        else:
                            unique_transaction_dates.add(date_typed)
            
            logger.info(f"Найдено {len(unique_transaction_dates)} уникальных дат создания транзакций для синхронизации")
            
            # Также собираем даты изменения (период запроса) - для них тоже нужно пересчитать метрики
            modification_dates = set()
            mod_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0).date()
            mod_end_date = to_date.replace(hour=0, minute=0, second=0, microsecond=0).date()
            while mod_date <= mod_end_date:
                modification_dates.add(mod_date)
                mod_date += timedelta(days=1)
            
            logger.info(f"Период изменения: {len(modification_dates)} дней (с {from_date.strftime('%Y-%m-%d')} по {to_date.strftime('%Y-%m-%d')})")
            
            # Объединяем все даты, которые нужно синхронизировать
            unique_dates = unique_transaction_dates | modification_dates
            
            # Добавляем сегодняшнюю дату
            today = datetime.now().date()
            unique_dates.add(today)
            
            # Сортируем даты для последовательной обработки
            sorted_dates = sorted(unique_dates)
            
            # Результаты синхронизации
            total_transactions_result = {"created": 0, "updated": 0, "errors": 0, "deleted": 0}
            total_sales_result = {"created": 0, "updated": 0, "errors": 0, "deleted": 0}
            synced_dates = []
            
            # Синхронизируем транзакции по каждой дате
            for transaction_date in sorted_dates:
                day_from = datetime.combine(transaction_date, datetime.min.time())
                day_to = datetime.combine(transaction_date + timedelta(days=1), datetime.min.time())
                
                logger.info(f"Синхронизация транзакций за {transaction_date.strftime('%Y-%m-%d')}...")
                transactions_result = await self.sync_transactions(db, day_from, day_to, skip_metrics_recalculation=True)
                total_transactions_result["created"] += transactions_result.get("created", 0)
                total_transactions_result["updated"] += transactions_result.get("updated", 0)
                total_transactions_result["errors"] += transactions_result.get("errors", 0)
                total_transactions_result["deleted"] += transactions_result.get("deleted", 0)
                synced_dates.append(transaction_date)
            
            # Синхронизируем продажи за все даты, за которые синхронизировались транзакции
            for sales_date in sorted_dates:
                day_from = datetime.combine(sales_date, datetime.min.time())
                day_to = datetime.combine(sales_date + timedelta(days=1), datetime.min.time())
                
                logger.info(f"Синхронизация продаж за {sales_date.strftime('%Y-%m-%d')}...")
                sales_result = await self.sync_sales(db, day_from, day_to, skip_metrics_recalculation=True)
                total_sales_result["created"] += sales_result.get("created", 0)
                total_sales_result["updated"] += sales_result.get("updated", 0)
                total_sales_result["errors"] += sales_result.get("errors", 0)
                total_sales_result["deleted"] += sales_result.get("deleted", 0)
            
            # Пересчитываем дневные метрики для всех затронутых дней:
            # 1. Дни создания транзакций (уже пересчитаны в sync_transactions, но пересчитаем еще раз для надежности)
            # 2. Дни изменения (период запроса) - важно пересчитать, так как там могли быть изменения
            all_dates_to_recalculate = unique_transaction_dates | modification_dates
            all_dates_to_recalculate.add(today)
            
            logger.info(f"Пересчет дневных метрик для {len(all_dates_to_recalculate)} дней (дни создания транзакций + дни изменения)")
            for recalc_date in sorted(all_dates_to_recalculate):
                _recalculate_metrics_for_date(db, recalc_date, "sync_by_modification_date")
            
            logger.info(
                f"Синхронизация по дате изменения завершена: "
                f"транзакций - создано {total_transactions_result['created']}, "
                f"удалено {total_transactions_result['deleted']}, "
                f"ошибок {total_transactions_result['errors']}; "
                f"продаж - создано {total_sales_result['created']}, "
                f"удалено {total_sales_result['deleted']}, "
                f"ошибок {total_sales_result['errors']}"
            )
            
            return {
                "transactions": total_transactions_result,
                "sales": total_sales_result,
                "dates_synced": [d.strftime('%Y-%m-%d') for d in synced_dates]
            }
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации по дате изменения: {e}")
            return {
                "transactions": {"created": 0, "updated": 0, "errors": 1, "deleted": 0},
                "sales": {"created": 0, "updated": 0, "errors": 1, "deleted": 0},
                "dates_synced": [],
                "error": str(e)
            }

    async def sync_warehouse_documents_from_transactions(
        self,
        db: Session,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        organization_id: Optional[int] = None,
    ) -> Dict[str, int]:
        """
        Синхронизация складских документов из транзакций iiko.
        
        Логика:
        1. Получить транзакции за период через get_transactions()
        2. Фильтровать транзакции, где document IS NOT NULL
        3. Группировать по document (номер документа)
        4. Для каждой группы определить тип (RECEIPT/WRITEOFF)
        5. Создать WarehouseDocument и WarehouseDocumentItem
        
        Args:
            db: сессия БД
            from_date: начало периода
            to_date: конец периода
            organization_id: ID организации для фильтрации (опционально)
        
        Returns:
            Словарь с результатами: {"created": int, "updated": int, "errors": int}
        """
        try:
            if not from_date or not to_date:
                logger.warning("Не указаны даты для синхронизации складских документов")
                return {"created": 0, "updated": 0, "errors": 0}
            
            logger.info(f"Синхронизация складских документов с {from_date.strftime('%Y-%m-%d')} по {to_date.strftime('%Y-%m-%d')}")
            
            # Получаем транзакции за период
            transactions_data = await self.service.get_transactions(from_date, to_date)
            
            if not transactions_data:
                logger.warning("Не удалось получить транзакции для синхронизации складских документов")
                return {"created": 0, "updated": 0, "errors": 0}
            
            # Парсим транзакции
            parsed_transactions = self.parser.parse_transactions(transactions_data)
            
            # Фильтруем транзакции с полем document (складские документы)
            warehouse_transactions = [
                t for t in parsed_transactions
                if t.get("document") and t.get("document").strip()
            ]
            
            if not warehouse_transactions:
                logger.info("Не найдено транзакций со складскими документами")
                return {"created": 0, "updated": 0, "errors": 0}
            
            logger.info(f"Найдено {len(warehouse_transactions)} транзакций со складскими документами")
            
            # Предзагружаем организации для оптимизации
            department_codes = set(t.get("department_code") for t in warehouse_transactions if t.get("department_code"))
            organizations_map = {}
            if department_codes:
                orgs = db.query(Organization).filter(Organization.code.in_(department_codes)).all()
                organizations_map = {org.code: org.id for org in orgs}
            
            # Группируем транзакции по номеру документа
            documents_dict = {}  # {document_number: [transactions]}
            
            for trans in warehouse_transactions:
                doc_number = trans.get("document", "").strip()
                if not doc_number:
                    continue
                
                # Фильтрация по организации, если указана
                if organization_id:
                    dept_code = trans.get("department_code")
                    trans_org_id = organizations_map.get(dept_code) if dept_code else None
                    if trans_org_id != organization_id:
                        continue
                
                if doc_number not in documents_dict:
                    documents_dict[doc_number] = []
                documents_dict[doc_number].append(trans)
            
            created = 0
            updated = 0
            errors = 0
            
            # Обрабатываем каждый документ
            for doc_number, transactions in documents_dict.items():
                try:
                    # Определяем тип документа по первой транзакции
                    first_trans = transactions[0]
                    
                    # Определяем тип: RECEIPT если amount_in > 0, WRITEOFF если amount_out > 0
                    amount_in = float(first_trans.get("amount_in") or 0)
                    amount_out = float(first_trans.get("amount_out") or 0)
                    
                    if amount_in > 0 and amount_out == 0:
                        doc_type = "RECEIPT"
                    elif amount_out > 0 and amount_in == 0:
                        doc_type = "WRITEOFF"
                    else:
                        # Если оба > 0, используем приоритет по сумме
                        if amount_in >= amount_out:
                            doc_type = "RECEIPT"
                        else:
                            doc_type = "WRITEOFF"
                    
                    # Получаем дату документа
                    date_typed = first_trans.get("date_typed") or first_trans.get("date_time_typed")
                    if isinstance(date_typed, str):
                        try:
                            if 'T' in date_typed or '+' in date_typed or 'Z' in date_typed:
                                doc_date = datetime.fromisoformat(date_typed.replace('Z', '+00:00'))
                            else:
                                doc_date = datetime.strptime(date_typed, '%Y-%m-%d')
                        except (ValueError, AttributeError):
                            doc_date = datetime.now()
                    elif isinstance(date_typed, (datetime, date)):
                        if isinstance(date_typed, date):
                            doc_date = datetime.combine(date_typed, datetime.min.time())
                        else:
                            doc_date = date_typed
                    else:
                        doc_date = datetime.now()
                    
                    # Получаем организацию
                    dept_code = first_trans.get("department_code")
                    doc_org_id = organizations_map.get(dept_code) if dept_code else None
                    if organization_id and doc_org_id != organization_id:
                        continue
                    
                    # Получаем склад
                    store_id = first_trans.get("store")
                    
                    # Проверяем, существует ли уже документ с таким номером
                    existing_doc = db.query(WarehouseDocument).filter(
                        WarehouseDocument.document_number == doc_number
                    ).first()
                    
                    if existing_doc:
                        # Обновляем существующий документ
                        existing_doc.document_type = doc_type
                        existing_doc.date = doc_date
                        existing_doc.organization_id = doc_org_id
                        existing_doc.store_id = store_id
                        existing_doc.updated_at = datetime.now()
                        
                        # Удаляем старые позиции
                        db.query(WarehouseDocumentItem).filter(
                            WarehouseDocumentItem.document_id == existing_doc.id
                        ).delete()
                        
                        doc_id = existing_doc.id
                        updated += 1
                    else:
                        # Создаем новый документ
                        new_doc = WarehouseDocument(
                            document_type=doc_type,
                            document_number=doc_number,
                            date=doc_date,
                            organization_id=doc_org_id,
                            store_id=store_id,
                        )
                        db.add(new_doc)
                        db.flush()
                        doc_id = new_doc.id
                        created += 1
                    
                    # Создаем позиции документа
                    for trans in transactions:
                        product_id = trans.get("product_id")
                        product_name = trans.get("product_name")
                        product_iiko_id = trans.get("product_id")  # Используем product_id как iiko_id
                        
                        # Количество и сумма
                        if doc_type == "RECEIPT":
                            quantity = float(trans.get("amount_in") or 0)
                            amount = float(trans.get("sum_incoming") or 0)
                        else:
                            quantity = float(trans.get("amount_out") or 0)
                            amount = float(trans.get("sum_outgoing") or 0)
                        
                        if quantity == 0:
                            continue
                        
                        # Цена за единицу
                        price = amount / quantity if quantity > 0 else 0
                        
                        # Ищем товар в нашей БД по iiko_id
                        item_id = None
                        if product_iiko_id:
                            item = db.query(Item).filter(Item.iiko_id == product_iiko_id).first()
                            if item:
                                item_id = item.id
                        
                        # Создаем позицию документа
                        doc_item = WarehouseDocumentItem(
                            document_id=doc_id,
                            item_id=item_id,
                            item_iiko_id=product_iiko_id,
                            item_name=product_name,
                            quantity=quantity,
                            price=price,
                            amount=amount,
                        )
                        db.add(doc_item)
                    
                    db.commit()
                    logger.debug(f"Обработан складской документ {doc_number}, тип={doc_type}, позиций={len(transactions)}")
                    
                except Exception as e:
                    db.rollback()
                    errors += 1
                    logger.error(f"Ошибка обработки складского документа {doc_number}: {e}")
            
            logger.info(f"Синхронизация складских документов завершена: создано={created}, обновлено={updated}, ошибок={errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Критическая ошибка синхронизации складских документов: {e}")
            return {"created": 0, "updated": 0, "errors": 1}

    async def sync_writeoff_documents(
        self,
        db: Session,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        status: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Синхронизация актов списания из iiko API
        
        Args:
            db: сессия БД
            from_date: начало периода
            to_date: конец периода
            status: статус документа (опционально)
        
        Returns:
            Словарь с результатами: {"created": int, "updated": int, "errors": int}
        """
        try:
            if not from_date or not to_date:
                logger.warning("Не указаны даты для синхронизации актов списания")
                return {"created": 0, "updated": 0, "errors": 0}
            
            date_from_str = from_date.strftime("%Y-%m-%d")
            date_to_str = to_date.strftime("%Y-%m-%d")
            
            logger.info(f"Синхронизация актов списания с {date_from_str} по {date_to_str}")
            
            # Получаем данные актов списания
            data = await self.service.get_writeoff_documents(date_from_str, date_to_str, status)
            
            if not data:
                logger.warning("Не удалось получить данные актов списания")
                return {"created": 0, "updated": 0, "errors": 0}
            
            # Парсим данные
            parsed_documents = self.parser.parse_writeoff_documents(data)
            
            if not parsed_documents:
                logger.info("Нет актов списания для синхронизации")
                return {"created": 0, "updated": 0, "errors": 0}
            
            created = 0
            updated = 0
            errors = 0
            
            # Предзагружаем счета для оптимизации
            account_ids = set(doc.get("account_id") for doc in parsed_documents if doc.get("account_id"))
            accounts_map = {}
            if account_ids:
                accounts = db.query(Account).filter(Account.iiko_id.in_(account_ids)).all()
                accounts_map = {acc.iiko_id: acc.id for acc in accounts}
            
            # Обрабатываем каждый документ
            for doc_data in parsed_documents:
                try:
                    iiko_id = doc_data.get("iiko_id")
                    if not iiko_id:
                        logger.warning("Акт списания без iiko_id, пропускаем")
                        errors += 1
                        continue
                    
                    # Парсим дату
                    date_incoming_str = doc_data.get("date_incoming")
                    if date_incoming_str:
                        try:
                            if 'T' in date_incoming_str:
                                date_incoming = datetime.fromisoformat(date_incoming_str.replace('Z', '+00:00'))
                            else:
                                date_incoming = datetime.strptime(date_incoming_str, '%Y-%m-%d')
                        except (ValueError, AttributeError):
                            date_incoming = datetime.now()
                    else:
                        date_incoming = datetime.now()
                    
                    # Связываем счет
                    account_iiko_id = doc_data.get("account_id")
                    account_id = accounts_map.get(account_iiko_id) if account_iiko_id else None
                    
                    # Проверяем существующий документ
                    existing_doc = db.query(WarehouseDocument).filter(
                        WarehouseDocument.iiko_id == iiko_id
                    ).first()
                    
                    if existing_doc:
                        # Обновляем существующий документ
                        existing_doc.document_type = "WRITEOFF"
                        existing_doc.document_source = "WRITEOFF"
                        existing_doc.document_number = doc_data.get("document_number")
                        existing_doc.date = date_incoming
                        existing_doc.date_incoming = date_incoming
                        existing_doc.status = doc_data.get("status")
                        existing_doc.store_id = doc_data.get("store_id")
                        existing_doc.account_id = account_iiko_id
                        existing_doc.updated_at = datetime.now()
                        
                        # Удаляем старые позиции
                        db.query(WarehouseDocumentItem).filter(
                            WarehouseDocumentItem.document_id == existing_doc.id
                        ).delete()
                        
                        doc_id = existing_doc.id
                        updated += 1
                    else:
                        # Создаем новый документ
                        new_doc = WarehouseDocument(
                            iiko_id=iiko_id,
                            document_type="WRITEOFF",
                            document_source="WRITEOFF",
                            document_number=doc_data.get("document_number"),
                            date=date_incoming,
                            date_incoming=date_incoming,
                            status=doc_data.get("status"),
                            store_id=doc_data.get("store_id"),
                            account_id=account_iiko_id,
                        )
                        db.add(new_doc)
                        db.flush()
                        doc_id = new_doc.id
                        created += 1
                    
                    # Создаем позиции документа
                    total_cost = 0.0
                    for item_data in doc_data.get("items", []):
                        product_id = item_data.get("product_id")
                        
                        # Ищем товар в нашей БД
                        item_id = None
                        if product_id:
                            item = db.query(Item).filter(Item.iiko_id == product_id).first()
                            if item:
                                item_id = item.id
                        
                        # Количество и стоимость
                        amount = float(item_data.get("amount") or 0)
                        cost = float(item_data.get("cost") or 0)
                        total_cost += cost
                        
                        if amount == 0:
                            continue
                        
                        # Создаем позицию
                        doc_item = WarehouseDocumentItem(
                            document_id=doc_id,
                            item_id=item_id,
                            item_iiko_id=product_id,
                            product_id=product_id,
                            num=item_data.get("num"),
                            product_size_id=item_data.get("product_size_id"),
                            amount_factor=item_data.get("amount_factor"),
                            amount=amount,
                            quantity=amount,  # Для обратной совместимости
                            measure_unit_id=item_data.get("measure_unit_id"),
                            container_id=item_data.get("container_id"),
                            cost=cost,
                            price=cost / amount if amount > 0 else 0,
                            amount_total=cost,
                        )
                        db.add(doc_item)
                    
                    # Создаем или обновляем Expense для акта списания
                    if total_cost > 0:
                        existing_expense = db.query(Expense).filter(
                            Expense.warehouse_document_id == doc_id
                        ).first()
                        
                        if existing_expense:
                            existing_expense.amount = total_cost
                            existing_expense.date = date_incoming
                            existing_expense.account_id = account_iiko_id
                            existing_expense.updated_at = datetime.now()
                        else:
                            new_expense = Expense(
                                expense_type="WRITEOFF",
                                amount=total_cost,
                                date=date_incoming,
                                account_id=account_iiko_id,
                                warehouse_document_id=doc_id,
                                comment=f"Акт списания {doc_data.get('document_number')}",
                            )
                            db.add(new_expense)
                    
                    db.commit()
                    logger.debug(f"Обработан акт списания {iiko_id}, позиций={len(doc_data.get('items', []))}")
                    
                except Exception as e:
                    db.rollback()
                    errors += 1
                    logger.error(f"Ошибка обработки акта списания {doc_data.get('iiko_id')}: {e}")
            
            logger.info(f"Синхронизация актов списания завершена: создано={created}, обновлено={updated}, ошибок={errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Критическая ошибка синхронизации актов списания: {e}")
            return {"created": 0, "updated": 0, "errors": 1}

    async def sync_incoming_invoices(
        self,
        db: Session,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Синхронизация приходных накладных из iiko API
        
        Args:
            db: сессия БД
            from_date: начало периода
            to_date: конец периода
        
        Returns:
            Словарь с результатами: {"created": int, "updated": int, "errors": int}
        """
        try:
            if not from_date or not to_date:
                logger.warning("Не указаны даты для синхронизации приходных накладных")
                return {"created": 0, "updated": 0, "errors": 0}
            
            date_from_str = from_date.strftime("%Y-%m-%d")
            date_to_str = to_date.strftime("%Y-%m-%d")
            
            logger.info(f"Синхронизация приходных накладных с {date_from_str} по {date_to_str}")
            
            # Получаем данные приходных накладных (XML)
            xml_data = await self.service.get_incoming_invoices(date_from_str, date_to_str)
            
            if not xml_data:
                logger.warning("Не удалось получить данные приходных накладных")
                return {"created": 0, "updated": 0, "errors": 0}
            
            # Парсим данные (уже распарсены из XML в сервисе)
            parsed_invoices = self.parser.parse_incoming_invoices(xml_data)
            
            if not parsed_invoices:
                logger.info("Нет приходных накладных для синхронизации")
                return {"created": 0, "updated": 0, "errors": 0}
            
            created = 0
            updated = 0
            errors = 0
            
            # Предзагружаем организации для оптимизации
            # Собираем все возможные organization_id (iiko_id) из данных
            org_iiko_ids = set()
            for invoice_data in parsed_invoices:
                org_iiko_id = invoice_data.get("organization_id")
                if org_iiko_id:
                    org_iiko_ids.add(org_iiko_id)
                # Также проверяем conception, так как она может быть связана с организацией
                conception = invoice_data.get("conception")
                if conception:
                    org_iiko_ids.add(conception)
            
            organizations_map = {}
            if org_iiko_ids:
                organizations = db.query(Organization).filter(Organization.iiko_id.in_(org_iiko_ids)).all()
                organizations_map = {org.iiko_id: org.id for org in organizations}
            
            # Обрабатываем каждую накладную
            for invoice_data in parsed_invoices:
                try:
                    iiko_id = invoice_data.get("iiko_id")
                    if not iiko_id:
                        logger.warning("Приходная накладная без iiko_id, пропускаем")
                        errors += 1
                        continue
                    
                    # Ищем организацию по organization_id (iiko_id) или по conception
                    organization_id = None
                    org_iiko_id = invoice_data.get("organization_id")
                    if org_iiko_id:
                        organization_id = organizations_map.get(org_iiko_id)
                    # Если organization_id не найден, пробуем найти по conception
                    if not organization_id:
                        conception = invoice_data.get("conception")
                        if conception:
                            organization_id = organizations_map.get(conception)
                    
                    # Парсим дату
                    date_incoming_str = invoice_data.get("date_incoming")
                    if date_incoming_str:
                        try:
                            if 'T' in date_incoming_str:
                                date_incoming = datetime.fromisoformat(date_incoming_str.replace('Z', '+00:00'))
                            else:
                                date_incoming = datetime.strptime(date_incoming_str, '%Y-%m-%d')
                        except (ValueError, AttributeError):
                            date_incoming = datetime.now()
                    else:
                        date_incoming = datetime.now()
                    
                    # Парсим другие даты
                    due_date = None
                    if invoice_data.get("due_date"):
                        try:
                            due_date_str = invoice_data.get("due_date")
                            if 'T' in due_date_str:
                                due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
                            else:
                                due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
                        except (ValueError, AttributeError):
                            pass
                    
                    incoming_date = None
                    if invoice_data.get("incoming_date"):
                        try:
                            incoming_date_str = invoice_data.get("incoming_date")
                            if 'T' in incoming_date_str:
                                incoming_date = datetime.fromisoformat(incoming_date_str.replace('Z', '+00:00'))
                            else:
                                incoming_date = datetime.strptime(incoming_date_str, '%Y-%m-%d')
                        except (ValueError, AttributeError):
                            pass
                    
                    # Проверяем существующий документ
                    existing_doc = db.query(WarehouseDocument).filter(
                        WarehouseDocument.iiko_id == iiko_id
                    ).first()
                    
                    if existing_doc:
                        # Обновляем существующий документ
                        existing_doc.document_type = "RECEIPT"
                        existing_doc.document_source = "INCOMING_INVOICE"
                        existing_doc.document_number = invoice_data.get("document_number")
                        existing_doc.date = date_incoming
                        existing_doc.date_incoming = date_incoming
                        existing_doc.status = invoice_data.get("status")
                        existing_doc.store_id = invoice_data.get("default_store")
                        existing_doc.default_store = invoice_data.get("default_store")
                        existing_doc.conception = invoice_data.get("conception")
                        existing_doc.conception_code = invoice_data.get("conception_code")
                        existing_doc.invoice = invoice_data.get("invoice")
                        existing_doc.supplier = invoice_data.get("supplier")
                        existing_doc.due_date = due_date
                        existing_doc.incoming_date = incoming_date
                        existing_doc.use_default_document_time = invoice_data.get("use_default_document_time", False)
                        existing_doc.incoming_document_number = invoice_data.get("incoming_document_number")
                        existing_doc.employee_pass_to_account = invoice_data.get("employee_pass_to_account")
                        existing_doc.transport_invoice_number = invoice_data.get("transport_invoice_number")
                        existing_doc.linked_outgoing_invoice_id = invoice_data.get("linked_outgoing_invoice_id")
                        existing_doc.distribution_algorithm = invoice_data.get("distribution_algorithm")
                        existing_doc.comment = invoice_data.get("comment")
                        if organization_id:
                            existing_doc.organization_id = organization_id
                        existing_doc.updated_at = datetime.now()
                        
                        # Удаляем старые позиции
                        db.query(WarehouseDocumentItem).filter(
                            WarehouseDocumentItem.document_id == existing_doc.id
                        ).delete()
                        
                        doc_id = existing_doc.id
                        updated += 1
                    else:
                        # Создаем новый документ
                        new_doc = WarehouseDocument(
                            iiko_id=iiko_id,
                            document_type="RECEIPT",
                            document_source="INCOMING_INVOICE",
                            document_number=invoice_data.get("document_number"),
                            date=date_incoming,
                            date_incoming=date_incoming,
                            status=invoice_data.get("status"),
                            store_id=invoice_data.get("default_store"),
                            default_store=invoice_data.get("default_store"),
                            conception=invoice_data.get("conception"),
                            conception_code=invoice_data.get("conception_code"),
                            invoice=invoice_data.get("invoice"),
                            supplier=invoice_data.get("supplier"),
                            due_date=due_date,
                            incoming_date=incoming_date,
                            use_default_document_time=invoice_data.get("use_default_document_time", False),
                            incoming_document_number=invoice_data.get("incoming_document_number"),
                            employee_pass_to_account=invoice_data.get("employee_pass_to_account"),
                            transport_invoice_number=invoice_data.get("transport_invoice_number"),
                            linked_outgoing_invoice_id=invoice_data.get("linked_outgoing_invoice_id"),
                            distribution_algorithm=invoice_data.get("distribution_algorithm"),
                            comment=invoice_data.get("comment"),
                            organization_id=organization_id,
                        )
                        db.add(new_doc)
                        db.flush()
                        doc_id = new_doc.id
                        created += 1
                    
                    # Создаем позиции документа
                    total_sum = 0.0
                    for item_data in invoice_data.get("items", []):
                        product_id = item_data.get("product")
                        product_article = item_data.get("product_article")
                        
                        # Ищем товар в нашей БД
                        item_id = None
                        item_iiko_id = product_id
                        if product_id:
                            item = db.query(Item).filter(Item.iiko_id == product_id).first()
                            if item:
                                item_id = item.id
                                item_iiko_id = item.iiko_id
                        
                        # Количество и сумма
                        amount = float(item_data.get("amount") or 0)
                        sum_value = float(item_data.get("sum") or 0)
                        price = float(item_data.get("price") or 0)
                        total_sum += sum_value
                        
                        if amount == 0:
                            continue
                        
                        # Парсим дополнительные поля
                        vat_percent = None
                        if item_data.get("vat_percent"):
                            try:
                                vat_percent = float(item_data.get("vat_percent"))
                            except (ValueError, TypeError):
                                pass
                        
                        vat_sum = None
                        if item_data.get("vat_sum"):
                            try:
                                vat_sum = float(item_data.get("vat_sum"))
                            except (ValueError, TypeError):
                                pass
                        
                        discount_sum = None
                        if item_data.get("discount_sum"):
                            try:
                                discount_sum = float(item_data.get("discount_sum"))
                            except (ValueError, TypeError):
                                pass
                        
                        price_without_vat = None
                        if item_data.get("price_without_vat"):
                            try:
                                price_without_vat = float(item_data.get("price_without_vat"))
                            except (ValueError, TypeError):
                                pass
                        
                        # Создаем позицию
                        doc_item = WarehouseDocumentItem(
                            document_id=doc_id,
                            item_id=item_id,
                            item_iiko_id=item_iiko_id,
                            product_id=product_id,
                            product_article=product_article,
                            num=item_data.get("num"),
                            is_additional_expense=item_data.get("is_additional_expense", False),
                            amount=amount,
                            quantity=amount,  # Для обратной совместимости
                            supplier_product=item_data.get("supplier_product"),
                            supplier_product_article=item_data.get("supplier_product_article"),
                            producer=item_data.get("producer"),
                            container_id=item_data.get("container_id"),
                            amount_unit=item_data.get("amount_unit"),
                            actual_unit_weight=item_data.get("actual_unit_weight"),
                            sum=sum_value,
                            discount_sum=discount_sum,
                            vat_percent=vat_percent,
                            vat_sum=vat_sum,
                            price_unit=item_data.get("price_unit"),
                            price=price,
                            price_without_vat=price_without_vat,
                            code=item_data.get("code"),
                            store=item_data.get("store"),
                            customs_declaration_number=item_data.get("customs_declaration_number"),
                            actual_amount=item_data.get("actual_amount"),
                            amount_total=sum_value,
                        )
                        db.add(doc_item)
                    
                    # Создаем или обновляем Income для приходной накладной
                    if total_sum > 0:
                        existing_income = db.query(Income).filter(
                            Income.warehouse_document_id == doc_id
                        ).first()
                        
                        if existing_income:
                            existing_income.amount = total_sum
                            existing_income.date = date_incoming
                            existing_income.updated_at = datetime.now()
                        else:
                            new_income = Income(
                                income_type="INCOMING_INVOICE",
                                amount=total_sum,
                                date=date_incoming,
                                warehouse_document_id=doc_id,
                                comment=f"Приходная накладная {invoice_data.get('document_number')}",
                            )
                            db.add(new_income)
                    
                    db.commit()
                    logger.debug(f"Обработана приходная накладная {iiko_id}, позиций={len(invoice_data.get('items', []))}")
                    
                except Exception as e:
                    db.rollback()
                    errors += 1
                    logger.error(f"Ошибка обработки приходной накладной {invoice_data.get('iiko_id')}: {e}")
            
            logger.info(f"Синхронизация приходных накладных завершена: создано={created}, обновлено={updated}, ошибок={errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Критическая ошибка синхронизации приходных накладных: {e}")
            return {"created": 0, "updated": 0, "errors": 1}

    async def sync_outgoing_invoices(
        self,
        db: Session,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Синхронизация расходных накладных из iiko API
        
        Args:
            db: сессия БД
            from_date: начало периода
            to_date: конец периода
        
        Returns:
            Словарь с результатами: {"created": int, "updated": int, "errors": int}
        """
        try:
            if not from_date or not to_date:
                logger.warning("Не указаны даты для синхронизации расходных накладных")
                return {"created": 0, "updated": 0, "errors": 0}
            
            date_from_str = from_date.strftime("%Y-%m-%d")
            date_to_str = to_date.strftime("%Y-%m-%d")
            
            logger.info(f"Синхронизация расходных накладных с {date_from_str} по {date_to_str}")
            
            # Получаем данные расходных накладных (XML)
            xml_data = await self.service.get_outgoing_invoices(date_from_str, date_to_str)
            
            if not xml_data:
                logger.warning("Не удалось получить данные расходных накладных")
                return {"created": 0, "updated": 0, "errors": 0}
            
            # Парсим данные (уже распарсены из XML в сервисе)
            parsed_invoices = self.parser.parse_outgoing_invoices(xml_data)
            
            if not parsed_invoices:
                logger.info("Нет расходных накладных для синхронизации")
                return {"created": 0, "updated": 0, "errors": 0}
            
            created = 0
            updated = 0
            errors = 0
            
            # Обрабатываем каждую накладную
            for invoice_data in parsed_invoices:
                try:
                    iiko_id = invoice_data.get("iiko_id")
                    if not iiko_id:
                        logger.warning("Расходная накладная без iiko_id, пропускаем")
                        errors += 1
                        continue
                    
                    # Парсим дату
                    date_incoming_str = invoice_data.get("date_incoming")
                    if date_incoming_str:
                        try:
                            if 'T' in date_incoming_str:
                                date_incoming = datetime.fromisoformat(date_incoming_str.replace('Z', '+00:00'))
                            else:
                                date_incoming = datetime.strptime(date_incoming_str, '%Y-%m-%d')
                        except (ValueError, AttributeError):
                            date_incoming = datetime.now()
                    else:
                        date_incoming = datetime.now()
                    
                    # Проверяем существующий документ
                    existing_doc = db.query(WarehouseDocument).filter(
                        WarehouseDocument.iiko_id == iiko_id
                    ).first()
                    
                    if existing_doc:
                        # Обновляем существующий документ
                        existing_doc.document_type = "WRITEOFF"
                        existing_doc.document_source = "OUTGOING_INVOICE"
                        existing_doc.document_number = invoice_data.get("document_number")
                        existing_doc.date = date_incoming
                        existing_doc.date_incoming = date_incoming
                        existing_doc.status = invoice_data.get("status")
                        existing_doc.use_default_document_time = invoice_data.get("use_default_document_time", False)
                        existing_doc.account_to_code = invoice_data.get("account_to_code")
                        existing_doc.revenue_account_code = invoice_data.get("revenue_account_code")
                        existing_doc.default_store_id = invoice_data.get("default_store_id")
                        existing_doc.default_store_code = invoice_data.get("default_store_code")
                        existing_doc.counteragent_id = invoice_data.get("counteragent_id")
                        existing_doc.counteragent_code = invoice_data.get("counteragent_code")
                        existing_doc.conception_id = invoice_data.get("conception_id")
                        existing_doc.conception_code = invoice_data.get("conception_code")
                        existing_doc.comment = invoice_data.get("comment")
                        existing_doc.linked_outgoing_invoice_id = invoice_data.get("linked_outgoing_invoice_id")
                        existing_doc.updated_at = datetime.now()
                        
                        # Удаляем старые позиции
                        db.query(WarehouseDocumentItem).filter(
                            WarehouseDocumentItem.document_id == existing_doc.id
                        ).delete()
                        
                        doc_id = existing_doc.id
                        updated += 1
                    else:
                        # Создаем новый документ
                        new_doc = WarehouseDocument(
                            iiko_id=iiko_id,
                            document_type="WRITEOFF",
                            document_source="OUTGOING_INVOICE",
                            document_number=invoice_data.get("document_number"),
                            date=date_incoming,
                            date_incoming=date_incoming,
                            status=invoice_data.get("status"),
                            use_default_document_time=invoice_data.get("use_default_document_time", False),
                            account_to_code=invoice_data.get("account_to_code"),
                            revenue_account_code=invoice_data.get("revenue_account_code"),
                            default_store_id=invoice_data.get("default_store_id"),
                            default_store_code=invoice_data.get("default_store_code"),
                            counteragent_id=invoice_data.get("counteragent_id"),
                            counteragent_code=invoice_data.get("counteragent_code"),
                            conception_id=invoice_data.get("conception_id"),
                            conception_code=invoice_data.get("conception_code"),
                            comment=invoice_data.get("comment"),
                            linked_outgoing_invoice_id=invoice_data.get("linked_outgoing_invoice_id"),
                        )
                        db.add(new_doc)
                        db.flush()
                        doc_id = new_doc.id
                        created += 1
                    
                    # Создаем позиции документа
                    total_sum = 0.0
                    for item_data in invoice_data.get("items", []):
                        product_id = item_data.get("product_id")
                        product_article = item_data.get("product_article")
                        
                        # Ищем товар в нашей БД
                        item_id = None
                        item_iiko_id = product_id
                        if product_id:
                            item = db.query(Item).filter(Item.iiko_id == product_id).first()
                            if item:
                                item_id = item.id
                                item_iiko_id = item.iiko_id
                        
                        # Количество и сумма
                        amount = float(item_data.get("amount") or 0)
                        sum_value = float(item_data.get("sum") or 0)
                        price = float(item_data.get("price") or 0)
                        total_sum += sum_value
                        
                        if amount == 0:
                            continue
                        
                        # Парсим дополнительные поля
                        vat_percent = None
                        if item_data.get("vat_percent"):
                            try:
                                vat_percent = float(item_data.get("vat_percent"))
                            except (ValueError, TypeError):
                                pass
                        
                        vat_sum = None
                        if item_data.get("vat_sum"):
                            try:
                                vat_sum = float(item_data.get("vat_sum"))
                            except (ValueError, TypeError):
                                pass
                        
                        discount_sum = None
                        if item_data.get("discount_sum"):
                            try:
                                discount_sum = float(item_data.get("discount_sum"))
                            except (ValueError, TypeError):
                                pass
                        
                        price_without_vat = None
                        if item_data.get("price_without_vat"):
                            try:
                                price_without_vat = float(item_data.get("price_without_vat"))
                            except (ValueError, TypeError):
                                pass
                        
                        # Создаем позицию
                        doc_item = WarehouseDocumentItem(
                            document_id=doc_id,
                            item_id=item_id,
                            item_iiko_id=item_iiko_id,
                            product_id=product_id,
                            product_article=product_article,
                            store_id=item_data.get("store_id"),
                            store_code=item_data.get("store_code"),
                            container_id=item_data.get("container_id"),
                            container_code=item_data.get("container_code"),
                            price=price,
                            price_without_vat=price_without_vat,
                            amount=amount,
                            quantity=amount,  # Для обратной совместимости
                            sum=sum_value,
                            discount_sum=discount_sum,
                            vat_percent=vat_percent,
                            vat_sum=vat_sum,
                            amount_total=sum_value,
                        )
                        db.add(doc_item)
                    
                    # Создаем или обновляем Expense для расходной накладной
                    if total_sum > 0:
                        existing_expense = db.query(Expense).filter(
                            Expense.warehouse_document_id == doc_id
                        ).first()
                        
                        if existing_expense:
                            existing_expense.amount = total_sum
                            existing_expense.date = date_incoming
                            existing_expense.account_id = invoice_data.get("account_to_code")
                            existing_expense.updated_at = datetime.now()
                        else:
                            new_expense = Expense(
                                expense_type="OUTGOING_INVOICE",
                                amount=total_sum,
                                date=date_incoming,
                                account_id=invoice_data.get("account_to_code"),
                                warehouse_document_id=doc_id,
                                comment=f"Расходная накладная {invoice_data.get('document_number')}",
                            )
                            db.add(new_expense)
                    
                    db.commit()
                    logger.debug(f"Обработана расходная накладная {iiko_id}, позиций={len(invoice_data.get('items', []))}")
                    
                except Exception as e:
                    db.rollback()
                    errors += 1
                    logger.error(f"Ошибка обработки расходной накладной {invoice_data.get('iiko_id')}: {e}")
            
            logger.info(f"Синхронизация расходных накладных завершена: создано={created}, обновлено={updated}, ошибок={errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Критическая ошибка синхронизации расходных накладных: {e}")
            return {"created": 0, "updated": 0, "errors": 1}

    async def sync_all_documents(
        self,
        db: Session,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Синхронизация всех типов документов
        
        Args:
            db: сессия БД
            from_date: начало периода
            to_date: конец периода
            status: статус для актов списания (опционально)
        
        Returns:
            Словарь с результатами синхронизации всех типов документов
        """
        try:
            logger.info(f"Запуск синхронизации всех документов с {from_date.strftime('%Y-%m-%d') if from_date else 'N/A'} по {to_date.strftime('%Y-%m-%d') if to_date else 'N/A'}")
            
            results = {}
            
            # Синхронизация актов списания
            results["writeoff_documents"] = await self.sync_writeoff_documents(db, from_date, to_date, status)
            
            # Синхронизация приходных накладных
            results["incoming_invoices"] = await self.sync_incoming_invoices(db, from_date, to_date)
            
            # Синхронизация расходных накладных
            results["outgoing_invoices"] = await self.sync_outgoing_invoices(db, from_date, to_date)
            
            # Подсчет общих результатов
            total_created = (
                results["writeoff_documents"].get("created", 0) +
                results["incoming_invoices"].get("created", 0) +
                results["outgoing_invoices"].get("created", 0)
            )
            total_updated = (
                results["writeoff_documents"].get("updated", 0) +
                results["incoming_invoices"].get("updated", 0) +
                results["outgoing_invoices"].get("updated", 0)
            )
            total_errors = (
                results["writeoff_documents"].get("errors", 0) +
                results["incoming_invoices"].get("errors", 0) +
                results["outgoing_invoices"].get("errors", 0)
            )
            
            results["total_created"] = total_created
            results["total_updated"] = total_updated
            results["total_errors"] = total_errors
            
            logger.info(f"Синхронизация всех документов завершена: создано={total_created}, обновлено={total_updated}, ошибок={total_errors}")
            return results
            
        except Exception as e:
            logger.error(f"Критическая ошибка синхронизации всех документов: {e}")
            return {
                "writeoff_documents": {"created": 0, "updated": 0, "errors": 1},
                "incoming_invoices": {"created": 0, "updated": 0, "errors": 1},
                "outgoing_invoices": {"created": 0, "updated": 0, "errors": 1},
                "total_created": 0,
                "total_updated": 0,
                "total_errors": 1
            }


# Глобальный экземпляр синхронизатора
iiko_sync = IikoSync()
