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

    @staticmethod
    def parse_transactions(data: List[Dict[Any, Any]]) -> List[Dict[Any, Any]]:
        """Парсинг транзакций"""
        if not data:
            return []
        
        parsed_transactions = []
        for transaction in data:
            # Извлекаем данные о сумме
            sum_data = transaction.get("Sum", {}) if isinstance(transaction.get("Sum"), dict) else {}
            start_balance = transaction.get("StartBalance", {}) if isinstance(transaction.get("StartBalance"), dict) else {}
            final_balance = transaction.get("FinalBalance", {}) if isinstance(transaction.get("FinalBalance"), dict) else {}
            amount_data = transaction.get("Amount", {}) if isinstance(transaction.get("Amount"), dict) else {}
            
            # Извлекаем данные о продукте
            product_data = transaction.get("Product", {}) if isinstance(transaction.get("Product"), dict) else {}
            product_category = product_data.get("Category", {}) if isinstance(product_data.get("Category"), dict) else {}
            product_tag = product_data.get("Tag", {}) if isinstance(product_data.get("Tag"), dict) else {}
            product_tags = product_data.get("Tags", {}) if isinstance(product_data.get("Tags"), dict) else {}
            product_alcohol_class = product_data.get("AlcoholClass", {}) if isinstance(product_data.get("AlcoholClass"), dict) else {}
            
            # Извлекаем данные о корреспонденте
            contr_product_data = transaction.get("Contr-Product", {}) if isinstance(transaction.get("Contr-Product"), dict) else {}
            contr_product_category = contr_product_data.get("Category", {}) if isinstance(contr_product_data.get("Category"), dict) else {}
            contr_product_tags = contr_product_data.get("Tags", {}) if isinstance(contr_product_data.get("Tags"), dict) else {}
            contr_product_alcohol_class = contr_product_data.get("AlcoholClass", {}) if isinstance(contr_product_data.get("AlcoholClass"), dict) else {}
            
            # Извлекаем данные о счетах
            account_data = transaction.get("Account", {}) if isinstance(transaction.get("Account"), dict) else {}
            contr_account_data = transaction.get("Contr-Account", {}) if isinstance(transaction.get("Contr-Account"), dict) else {}
            
            # Извлекаем данные о контрагенте
            counteragent_data = transaction.get("Counteragent", {}) if isinstance(transaction.get("Counteragent"), dict) else {}
            
            # Извлекаем данные о подразделении
            department_data = transaction.get("Department", {}) if isinstance(transaction.get("Department"), dict) else {}
            
            # Извлекаем данные о сессии
            session_data = transaction.get("Session", {}) if isinstance(transaction.get("Session"), dict) else {}
            
            # Извлекаем данные о концепции
            conception_data = transaction.get("Conception", {}) if isinstance(transaction.get("Conception"), dict) else {}
            
            # Извлекаем данные о движении денежных средств
            cash_flow_category_data = transaction.get("CashFlowCategory", {}) if isinstance(transaction.get("CashFlowCategory"), dict) else {}
            
            # Извлекаем данные о дате
            date_time_data = transaction.get("DateTime", {}) if isinstance(transaction.get("DateTime"), dict) else {}
            date_secondary_data = transaction.get("DateSecondary", {}) if isinstance(transaction.get("DateSecondary"), dict) else {}
            
            parsed_transaction = {
                # Основные поля
                "iiko_id": transaction.get("Id"),
                "order_id": transaction.get("OrderId"),
                "order_num": transaction.get("OrderNum"),
                "document": transaction.get("Document"),
                
                # Финансовые поля
                "amount": transaction.get("Amount"),
                "sum_resigned": sum_data.get("ResignedSum"),
                "sum_incoming": sum_data.get("Incoming"),
                "sum_outgoing": sum_data.get("Outgoing"),
                "sum_part_of_income": sum_data.get("PartOfIncome"),
                "sum_part_of_total_income": sum_data.get("PartOfTotalIncome"),
                
                # Остатки
                "start_balance_money": start_balance.get("Money"),
                "final_balance_money": final_balance.get("Money"),
                "start_balance_amount": start_balance.get("Amount"),
                "final_balance_amount": final_balance.get("Amount"),
                
                # Приход/расход
                "amount_in": amount_data.get("In"),
                "amount_out": amount_data.get("Out"),
                "contr_amount": transaction.get("Contr-Amount"),
                
                # Типы и категории
                "transaction_type": transaction.get("TransactionType"),
                "transaction_type_code": transaction.get("TransactionType", {}).get("Code") if isinstance(transaction.get("TransactionType"), dict) else None,
                "transaction_side": transaction.get("TransactionSide"),
                
                # Номенклатура
                "product_id": product_data.get("Id"),
                "product_name": product_data.get("Name"),
                "product_num": product_data.get("Num"),
                "product_category_id": product_category.get("Id"),
                "product_category": product_category.get("Name"),
                "product_type": product_data.get("Type"),
                "product_measure_unit": product_data.get("MeasureUnit"),
                "product_avg_sum": product_data.get("AvgSum"),
                "product_cooking_place_type": product_data.get("CookingPlaceType"),
                "product_accounting_category": product_data.get("AccountingCategory"),
                
                # Иерархия номенклатуры
                "product_top_parent": product_data.get("TopParent"),
                "product_second_parent": product_data.get("SecondParent"),
                "product_third_parent": product_data.get("ThirdParent"),
                "product_hierarchy": product_data.get("Hierarchy"),
                
                # Пользовательские свойства номенклатуры
                "product_tag_id": product_tag.get("Id"),
                "product_tag_name": product_tag.get("Name"),
                "product_tags_ids_combo": product_tags.get("IdsCombo"),
                "product_tags_names_combo": product_tags.get("NamesCombo"),
                
                # Алкогольная продукция
                "product_alcohol_class": product_alcohol_class.get("Name"),
                "product_alcohol_class_code": product_alcohol_class.get("Code"),
                "product_alcohol_class_group": product_alcohol_class.get("Group"),
                "product_alcohol_class_type": product_alcohol_class.get("Type"),
                
                # Корреспондент (контрагент)
                "contr_product_id": contr_product_data.get("Id"),
                "contr_product_name": contr_product_data.get("Name"),
                "contr_product_num": contr_product_data.get("Num"),
                "contr_product_category_id": contr_product_category.get("Id"),
                "contr_product_category": contr_product_category.get("Name"),
                "contr_product_type": contr_product_data.get("Type"),
                "contr_product_measure_unit": contr_product_data.get("MeasureUnit"),
                "contr_product_accounting_category": contr_product_data.get("AccountingCategory"),
                
                # Иерархия корреспондента
                "contr_product_top_parent": contr_product_data.get("TopParent"),
                "contr_product_second_parent": contr_product_data.get("SecondParent"),
                "contr_product_third_parent": contr_product_data.get("ThirdParent"),
                "contr_product_hierarchy": contr_product_data.get("Hierarchy"),
                
                # Пользовательские свойства корреспондента
                "contr_product_tags_ids_combo": contr_product_tags.get("IdsCombo"),
                "contr_product_tags_names_combo": contr_product_tags.get("NamesCombo"),
                
                # Алкогольная продукция корреспондента
                "contr_product_alcohol_class": contr_product_alcohol_class.get("Name"),
                "contr_product_alcohol_class_code": contr_product_alcohol_class.get("Code"),
                "contr_product_alcohol_class_group": contr_product_alcohol_class.get("Group"),
                "contr_product_alcohol_class_type": contr_product_alcohol_class.get("Type"),
                "contr_product_cooking_place_type": contr_product_data.get("CookingPlaceType"),
                
                # Счета
                "account_id": account_data.get("Id"),
                "account_name": account_data.get("Name"),
                "account_code": account_data.get("Code"),
                "account_type": account_data.get("Type"),
                "account_group": account_data.get("Group"),
                "account_store_or_account": account_data.get("StoreOrAccount"),
                "account_counteragent_type": account_data.get("CounteragentType"),
                "account_is_cash_flow_account": account_data.get("IsCashFlowAccount"),
                
                # Иерархия счетов
                "account_hierarchy_top": account_data.get("AccountHierarchyTop"),
                "account_hierarchy_second": account_data.get("AccountHierarchySecond"),
                "account_hierarchy_third": account_data.get("AccountHierarchyThird"),
                "account_hierarchy_full": account_data.get("AccountHierarchyFull"),
                
                # Корреспондентские счета
                "contr_account_name": contr_account_data.get("Name"),
                "contr_account_code": contr_account_data.get("Code"),
                "contr_account_type": contr_account_data.get("Type"),
                "contr_account_group": contr_account_data.get("Group"),
                
                # Контрагенты
                "counteragent_id": counteragent_data.get("Id"),
                "counteragent_name": counteragent_data.get("Name"),
                
                # Организация и подразделения
                "department": department_data.get("Name"),
                "department_code": department_data.get("Code"),  # Это поле будем использовать для поиска организации
                "department_jur_person": department_data.get("JurPerson"),
                "department_category1": department_data.get("Category1"),
                "department_category2": department_data.get("Category2"),
                "department_category3": department_data.get("Category3"),
                "department_category4": department_data.get("Category4"),
                "department_category5": department_data.get("Category5"),
                
                # Сессии и кассы
                "session_group_id": session_data.get("GroupId"),
                "session_group": session_data.get("Group"),
                "session_cash_register": session_data.get("CashRegister"),
                "session_restaurant_section": session_data.get("RestaurantSection"),
                
                # Концепции
                "conception": conception_data.get("Name"),
                "conception_code": conception_data.get("Code"),
                
                # Склады
                "store": transaction.get("Store"),
                
                # Движение денежных средств
                "cash_flow_category": cash_flow_category_data.get("Name"),
                "cash_flow_category_type": cash_flow_category_data.get("Type"),
                "cash_flow_category_hierarchy": cash_flow_category_data.get("Hierarchy"),
                "cash_flow_category_hierarchy_level1": cash_flow_category_data.get("HierarchyLevel1"),
                "cash_flow_category_hierarchy_level2": cash_flow_category_data.get("HierarchyLevel2"),
                "cash_flow_category_hierarchy_level3": cash_flow_category_data.get("HierarchyLevel3"),
                
                # Даты и время
                "date_time": date_time_data.get("Typed"),
                "date_time_typed": date_time_data.get("Typed"),
                "date_typed": date_time_data.get("DateTyped"),
                "date_secondary_date_time_typed": date_secondary_data.get("DateTimeTyped"),
                "date_secondary_date_typed": date_secondary_data.get("DateTyped"),
                
                # Временные группировки
                "date_time_year": date_time_data.get("Year"),
                "date_time_quarter": date_time_data.get("Quarter"),
                "date_time_month": date_time_data.get("Month"),
                "date_time_week_in_year": date_time_data.get("WeekInYear"),
                "date_time_week_in_month": date_time_data.get("WeekInMonth"),
                "date_time_day_of_week": date_time_data.get("DayOfWeak"),
                "date_time_hour": date_time_data.get("Hour"),
                
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
            # Извлекаем данные о валютах
            currencies_data = sale.get("Currencies", {}) if isinstance(sale.get("Currencies"), dict) else {}
            currencies_sum_in_currency = currencies_data.get("SumInCurrency", {}) if isinstance(currencies_data.get("SumInCurrency"), dict) else {}
            
            # Извлекаем данные о блюде
            dish_category_data = sale.get("DishCategory", {}) if isinstance(sale.get("DishCategory"), dict) else {}
            dish_group_data = sale.get("DishGroup", {}) if isinstance(sale.get("DishGroup"), dict) else {}
            dish_tag_data = sale.get("DishTag", {}) if isinstance(sale.get("DishTag"), dict) else {}
            dish_tags_data = sale.get("DishTags", {}) if isinstance(sale.get("DishTags"), dict) else {}
            dish_tax_category_data = sale.get("DishTaxCategory", {}) if isinstance(sale.get("DishTaxCategory"), dict) else {}
            dish_size_data = sale.get("DishSize", {}) if isinstance(sale.get("DishSize"), dict) else {}
            dish_size_scale_data = dish_size_data.get("Scale", {}) if isinstance(dish_size_data.get("Scale"), dict) else {}
            
            # Извлекаем данные о доставке
            delivery_data = sale.get("Delivery", {}) if isinstance(sale.get("Delivery"), dict) else {}
            
            # Извлекаем данные о скидках заказа
            order_discount_data = sale.get("OrderDiscount", {}) if isinstance(sale.get("OrderDiscount"), dict) else {}
            
            # Извлекаем данные о наценках заказа
            order_increase_data = sale.get("OrderIncrease", {}) if isinstance(sale.get("OrderIncrease"), dict) else {}
            
            # Извлекаем данные о событии продажи товара
            item_sale_event_discount_type_data = sale.get("ItemSaleEventDiscountType", {}) if isinstance(sale.get("ItemSaleEventDiscountType"), dict) else {}
            
            # Извлекаем данные о платежной транзакции
            payment_transaction_data = sale.get("PaymentTransaction", {}) if isinstance(sale.get("PaymentTransaction"), dict) else {}
            
            # Извлекаем данные о кредитном пользователе
            credit_user_data = sale.get("CreditUser", {}) if isinstance(sale.get("CreditUser"), dict) else {}
            
            # Извлекаем данные о ценовой категории
            price_category_data = sale.get("PriceCategory", {}) if isinstance(sale.get("PriceCategory"), dict) else {}
            
            # Извлекаем данные о стоимости продукта
            product_cost_base_data = sale.get("ProductCostBase", {}) if isinstance(sale.get("ProductCostBase"), dict) else {}
            
            # Извлекаем данные о стимулирующей сумме
            incentive_sum_base_data = sale.get("IncentiveSumBase", {}) if isinstance(sale.get("IncentiveSumBase"), dict) else {}
            
            # Извлекаем данные о проценте от итога
            percent_of_summary_data = sale.get("PercentOfSummary", {}) if isinstance(sale.get("PercentOfSummary"), dict) else {}
            
            # Извлекаем данные о продано с блюдом
            sold_with_dish_data = sale.get("SoldWithDish", {}) if isinstance(sale.get("SoldWithDish"), dict) else {}
            
            # Извлекаем данные о складе
            store_data = sale.get("Store", {}) if isinstance(sale.get("Store"), dict) else {}
            
            # Извлекаем данные о ресторанной группе
            restoraunt_group_data = sale.get("RestorauntGroup", {}) if isinstance(sale.get("RestorauntGroup"), dict) else {}
            
            # Извлекаем данные о ресторанной секции
            restaurant_section_data = sale.get("RestaurantSection", {}) if isinstance(sale.get("RestaurantSection"), dict) else {}
            
            # Извлекаем данные о кассе
            cash_register_name_data = sale.get("CashRegisterName", {}) if isinstance(sale.get("CashRegisterName"), dict) else {}
            
            # Извлекаем данные о платежах
            pay_types_data = sale.get("PayTypes", {}) if isinstance(sale.get("PayTypes"), dict) else {}
            
            # Извлекаем данные о бонусах
            bonus_data = sale.get("Bonus", {}) if isinstance(sale.get("Bonus"), dict) else {}
            
            # Извлекаем данные о валютах
            currencies_data = sale.get("Currencies", {}) if isinstance(sale.get("Currencies"), dict) else {}
            
            # Извлекаем данные о готовке
            cooking_data = sale.get("Cooking", {}) if isinstance(sale.get("Cooking"), dict) else {}
            
            # Извлекаем данные о времени заказа
            order_time_data = sale.get("OrderTime", {}) if isinstance(sale.get("OrderTime"), dict) else {}
            
            # Извлекаем данные о времени печати блюда
            dish_service_print_time_data = sale.get("DishServicePrintTime", {}) if isinstance(sale.get("DishServicePrintTime"), dict) else {}
            
            # Извлекаем данные о времени открытия
            open_time_data = sale.get("OpenTime", {}) if isinstance(sale.get("OpenTime"), dict) else {}
            
            # Извлекаем данные о времени закрытия
            close_time_data = sale.get("CloseTime", {}) if isinstance(sale.get("CloseTime"), dict) else {}
            
            # Извлекаем данные о времени предчека
            precheque_time_data = sale.get("PrechequeTime", {}) if isinstance(sale.get("PrechequeTime"), dict) else {}
            
            # Извлекаем данные о времени открытия даты
            open_date_typed_data = sale.get("OpenDate", {}) if isinstance(sale.get("OpenDate"), dict) else {}
            
            # Извлекаем данные о НДС
            vat_data = sale.get("VAT", {}) if isinstance(sale.get("VAT"), dict) else {}
            
            # Извлекаем данные о внешних данных
            public_external_data_data = sale.get("PublicExternalData", {}) if isinstance(sale.get("PublicExternalData"), dict) else {}
            
            parsed_sale = {
                # Основные поля
                "iiko_id": sale.get("ItemSaleEvent.Id"),
                
                # Организация и подразделения
                "department": sale.get("Department"),
                "department_code": sale.get("Department.Code"),  # Это поле будем использовать для поиска организации
                "department_id": sale.get("Department.Id"),
                "department_category1": sale.get("Department.Category1"),
                "department_category2": sale.get("Department.Category2"),
                "department_category3": sale.get("Department.Category3"),
                "department_category4": sale.get("Department.Category4"),
                "department_category5": sale.get("Department.Category5"),
                
                # Концепция
                "conception": sale.get("Conception"),
                "conception_code": sale.get("Conception.Code"),
                
                # Заказ
                "order_id": sale.get("UniqOrderId.Id"),
                "order_num": sale.get("OrderNum"),
                "order_items": sale.get("OrderItems"),
                "order_type": sale.get("OrderType"),
                "order_type_id": sale.get("OrderType.Id"),
                "order_service_type": sale.get("OrderServiceType"),
                "order_comment": sale.get("OrderComment"),
                "order_deleted": sale.get("OrderDeleted"),
                
                # Время заказа
                "open_time": sale.get("OpenTime"),
                "close_time": sale.get("CloseTime"),
                "precheque_time": sale.get("PrechequeTime"),
                "open_date_typed": open_date_typed_data.get("Typed"),
                
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
                "dish_id": sale.get("DishId"),
                "dish_name": sale.get("DishName"),
                "dish_code": sale.get("DishCode"),
                "dish_code_quick": sale.get("DishCode.Quick"),
                "dish_foreign_name": sale.get("DishForeignName"),
                "dish_full_name": sale.get("DishFullName"),
                "dish_type": sale.get("DishType"),
                "dish_measure_unit": sale.get("DishMeasureUnit"),
                "dish_amount_int": sale.get("DishAmountInt"),
                "dish_amount_int_per_order": sale.get("DishAmountInt.PerOrder"),
                
                # Категория блюда
                "dish_category": dish_category_data.get("Name"),
                "dish_category_id": dish_category_data.get("Id"),
                "dish_category_accounting": dish_category_data.get("Accounting"),
                "dish_category_accounting_id": dish_category_data.get("Accounting.Id"),
                
                # Группа блюда
                "dish_group": dish_group_data.get("Name"),
                "dish_group_id": dish_group_data.get("Id"),
                "dish_group_num": dish_group_data.get("Num"),
                "dish_group_hierarchy": dish_group_data.get("Hierarchy"),
                "dish_group_top_parent": dish_group_data.get("TopParent"),
                "dish_group_second_parent": dish_group_data.get("SecondParent"),
                "dish_group_third_parent": dish_group_data.get("ThirdParent"),
                
                # Теги блюда
                "dish_tag_id": dish_tag_data.get("Id"),
                "dish_tag_name": dish_tag_data.get("Name"),
                "dish_tags_ids_combo": dish_tags_data.get("IdsCombo"),
                "dish_tags_names_combo": dish_tags_data.get("NamesCombo"),
                
                # Налоговая категория
                "dish_tax_category_id": dish_tax_category_data.get("Id"),
                "dish_tax_category_name": dish_tax_category_data.get("Name"),
                
                # Размер блюда
                "dish_size_id": dish_size_data.get("Id"),
                "dish_size_name": dish_size_data.get("Name"),
                "dish_size_short_name": dish_size_data.get("ShortName"),
                "dish_size_priority": dish_size_data.get("Priority"),
                "dish_size_scale_id": dish_size_scale_data.get("Id"),
                "dish_size_scale_name": dish_size_scale_data.get("Name"),
                
                # Финансовые поля
                "dish_sum_int": sale.get("DishSumInt"),
                "dish_sum_int_average_price_with_vat": sale.get("DishSumInt.averagePriceWithVAT"),
                "dish_discount_sum_int": sale.get("DishDiscountSumInt"),
                "dish_discount_sum_int_average": sale.get("DishDiscountSumInt.average"),
                "dish_discount_sum_int_average_by_guest": sale.get("DishDiscountSumInt.averageByGuest"),
                "dish_discount_sum_int_average_price": sale.get("DishDiscountSumInt.averagePrice"),
                "dish_discount_sum_int_average_price_with_vat": sale.get("DishDiscountSumInt.averagePriceWithVAT"),
                "dish_discount_sum_int_average_without_vat": sale.get("DishDiscountSumInt.averageWithoutVAT"),
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
                "vat_percent": vat_data.get("Percent"),
                "vat_sum": vat_data.get("Sum"),
                
                # Сессия и касса
                "session_id": sale.get("SessionID"),
                "session_num": sale.get("SessionNum"),
                "cash_register_name": sale.get("CashRegisterName"),
                "cash_register_name_serial_number": cash_register_name_data.get("CashRegisterSerialNumber"),
                "cash_register_name_number": cash_register_name_data.get("Number"),
                
                # Ресторанная секция
                "restaurant_section": restaurant_section_data.get("Name"),
                "restaurant_section_id": restaurant_section_data.get("Id"),
                
                # Стол
                "table_num": sale.get("TableNum"),
                
                # Гости
                "guest_num": sale.get("GuestNum"),
                "guest_num_avg": sale.get("GuestNum.Avg"),
                
                # Официант
                "waiter_name": sale.get("WaiterName"),
                "waiter_name_id": sale.get("WaiterName.ID"),
                "order_waiter_id": sale.get("OrderWaiter.Id"),
                "order_waiter_name": sale.get("OrderWaiter.Name"),
                "waiter_team_id": sale.get("WaiterTeam.Id"),
                "waiter_team_name": sale.get("WaiterTeam.Name"),
                
                # Кассир
                "cashier": sale.get("Cashier"),
                "cashier_code": sale.get("Cashier.Code"),
                "cashier_id": sale.get("Cashier.Id"),
                
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
                "bonus_card_number": bonus_data.get("CardNumber"),
                "bonus_sum": bonus_data.get("Sum"),
                "bonus_type": bonus_data.get("Type"),
                
                # Фискальный чек
                "fiscal_cheque_number": sale.get("FiscalChequeNumber"),
                
                # Валюты
                "currencies_currency": currencies_data.get("Currency"),
                "currencies_currency_rate": currencies_data.get("CurrencyRate"),
                "currencies_sum_in_currency": currencies_sum_in_currency.get("sum"),
                
                # Готовка
                "cooking_place": sale.get("CookingPlace"),
                "cooking_place_id": sale.get("CookingPlace.Id"),
                "cooking_place_type": sale.get("CookingPlaceType"),
                
                # Время готовки
                "cooking_cooking_duration_avg": cooking_data.get("CookingDuration.Avg"),
                "cooking_cooking1_duration_avg": cooking_data.get("Cooking1Duration.Avg"),
                "cooking_cooking2_duration_avg": cooking_data.get("Cooking2Duration.Avg"),
                "cooking_cooking3_duration_avg": cooking_data.get("Cooking3Duration.Avg"),
                "cooking_cooking4_duration_avg": cooking_data.get("Cooking4Duration.Avg"),
                "cooking_cooking_late_time_avg": cooking_data.get("CookingLateTime.Avg"),
                "cooking_feed_late_time_avg": cooking_data.get("FeedLateTime.Avg"),
                "cooking_guest_wait_time_avg": cooking_data.get("GuestWaitTime.Avg"),
                "cooking_kitchen_time_avg": cooking_data.get("KitchenTime.Avg"),
                "cooking_serve_number": cooking_data.get("ServeNumber"),
                "cooking_serve_time_avg": cooking_data.get("ServeTime.Avg"),
                "cooking_start_delay_time_avg": cooking_data.get("StartDelayTime.Avg"),
                
                # Время заказа
                "order_time_average_order_time": order_time_data.get("AverageOrderTime"),
                "order_time_average_precheque_time": order_time_data.get("AveragePrechequeTime"),
                "order_time_order_length": order_time_data.get("OrderLength"),
                "order_time_order_length_sum": order_time_data.get("OrderLengthSum"),
                "order_time_precheque_length": order_time_data.get("PrechequeLength"),
                
                # Доставка
                "delivery_is_delivery": delivery_data.get("IsDelivery"),
                "delivery_id": delivery_data.get("Id"),
                "delivery_number": delivery_data.get("Number"),
                "delivery_address": delivery_data.get("Address"),
                "delivery_city": delivery_data.get("City"),
                "delivery_street": delivery_data.get("Street"),
                "delivery_index": delivery_data.get("Index"),
                "delivery_region": delivery_data.get("Region"),
                "delivery_zone": delivery_data.get("Zone"),
                "delivery_phone": delivery_data.get("Phone"),
                "delivery_email": delivery_data.get("Email"),
                "delivery_courier": delivery_data.get("Courier"),
                "delivery_courier_id": delivery_data.get("Courier.Id"),
                "delivery_operator": delivery_data.get("DeliveryOperator"),
                "delivery_operator_id": delivery_data.get("DeliveryOperator.Id"),
                "delivery_service_type": delivery_data.get("ServiceType"),
                "delivery_expected_time": delivery_data.get("ExpectedTime"),
                "delivery_actual_time": delivery_data.get("ActualTime"),
                "delivery_close_time": delivery_data.get("CloseTime"),
                "delivery_cooking_finish_time": delivery_data.get("CookingFinishTime"),
                "delivery_send_time": delivery_data.get("SendTime"),
                "delivery_bill_time": delivery_data.get("BillTime"),
                "delivery_print_time": delivery_data.get("PrintTime"),
                "delivery_delay": delivery_data.get("Delay"),
                "delivery_delay_avg": delivery_data.get("DelayAvg"),
                "delivery_way_duration": delivery_data.get("WayDuration"),
                "delivery_way_duration_avg": delivery_data.get("WayDurationAvg"),
                "delivery_way_duration_sum": delivery_data.get("WayDurationSum"),
                "delivery_cooking_to_send_duration": delivery_data.get("CookingToSendDuration"),
                "delivery_diff_between_actual_delivery_time_and_predicted_delivery_time": delivery_data.get("DiffBetweenActualDeliveryTimeAndPredictedDeliveryTime"),
                "delivery_predicted_cooking_complete_time": delivery_data.get("PredictedCookingCompleteTime"),
                "delivery_predicted_delivery_time": delivery_data.get("PredictedDeliveryTime"),
                "delivery_customer_name": delivery_data.get("CustomerName"),
                "delivery_customer_phone": delivery_data.get("CustomerPhone"),
                "delivery_customer_email": delivery_data.get("CustomerEmail"),
                "delivery_customer_card_number": delivery_data.get("CustomerCardNumber"),
                "delivery_customer_card_type": delivery_data.get("CustomerCardType"),
                "delivery_customer_comment": delivery_data.get("CustomerComment"),
                "delivery_customer_created_date_typed": delivery_data.get("CustomerCreatedDateTyped"),
                "delivery_customer_marketing_source": delivery_data.get("CustomerMarketingSource"),
                "delivery_customer_opinion_comment": delivery_data.get("CustomerOpinionComment"),
                "delivery_delivery_comment": delivery_data.get("DeliveryComment"),
                "delivery_cancel_cause": delivery_data.get("CancelCause"),
                "delivery_cancel_comment": delivery_data.get("CancelComment"),
                "delivery_marketing_source": delivery_data.get("MarketingSource"),
                "delivery_external_cartography_id": delivery_data.get("ExternalCartographyId"),
                "delivery_source_key": delivery_data.get("SourceKey"),
                "delivery_ecs_service": delivery_data.get("EcsService"),
                
                # Оценки доставки
                "delivery_avg_mark": delivery_data.get("AvgMark"),
                "delivery_avg_food_mark": delivery_data.get("AvgFoodMark"),
                "delivery_avg_courier_mark": delivery_data.get("AvgCourierMark"),
                "delivery_avg_operator_mark": delivery_data.get("AvgOperatorMark"),
                "delivery_aggregated_avg_mark": delivery_data.get("AggregatedAvgMark"),
                "delivery_aggregated_avg_food_mark": delivery_data.get("AggregatedAvgFoodMark"),
                "delivery_aggregated_avg_courier_mark": delivery_data.get("AggregatedAvgCourierMark"),
                "delivery_aggregated_avg_operator_mark": delivery_data.get("AggregatedAvgOperatorMark"),
                
                # Скидки заказа
                "order_discount_guest_card": order_discount_data.get("GuestCard"),
                "order_discount_type": order_discount_data.get("Type"),
                "order_discount_type_ids": order_discount_data.get("Type.IDs"),
                
                # Наценки заказа
                "order_increase_type": order_increase_data.get("Type"),
                "order_increase_type_ids": order_increase_data.get("Type.IDs"),
                
                # Событие продажи товара
                "item_sale_event_discount_type": sale.get("ItemSaleEventDiscountType"),
                "item_sale_event_discount_type_combo_amount": item_sale_event_discount_type_data.get("ComboAmount"),
                "item_sale_event_discount_type_discount_amount": item_sale_event_discount_type_data.get("DiscountAmount"),
                
                # Платежная транзакция
                "payment_transaction_id": payment_transaction_data.get("Id"),
                "payment_transaction_ids": payment_transaction_data.get("Ids"),
                
                # Тип операции
                "operation_type": sale.get("OperationType"),
                
                # Контрагент
                "counteragent_name": sale.get("Counteragent.Name"),
                
                # Кредитный пользователь
                "credit_user": credit_user_data.get("Name"),
                "credit_user_company": credit_user_data.get("Company"),
                
                # Ценовая категория
                "price_category": price_category_data.get("Name"),
                "price_category_card": sale.get("PriceCategoryCard"),
                "price_category_discount_card_owner": sale.get("PriceCategoryDiscountCardOwner"),
                "price_category_user_card_owner": sale.get("PriceCategoryUserCardOwner"),
                
                # Стоимость продукта
                "product_cost_base_mark_up": product_cost_base_data.get("MarkUp"),
                "product_cost_base_one_item": product_cost_base_data.get("OneItem"),
                "product_cost_base_percent": product_cost_base_data.get("Percent"),
                "product_cost_base_percent_without_vat": product_cost_base_data.get("PercentWithoutVAT"),
                "product_cost_base_product_cost": product_cost_base_data.get("ProductCost"),
                "product_cost_base_profit": product_cost_base_data.get("Profit"),
                
                # Стимулирующая сумма
                "incentive_sum_base_sum": incentive_sum_base_data.get("Sum"),
                
                # Процент от итога
                "percent_of_summary_by_col": percent_of_summary_data.get("ByCol"),
                "percent_of_summary_by_row": percent_of_summary_data.get("ByRow"),
                
                # Продано с блюдом
                "sold_with_dish": sold_with_dish_data.get("Name"),
                "sold_with_dish_id": sold_with_dish_data.get("Id"),
                "sold_with_item_id": sale.get("SoldWithItem.Id"),
                
                # Склад
                "store_id": store_data.get("Id"),
                "store_name": store_data.get("Name"),
                "store_to": sale.get("StoreTo"),
                
                # Ресторанная группа
                "restoraunt_group": restoraunt_group_data.get("Name"),
                "restoraunt_group_id": restoraunt_group_data.get("Id"),
                
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
                "dish_service_print_time_max": dish_service_print_time_data.get("Max"),
                "dish_service_print_time_open_to_last_print_duration": dish_service_print_time_data.get("OpenToLastPrintDuration"),
                
                # Временные группировки по минутам
                "open_time_minutes15": open_time_data.get("Minutes15"),
                "close_time_minutes15": close_time_data.get("Minutes15"),
                
                # Внешние данные
                "public_external_data": sale.get("PublicExternalData"),
                "public_external_data_xml": sale.get("PublicExternalData.Xml")
            }
            parsed_sales.append(parsed_sale)
        
        logger.info(f"Парсинг продаж: {len(parsed_sales)} записей")
        return parsed_sales


# Глобальный экземпляр парсера
iiko_parser = IikoParser()
