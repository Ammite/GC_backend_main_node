"""
Парсер данных из iiko API
Содержит функции для обработки и нормализации данных, полученных от iiko API
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

def _parse_boolean(value):
    """Парсинг boolean значений из различных форматов"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return False


class IikoParser:
    """Класс для парсинга данных из iiko API"""
    
    @staticmethod
    def parse_organizations(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг организаций"""
        if not data:
            return []
        
        parsed_orgs = []
        for org in data:
            parsed_org = {
                "iiko_id": org.get("id"),
                "name": org.get("name"),
                "code": org.get("code", ""),
                "is_active": True,  # По умолчанию активна
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            parsed_orgs.append(parsed_org)
        
        logger.info(f"Парсинг организаций: {len(parsed_orgs)} записей")
        return parsed_orgs

    @staticmethod
    def parse_menu_nomenclature(data: Dict[Any, Any]) -> Dict[str, List[Dict[Any, Any]]]:
        """Парсинг номенклатуры меню (Cloud API)"""
        if not data:
            return {"categories": [], "items": [], "modifiers": []}
        
        categories = []
        items = []
        modifiers = []
        
        # Парсинг групп (категорий) - используем productCategories
        groups = data.get("productCategories", [])
        for group in groups:
            category = {
                "iiko_id": group.get("id"),
                "name": group.get("name"),
                "parent_id": group.get("parentId")  # Нужно будет получить из других категорий
            }
            categories.append(category)
        
        # Парсинг продуктов (блюд)
        products = data.get("products", [])
        for product in products:
            item = {
                "iiko_id": product.get("id"),
                "name": product.get("name"),
                "description": product.get("description", ""),
                "category_id": product.get("groupId"),
                "price": product.get("price", 0),
                "is_active": not product.get("isDeleted", False),
                "sort_order": product.get("sortOrder", 0),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            items.append(item)
        
        # Парсинг модификаторов
        product_modifiers = data.get("productModifiers", [])
        for modifier in product_modifiers:
            modifier_data = {
                "iiko_id": modifier.get("id"),
                "name": modifier.get("name"),
                "description": modifier.get("description", ""),
                "price": modifier.get("price", 0),
                "is_active": not modifier.get("isDeleted", False),
                "sort_order": modifier.get("sortOrder", 0),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            modifiers.append(modifier_data)
        
        logger.info(f"Парсинг меню: {len(categories)} категорий, {len(items)} блюд, {len(modifiers)} модификаторов")
        return {
            "categories": categories,
            "items": items,
            "modifiers": modifiers
        }

    @staticmethod
    def parse_products(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг продуктов (Server API)"""
        if not data:
            return []
        
        parsed_products = []
        for product in data:
            parsed_product = {
                "iiko_id": product.get("id"),
                "name": product.get("name"),
                "description": product.get("description", ""),
                "price": product.get("price", 0),
                "is_active": not product.get("isDeleted", False),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            parsed_products.append(parsed_product)
        
        logger.info(f"Парсинг продуктов: {len(parsed_products)} записей")
        return parsed_products

    @staticmethod
    def parse_product_groups(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг групп продуктов (Server API)"""
        if not data:
            return []
        
        parsed_groups = []
        for group in data:
            parsed_group = {
                "iiko_id": group.get("id"),
                "name": group.get("name"),
                "description": group.get("description", ""),
                "is_active": not group.get("isDeleted", False),
                "sort_order": group.get("sortOrder", 0),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            parsed_groups.append(parsed_group)
        
        logger.info(f"Парсинг групп продуктов: {len(parsed_groups)} записей")
        return parsed_groups

    @staticmethod
    def parse_product_categories(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг категорий продуктов (Server API)"""
        if not data:
            return []
        
        parsed_categories = []
        for category in data:
            parsed_category = {
                "iiko_id": category.get("id"),
                "name": category.get("name"),
                "parent_id": category.get("parentId")  # Нужно будет получить из других категорий
            }
            parsed_categories.append(parsed_category)
        
        logger.info(f"Парсинг категорий продуктов: {len(parsed_categories)} записей")
        return parsed_categories

    @staticmethod
    def parse_employees(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг сотрудников (Server API XML)"""
        if not data:
            return []
        
        parsed_employees = []
        for employee in data:
            # Server API предоставляет данные в XML формате
            parsed_employee = {
                "iiko_id": employee.get("id"),
                "code": employee.get("code", ""),
                "name": employee.get("name", ""),
                "login": employee.get("login", ""),
                "password": employee.get("password", ""),
                
                # Имена
                "first_name": employee.get("firstName", ""),
                "middle_name": employee.get("middleName", ""),
                "last_name": employee.get("lastName", ""),
                
                # Контакты
                "phone": employee.get("phone", ""),
                "cell_phone": employee.get("cellPhone", ""),
                "email": employee.get("email", ""),
                "address": employee.get("address", ""),
                
                # Даты
                "birthday": employee.get("birthday") if employee.get("birthday") else None,
                "hire_date": employee.get("hireDate", ""),
                "hire_document_number": employee.get("hireDocumentNumber", ""),
                "fire_date": employee.get("fireDate") if employee.get("fireDate") else None,
                "activation_date": employee.get("activationDate") if employee.get("activationDate") else None,
                "deactivation_date": employee.get("deactivationDate") if employee.get("deactivationDate") else None,
                
                # Дополнительная информация
                "note": employee.get("note", ""),
                "card_number": employee.get("cardNumber", ""),
                "pin_code": employee.get("pinCode", ""),
                "taxpayer_id_number": employee.get("taxpayerIdNumber", ""),
                "snils": employee.get("snils", ""),
                "gln": employee.get("gln", ""),
                
                # Роли и должности
                "main_role_iiko_id": employee.get("mainRoleId"),
                "roles_iiko_ids": employee.get("rolesIds", []),
                "main_role_code": employee.get("mainRoleCode", ""),
                "role_codes": employee.get("roleCodes", []),
                
                # Подразделения
                "preferred_department_code": employee.get("preferredDepartmentCode", ""),
                "department_codes": employee.get("departmentCodes", []),
                "responsibility_department_codes": employee.get("responsibilityDepartmentCodes", []),
                
                # Статусы
                "deleted": _parse_boolean(employee.get("deleted", "false")),
                "client": _parse_boolean(employee.get("client", "false")),
                "supplier": _parse_boolean(employee.get("supplier", "false")),
                "employee": _parse_boolean(employee.get("employee", "false")),
                "represents_store": _parse_boolean(employee.get("representsStore", "false"))
            }
            parsed_employees.append(parsed_employee)
        
        logger.info(f"Парсинг сотрудников: {len(parsed_employees)} записей")
        return parsed_employees

    @staticmethod
    def parse_departments(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг отделов"""
        if not data:
            return []
        
        parsed_departments = []
        for department in data:
            parsed_department = {
                "iiko_id": department.get("id"),
                "name": department.get("name"),
                "description": department.get("description", ""),
                "is_active": not department.get("isDeleted", False),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            parsed_departments.append(parsed_department)
        
        logger.info(f"Парсинг отделов: {len(parsed_departments)} записей")
        return parsed_departments

    @staticmethod
    def parse_roles(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг ролей (Server API)"""
        if not data:
            return []
        
        parsed_roles = []
        for role in data:
            # Если код отсутствует, генерируем его на основе имени
            code = role.get("code")
            if not code:
                name = role.get("name", "")
                # Берем первые 3-5 символов имени и делаем их заглавными
                code = name[:5].upper().replace(" ", "") if name else "ROLE"
            
            parsed_role = {
                "iiko_id": role.get("id"),
                "code": code,
                "name": role.get("name"),
                "payment_per_hour": role.get("paymentPerHour", 0.0),
                "steady_salary": role.get("steadySalary", 0.0),
                "schedule_type": role.get("scheduleType"),
                "deleted": role.get("deleted", False)
            }
            parsed_roles.append(parsed_role)
        
        logger.info(f"Парсинг ролей: {len(parsed_roles)} записей")
        return parsed_roles

    @staticmethod
    def parse_schedule_types(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг типов расписания"""
        if not data:
            return []
        
        parsed_schedules = []
        for schedule in data:
            parsed_schedule = {
                "iiko_id": schedule.get("id"),
                "name": schedule.get("name"),
                "description": schedule.get("description", ""),
                "is_active": not schedule.get("isDeleted", False),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            parsed_schedules.append(parsed_schedule)
        
        logger.info(f"Парсинг типов расписания: {len(parsed_schedules)} записей")
        return parsed_schedules

    @staticmethod
    def parse_attendance_types(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг типов посещаемости"""
        if not data:
            return []
        
        parsed_attendance = []
        for attendance in data:
            parsed_attendance_item = {
                "iiko_id": attendance.get("id"),
                "name": attendance.get("name"),
                "description": attendance.get("description", ""),
                "is_active": not attendance.get("isDeleted", False),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            parsed_attendance.append(parsed_attendance_item)
        
        logger.info(f"Парсинг типов посещаемости: {len(parsed_attendance)} записей")
        return parsed_attendance

    @staticmethod
    def parse_tables(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг столов ресторана"""
        if not data:
            return []
        
        parsed_tables = []
        for table in data:
            parsed_table = {
                "iiko_id": table.get("id"),
                "section_id": table.get("sectionId"),  # Нужно будет получить из restaurant_sections
                "number": table.get("number", 0),
                "name": table.get("name", ""),
                "revision": table.get("revision", ""),
                "is_deleted": table.get("isDeleted", False),
                "pos_id": table.get("posId", "")
            }
            parsed_tables.append(parsed_table)
        
        logger.info(f"Парсинг столов: {len(parsed_tables)} записей")
        return parsed_tables

    @staticmethod
    def parse_terminals(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг терминалов"""
        if not data:
            return []
        
        parsed_terminals = []
        for terminal in data:
            parsed_terminal = {
                "iiko_id": terminal.get("id"),
                "organization_id": terminal.get("organizationId"),
                "name": terminal.get("name"),
                "address": terminal.get("address", ""),
                "time_zone": terminal.get("timeZone", ""),
                "is_active": True,  # По умолчанию активен
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            parsed_terminals.append(parsed_terminal)
        
        logger.info(f"Парсинг терминалов: {len(parsed_terminals)} записей")
        return parsed_terminals

    @staticmethod
    def parse_orders(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг заказов"""
        if not data:
            return []
        
        parsed_orders = []
        for order in data:
            parsed_order = {
                "iiko_id": order.get("id"),
                "order_number": order.get("orderNumber"),
                "table_id": order.get("tableId"),
                "terminal_id": order.get("terminalId"),
                "waiter_id": order.get("waiterId"),
                "status": order.get("status"),
                "total_amount": order.get("totalAmount", 0),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            parsed_orders.append(parsed_order)
        
        logger.info(f"Парсинг заказов: {len(parsed_orders)} записей")
        return parsed_orders

    @staticmethod
    def parse_reports(data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Парсинг отчетов"""
        if not data:
            return {}
        
        parsed_report = {
            "report_type": data.get("reportType"),
            "data": data.get("data", []),
            "total_rows": data.get("totalRows", 0),
            "created_at": datetime.now()
        }
        
        logger.info(f"Парсинг отчета: {parsed_report['total_rows']} строк")
        return parsed_report


# Глобальный экземпляр парсера
iiko_parser = IikoParser()
