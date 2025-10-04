import httpx
import logging
from typing import Optional, Dict, Any, List
from enum import Enum
import config
from datetime import datetime, timedelta

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
        self.organization_id = config.IIKO_ORGANIZATION_ID
        self.timeout = 30

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
        return await self._make_request(
            IikoApiType.CLOUD,
            "/organizations"
        )

    async def get_cloud_menu(self, organization_id: Optional[str] = None) -> Optional[Dict[Any, Any]]:
        """Получение меню (Cloud API)"""
        org_id = organization_id or self.organization_id
        return await self._make_request(
            IikoApiType.CLOUD,
            "/nomenclature",
            method="POST",
            data={"organizationId": org_id}
        )

    async def get_cloud_employees(self, organization_id: Optional[str] = None) -> Optional[List[Dict[Any, Any]]]:
        """Получение сотрудников (Cloud API)"""
        org_id = organization_id or self.organization_id
        return await self._make_request(
            IikoApiType.CLOUD,
            "/employees",
            method="POST",
            data={"organizationId": org_id}
        )

    # Server API методы
    async def get_server_organizations(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение списка организаций (Server API)"""
        return await self._make_request(
            IikoApiType.SERVER,
            "/organizations"
        )

    async def get_server_menu(self, organization_id: Optional[str] = None) -> Optional[Dict[Any, Any]]:
        """Получение меню (Server API)"""
        org_id = organization_id or self.organization_id
        return await self._make_request(
            IikoApiType.SERVER,
            "/nomenclature",
            method="POST",
            data={"organizationId": org_id}
        )

    async def get_server_employees(self, organization_id: Optional[str] = None) -> Optional[List[Dict[Any, Any]]]:
        """Получение сотрудников (Server API)"""
        org_id = organization_id or self.organization_id
        return await self._make_request(
            IikoApiType.SERVER,
            "/employees",
            method="POST",
            data={"organizationId": org_id}
        )

    async def get_server_orders(
        self, 
        organization_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> Optional[List[Dict[Any, Any]]]:
        """Получение заказов (Server API)"""
        org_id = organization_id or self.organization_id
        
        # Если даты не указаны, берем последние 7 дней
        if not from_date:
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        return await self._make_request(
            IikoApiType.SERVER,
            "/orders",
            method="POST",
            data={
                "organizationId": org_id,
                "from": from_date,
                "to": to_date
            }
        )

    # Универсальные методы (пробуют оба API)
    async def get_menu(self, organization_id: Optional[str] = None, prefer_cloud: bool = True) -> Optional[Dict[Any, Any]]:
        """Получение меню (пробует Cloud, затем Server)"""
        if prefer_cloud:
            result = await self.get_cloud_menu(organization_id)
            if result:
                return result
            return await self.get_server_menu(organization_id)
        else:
            result = await self.get_server_menu(organization_id)
            if result:
                return result
            return await self.get_cloud_menu(organization_id)

    async def get_employees(self, organization_id: Optional[str] = None, prefer_cloud: bool = True) -> Optional[List[Dict[Any, Any]]]:
        """Получение сотрудников (пробует Cloud, затем Server)"""
        if prefer_cloud:
            result = await self.get_cloud_employees(organization_id)
            if result:
                return result
            return await self.get_server_employees(organization_id)
        else:
            result = await self.get_server_employees(organization_id)
            if result:
                return result
            return await self.get_cloud_employees(organization_id)

    async def get_organizations(self, prefer_cloud: bool = True) -> Optional[List[Dict[Any, Any]]]:
        """Получение организаций (пробует Cloud, затем Server)"""
        if prefer_cloud:
            result = await self.get_cloud_organizations()
            if result:
                return result
            return await self.get_server_organizations()
        else:
            result = await self.get_server_organizations()
            if result:
                return result
            return await self.get_cloud_organizations()

    def clear_tokens(self):
        """Очистка токенов (для принудительного обновления)"""
        self.cloud_token = None
        self.server_token = None
        self.cloud_token_expires = None
        self.server_token_expires = None
        logger.info("Токены iiko API очищены")

# Глобальный экземпляр сервиса
iiko_service = IikoService()
