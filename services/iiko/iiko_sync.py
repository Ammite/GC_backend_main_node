"""
Синхронизация данных с iiko API
Содержит функции для синхронизации данных из iiko API с локальной базой данных
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .iiko_service import iiko_service
from .iiko_parser import iiko_parser
from database.database import get_db
from models import (
    Organization, Category, Item, Modifier, Employees, 
    Roles, Shift, Table, Terminal, ProductGroup,
    AttendanceType, RestaurantSection, TerminalGroup
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
        """Синхронизация меню"""
        try:
            # Получаем данные меню
            menu_data = await self.service.get_menu(organization_id)
            
            if not menu_data:
                logger.warning("Не удалось получить данные меню")
                return {"categories": 0, "items": 0, "modifiers": 0, "errors": 0}
            
            # Парсим данные
            parsed_data = self.parser.parse_menu_nomenclature(menu_data)
            
            categories_result = await self._sync_categories(db, parsed_data["categories"])
            items_result = await self._sync_items(db, parsed_data["items"])
            modifiers_result = await self._sync_modifiers(db, parsed_data["modifiers"])
            
            total_created = categories_result["created"] + items_result["created"] + modifiers_result["created"]
            total_updated = categories_result["updated"] + items_result["updated"] + modifiers_result["updated"]
            total_errors = categories_result["errors"] + items_result["errors"] + modifiers_result["errors"]
            
            logger.info(f"Синхронизация меню завершена: создано {total_created}, обновлено {total_updated}, ошибок {total_errors}")
            return {
                "categories": categories_result,
                "items": items_result,
                "modifiers": modifiers_result,
                "total_created": total_created,
                "total_updated": total_updated,
                "total_errors": total_errors
            }
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации меню: {e}")
            db.rollback()
            return {"categories": 0, "items": 0, "modifiers": 0, "errors": 1}
    
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
                    
                    if existing_emp:
                        for key, value in emp_data.items():
                            if key not in ["created_at"]:
                                setattr(existing_emp, key, value)
                        existing_emp.updated_at = datetime.now()
                        updated += 1
                    else:
                        new_emp = Employees(**emp_data)
                        db.add(new_emp)
                        created += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка синхронизации сотрудника {emp_data.get('name')}: {e}")
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
                            if key not in ["created_at"]:
                                setattr(existing_role, key, value)
                        existing_role.updated_at = datetime.now()
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
    
    async def sync_tables(self, db: Session, organization_id: Optional[str] = None) -> Dict[str, int]:
        """Синхронизация столов"""
        try:
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
                    existing_table = db.query(Table).filter(
                        Table.iiko_id == table_data["iiko_id"]
                    ).first()
                    
                    if existing_table:
                        for key, value in table_data.items():
                            if key not in ["created_at"]:
                                setattr(existing_table, key, value)
                        existing_table.updated_at = datetime.now()
                        updated += 1
                    else:
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
            
            # Синхронизируем столы
            results["tables"] = await self.sync_tables(db, organization_id)
            
            # Синхронизируем терминалы
            results["terminals"] = await self.sync_terminals(db, organization_id)
            
            logger.info("Полная синхронизация данных завершена успешно")
            return results
            
        except Exception as e:
            logger.error(f"Ошибка полной синхронизации: {e}")
            return {"error": str(e)}


# Глобальный экземпляр синхронизатора
iiko_sync = IikoSync()
