"""
Синхронизация данных с iiko API
Содержит функции для синхронизации данных из iiko API с локальной базой данных
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .iiko_service import iiko_service
from .iiko_parser import iiko_parser
from database.database import get_db
from models import (
    Organization, Category, Item, Modifier, ItemModifier, Employees, 
    Roles, Shift, Table, Terminal, ProductGroup, MenuCategory,
    AttendanceType, RestaurantSection, TerminalGroup, Transaction, Sales, Account, UserSalary
)

logger = logging.getLogger(__name__)


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
                    # Проверяем существование организации
                    existing_org = db.query(Organization).filter(
                        Organization.iiko_id == org_data["iiko_id"]
                    ).first()
                    
                    if existing_org:
                        # Обновляем существующую
                        for key, value in org_data.items():
                            if key not in ["created_at"]:
                                setattr(existing_org, key, value)
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
                    existing_emp = db.query(Employees).filter(
                        Employees.iiko_id == emp_data["iiko_id"]
                    ).first()
                    
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

    async def sync_tables(self, db: Session, organization_id: Optional[str] = None) -> Dict[str, int]:
        """Синхронизация столов"""
        try:
            # Сначала синхронизируем секции, чтобы они существовали
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
                    
                    existing_table = db.query(Table).filter(
                        Table.iiko_id == table_data["iiko_id"]
                    ).first()
                    
                    if existing_table:
                        # Обновляем существующий стол
                        for key, value in table_data.items():
                            if key not in ["created_at"]:
                                setattr(existing_table, key, value)
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

    async def sync_transactions(self, db: Session, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None) -> Dict[str, int]:
        """Синхронизация транзакций"""  
        try:
            transactions_data = await self.service.get_transactions(from_date, to_date)
            
            if not transactions_data:
                logger.warning("Не удалось получить данные транзакций")
                return {"created": 0, "updated": 0, "errors": 0}
            
            parsed_data = self.parser.parse_transactions(transactions_data)
            
            if not parsed_data:
                logger.warning("Нет данных для синхронизации транзакций")
                return {"created": 0, "updated": 0, "errors": 0}
            
            created = 0
            updated = 0
            errors = 0
            didnt_find_unique_key = 0
            
            for trans_data in parsed_data:
                try:
                    # Ищем существующую транзакцию по составному ключу
                    existing_trans = self._find_existing_transaction(db, trans_data)
                    
                    if not existing_trans:
                        # logger.warning(f"Не удалось найти уникальный ключ для транзакции: order_id={trans_data.get('order_id')}, order_num={trans_data.get('order_num')}, product_id={trans_data.get('product_id')}, date_time={trans_data.get('date_time')}, amount={trans_data.get('amount')}")
                        didnt_find_unique_key += 1
                    else:
                        logger.debug(f"Найдена существующая транзакция для обновления")
                    
                    # Ищем организацию по Department.Code
                    department_code = trans_data.get("department_code")
                    organization_id = None
                    if department_code:
                        organization = db.query(Organization).filter(
                            Organization.code == department_code
                        ).first()
                        if organization:
                            organization_id = organization.id
                    
                    # Добавляем organization_id в данные
                    trans_data["organization_id"] = organization_id
                    
                    # Убираем поля, которые не должны обновляться
                    trans_data.pop("created_at", None)
                    
                    if existing_trans:
                        for key, value in trans_data.items():
                            setattr(existing_trans, key, value)
                        existing_trans.updated_at = datetime.now()
                        updated += 1
                    else:
                        trans_data["created_at"] = datetime.now()
                        trans_data["updated_at"] = datetime.now()
                        new_trans = Transaction(**trans_data)
                        db.add(new_trans)
                        created += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации транзакции order_id={trans_data.get('order_id', 'Unknown')}, order_num={trans_data.get('order_num', 'Unknown')}: {e}")
                    db.rollback()  # Откатываем транзакцию при ошибке
                    errors += 1
            
            db.commit()
            logger.info(f"Синхронизация транзакций завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors, "didnt_find_unique_key": didnt_find_unique_key}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации транзакций: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}

    async def sync_sales(self, db: Session, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None) -> Dict[str, int]:
        """Синхронизация продаж"""  
        try:
            sales_data = await self.service.get_sales(from_date, to_date)
            
            if not sales_data:
                logger.warning("Не удалось получить данные продаж")
                return {"created": 0, "updated": 0, "errors": 0}
            
            parsed_data = self.parser.parse_sales(sales_data)
            
            if not parsed_data:
                logger.warning("Нет данных для синхронизации продаж")
                return {"created": 0, "updated": 0, "errors": 0}
            
            created = 0
            updated = 0
            errors = 0
            
            for sale_data in parsed_data:
                try:
                    # Ищем организацию по Department.Code
                    department_code = sale_data.get("department_code")
                    organization_id = None
                    if department_code:
                        organization = db.query(Organization).filter(
                            Organization.code == department_code
                        ).first()
                        if organization:
                            organization_id = organization.id
                    
                    # Добавляем organization_id в данные
                    sale_data["organization_id"] = organization_id
                    
                    # Всегда создаем новую запись продажи
                    sale_data["created_at"] = datetime.now()
                    sale_data["updated_at"] = datetime.now()
                    new_sale = Sales(**sale_data)
                    db.add(new_sale)
                    created += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации продажи {sale_data.get('item_sale_event_id', 'Unknown')}: {e}")
                    db.rollback()  # Откатываем транзакцию при ошибке
                    errors += 1
            
            db.commit()
            logger.info(f"Синхронизация продаж завершена: создано {created}, ошибок {errors}")
            return {"created": created, "updated": 0, "errors": errors}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации продаж: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}

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
                    logger.error(f"Ошибка синхронизации оклада для сотрудника {salary_data.get('employee_iiko_id')}: {e}")
                    errors += 1
            
            db.commit()
            logger.info(f"Синхронизация окладов завершена: создано {created}, обновлено {updated}, ошибок {errors}")
            return {"created": created, "updated": updated, "errors": errors}
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации окладов: {e}")
            db.rollback()
            return {"created": 0, "updated": 0, "errors": 1}
        


# Глобальный экземпляр синхронизатора
iiko_sync = IikoSync()
