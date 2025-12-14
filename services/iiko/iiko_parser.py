"""
Парсер данных из iiko API
Содержит функции для обработки и нормализации данных, полученных от iiko API
"""

import json
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


def _safe_get(data: Dict[Any, Any], key: str, default: Any = None) -> Any:
    """Безопасное получение значения с обработкой пустых объектов"""
    value = data.get(key, default)
    if value == {}:  # Если значение - пустой словарь, возвращаем None
        return None
    return value


def _extract_numeric_value(value: Any) -> Optional[float]:
    """Извлечение числового значения из различных типов данных"""
    if isinstance(value, dict):
        # Если это словарь, ищем числовые значения
        for key in ['sum', 'value', 'amount', 'price', 'average']:
            if key in value and isinstance(value[key], (int, float)):
                return float(value[key])
        # Если не нашли числовое значение, возвращаем None
        return None
    elif isinstance(value, (int, float)):
        # Если это число, возвращаем как есть
        return float(value)
    elif isinstance(value, str):
        # Если это строка, пытаемся преобразовать в число
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    else:
        return None


def _extract_currency_sum(value: Any) -> Optional[float]:
    """Извлечение суммы из валютного объекта"""
    return _extract_numeric_value(value)


def _extract_fiscal_cheque_number(value: Any) -> Optional[str]:
    """
    Приводит FiscalChequeNumber к строке.
    Поддерживает числа, строки и коллекции чисел/строк (соединяются через запятую).
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # убираем .0 у целых
        return str(int(value)) if float(value).is_integer() else str(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        # Список значений -> строка через запятую
        cleaned = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, (int, float)):
                cleaned.append(str(int(item)) if float(item).is_integer() else str(item))
            else:
                cleaned.append(str(item).strip())
        return ", ".join(cleaned) if cleaned else None
    # Другие типы – пробуем строковое представление
    return str(value).strip()


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
    def parse_items_cloud(data: List[Dict[Any, Any]], organization_id: int) -> List[Dict[Any, Any]]:
        """Парсинг товаров из Cloud API"""
        if not data:
            return []
        
        parsed_items = []
        for item in data:
            # Получаем цену из sizePrices
            price = 0
            if item.get("sizePrices") and len(item["sizePrices"]) > 0:
                price_data = item["sizePrices"][0].get("price", {})
                price = price_data.get("currentPrice", 0)
            
            parsed_item = {
                "iiko_id": item.get("id"),
                "name": item.get("name"),
                "description": item.get("description", ""),
                "code": item.get("code"),
                "price": price,
                "deleted": item.get("isDeleted", False),
                "organization_id": organization_id,
                "data_source": "cloud",
                "is_duplicate": False,
                
                # Cloud API поля
                "fat_amount": item.get("fatAmount"),
                "proteins_amount": item.get("proteinsAmount"),
                "carbohydrates_amount": item.get("carbohydratesAmount"),
                "energy_amount": item.get("energyAmount"),
                "fat_full_amount": item.get("fatFullAmount"),
                "proteins_full_amount": item.get("proteinsFullAmount"),
                "carbohydrates_full_amount": item.get("carbohydratesFullAmount"),
                "energy_full_amount": item.get("energyFullAmount"),
                "weight": item.get("weight"),
                "group_id": item.get("groupId"),
                "product_category_id": item.get("productCategoryId"),
                "type": item.get("type"),
                "order_item_type": item.get("orderItemType"),
                "modifier_schema_id": item.get("modifierSchemaId"),
                "modifier_schema_name": item.get("modifierSchemaName"),
                "splittable": item.get("splittable", False),
                "measure_unit": item.get("measureUnit"),
                "parent_group": item.get("parentGroup"),
                "order_position": item.get("order"),
                "full_name_english": item.get("fullNameEnglish"),
                "use_balance_for_sell": item.get("useBalanceForSell", False),
                "can_set_open_price": item.get("canSetOpenPrice", False),
                "payment_subject": item.get("paymentSubject"),
                "additional_info": item.get("additionalInfo"),
                "is_deleted_cloud": item.get("isDeleted", False),
                "seo_description": item.get("seoDescription"),
                "seo_text": item.get("seoText"),
                "seo_keywords": item.get("seoKeywords"),
                "seo_title": item.get("seoTitle"),
                
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            parsed_items.append(parsed_item)
        
        logger.info(f"Парсинг товаров Cloud API: {len(parsed_items)} записей")
        return parsed_items

    @staticmethod
    def parse_items_server(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг товаров из Server API"""
        if not data:
            return []
        
        parsed_items = []
        for item in data:
            parsed_item = {
                "iiko_id": item.get("id"),
                "name": item.get("name"),
                "description": item.get("description", ""),
                "code": item.get("code"),
                "num": item.get("num"),
                "price": item.get("defaultSalePrice", 0) if item.get("defaultSalePrice") else 0,
                "deleted": item.get("deleted", False),
                "organization_id": None,  # Server API не привязан к организации
                "data_source": "server",
                "is_duplicate": False,
                
                # Server API поля
                "parent": item.get("parent"),
                "tax_category": item.get("taxCategory"),
                "category_server": item.get("category"),
                "accounting_category": item.get("accountingCategory"),
                "front_image_id": item.get("frontImageId"),
                "position_server": item.get("position"),
                "main_unit": item.get("mainUnit"),
                "default_sale_price": item.get("defaultSalePrice"),
                "place_type": item.get("placeType"),
                "default_included_in_menu": item.get("defaultIncludedInMenu", False),
                "type_server": item.get("type"),
                "unit_weight": item.get("unitWeight"),
                "unit_capacity": item.get("unitCapacity"),
                "product_scale_id": item.get("productScaleId"),
                "modifier_schema_id": item.get("modifierSchemaId"),
                
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            parsed_items.append(parsed_item)
        
        logger.info(f"Парсинг товаров Server API: {len(parsed_items)} записей")
        return parsed_items

    @staticmethod
    def parse_product_groups(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг групп продуктов (Server API)"""
        if not data:
            return []
        
        parsed_groups = []
        for group in data:
            # Получаем position - может быть числом или None
            position = group.get("position")
            if isinstance(position, (int, float)):
                position = str(int(position))
            elif position is None:
                position = None
            else:
                position = str(position) if position else None
            
            # Обрабатываем visibility_filter - может быть dict или None
            visibility_filter = group.get("visibilityFilter")
            if isinstance(visibility_filter, dict):
                # Конвертируем dict в JSON строку
                visibility_filter = json.dumps(visibility_filter, ensure_ascii=False)
            elif visibility_filter is None:
                visibility_filter = None
            else:
                visibility_filter = str(visibility_filter)
            
            parsed_group = {
                "iiko_id": group.get("id"),
                "name": group.get("name"),
                "description": group.get("description", ""),
                "num": group.get("num"),
                "code": group.get("code"),
                "deleted": group.get("deleted", False),
                "parent_iiko_id": group.get("parent"),  # ID родительской группы
                "accounting_category_id": group.get("accountingCategory"),
                "front_image_id": group.get("frontImageId"),
                "position": position,
                "modifier_schema_id": group.get("modifierSchemaId"),
                "visibility_filter": visibility_filter,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            # НЕ сохраняем поле "modifiers" - это массив объектов, его нельзя сохранить напрямую
            parsed_groups.append(parsed_group)
        
        logger.info(f"Парсинг групп продуктов: {len(parsed_groups)} записей")
        return parsed_groups

    @staticmethod
    def parse_product_categories(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг категорий продуктов (Server API) - для MenuCategory"""
        if not data:
            return []
        
        parsed_categories = []
        for category in data:
            parsed_category = {
                "iiko_id": category.get("id"),
                "name": category.get("name"),
                "is_deleted": category.get("deleted", False),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            parsed_categories.append(parsed_category)
        
        logger.info(f"Парсинг категорий продуктов: {len(parsed_categories)} записей")
        return parsed_categories
    
    @staticmethod
    def parse_item_modifiers(modifiers_data: List[Dict[Any, Any]], item_iiko_id: str) -> List[Dict[Any, Any]]:
        """Парсинг модификаторов товара из Server API
        
        Args:
            modifiers_data: массив модификаторов из поля modifiers товара
            item_iiko_id: iiko_id товара, к которому относятся модификаторы
        
        Returns:
            Список словарей с данными модификаторов
        """
        if not modifiers_data:
            return []
        
        parsed_modifiers = []
        
        def parse_modifier_recursive(mod_data: Dict[Any, Any], parent_modifier_iiko_id: Optional[str] = None):
            """Рекурсивно парсит модификатор и его дочерние модификаторы"""
            modifier_iiko_id = mod_data.get("modifier")
            if not modifier_iiko_id:
                return
            
            parsed_modifier = {
                "iiko_id": modifier_iiko_id,
                "item_iiko_id": item_iiko_id,  # К какому товару относится
                "parent_modifier_iiko_id": parent_modifier_iiko_id,  # Родительский модификатор
                "deleted": mod_data.get("deleted", False),
                "default_amount": mod_data.get("defaultAmount", 0),
                "free_of_charge_amount": mod_data.get("freeOfChargeAmount", 0),
                "minimum_amount": mod_data.get("minimumAmount", 0),
                "maximum_amount": mod_data.get("maximumAmount", 0),
                "hide_if_default_amount": mod_data.get("hideIfDefaultAmount", False),
                "child_modifiers_have_min_max_restrictions": mod_data.get("childModifiersHaveMinMaxRestrictions", False),
                "splittable": mod_data.get("splittable", False),
            }
            parsed_modifiers.append(parsed_modifier)
            
            # Рекурсивно обрабатываем дочерние модификаторы
            child_modifiers = mod_data.get("childModifiers")
            if child_modifiers:
                for child_mod in child_modifiers:
                    parse_modifier_recursive(child_mod, modifier_iiko_id)
        
        # Парсим все модификаторы верхнего уровня
        for modifier in modifiers_data:
            parse_modifier_recursive(modifier)
        
        logger.debug(f"Парсинг модификаторов товара {item_iiko_id}: {len(parsed_modifiers)} записей")
        return parsed_modifiers

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
                "roles_iiko_ids": employee.get("rolesIds", []) if isinstance(employee.get("rolesIds"), list) else [],
                "main_role_code": employee.get("mainRoleCode", ""),
                "role_codes": employee.get("roleCodes", []) if isinstance(employee.get("roleCodes"), list) else [],
                
                # Подразделения
                "preferred_department_code": employee.get("preferredDepartmentCode", ""),
                "department_codes": employee.get("departmentCodes", []) if isinstance(employee.get("departmentCodes"), list) else [],
                "responsibility_department_codes": employee.get("responsibilityDepartmentCodes", []) if isinstance(employee.get("responsibilityDepartmentCodes"), list) else [],
                
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
    def parse_restaurant_sections(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг секций ресторана"""
        if not data:
            return []
        
        # Проверяем, что data это список
        if not isinstance(data, list):
            logger.error(f"Ожидался список в parse_restaurant_sections, получен тип: {type(data)}")
            return []
        
        parsed_sections = []
        for section in data:
            # Проверяем, что section это словарь
            if not isinstance(section, dict):
                logger.warning(f"Секция должна быть словарем в parse_restaurant_sections, получен тип: {type(section)}, пропускаем")
                continue
            
            parsed_section = {
                "iiko_id": section.get("id"),
                "name": section.get("name", ""),
                "terminal_group_iiko_id": section.get("terminalGroupId")  # Это iiko_id терминальной группы
            }
            parsed_sections.append(parsed_section)
        
        logger.info(f"Парсинг секций ресторана: {len(parsed_sections)} записей")
        return parsed_sections

    @staticmethod
    def parse_tables(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг столов ресторана"""
        if not data:
            return []
        
        # Проверяем, что data это список
        if not isinstance(data, list):
            logger.error(f"Ожидался список в parse_tables, получен тип: {type(data)}")
            return []
        
        parsed_tables = []
        for table in data:
            # Проверяем, что table это словарь
            if not isinstance(table, dict):
                logger.warning(f"Стол должен быть словарем в parse_tables, получен тип: {type(table)}, пропускаем")
                continue
            
            parsed_table = {
                "iiko_id": table.get("id"),
                "section_iiko_id": table.get("sectionId"),  # iiko_id секции, нужно будет найти section_id при синхронизации
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
    def parse_terminal_groups(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг групп терминалов"""
        if not data:
            return []
        
        parsed_groups = []
        for group in data:
            parsed_group = {
                "iiko_id": group.get("id"),
                "name": group.get("name"),
                "organization_id": group.get("organizationId"),  # Это iiko_id организации
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            parsed_groups.append(parsed_group)
        
        logger.info(f"Парсинг групп терминалов: {len(parsed_groups)} записей")
        return parsed_groups

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

    @staticmethod
    def parse_transactions(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг транзакций"""
        if not data:
            return []
        
        parsed_transactions = []
        for transaction in data:
            parsed_transaction = {
                # Основные поля
                "iiko_id": _safe_get(transaction, "Id"),
                "order_id": _safe_get(transaction, "OrderId"),
                "order_num": transaction.get("OrderNum"),
                "document": transaction.get("Document"),
                
                # Финансовые поля
                "amount": transaction.get("Amount"),
                "sum_resigned": _extract_numeric_value(transaction.get("Sum.ResignedSum")),
                "sum_incoming": _extract_numeric_value(transaction.get("Sum.Incoming")),
                "sum_outgoing": _extract_numeric_value(transaction.get("Sum.Outgoing")),
                "sum_part_of_income": _extract_numeric_value(transaction.get("Sum.PartOfIncome")),
                "sum_part_of_total_income": _extract_numeric_value(transaction.get("Sum.PartOfTotalIncome")),
                
                # Остатки
                "start_balance_money": _extract_numeric_value(transaction.get("StartBalance.Money")),
                "final_balance_money": _extract_numeric_value(transaction.get("FinalBalance.Money")),
                "start_balance_amount": _extract_numeric_value(transaction.get("StartBalance.Amount")),
                "final_balance_amount": _extract_numeric_value(transaction.get("FinalBalance.Amount")),
                
                # Приход/расход
                "amount_in": _extract_numeric_value(transaction.get("Amount.In")),
                "amount_out": _extract_numeric_value(transaction.get("Amount.Out")),
                "contr_amount": transaction.get("Contr-Amount"),
                
                # Типы и категории
                "transaction_type": transaction.get("TransactionType"),
                "transaction_type_code": _safe_get(transaction, "TransactionType.Code"),
                "transaction_side": transaction.get("TransactionSide"),
                
                # Номенклатура
                "product_id": _safe_get(transaction, "Product.Id"),
                "product_name": transaction.get("Product.Name"),
                "product_num": transaction.get("Product.Num"),
                "product_category_id": _safe_get(transaction, "Product.Category.Id"),
                "product_category": transaction.get("Product.Category"),
                "product_type": transaction.get("Product.Type"),
                "product_measure_unit": transaction.get("Product.MeasureUnit"),
                "product_avg_sum": _extract_numeric_value(transaction.get("Product.AvgSum")),
                "product_cooking_place_type": transaction.get("Product.CookingPlaceType"),
                "product_accounting_category": transaction.get("Product.AccountingCategory"),
                
                # Иерархия номенклатуры
                "product_top_parent": transaction.get("Product.TopParent"),
                "product_second_parent": transaction.get("Product.SecondParent"),
                "product_third_parent": transaction.get("Product.ThirdParent"),
                "product_hierarchy": transaction.get("Product.Hierarchy"),
                
                # Пользовательские свойства номенклатуры
                "product_tag_id": _safe_get(transaction, "Product.Tag.Id"),
                "product_tag_name": transaction.get("Product.Tag.Name"),
                "product_tags_ids_combo": transaction.get("Product.Tags.IdsCombo"),
                "product_tags_names_combo": transaction.get("Product.Tags.NamesCombo"),
                
                # Алкогольная продукция
                "product_alcohol_class": transaction.get("Product.AlcoholClass"),
                "product_alcohol_class_code": _safe_get(transaction, "Product.AlcoholClass.Code"),
                "product_alcohol_class_group": transaction.get("Product.AlcoholClass.Group"),
                "product_alcohol_class_type": transaction.get("Product.AlcoholClass.Type"),
                
                # Корреспондент (контрагент)
                "contr_product_id": _safe_get(transaction, "Contr-Product.Id"),
                "contr_product_name": transaction.get("Contr-Product.Name"),
                "contr_product_num": transaction.get("Contr-Product.Num"),
                "contr_product_category_id": _safe_get(transaction, "Contr-Product.Category.Id"),
                "contr_product_category": transaction.get("Contr-Product.Category"),
                "contr_product_type": transaction.get("Contr-Product.Type"),
                "contr_product_measure_unit": transaction.get("Contr-Product.MeasureUnit"),
                "contr_product_accounting_category": transaction.get("Contr-Product.AccountingCategory"),
                
                # Иерархия корреспондента
                "contr_product_top_parent": transaction.get("Contr-Product.TopParent"),
                "contr_product_second_parent": transaction.get("Contr-Product.SecondParent"),
                "contr_product_third_parent": transaction.get("Contr-Product.ThirdParent"),
                "contr_product_hierarchy": transaction.get("Contr-Product.Hierarchy"),
                
                # Пользовательские свойства корреспондента
                "contr_product_tags_ids_combo": transaction.get("Contr-Product.Tags.IdsCombo"),
                "contr_product_tags_names_combo": transaction.get("Contr-Product.Tags.NamesCombo"),
                
                # Алкогольная продукция корреспондента
                "contr_product_alcohol_class": transaction.get("Contr-Product.AlcoholClass"),
                "contr_product_alcohol_class_code": _safe_get(transaction, "Contr-Product.AlcoholClass.Code"),
                "contr_product_alcohol_class_group": transaction.get("Contr-Product.AlcoholClass.Group"),
                "contr_product_alcohol_class_type": transaction.get("Contr-Product.AlcoholClass.Type"),
                "contr_product_cooking_place_type": transaction.get("Contr-Product.CookingPlaceType"),
                
                # Счета
                "account_id": _safe_get(transaction, "Account.Id"),
                "account_name": transaction.get("Account.Name"),
                "account_code": _safe_get(transaction, "Account.Code"),
                "account_type": transaction.get("Account.Type"),
                "account_group": transaction.get("Account.Group"),
                "account_store_or_account": transaction.get("Account.StoreOrAccount"),
                "account_counteragent_type": transaction.get("Account.CounteragentType"),
                "account_is_cash_flow_account": transaction.get("Account.IsCashFlowAccount"),
                
                # Иерархия счетов
                "account_hierarchy_top": transaction.get("Account.AccountHierarchyTop"),
                "account_hierarchy_second": transaction.get("Account.AccountHierarchySecond"),
                "account_hierarchy_third": transaction.get("Account.AccountHierarchyThird"),
                "account_hierarchy_full": transaction.get("Account.AccountHierarchyFull"),
                
                # Корреспондентские счета
                "contr_account_name": transaction.get("Contr-Account.Name"),
                "contr_account_code": _safe_get(transaction, "Contr-Account.Code"),
                "contr_account_type": transaction.get("Contr-Account.Type"),
                "contr_account_group": transaction.get("Contr-Account.Group"),
                
                # Контрагенты
                "counteragent_id": _safe_get(transaction, "Counteragent.Id"),
                "counteragent_name": transaction.get("Counteragent.Name"),
                
                # Организация и подразделения
                "department": transaction.get("Department"),
                "department_code": transaction.get("Department.Code"),  # Это поле будем использовать для поиска организации
                "department_jur_person": transaction.get("Department.JurPerson"),
                "department_category1": transaction.get("Department.Category1"),
                "department_category2": transaction.get("Department.Category2"),
                "department_category3": transaction.get("Department.Category3"),
                "department_category4": transaction.get("Department.Category4"),
                "department_category5": transaction.get("Department.Category5"),
                
                # Сессии и кассы
                "session_group_id": _safe_get(transaction, "Session.GroupId"),
                "session_group": transaction.get("Session.Group"),
                "session_cash_register": transaction.get("Session.CashRegister"),
                "session_restaurant_section": transaction.get("Session.RestaurantSection"),
                
                # Концепции
                "conception": transaction.get("Conception"),
                "conception_code": _safe_get(transaction, "Conception.Code"),
                
                # Склады
                "store": transaction.get("Store"),
                
                # Движение денежных средств
                "cash_flow_category": transaction.get("CashFlowCategory"),
                "cash_flow_category_type": transaction.get("CashFlowCategory.Type"),
                "cash_flow_category_hierarchy": transaction.get("CashFlowCategory.Hierarchy"),
                "cash_flow_category_hierarchy_level1": transaction.get("CashFlowCategory.HierarchyLevel1"),
                "cash_flow_category_hierarchy_level2": transaction.get("CashFlowCategory.HierarchyLevel2"),
                "cash_flow_category_hierarchy_level3": transaction.get("CashFlowCategory.HierarchyLevel3"),
                
                # Даты и время
                "date_time": transaction.get("DateTime.Typed"),
                "date_time_typed": transaction.get("DateTime.Typed"),
                "date_typed": transaction.get("DateTime.DateTyped"),
                "date_secondary_date_time_typed": transaction.get("DateSecondary.DateTimeTyped"),
                "date_secondary_date_typed": transaction.get("DateSecondary.DateTyped"),
                
                # Временные группировки
                "date_time_year": transaction.get("DateTime.Year"),
                "date_time_quarter": transaction.get("DateTime.Quarter"),
                "date_time_month": transaction.get("DateTime.Month"),
                "date_time_week_in_year": transaction.get("DateTime.WeekInYear"),
                "date_time_week_in_month": transaction.get("DateTime.WeekInMonth"),
                "date_time_day_of_week": transaction.get("DateTime.DayOfWeak"),
                "date_time_hour": transaction.get("DateTime.Hour"),
                
                # Комментарии и дополнительные данные
                "comment": transaction.get("Comment"),
                
                # Дополнительные данные
                "additional_data": transaction.get("AdditionalData")
            }
            parsed_transactions.append(parsed_transaction)
        
        logger.info(f"Парсинг транзакций: {len(parsed_transactions)} записей")
        return parsed_transactions

    @staticmethod
    def parse_sales(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг продаж"""
        if not data:
            return []
        
        parsed_sales = []
        for sale in data:
            parsed_sale = {
                # Основные поля
                "item_sale_event_id": _safe_get(sale, "ItemSaleEvent.Id"),
                
                # Организация и подразделения
                "department": sale.get("Department"),
                "department_code": sale.get("Department.Code"),  # Это поле будем использовать для поиска организации
                "department_id": _safe_get(sale, "Department.Id"),
                "department_category1": sale.get("Department.Category1"),
                "department_category2": sale.get("Department.Category2"),
                "department_category3": sale.get("Department.Category3"),
                "department_category4": sale.get("Department.Category4"),
                "department_category5": sale.get("Department.Category5"),
                
                # Концепция
                "conception": sale.get("Conception"),
                "conception_code": _safe_get(sale, "Conception.Code"),
                
                # Заказ
                "order_id": _safe_get(sale, "UniqOrderId.Id"),
                "order_num": sale.get("OrderNum"),
                "order_items": sale.get("OrderItems"),
                "order_type": sale.get("OrderType"),
                "order_type_id": _safe_get(sale, "OrderType.Id"),
                "order_service_type": sale.get("OrderServiceType"),
                "order_comment": sale.get("OrderComment"),
                "order_deleted": sale.get("OrderDeleted"),
                
                # Время заказа
                "open_time": sale.get("OpenTime"),
                "close_time": sale.get("CloseTime"),
                "precheque_time": sale.get("PrechequeTime"),
                "open_date_typed": sale.get("OpenDate.Typed"),
                
                # Временные группировки
                "year_open": sale.get("YearOpen"),
                "quarter_open": sale.get("QuarterOpen"),
                "month_open": sale.get("Mounth"),
                "week_in_year_open": sale.get("WeekInYearOpen"),
                "week_in_month_open": sale.get("WeekInMonthOpen"),
                "day_of_week_open": sale.get("DayOfWeekOpen"),
                "hour_open": sale.get("HourOpen"),
                "hour_close": sale.get("HourClose"),
                
                # Блюдо/товар
                "dish_id": _safe_get(sale, "DishId"),
                "dish_name": sale.get("DishName"),
                "dish_code": sale.get("DishCode"),
                "dish_code_quick": _safe_get(sale, "DishCode.Quick"),
                "dish_foreign_name": sale.get("DishForeignName"),
                "dish_full_name": sale.get("DishFullName"),
                "dish_type": sale.get("DishType"),
                "dish_measure_unit": sale.get("DishMeasureUnit"),
                "dish_amount_int": sale.get("DishAmountInt"),
                "dish_amount_int_per_order": sale.get("DishAmountInt.PerOrder"),
                
                # Категория блюда
                "dish_category": sale.get("DishCategory"),
                "dish_category_id": _safe_get(sale, "DishCategory.Id"),
                "dish_category_accounting": sale.get("DishCategory.Accounting"),
                "dish_category_accounting_id": _safe_get(sale, "DishCategory.Accounting.Id"),
                
                # Группа блюда
                "dish_group": sale.get("DishGroup"),
                "dish_group_id": _safe_get(sale, "DishGroup.Id"),
                "dish_group_num": sale.get("DishGroup.Num"),
                "dish_group_hierarchy": sale.get("DishGroup.Hierarchy"),
                "dish_group_top_parent": sale.get("DishGroup.TopParent"),
                "dish_group_second_parent": sale.get("DishGroup.SecondParent"),
                "dish_group_third_parent": sale.get("DishGroup.ThirdParent"),
                
                # Теги блюда
                "dish_tag_id": _safe_get(sale, "DishTag.Id"),
                "dish_tag_name": sale.get("DishTag.Name"),
                "dish_tags_ids_combo": sale.get("DishTags.IdsCombo"),
                "dish_tags_names_combo": sale.get("DishTags.NamesCombo"),
                
                # Налоговая категория
                "dish_tax_category_id": _safe_get(sale, "DishTaxCategory.Id"),
                "dish_tax_category_name": sale.get("DishTaxCategory.Name"),
                
                # Размер блюда
                "dish_size_id": _safe_get(sale, "DishSize.Id"),
                "dish_size_name": sale.get("DishSize.Name"),
                "dish_size_short_name": sale.get("DishSize.ShortName"),
                "dish_size_priority": sale.get("DishSize.Priority"),
                "dish_size_scale_id": _safe_get(sale, "DishSize.Scale.Id"),
                "dish_size_scale_name": sale.get("DishSize.Scale.Name"),
                
                # Финансовые поля
                "dish_sum_int": sale.get("DishSumInt"),
                "dish_sum_int_average_price_with_vat": _extract_numeric_value(sale.get("DishSumInt.averagePriceWithVAT")),
                "dish_discount_sum_int": sale.get("DishDiscountSumInt"),
                "dish_discount_sum_int_average": _extract_numeric_value(sale.get("DishDiscountSumInt.average")),
                "dish_discount_sum_int_average_by_guest": _extract_numeric_value(sale.get("DishDiscountSumInt.averageByGuest")),
                "dish_discount_sum_int_average_price": _extract_numeric_value(sale.get("DishDiscountSumInt.averagePrice")),
                "dish_discount_sum_int_average_price_with_vat": _extract_numeric_value(sale.get("DishDiscountSumInt.averagePriceWithVAT")),
                "dish_discount_sum_int_average_without_vat": _extract_numeric_value(sale.get("DishDiscountSumInt.averageWithoutVAT")),
                "dish_discount_sum_int_without_vat": sale.get("DishDiscountSumInt.withoutVAT"),
                "dish_return_sum": sale.get("DishReturnSum"),
                "dish_return_sum_without_vat": sale.get("DishReturnSum.withoutVAT"),
                
                # Скидки и наценки
                "discount_percent": sale.get("DiscountPercent"),
                "discount_sum": sale.get("DiscountSum"),
                "discount_without_vat": sale.get("discountWithoutVAT"),
                "increase_percent": sale.get("IncreasePercent"),
                "increase_sum": sale.get("IncreaseSum"),
                "full_sum": sale.get("fullSum"),
                "sum_after_discount_without_vat": sale.get("sumAfterDiscountWithoutVAT"),
                
                # НДС
                "vat_percent": _extract_numeric_value(sale.get("VAT.Percent")),
                "vat_sum": _extract_numeric_value(sale.get("VAT.Sum")),
                
                # Сессия и касса
                "session_id": sale.get("SessionID"),
                "session_num": sale.get("SessionNum"),
                "cash_register_name": sale.get("CashRegisterName"),
                "cash_register_name_serial_number": sale.get("CashRegisterName.CashRegisterSerialNumber"),
                "cash_register_name_number": sale.get("CashRegisterName.Number"),
                
                # Ресторанная секция
                "restaurant_section": sale.get("RestaurantSection"),
                "restaurant_section_id": _safe_get(sale, "RestaurantSection.Id"),
                
                # Стол
                "table_num": sale.get("TableNum"),
                
                # Гости
                "guest_num": sale.get("GuestNum"),
                "guest_num_avg": _extract_numeric_value(sale.get("GuestNum.Avg")),
                
                # Официант
                "waiter_name": sale.get("WaiterName"),
                "waiter_name_id": sale.get("WaiterName.ID"),
                "order_waiter_id": _safe_get(sale, "OrderWaiter.Id"),
                "order_waiter_name": sale.get("OrderWaiter.Name"),
                "waiter_team_id": _safe_get(sale, "WaiterTeam.Id"),
                "waiter_team_name": sale.get("WaiterTeam.Name"),
                
                # Кассир
                "cashier": sale.get("Cashier"),
                "cashier_code": _safe_get(sale, "Cashier.Code"),
                "cashier_id": _safe_get(sale, "Cashier.Id"),
                
                # Пользователь авторизации
                "auth_user": sale.get("AuthUser"),
                "auth_user_id": sale.get("AuthUser.Id"),
                
                # Платежи
                "pay_types": sale.get("PayTypes"),
                "pay_types_combo": sale.get("PayTypes.Combo"),
                "pay_types_guid": sale.get("PayTypes.GUID"),
                "pay_types_group": sale.get("PayTypes.Group"),
                "pay_types_is_print_cheque": sale.get("PayTypes.IsPrintCheque"),
                "pay_types_voucher_num": sale.get("PayTypes.VoucherNum"),
                
                # Карты
                "card": sale.get("Card"),
                "card_number": sale.get("CardNumber"),
                "card_owner": sale.get("CardOwner"),
                "card_type": sale.get("CardType"),
                "card_type_name": sale.get("CardTypeName"),
                
                # Бонусы
                "bonus_card_number": sale.get("Bonus.CardNumber"),
                "bonus_sum": _extract_numeric_value(sale.get("Bonus.Sum")),
                "bonus_type": sale.get("Bonus.Type"),
                
                # Фискальный чек
                "fiscal_cheque_number": _extract_fiscal_cheque_number(sale.get("FiscalChequeNumber")),
                
                # Валюты
                "currencies_currency": sale.get("Currencies.Currency"),
                "currencies_currency_rate": sale.get("Currencies.CurrencyRate"),
                "currencies_sum_in_currency": _extract_currency_sum(sale.get("Currencies.SumInCurrency")),
                
                # Готовка
                "cooking_place": sale.get("CookingPlace"),
                "cooking_place_id": sale.get("CookingPlace.Id"),
                "cooking_place_type": sale.get("CookingPlaceType"),
                
                # Время готовки
                "cooking_cooking_duration_avg": _extract_numeric_value(sale.get("Cooking.CookingDuration.Avg")),
                "cooking_cooking1_duration_avg": _extract_numeric_value(sale.get("Cooking.Cooking1Duration.Avg")),
                "cooking_cooking2_duration_avg": _extract_numeric_value(sale.get("Cooking.Cooking2Duration.Avg")),
                "cooking_cooking3_duration_avg": _extract_numeric_value(sale.get("Cooking.Cooking3Duration.Avg")),
                "cooking_cooking4_duration_avg": _extract_numeric_value(sale.get("Cooking.Cooking4Duration.Avg")),
                "cooking_cooking_late_time_avg": _extract_numeric_value(sale.get("Cooking.CookingLateTime.Avg")),
                "cooking_feed_late_time_avg": _extract_numeric_value(sale.get("Cooking.FeedLateTime.Avg")),
                "cooking_guest_wait_time_avg": _extract_numeric_value(sale.get("Cooking.GuestWaitTime.Avg")),
                "cooking_kitchen_time_avg": _extract_numeric_value(sale.get("Cooking.KitchenTime.Avg")),
                "cooking_serve_number": sale.get("Cooking.ServeNumber"),
                "cooking_serve_time_avg": _extract_numeric_value(sale.get("Cooking.ServeTime.Avg")),
                "cooking_start_delay_time_avg": _extract_numeric_value(sale.get("Cooking.StartDelayTime.Avg")),
                
                # Время заказа
                "order_time_average_order_time": sale.get("OrderTime.AverageOrderTime"),
                "order_time_average_precheque_time": sale.get("OrderTime.AveragePrechequeTime"),
                "order_time_order_length": _extract_numeric_value(sale.get("OrderTime.OrderLength")),
                "order_time_order_length_sum": _extract_numeric_value(sale.get("OrderTime.OrderLengthSum")),
                "order_time_precheque_length": _extract_numeric_value(sale.get("OrderTime.PrechequeLength")),
                
                # Доставка
                "delivery_is_delivery": sale.get("Delivery.IsDelivery"),
                "delivery_id": sale.get("Delivery.Id"),
                "delivery_number": sale.get("Delivery.Number"),
                "delivery_address": sale.get("Delivery.Address"),
                "delivery_city": sale.get("Delivery.City"),
                "delivery_street": sale.get("Delivery.Street"),
                "delivery_index": sale.get("Delivery.Index"),
                "delivery_region": sale.get("Delivery.Region"),
                "delivery_zone": sale.get("Delivery.Zone"),
                "delivery_phone": sale.get("Delivery.Phone"),
                "delivery_email": sale.get("Delivery.Email"),
                "delivery_courier": sale.get("Delivery.Courier"),
                "delivery_courier_id": sale.get("Delivery.Courier.Id"),
                "delivery_operator": sale.get("Delivery.DeliveryOperator"),
                "delivery_operator_id": sale.get("Delivery.DeliveryOperator.Id"),
                "delivery_service_type": sale.get("Delivery.ServiceType"),
                "delivery_expected_time": sale.get("Delivery.ExpectedTime"),
                "delivery_actual_time": sale.get("Delivery.ActualTime"),
                "delivery_close_time": sale.get("Delivery.CloseTime"),
                "delivery_cooking_finish_time": sale.get("Delivery.CookingFinishTime"),
                "delivery_send_time": sale.get("Delivery.SendTime"),
                "delivery_bill_time": sale.get("Delivery.BillTime"),
                "delivery_print_time": sale.get("Delivery.PrintTime"),
                "delivery_delay": sale.get("Delivery.Delay"),
                "delivery_delay_avg": _extract_numeric_value(sale.get("Delivery.DelayAvg")),
                "delivery_way_duration": _extract_numeric_value(sale.get("Delivery.WayDuration")),
                "delivery_way_duration_avg": _extract_numeric_value(sale.get("Delivery.WayDurationAvg")),
                "delivery_way_duration_sum": _extract_numeric_value(sale.get("Delivery.WayDurationSum")),
                "delivery_cooking_to_send_duration": _extract_numeric_value(sale.get("Delivery.CookingToSendDuration")),
                "delivery_diff_between_actual_delivery_time_and_predicted_delivery_time": sale.get("Delivery.DiffBetweenActualDeliveryTimeAndPredictedDeliveryTime"),
                "delivery_predicted_cooking_complete_time": sale.get("Delivery.PredictedCookingCompleteTime"),
                "delivery_predicted_delivery_time": sale.get("Delivery.PredictedDeliveryTime"),
                "delivery_customer_name": sale.get("Delivery.CustomerName"),
                "delivery_customer_phone": sale.get("Delivery.CustomerPhone"),
                "delivery_customer_email": sale.get("Delivery.CustomerEmail"),
                "delivery_customer_card_number": sale.get("Delivery.CustomerCardNumber"),
                "delivery_customer_card_type": sale.get("Delivery.CustomerCardType"),
                "delivery_customer_comment": sale.get("Delivery.CustomerComment"),
                "delivery_customer_created_date_typed": sale.get("Delivery.CustomerCreatedDateTyped"),
                "delivery_customer_marketing_source": sale.get("Delivery.CustomerMarketingSource"),
                "delivery_customer_opinion_comment": sale.get("Delivery.CustomerOpinionComment"),
                "delivery_delivery_comment": sale.get("Delivery.DeliveryComment"),
                "delivery_cancel_cause": sale.get("Delivery.CancelCause"),
                "delivery_cancel_comment": sale.get("Delivery.CancelComment"),
                "delivery_marketing_source": sale.get("Delivery.MarketingSource"),
                "delivery_external_cartography_id": sale.get("Delivery.ExternalCartographyId"),
                "delivery_source_key": sale.get("Delivery.SourceKey"),
                "delivery_ecs_service": sale.get("Delivery.EcsService"),
                
                # Оценки доставки
                "delivery_avg_mark": _extract_numeric_value(sale.get("Delivery.AvgMark")),
                "delivery_avg_food_mark": _extract_numeric_value(sale.get("Delivery.AvgFoodMark")),
                "delivery_avg_courier_mark": _extract_numeric_value(sale.get("Delivery.AvgCourierMark")),
                "delivery_avg_operator_mark": _extract_numeric_value(sale.get("Delivery.AvgOperatorMark")),
                "delivery_aggregated_avg_mark": _extract_numeric_value(sale.get("Delivery.AggregatedAvgMark")),
                "delivery_aggregated_avg_food_mark": _extract_numeric_value(sale.get("Delivery.AggregatedAvgFoodMark")),
                "delivery_aggregated_avg_courier_mark": _extract_numeric_value(sale.get("Delivery.AggregatedAvgCourierMark")),
                "delivery_aggregated_avg_operator_mark": _extract_numeric_value(sale.get("Delivery.AggregatedAvgOperatorMark")),
                
                # Скидки заказа
                "order_discount_guest_card": sale.get("OrderDiscount.GuestCard"),
                "order_discount_type": sale.get("OrderDiscount.Type"),
                "order_discount_type_ids": sale.get("OrderDiscount.Type.IDs"),
                
                # Наценки заказа
                "order_increase_type": sale.get("OrderIncrease.Type"),
                "order_increase_type_ids": sale.get("OrderIncrease.Type.IDs"),
                
                # Событие продажи товара
                "item_sale_event_discount_type": sale.get("ItemSaleEventDiscountType"),
                "item_sale_event_discount_type_combo_amount": sale.get("ItemSaleEventDiscountType.ComboAmount"),
                "item_sale_event_discount_type_discount_amount": sale.get("ItemSaleEventDiscountType.DiscountAmount"),
                
                # Платежная транзакция
                "payment_transaction_id": sale.get("PaymentTransaction.Id"),
                "payment_transaction_ids": sale.get("PaymentTransaction.Ids"),
                
                # Тип операции
                "operation_type": sale.get("OperationType"),
                
                # Контрагент
                "counteragent_name": sale.get("Counteragent.Name"),
                
                # Кредитный пользователь
                "credit_user": sale.get("CreditUser"),
                "credit_user_company": sale.get("CreditUser.Company"),
                
                # Ценовая категория
                "price_category": sale.get("PriceCategory"),
                "price_category_card": sale.get("PriceCategoryCard"),
                "price_category_discount_card_owner": sale.get("PriceCategoryDiscountCardOwner"),
                "price_category_user_card_owner": sale.get("PriceCategoryUserCardOwner"),
                
                # Стоимость продукта
                "product_cost_base_mark_up": sale.get("ProductCostBase.MarkUp"),
                "product_cost_base_one_item": sale.get("ProductCostBase.OneItem"),
                "product_cost_base_percent": _extract_numeric_value(sale.get("ProductCostBase.Percent")),
                "product_cost_base_percent_without_vat": _extract_numeric_value(sale.get("ProductCostBase.PercentWithoutVAT")),
                "product_cost_base_product_cost": sale.get("ProductCostBase.ProductCost"),
                "product_cost_base_profit": sale.get("ProductCostBase.Profit"),
                
                # Стимулирующая сумма
                "incentive_sum_base_sum": _extract_numeric_value(sale.get("IncentiveSumBase.Sum")),
                
                # Процент от итога
                "percent_of_summary_by_col": _extract_numeric_value(sale.get("PercentOfSummary.ByCol")),
                "percent_of_summary_by_row": _extract_numeric_value(sale.get("PercentOfSummary.ByRow")),
                
                # Продано с блюдом
                "sold_with_dish": sale.get("SoldWithDish"),
                "sold_with_dish_id": sale.get("SoldWithDish.Id"),
                "sold_with_item_id": sale.get("SoldWithItem.Id"),
                
                # Склад
                "store_id": sale.get("Store.Id"),
                "store_name": sale.get("Store.Name"),
                "store_to": sale.get("StoreTo"),
                
                # Ресторанная группа
                "restoraunt_group": sale.get("RestorauntGroup"),
                "restoraunt_group_id": sale.get("RestorauntGroup.Id"),
                
                # Юридическое лицо
                "jur_name": sale.get("JurName"),
                
                # Внешний номер
                "external_number": sale.get("ExternalNumber"),
                
                # Происхождение
                "origin_name": sale.get("OriginName"),
                
                # Тип удаления
                "removal_type": sale.get("RemovalType"),
                
                # Списание
                "writeoff_reason": sale.get("WriteoffReason"),
                "writeoff_user": sale.get("WriteoffUser"),
                
                # Статусы
                "banquet": sale.get("Banquet"),
                "storned": sale.get("Storned"),
                "deleted_with_writeoff": sale.get("DeletedWithWriteoff"),
                "deletion_comment": sale.get("DeletionComment"),
                
                # Тип безналичного платежа
                "non_cash_payment_type": sale.get("NonCashPaymentType"),
                "non_cash_payment_type_document_type": sale.get("NonCashPaymentType.DocumentType"),
                
                # Расположение наличных
                "cash_location": sale.get("CashLocation"),
                
                # Время печати блюда
                "dish_service_print_time": sale.get("DishServicePrintTime"),
                "dish_service_print_time_max": _extract_numeric_value(sale.get("DishServicePrintTime.Max")),
                "dish_service_print_time_open_to_last_print_duration": _extract_numeric_value(sale.get("DishServicePrintTime.OpenToLastPrintDuration")),
                
                # Временные группировки по минутам
                "open_time_minutes15": sale.get("OpenTime.Minutes15"),
                "close_time_minutes15": sale.get("CloseTime.Minutes15"),
                
                # Внешние данные
                "public_external_data": sale.get("PublicExternalData"),
                "public_external_data_xml": sale.get("PublicExternalData.Xml")
            }
            parsed_sales.append(parsed_sale)
        
        logger.info(f"Парсинг продаж: {len(parsed_sales)} записей")
        return parsed_sales

    @staticmethod
    def parse_accounts(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг счетов (accounts) из Server API"""
        if not data:
            return []
        
        # Проверяем, что data это список
        if not isinstance(data, list):
            logger.error(f"Ожидался список в parse_accounts, получен тип: {type(data)}")
            return []
        
        parsed_accounts = []
        for account in data:
            # Проверяем, что account это словарь
            if not isinstance(account, dict):
                logger.warning(f"Счет должен быть словарем в parse_accounts, получен тип: {type(account)}, пропускаем")
                continue
            
            parsed_account = {
                "iiko_id": account.get("id"),
                "root_type": account.get("rootType"),
                "account_parent_id": account.get("accountParentId"),
                "parent_corporate_id": account.get("parentCorporateId"),
                "type": account.get("type"),
                "system": account.get("system"),
                "custom_transactions_allowed": account.get("customTransactionsAllowed"),
                "deleted": account.get("deleted", False),
                "code": account.get("code", ""),
                "name": account.get("name", "")
            }
            parsed_accounts.append(parsed_account)
        
        logger.info(f"Парсинг счетов: {len(parsed_accounts)} записей")
        return parsed_accounts

    @staticmethod
    def parse_salaries(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг окладов сотрудников из Server API"""
        if not data:
            return []
        
        # Проверяем, что data это список
        if not isinstance(data, list):
            logger.error(f"Ожидался список в parse_salaries, получен тип: {type(data)}")
            return []
        
        parsed_salaries = []
        for salary in data:
            # Проверяем, что salary это словарь
            if not isinstance(salary, dict):
                logger.warning(f"Оклад должен быть словарем в parse_salaries, получен тип: {type(salary)}, пропускаем")
                continue
            
            parsed_salary = {
                "employee_iiko_id": salary.get("employeeId"),  # ID сотрудника из iiko
                "date_from": salary.get("dateFrom"),
                "date_to": salary.get("dateTo"),
                "salary": salary.get("payment")
            }
            parsed_salaries.append(parsed_salary)
        
        logger.info(f"Парсинг окладов: {len(parsed_salaries)} записей")
        return parsed_salaries


# Глобальный экземпляр парсера
iiko_parser = IikoParser()
