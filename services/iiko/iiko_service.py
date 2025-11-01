import json
import httpx
import logging
import asyncio
from typing import Optional, Dict, Any, List
from enum import Enum
import config
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from services.iiko import data_frames

logger = logging.getLogger(__name__)

class IikoApiType(Enum):
    CLOUD = "cloud"
    SERVER = "server"

class IikoService:
    def __init__(self):
        self.cloud_token = None
        self.server_token = None
        self.cloud_token_expires = None
        self.server_token_expires = None
        
        # Cloud API настройки
        self.cloud_base_url = config.IIKO_CLOUD_API_URL
        self.cloud_login = config.IIKO_CLOUD_LOGIN  # apiLogin для Cloud API
        
        # Server API настройки
        self.server_base_url = config.IIKO_SERVER_API_URL
        self.server_login = config.IIKO_SERVER_LOGIN  # логин для Server API
        self.server_password = config.IIKO_SERVER_PASSWORD
        
        # Общие настройки
        self.timeout = 60  # Увеличиваем общий timeout до 60 секунд
        self.cloud_request_delay = 60  # Задержка между Cloud API запросами (секунды)
        self.server_request_delay = 0.5  # Задержка между Server API запросами (секунды)

    async def _add_request_delay(self, api_type: IikoApiType):
        """Добавляет задержку между запросами для предотвращения rate limiting"""
        if api_type == IikoApiType.CLOUD:
            await asyncio.sleep(self.cloud_request_delay)
        elif api_type == IikoApiType.SERVER:
            await asyncio.sleep(self.server_request_delay)

    async def _get_cloud_token(self) -> Optional[str]:
        """Получение токена для Cloud API"""
        if self.cloud_token and self.cloud_token_expires and datetime.now() < self.cloud_token_expires:
            return self.cloud_token
            
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.cloud_base_url}/api/1/access_token",
                    json={
                        "apiLogin": self.cloud_login
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                self.cloud_token = data.get("token")
                
                # Токен действует 1 час, обновляем за 5 минут до истечения
                self.cloud_token_expires = datetime.now() + timedelta(minutes=55)
                
                logger.info("Cloud API токен успешно получен")
                return self.cloud_token
                
        except Exception as e:
            logger.error(f"Ошибка получения Cloud API токена: {e}")
            return None

    async def _get_server_token(self) -> Optional[str]:
        """Получение токена для Server API"""
        if self.server_token and self.server_token_expires and datetime.now() < self.server_token_expires:
            return self.server_token
            
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.server_base_url}/resto/api/auth",
                    params={
                        "login": self.server_login,
                        "pass": self.server_password
                    }
                )
                response.raise_for_status()
                
                # Server API возвращает токен как строку
                self.server_token = response.text.strip()
                
                # Токен действует 1 час, обновляем за 5 минут до истечения
                self.server_token_expires = datetime.now() + timedelta(minutes=55)
                
                logger.info("Server API токен успешно получен")
                return self.server_token
                
        except Exception as e:
            logger.error(f"Ошибка получения Server API токена: {e}")
            return None

    async def _make_request(
        self, 
        api_type: IikoApiType, 
        endpoint: str, 
        method: str = "GET",
        data: Optional[Dict[Any, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[Any, Any]]:
        """Универсальный метод для запросов к iiko API"""
        
        # Добавляем задержку для предотвращения rate limiting
        await self._add_request_delay(api_type)
        
        # Получаем токен в зависимости от типа API
        if api_type == IikoApiType.CLOUD:
            token = await self._get_cloud_token()
            base_url = self.cloud_base_url
        else:
            token = await self._get_server_token()
            base_url = self.server_base_url
            
        if not token:
            logger.error(f"Не удалось получить токен для {api_type.value} API")
            return None
            
        # Разные способы авторизации для разных API
        if api_type == IikoApiType.CLOUD:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            # Для Cloud API токен в headers
            request_params = params or {}
        else:
            headers = {
                "Content-Type": "application/json"
            }
            # Для Server API токен в параметрах
            request_params = params or {}
            request_params["key"] = token
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method.upper() == "GET":
                    response = await client.get(
                        f"{base_url}{endpoint}",
                        headers=headers,
                        params=request_params
                    )
                elif method.upper() == "POST":
                    response = await client.post(
                        f"{base_url}{endpoint}",
                        headers=headers,
                        json=data,
                        params=request_params
                    )
                elif method.upper() == "PUT":
                    response = await client.put(
                        f"{base_url}{endpoint}",
                        headers=headers,
                        json=data,
                        params=request_params
                    )
                else:
                    raise ValueError(f"Неподдерживаемый HTTP метод: {method}")
                
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP ошибка {api_type.value} API: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Ошибка запроса к {api_type.value} API: {e}")
            return None

    # Cloud API методы
    async def get_cloud_organizations(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение списка организаций (Cloud API)"""
        result = await self._make_request(
            IikoApiType.CLOUD,
            "/api/1/organizations",
            method="POST",
            data={}
        )
        # Cloud API возвращает список организаций напрямую
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "organizations" in result:
            return result["organizations"]
        return None

    async def get_cloud_menu(self, organization_id: Optional[str] = None) -> Optional[List[Dict[Any, Any]]]:
        """Получение меню (Cloud API) - возвращает только продукты"""
        if organization_id:
            menu_data = await self._make_request(
                IikoApiType.CLOUD,
                "/api/1/nomenclature",
                method="POST",
                data={"organizationId": organization_id}
            )
            if menu_data:
                return menu_data.get("products", [])
            return []
        else:
            # Если organization_id не указан, получаем все организации и их меню
            organizations = await self.get_organizations()
            if not organizations:
                return []
            
            all_products = []
            
            for org in organizations:
                org_id = org.get("id")
                if org_id:
                    menu_data = await self._make_request(
                        IikoApiType.CLOUD,
                        "/api/1/nomenclature",
                        method="POST",
                        data={"organizationId": org_id}
                    )
                    if menu_data:
                        # Добавляем продукты из всех организаций
                        all_products.extend(menu_data.get("products", []))
            
            return all_products

    async def get_cloud_employees(self, organization_id: Optional[str] = None) -> Optional[List[Dict[Any, Any]]]:
        """Получение сотрудников (Cloud API)"""
        if organization_id:
            return await self._make_request(
                IikoApiType.CLOUD,
                "/api/1/employees",
                method="POST",
                data={"organizationId": organization_id}
            )
        else:
            # Если organization_id не указан, получаем сотрудников из всех организаций
            organizations = await self.get_organizations()
            if not organizations:
                return None
            
            all_employees = []
            for org in organizations:
                org_id = org.get("id")
                if org_id:
                    employees = await self._make_request(
                        IikoApiType.CLOUD,
                        "/api/1/employees",
                        method="POST",
                        data={"organizationId": org_id}
                    )
                    if employees:
                        all_employees.extend(employees)
            
            return all_employees

    async def get_cloud_employee_by_id(self, organization_id: Optional[str] = None, employee_id: str = None) -> Optional[Dict[Any, Any]]:
        """Получение сотрудника по ID (Cloud API)"""
        if not organization_id or not employee_id:
            return None
        return await self._make_request(
            IikoApiType.CLOUD,
            "/api/1/employees/info",
            method="POST",
            data={"organizationId": organization_id, "employeeId": employee_id}
        )

    async def get_cloud_restaurant_sections(self, organization_id: Optional[str] = None) -> Optional[List[Dict[Any, Any]]]:
        """Получение секций ресторана (Cloud API)"""
        if organization_id:
            # Сначала получаем терминалы для организации
            terminals_data = await self.get_cloud_terminals(organization_id)
            if not terminals_data:
                logger.warning(f"Не удалось получить терминалы для организации {organization_id}")
                return []
            
            # Извлекаем ID терминальных групп
            terminal_group_ids = []
            for terminal in terminals_data:
                terminal_id = terminal.get("id")
                if terminal_id:
                    terminal_group_ids.append(terminal_id)
            
            if not terminal_group_ids:
                logger.warning(f"Не найдены терминальные группы для организации {organization_id}")
                return []
            
            # Запрашиваем секции через API
            response = await self._make_request(
                IikoApiType.CLOUD,
                "/api/1/reserve/available_restaurant_sections",
                method="POST",
                data={
                    "organizationId": organization_id,
                    "terminalGroupIds": terminal_group_ids
                }
            )
            
            if not response or not isinstance(response, dict):
                logger.warning(f"Не удалось получить секции для организации {organization_id}")
                return []
            
            # Извлекаем секции
            sections = []
            if "restaurantSections" in response:
                restaurant_sections = response["restaurantSections"]
                if isinstance(restaurant_sections, list):
                    for section in restaurant_sections:
                        if isinstance(section, dict):
                            sections.append({
                                "id": section.get("id"),
                                "name": section.get("name", ""),
                                "terminalGroupId": section.get("terminalGroupId")
                            })
            
            logger.info(f"Получено {len(sections)} секций для организации {organization_id}")
            return sections
        else:
            # Если organization_id не указан, получаем секции из всех организаций
            organizations = await self.get_organizations()
            if not organizations:
                return []
            
            all_sections = []
            for org in organizations:
                org_id = org.get("id")
                if org_id:
                    sections = await self.get_cloud_restaurant_sections(org_id)  # Рекурсивный вызов
                    if sections:
                        all_sections.extend(sections)
            
            return all_sections

    async def get_cloud_tables(self, organization_id: Optional[str] = None) -> Optional[List[Dict[Any, Any]]]:
        """Получение столов ресторана (Cloud API)"""
        if organization_id:
            # Сначала получаем терминалы для организации
            terminals_data = await self.get_cloud_terminals(organization_id)
            if not terminals_data:
                logger.warning(f"Не удалось получить терминалы для организации {organization_id}")
                return []
            
            # Извлекаем ID терминальных групп
            terminal_group_ids = []
            for terminal in terminals_data:
                # ID терминальной группы находится в поле "id" каждого терминала
                terminal_id = terminal.get("id")
                if terminal_id:
                    terminal_group_ids.append(terminal_id)
                    logger.debug(f"Найден терминал с ID: {terminal_id}, название: {terminal.get('name', 'N/A')}")
            
            if not terminal_group_ids:
                logger.warning(f"Не найдены терминальные группы для организации {organization_id}. Получено терминалов: {len(terminals_data) if terminals_data else 0}")
                return []
            
            logger.info(f"Найдено {len(terminal_group_ids)} терминальных групп для организации {organization_id}")
            
            # Запрашиваем столы через API
            response = await self._make_request(
                IikoApiType.CLOUD,
                "/api/1/reserve/available_restaurant_sections",
                method="POST",
                data={
                    "organizationId": organization_id,
                    "terminalGroupIds": terminal_group_ids
                }
            )
            
            if not response:
                logger.warning(f"Не удалось получить столы для организации {organization_id}")
                return []
            
            # Извлекаем все столы из всех секций ресторана
            # Структура ответа: {"restaurantSections": [...], "revision": ...}
            # Каждая секция содержит: {"id": ..., "terminalGroupId": ..., "name": ..., "tables": [...]}
            all_tables = []
            
            # Проверяем, что response это словарь
            if not isinstance(response, dict):
                logger.error(f"Ожидался словарь в ответе, получен тип: {type(response)}")
                return []
            
            if "restaurantSections" in response:
                sections = response["restaurantSections"]
                if not isinstance(sections, list):
                    logger.error(f"restaurantSections должен быть списком, получен тип: {type(sections)}")
                    return []
                
                for section in sections:
                    # Проверяем, что section это словарь
                    if not isinstance(section, dict):
                        logger.warning(f"Секция должна быть словарем, получен тип: {type(section)}, пропускаем")
                        continue
                    
                    section_id = section.get("id")
                    section_name = section.get("name", "")
                    terminal_group_id = section.get("terminalGroupId")
                    
                    if "tables" in section:
                        tables = section["tables"]
                        if not isinstance(tables, list):
                            logger.warning(f"tables должен быть списком в секции {section_id}, получен тип: {type(tables)}, пропускаем")
                            continue
                        
                        for table in tables:
                            # Проверяем, что table это словарь
                            if not isinstance(table, dict):
                                logger.warning(f"Стол должен быть словарем, получен тип: {type(table)}, пропускаем")
                                continue
                            
                            # Добавляем к каждому столу информацию о секции
                            table_with_section = table.copy()
                            table_with_section["sectionId"] = section_id
                            table_with_section["restaurantSectionName"] = section_name
                            table_with_section["terminalGroupId"] = terminal_group_id
                            all_tables.append(table_with_section)
            
            logger.info(f"Извлечено {len(all_tables)} столов из {len(response.get('restaurantSections', []))} секций для организации {organization_id}")
            return all_tables
        else:
            # Если organization_id не указан, получаем столы из всех организаций
            organizations = await self.get_organizations()
            if not organizations:
                return []
            
            all_tables = []
            for org in organizations:
                org_id = org.get("id")
                if org_id:
                    tables_data = await self.get_cloud_tables(org_id)  # Рекурсивный вызов
                    if tables_data:
                        all_tables.extend(tables_data)
            
            return all_tables

    async def get_cloud_terminals(self, organization_id: Optional[str] = None) -> Optional[List[Dict[Any, Any]]]:
        """Получение терминалов (Cloud API)"""
        if organization_id:
            result = await self._make_request(
                IikoApiType.CLOUD,
                "/api/1/terminal_groups",
                method="POST",
                data={"organizationIds": [organization_id]}
            )
            logger.info(f"Терминалы: {json.dumps(result, indent=4, ensure_ascii=False)}")
            # Извлекаем терминалы из структуры ответа
            if result and "terminalGroups" in result:
                terminals = []
                for group in result["terminalGroups"]:
                    if "items" in group:
                        terminals.extend(group["items"])
                return terminals
            return None
        else:
            # Если organization_id не указан, получаем терминалы из всех организаций
            organizations = await self.get_organizations()
            if not organizations:
                return None
            
            all_terminals = []
            for org in organizations:
                org_id = org.get("id")
                if org_id:
                    terminals = await self.get_cloud_terminals(org_id)
                    logger.info(f"Терминалы: {json.dumps(terminals, indent=4, ensure_ascii=False)}")
                    if terminals:
                        all_terminals.extend(terminals)
            
            return all_terminals

    async def get_cloud_orders_by_table(self, organization_id: Optional[str] = None, table_id: str = None) -> Optional[List[Dict[Any, Any]]]:
        """Получение заказов по столу (Cloud API)"""
        if not organization_id or not table_id:
            return None
        return await self._make_request(
            IikoApiType.CLOUD,
            "/api/1/order/by_table",
            method="POST",
            data={"organizationId": organization_id, "tableId": table_id}
        )

    # Server API методы
    async def get_server_organizations(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение списка организаций (Server API) - НЕ ПОДДЕРЖИВАЕТСЯ"""
        # Server API не имеет эндпоинта для получения организаций
        logger.warning("Server API не поддерживает получение организаций")
        return None

    async def get_server_products(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение продуктов (Server API)"""
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/v2/entities/products/list"
        )

    async def get_server_menu(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение меню (Server API) - алиас для get_server_products"""
        return await self.get_server_products()

    async def get_server_product_groups(self, date_from: str = None, date_to: str = None) -> Optional[List[Dict[Any, Any]]]:
        """Получение групп продуктов (Server API)"""
        params = {}
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/v2/entities/products/group/list",
            params=params
        )

    async def get_server_product_categories(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение категорий продуктов (Server API)"""
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/v2/entities/products/category/list"
        )

    async def get_server_employees(self, include_deleted: bool = True) -> Optional[List[Dict[Any, Any]]]:
        """Получение сотрудников (Server API) - возвращает XML"""
        params = {}
        if include_deleted:
            params["includeDeleted"] = "true"
        
        # Получаем токен
        token = await self._get_server_token()
        if not token:
            logger.error("Не удалось получить токен для Server API")
            return None
        
        # Добавляем токен в параметры
        params["key"] = token
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.server_base_url}/resto/api/employees"
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    # Server API возвращает XML, нужно парсить его
                    xml_content = response.text
                    return await self._parse_xml_employees(xml_content)
                else:
                    logger.error(f"HTTP ошибка server API: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка запроса к server API: {e}")
            return None

    async def _parse_xml_employees(self, xml_content: str) -> Optional[List[Dict[Any, Any]]]:
        """Парсинг XML ответа с сотрудниками"""
        try:
            root = ET.fromstring(xml_content)
            employees = []
            
            for employee_elem in root.findall('employee'):
                employee_data = {}
                
                # Основные поля
                employee_data['id'] = employee_elem.find('id').text if employee_elem.find('id') is not None else None
                employee_data['code'] = employee_elem.find('code').text if employee_elem.find('code') is not None else None
                employee_data['name'] = employee_elem.find('name').text if employee_elem.find('name') is not None else None
                employee_data['login'] = employee_elem.find('login').text if employee_elem.find('login') is not None else None
                
                # Роли
                employee_data['mainRoleId'] = employee_elem.find('mainRoleId').text if employee_elem.find('mainRoleId') is not None else None
                employee_data['mainRoleCode'] = employee_elem.find('mainRoleCode').text if employee_elem.find('mainRoleCode') is not None else None
                
                # Собираем множественные поля
                roles_ids = []
                for role_id in employee_elem.findall('rolesIds'):
                    if role_id.text:
                        roles_ids.append(role_id.text)
                employee_data['rolesIds'] = roles_ids
                
                role_codes = []
                for role_code in employee_elem.findall('roleCodes'):
                    if role_code.text:
                        role_codes.append(role_code.text)
                employee_data['roleCodes'] = role_codes
                
                # Отделы
                employee_data['preferredDepartmentCode'] = employee_elem.find('preferredDepartmentCode').text if employee_elem.find('preferredDepartmentCode') is not None else None
                
                department_codes = []
                for dept_code in employee_elem.findall('departmentCodes'):
                    if dept_code.text:
                        department_codes.append(dept_code.text)
                employee_data['departmentCodes'] = department_codes
                
                responsibility_department_codes = []
                for resp_dept_code in employee_elem.findall('responsibilityDepartmentCodes'):
                    if resp_dept_code.text:
                        responsibility_department_codes.append(resp_dept_code.text)
                employee_data['responsibilityDepartmentCodes'] = responsibility_department_codes
                
                # Булевые поля
                employee_data['deleted'] = employee_elem.find('deleted').text == 'true' if employee_elem.find('deleted') is not None else False
                employee_data['supplier'] = employee_elem.find('supplier').text == 'true' if employee_elem.find('supplier') is not None else False
                employee_data['employee'] = employee_elem.find('employee').text == 'true' if employee_elem.find('employee') is not None else False
                employee_data['client'] = employee_elem.find('client').text == 'true' if employee_elem.find('client') is not None else False
                employee_data['representsStore'] = employee_elem.find('representsStore').text == 'true' if employee_elem.find('representsStore') is not None else False
                
                # Дополнительные поля
                employee_data['cardNumber'] = employee_elem.find('cardNumber').text if employee_elem.find('cardNumber') is not None else None
                employee_data['taxpayerIdNumber'] = employee_elem.find('taxpayerIdNumber').text if employee_elem.find('taxpayerIdNumber') is not None else None
                employee_data['snils'] = employee_elem.find('snils').text if employee_elem.find('snils') is not None else None
                
                employees.append(employee_data)
            
            logger.info(f"Парсинг XML сотрудников: {len(employees)} записей")
            return employees
            
        except Exception as e:
            logger.error(f"Ошибка парсинга XML сотрудников: {e}")
            return None

    async def _parse_xml_roles(self, xml_content: str) -> Optional[List[Dict[Any, Any]]]:
        """Парсинг XML ответа с ролями"""
        try:
            root = ET.fromstring(xml_content)
            roles = []
            
            for role_elem in root.findall('role'):
                role_data = {}
                
                # Основные поля
                role_data['id'] = role_elem.find('id').text if role_elem.find('id') is not None else None
                role_data['code'] = role_elem.find('code').text if role_elem.find('code') is not None else None
                role_data['name'] = role_elem.find('name').text if role_elem.find('name') is not None else None
                
                # Финансовые поля
                payment_per_hour = role_elem.find('paymentPerHour')
                if payment_per_hour is not None and payment_per_hour.text:
                    try:
                        role_data['paymentPerHour'] = float(payment_per_hour.text)
                    except ValueError:
                        role_data['paymentPerHour'] = 0.0
                else:
                    role_data['paymentPerHour'] = 0.0
                
                steady_salary = role_elem.find('steadySalary')
                if steady_salary is not None and steady_salary.text:
                    try:
                        role_data['steadySalary'] = float(steady_salary.text)
                    except ValueError:
                        role_data['steadySalary'] = 0.0
                else:
                    role_data['steadySalary'] = 0.0
                
                # Тип расписания
                role_data['scheduleType'] = role_elem.find('scheduleType').text if role_elem.find('scheduleType') is not None else None
                
                # Булевое поле
                role_data['deleted'] = role_elem.find('deleted').text == 'true' if role_elem.find('deleted') is not None else False
                
                roles.append(role_data)
            
            logger.info(f"Парсинг XML ролей: {len(roles)} записей")
            return roles
            
        except Exception as e:
            logger.error(f"Ошибка парсинга XML ролей: {e}")
            return None

    async def get_server_departments(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение отделов (Server API)"""
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/corporation/departments"
        )

    async def get_server_roles(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение ролей сотрудников (Server API) - возвращает XML"""
        # Получаем токен
        token = await self._get_server_token()
        if not token:
            logger.error("Не удалось получить токен для Server API")
            return None
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.server_base_url}/resto/api/employees/roles"
                params = {"key": token}
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    # Server API возвращает XML, нужно парсить его
                    xml_content = response.text
                    return await self._parse_xml_roles(xml_content)
                else:
                    logger.error(f"HTTP ошибка server API: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка запроса к server API: {e}")
            return None

    async def get_server_schedule_types(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение типов расписания (Server API)"""
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/employees/schedule/types"
        )

    async def get_server_attendance_types(self, include_deleted: bool = True) -> Optional[List[Dict[Any, Any]]]:
        """Получение типов посещаемости (Server API)"""
        params = {}
        if include_deleted:
            params["includeDeleted"] = "true"
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/employees/attendance/types",
            params=params
        )

    async def get_transactions(self, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None) -> Optional[List[Dict[Any, Any]]]:
        """Получение транзакций (Server API) для заданного периода"""
        
        params = data_frames.iiko_transactions_data_frame.copy()
        params["filters"]["DateTime.Typed"]["from"] = from_date.isoformat()
        params["filters"]["DateTime.Typed"]["to"] = to_date.isoformat()
        result = await self.get_server_transactions_report(params)
        if result and "data" in result:
            logger.info(f"Получено транзакций за период с {from_date.isoformat()} по {to_date.isoformat()}: {len(result['data'])}")
            return result["data"]
        return None

    async def get_sales(self, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None) -> Optional[List[Dict[Any, Any]]]:
        """Получение продаж (Server API) для заданного периода"""

        params = data_frames.iiko_sales_data_frame.copy()
        params["filters"]["OpenDate.Typed"]["from"] = from_date.isoformat()
        params["filters"]["OpenDate.Typed"]["to"] = to_date.isoformat()
        result = await self.get_server_sales_report(params)
        
        if result and "data" in result:
            logger.info(f"Получено продаж за период с {from_date.isoformat()} по {to_date.isoformat()}: {len(result['data'])}")
            return result["data"]
        return None

    async def get_server_transactions_report(self, report_data: Dict[Any, Any]) -> Optional[Dict[Any, Any]]:
        """Получение отчета по транзакциям (Server API)"""
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/v2/reports/olap",
            method="POST",
            data=report_data
        )

    async def get_server_sales_report(self, report_data: Dict[Any, Any]) -> Optional[Dict[Any, Any]]:
        """Получение отчета по продажам (Server API)"""
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/v2/reports/olap",
            method="POST",
            data=report_data
        )

    async def get_server_deliveries_report(self, report_data: Dict[Any, Any]) -> Optional[Dict[Any, Any]]:
        """Получение отчета по доставкам (Server API)"""
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/v2/reports/olap",
            method="POST",
            data=report_data
        )

    async def get_server_report_presets(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение пресетов отчетов (Server API)"""
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/v2/reports/olap/presets"
        )

    async def get_server_report_fields(self, report_type: str) -> Optional[List[Dict[Any, Any]]]:
        """Получение полей отчетов (Server API)"""
        return await self._make_request(
            IikoApiType.SERVER,
            f"/resto/api/v2/reports/olap/columns?reportType={report_type}"
        )

    async def get_server_store_report_presets(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение пресетов складских отчетов (Server API)"""
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/reports/storeReportPresets"
        )

    async def get_server_product_expense_report(self, department: str, date_from: str, date_to: str) -> Optional[Dict[Any, Any]]:
        """Получение отчета по расходу продуктов (Server API)"""
        params = {
            "department": department,
            "dateFrom": date_from,
            "dateTo": date_to
        }
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/reports/productExpense",
            params=params
        )

    async def logout_server(self) -> Optional[Dict[Any, Any]]:
        """Выход из системы (Server API)"""
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/logout"
        )

    # Универсальные методы (пробуют оба API)
    async def get_menu(self, organization_id: Optional[str] = None, prefer_cloud: bool = True) -> Optional[Dict[Any, Any]]:
        """Получение меню (пробует Cloud, затем Server)"""
        if prefer_cloud:
            result = await self.get_cloud_menu(organization_id)
            if result:
                return result
            return await self.get_server_products()
        else:
            result = await self.get_server_products()
            if result:
                return result
            return await self.get_cloud_menu(organization_id)

    async def get_employees(self, organization_id: Optional[str] = None, prefer_cloud: bool = True) -> Optional[List[Dict[Any, Any]]]:
        """Получение сотрудников (только Server API)"""
        result = await self.get_server_employees()
        if result:
            return result
        return None

    async def get_organizations(self, prefer_cloud: bool = True) -> Optional[List[Dict[Any, Any]]]:
        """Получение организаций (только Cloud API)"""
        return await self.get_cloud_organizations()

    async def get_restaurant_sections(self, organization_id: Optional[str] = None, prefer_cloud: bool = True) -> Optional[List[Dict[Any, Any]]]:
        """Получение секций ресторана (пробует Cloud, затем Server)"""
        if prefer_cloud:
            result = await self.get_cloud_restaurant_sections(organization_id)
            if result:
                return result
            # Server API не имеет прямого аналога для секций
            return None
        else:
            result = await self.get_cloud_restaurant_sections(organization_id)
            if result:
                return result
            return None

    async def get_tables(self, organization_id: Optional[str] = None, prefer_cloud: bool = True) -> Optional[List[Dict[Any, Any]]]:
        """Получение столов (пробует Cloud, затем Server)"""
        if prefer_cloud:
            result = await self.get_cloud_tables(organization_id)
            if result:
                return result
            # Server API не имеет прямого аналога для столов
            return None
        else:
            result = await self.get_cloud_tables(organization_id)
            if result:
                return result
            return None

    async def get_terminals(self, organization_id: Optional[str] = None, prefer_cloud: bool = True) -> Optional[List[Dict[Any, Any]]]:
        """Получение терминалов (пробует Cloud, затем Server)"""
        if prefer_cloud:
            result = await self.get_cloud_terminals(organization_id)
            if result:
                return result
            # Server API не имеет прямого аналога для терминалов
            return None
        else:
            result = await self.get_cloud_terminals(organization_id)
            if result:
                return result
            return None

    async def get_product_groups(self, date_from: str = None, date_to: str = None, prefer_cloud: bool = False) -> Optional[List[Dict[Any, Any]]]:
        """Получение групп продуктов (только Server API)"""
        return await self.get_server_product_groups(date_from, date_to)

    async def get_product_categories(self, prefer_cloud: bool = False) -> Optional[List[Dict[Any, Any]]]:
        """Получение категорий продуктов (только Server API)"""
        return await self.get_server_product_categories()

    async def get_departments(self, prefer_cloud: bool = False) -> Optional[List[Dict[Any, Any]]]:
        """Получение отделов (только Server API)"""
        return await self.get_server_departments()

    async def get_roles(self, prefer_cloud: bool = False) -> Optional[List[Dict[Any, Any]]]:
        """Получение ролей (только Server API)"""
        return await self.get_server_roles()

    async def get_schedule_types(self, prefer_cloud: bool = False) -> Optional[List[Dict[Any, Any]]]:
        """Получение типов расписания (только Server API)"""
        return await self.get_server_schedule_types()

    async def get_attendance_types(self, prefer_cloud: bool = False) -> Optional[List[Dict[Any, Any]]]:
        """Получение типов посещаемости (только Server API)"""
        return await self.get_server_attendance_types()

    def clear_tokens(self):
        """Очистка токенов (для принудительного обновления)"""
        self.cloud_token = None
        self.server_token = None
        self.cloud_token_expires = None
        self.server_token_expires = None
        logger.info("Токены iiko API очищены")

# Глобальный экземпляр сервиса
iiko_service = IikoService()
