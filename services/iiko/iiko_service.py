import json
import httpx
import logging
import asyncio
import time
import traceback
from typing import Optional, Dict, Any, List
from enum import Enum
import config
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from services.iiko import data_frames

logger = logging.getLogger(__name__)


# =============================================================================
# Политика чанкования iiko-запросов с диапазоном дат (бизнес-решение 2026-05-24)
# =============================================================================
# Лимит iiko Server по «открытому периоду» — 65 дней. У OLAP-отчётов нехватка
# памяти начинается на ~91 дне (зафиксировано инцидентом 2026-05-04).
# Все методы с date-from/date-to чанкуются ПО ДНЯМ. Максимальное окно — 60 дней.
# Если пришёл диапазон > 60 дней — это либо ошибка вызывающего кода, либо
# user-input (тогда возвращаем 400 в роутере до того, как сюда зашло).
MAX_IIKO_DATE_WINDOW_DAYS = 60


def _to_date(value):
    """Привести datetime / date / 'YYYY-MM-DD' к date."""
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    if isinstance(value, datetime):
        return value.date()
    return value  # уже date


def iter_day_chunks(date_from, date_to):
    """Итератор по дням [date_from, date_to] включительно.

    Возвращает кортежи (chunk_start_date, chunk_end_date_exclusive) — для
    использования с iiko-фильтрами в полуоткрытом интервале.
    Бросает ValueError если окно > MAX_IIKO_DATE_WINDOW_DAYS.
    """
    start = _to_date(date_from)
    end = _to_date(date_to)
    if start > end:
        raise ValueError(f"date_from > date_to ({start} > {end})")
    if (end - start).days > MAX_IIKO_DATE_WINDOW_DAYS:
        raise ValueError(
            f"Окно {(end - start).days} дней превышает лимит iiko "
            f"({MAX_IIKO_DATE_WINDOW_DAYS} дней). Чанкование рассчитано на узкое окно — "
            f"для большего диапазона разрезайте на стороне вызывающего."
        )
    current = start
    while current <= end:
        yield current, current + timedelta(days=1)
        current += timedelta(days=1)


def assert_iiko_date_window(date_from, date_to, label: str = ""):
    """Бросает ValueError если окно превышает MAX_IIKO_DATE_WINDOW_DAYS. Без чанкования."""
    start = _to_date(date_from)
    end = _to_date(date_to)
    if start > end:
        raise ValueError(f"{label}: date_from > date_to ({start} > {end})")
    diff = (end - start).days
    if diff > MAX_IIKO_DATE_WINDOW_DAYS:
        raise ValueError(
            f"{label}: окно {diff} дней превышает лимит iiko "
            f"({MAX_IIKO_DATE_WINDOW_DAYS} дней). Уменьшите диапазон."
        )


class IikoApiType(Enum):
    CLOUD = "cloud"
    CLOUD_OLD = "cloud_old"
    SERVER = "server"

class IikoService:
    def __init__(self):
        self.cloud_token = None
        self.server_token = None
        self.cloud_token_expires = None
        self.server_token_expires = None
        self.cloud_old_token = None
        self.cloud_old_token_expires = None

        # Cloud API настройки
        self.cloud_base_url = config.IIKO_CLOUD_API_URL
        self.cloud_login = config.IIKO_CLOUD_LOGIN  # apiLogin для Cloud API
        self.cloud_old_login = config.IIKO_OLD_LOGIN_KEY  # старый apiLogin для заказов

        # Server API настройки
        self.server_base_url = config.IIKO_SERVER_API_URL
        self.server_login = config.IIKO_SERVER_LOGIN  # логин для Server API
        self.server_password = config.IIKO_SERVER_PASSWORD

        # Общие настройки
        self.timeout = 180  # Увеличиваем общий timeout до 3 минут (180 секунд)
        self.cloud_request_delay = config.IIKO_CLOUD_REQUEST_DELAY
        self.server_request_delay = config.IIKO_SERVER_REQUEST_DELAY

        # Трекинг времени последнего запроса для умной задержки
        self._last_server_request_time = None
        self._last_cloud_request_time = None

        # Кеш для снижения нагрузки на iiko API во время sync-сессий
        self._terminals_cache: Dict[str, List] = {}
        self._terminal_groups_cache: Dict[str, List] = {}
        self._organizations_cache: Optional[List] = None

    def clear_sync_cache(self):
        """Очистить кеш sync-сессии"""
        self._terminals_cache.clear()
        self._terminal_groups_cache.clear()
        self._organizations_cache = None

    async def _add_request_delay(self, api_type: IikoApiType):
        """Добавляет задержку между запросами для предотвращения rate limiting.
        Спит только оставшееся время с момента последнего запроса."""
        now = time.monotonic()
        if api_type in (IikoApiType.CLOUD, IikoApiType.CLOUD_OLD):
            if self._last_cloud_request_time is not None:
                elapsed = now - self._last_cloud_request_time
                remaining = self.cloud_request_delay - elapsed
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last_cloud_request_time = time.monotonic()
        elif api_type == IikoApiType.SERVER:
            if self._last_server_request_time is not None:
                elapsed = now - self._last_server_request_time
                remaining = self.server_request_delay - elapsed
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last_server_request_time = time.monotonic()

    async def _get_cloud_token(self) -> Optional[str]:
        """Получение токена для Cloud API"""
        if config.IIKO_REQUESTS_DISABLED:
            logger.warning("[IIKO_DISABLED] Cloud token request пропущен (IIKO_REQUESTS_DISABLED=true)")
            return None
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

    async def _get_cloud_old_token(self) -> Optional[str]:
        """Получение токена для Cloud API (старый ключ — для заказов)"""
        if config.IIKO_REQUESTS_DISABLED:
            logger.warning("[IIKO_DISABLED] Cloud OLD token request пропущен (IIKO_REQUESTS_DISABLED=true)")
            return None
        logger.info(f"[OLD TOKEN] Используется apiLogin (IIKO_OLD_LOGIN_KEY): '{self.cloud_old_login}'")
        if self.cloud_old_token and self.cloud_old_token_expires and datetime.now() < self.cloud_old_token_expires:
            logger.info(f"[OLD TOKEN] Используем кэшированный токен (первые 10 символов): '{self.cloud_old_token[:10]}...'")
            return self.cloud_old_token

        try:
            logger.info(f"[OLD TOKEN] Запрашиваем новый токен через /api/1/access_token с apiLogin='{self.cloud_old_login}'")
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.cloud_base_url}/api/1/access_token",
                    json={"apiLogin": self.cloud_old_login}
                )
                response.raise_for_status()

                data = response.json()
                self.cloud_old_token = data.get("token")
                self.cloud_old_token_expires = datetime.now() + timedelta(minutes=55)

                logger.info(f"[OLD TOKEN] Новый токен получен (первые 10 символов): '{self.cloud_old_token[:10] if self.cloud_old_token else None}...'")
                return self.cloud_old_token

        except Exception as e:
            logger.error(f"Ошибка получения Cloud OLD API токена: {e}")
            return None

    async def _get_server_token(self) -> Optional[str]:
        """Получение токена для Server API"""
        if config.IIKO_REQUESTS_DISABLED:
            logger.warning("[IIKO_DISABLED] Server token request пропущен (IIKO_REQUESTS_DISABLED=true)")
            return None
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

    @staticmethod
    def _check_olap_date_window(report_data: Dict[Any, Any]) -> None:
        """Проверяет, что все date-фильтры OLAP-запроса укладываются в 60 дней.

        Бросает ValueError, если хоть один фильтр шире — задача вызывающего
        решить, как реагировать (raise / log).
        """
        filters = report_data.get("filters") if isinstance(report_data, dict) else None
        if not isinstance(filters, dict):
            return
        # iiko OLAP'у мы знакомо передаём как минимум эти ключи дат:
        date_filter_keys = (
            "DateTime.DateTyped",        # дата создания транзакции
            "DateSecondary.DateTyped",   # дата редактирования транзакции
            "OpenDate.Typed",            # дата открытия заказа (sales)
            "CloseDate.Typed",
        )
        for key in date_filter_keys:
            f = filters.get(key)
            if not isinstance(f, dict):
                continue
            f_from = f.get("from")
            f_to = f.get("to")
            if not f_from or not f_to:
                continue
            try:
                d_from = _to_date(f_from)
                d_to = _to_date(f_to)
            except Exception:
                continue
            diff = (d_to - d_from).days
            if diff > MAX_IIKO_DATE_WINDOW_DAYS:
                raise ValueError(
                    f"OLAP filter {key!r}: окно {diff} дней > {MAX_IIKO_DATE_WINDOW_DAYS}. "
                    f"from={f_from}, to={f_to}. "
                    f"Используйте чанкование по дням (см. iter_day_chunks)."
                )

    async def _make_request(
        self,
        api_type: IikoApiType,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[Any, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[Any, Any]]:
        """Универсальный метод для запросов к iiko API"""

        if config.IIKO_REQUESTS_DISABLED:
            logger.warning(
                f"[IIKO_DISABLED] Запрос к iiko пропущен (IIKO_REQUESTS_DISABLED=true): "
                f"api_type={api_type.value}, endpoint={endpoint}, method={method}"
            )
            return None

        # Guardrail: для OLAP-запросов сверяем, что окно дат в filters не превышает 60 дней.
        # Это safety net — если кто-то добавит новый OLAP-метод и забудет про чанкование,
        # мы поймаем это до того, как iiko снова жалуется на нехватку памяти (см. task 6).
        if endpoint == "/resto/api/v2/reports/olap" and isinstance(data, dict):
            try:
                self._check_olap_date_window(data)
            except ValueError as e:
                logger.error(f"[OLAP guardrail] BLOCKED: {e}. endpoint={endpoint}")
                raise

        # Добавляем задержку для предотвращения rate limiting
        await self._add_request_delay(api_type)
        
        # Получаем токен в зависимости от типа API
        if api_type == IikoApiType.CLOUD:
            token = await self._get_cloud_token()
            base_url = self.cloud_base_url
        elif api_type == IikoApiType.CLOUD_OLD:
            token = await self._get_cloud_old_token()
            base_url = self.cloud_base_url
        else:
            token = await self._get_server_token()
            base_url = self.server_base_url
            
        if not token:
            logger.error(f"Не удалось получить токен для {api_type.value} API")
            return None

        if api_type == IikoApiType.CLOUD_OLD:
            logger.info(
                f"[CLOUD_OLD REQUEST] endpoint={endpoint}, "
                f"apiLogin='{self.cloud_old_login}', "
                f"token (первые 10)='{token[:10]}...'"
            )

        # Разные способы авторизации для разных API
        if api_type in (IikoApiType.CLOUD, IikoApiType.CLOUD_OLD):
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
            logger.error(
                f"HTTP ошибка {api_type.value} API: "
                f"status_code={e.response.status_code}, "
                f"url={base_url}{endpoint}, "
                f"method={method}, "
                f"response_text={e.response.text[:500] if e.response.text else 'None'}"
            )
            logger.debug(f"Traceback для HTTP ошибки:\n{traceback.format_exc()}")
            return None
        except httpx.TimeoutException as e:
            logger.error(
                f"Таймаут запроса к {api_type.value} API: "
                f"url={base_url}{endpoint}, "
                f"method={method}, "
                f"timeout={self.timeout}s"
            )
            logger.debug(f"Traceback для таймаута:\n{traceback.format_exc()}")
            return None
        except Exception as e:
            logger.error(
                f"Ошибка запроса к {api_type.value} API: "
                f"url={base_url}{endpoint}, "
                f"method={method}, "
                f"error_type={type(e).__name__}, "
                f"error_message={str(e)}"
            )
            logger.debug(f"Traceback для ошибки:\n{traceback.format_exc()}")
            return None

    async def wait_command(
        self,
        organization_id: str,
        correlation_id: str,
        *,
        command_label: str = "iiko command",
        timeout: float = 15.0,
        interval: float = 0.5,
        notify_on_failure: bool = True,
    ) -> Dict[str, Any]:
        """
        Поллит /api/1/commands/status пока state не станет финальным
        (Success/Error) или не сработает timeout.

        Cloud-команды iiko асинхронные: первый ответ /order/* лишь подтверждает
        приём, реальный результат приходит позже. Без поллинга мы не видели,
        что часть команд падает на стороне iiko (см. task 9.1).

        Никогда не поднимает исключений: при Error/Timeout/транспорте возвращает
        dict с полем state и шлёт alert в Telegram (notify_on_failure).
        """
        from utils.telegram_notify import send_telegram_alert

        deadline = time.monotonic() + timeout
        last_response: Optional[Dict[Any, Any]] = None
        attempts = 0

        while True:
            attempts += 1
            resp = await self._make_request(
                api_type=IikoApiType.CLOUD,
                endpoint="/api/1/commands/status",
                method="POST",
                data={"organizationId": organization_id, "correlationId": correlation_id},
            )

            if not isinstance(resp, dict):
                logger.error(
                    f"[wait_command] {command_label}: пустой/невалидный ответ commands/status, "
                    f"correlation_id={correlation_id}, attempt={attempts}"
                )
                if notify_on_failure:
                    await send_telegram_alert(
                        f"<b>[Грузин]</b> iiko poll TRANSPORT FAIL\n"
                        f"command: {command_label}\n"
                        f"correlationId: <code>{correlation_id}</code>\n"
                        f"orgId: <code>{organization_id}</code>"
                    )
                return {
                    "state": "TransportError",
                    "correlationId": correlation_id,
                    "raw": resp,
                }

            last_response = resp
            state = resp.get("state")

            if state == "Success":
                logger.info(
                    f"[wait_command] {command_label}: Success "
                    f"(correlation_id={correlation_id}, attempts={attempts})"
                )
                return {"state": "Success", "correlationId": correlation_id, "raw": resp}

            if state == "Error":
                exception_info = resp.get("exception") or {}
                err_msg = (
                    exception_info.get("message")
                    or exception_info.get("description")
                    or str(exception_info)
                    or "iiko returned state=Error"
                )
                logger.error(
                    f"[wait_command] {command_label}: ERROR "
                    f"(correlation_id={correlation_id}): {err_msg}"
                )
                if notify_on_failure:
                    await send_telegram_alert(
                        f"<b>[Грузин]</b> iiko {command_label} FAILED\n"
                        f"correlationId: <code>{correlation_id}</code>\n"
                        f"orgId: <code>{organization_id}</code>\n"
                        f"error: {err_msg}"
                    )
                return {
                    "state": "Error",
                    "correlationId": correlation_id,
                    "exception": exception_info,
                    "raw": resp,
                }

            # state in ("InProgress", None, unknown) → ждём, проверяем deadline
            if time.monotonic() >= deadline:
                logger.warning(
                    f"[wait_command] {command_label}: TIMEOUT after {timeout}s "
                    f"(correlation_id={correlation_id}, last state={state}, attempts={attempts})"
                )
                if notify_on_failure:
                    await send_telegram_alert(
                        f"<b>[Грузин]</b> iiko {command_label} TIMEOUT {timeout}s\n"
                        f"correlationId: <code>{correlation_id}</code>\n"
                        f"orgId: <code>{organization_id}</code>\n"
                        f"last state: {state}"
                    )
                return {
                    "state": "Timeout",
                    "correlationId": correlation_id,
                    "raw": last_response,
                }

            await asyncio.sleep(interval)

    # Cloud API методы
    async def get_cloud_organizations(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение списка организаций (Cloud API)"""
        if self._organizations_cache is not None:
            return self._organizations_cache

        result = await self._make_request(
            IikoApiType.CLOUD,
            "/api/1/organizations",
            method="POST",
            data={}
        )
        # Cloud API возвращает список организаций напрямую
        orgs = None
        if isinstance(result, list):
            orgs = result
        elif isinstance(result, dict) and "organizations" in result:
            orgs = result["organizations"]

        if orgs is not None:
            self._organizations_cache = orgs
        return orgs

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

    async def get_cloud_restaurant_sections(self, organization_id: Optional[str] = None, terminals_data=None) -> Optional[List[Dict[Any, Any]]]:
        """Получение секций ресторана (Cloud API)"""
        if organization_id:
            # Сначала получаем терминалы для организации
            if terminals_data is None:
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

    async def get_cloud_tables(self, organization_id: Optional[str] = None, terminals_data=None) -> Optional[List[Dict[Any, Any]]]:
        """Получение столов ресторана (Cloud API)"""
        if organization_id:
            # Сначала получаем терминалы для организации
            if terminals_data is None:
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

    async def get_cloud_terminal_groups(self, organization_id: Optional[str] = None) -> Optional[List[Dict[Any, Any]]]:
        """Получение групп терминалов (Cloud API)"""
        if organization_id:
            if organization_id in self._terminal_groups_cache:
                return self._terminal_groups_cache[organization_id]

            result = await self._make_request(
                IikoApiType.CLOUD,
                "/api/1/terminal_groups",
                method="POST",
                data={"organizationIds": [organization_id]}
            )
            logger.info(f"Группы терминалов: {json.dumps(result, indent=4, ensure_ascii=False)}")
            # Извлекаем группы терминалов из структуры ответа
            if result and "terminalGroups" in result:
                # Возвращаем сами группы с информацией об организации
                groups = []
                terminals = []
                for group in result["terminalGroups"]:
                    if "items" in group and group["items"]:
                        for item in group["items"]:
                            groups.append({
                                "id": item.get("id"),
                                "name": item.get("name"),
                                "organizationId": organization_id
                            })
                            terminals.append(item)
                self._terminal_groups_cache[organization_id] = groups
                # Заполняем кеш терминалов тем же ответом (тот же endpoint)
                if organization_id not in self._terminals_cache:
                    self._terminals_cache[organization_id] = terminals
                return groups
            return None
        else:
            # Если organization_id не указан, получаем группы терминалов из всех организаций
            organizations = await self.get_organizations()
            if not organizations:
                return None
            
            all_groups = []
            for org in organizations:
                org_id = org.get("id")
                if org_id:
                    groups = await self.get_cloud_terminal_groups(org_id)
                    logger.info(f"Группы терминалов: {json.dumps(groups, indent=4, ensure_ascii=False)}")
                    if groups:
                        all_groups.extend(groups)
            
            return all_groups

    async def get_cloud_terminals(self, organization_id: Optional[str] = None) -> Optional[List[Dict[Any, Any]]]:
        """Получение терминалов (Cloud API)"""
        if organization_id:
            if organization_id in self._terminals_cache:
                return self._terminals_cache[organization_id]

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
                groups = []
                for group in result["terminalGroups"]:
                    if "items" in group:
                        for item in group["items"]:
                            terminals.append(item)
                            groups.append({
                                "id": item.get("id"),
                                "name": item.get("name"),
                                "organizationId": organization_id
                            })
                self._terminals_cache[organization_id] = terminals
                # Заполняем кеш terminal_groups тем же ответом (тот же endpoint)
                if organization_id not in self._terminal_groups_cache:
                    self._terminal_groups_cache[organization_id] = groups
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

    async def get_cloud_orders_by_table(
        self,
        organization_ids: Optional[List[str]] = None,
        table_ids: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """POST /api/1/order/by_table — заказы по столам (Cloud API).

        iiko требует множественные `organizationIds` + `tableIds` (research 2026-05-28,
        task 9.3): single-форма даёт HTTP 400 INVALID_BODY_JSON_FORMAT. Batched-форма
        позволяет дёрнуть все столы одной точки одним запросом.

        Возвращает `{correlationId, orders: [...]}` или None при транспортной ошибке.
        Внимание: `by_table` НЕ показывает iikoFront-заказы без предварительного
        `init_by_table` (см. task_9_3_research_2026_05_28.md).
        """
        if not organization_ids or not table_ids:
            return None
        return await self._make_request(
            IikoApiType.CLOUD,
            "/api/1/order/by_table",
            method="POST",
            data={"organizationIds": organization_ids, "tableIds": table_ids},
        )

    # Server API методы
    async def get_server_organizations(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение списка организаций (Server API) - НЕ ПОДДЕРЖИВАЕТСЯ"""
        # Server API не имеет эндпоинта для получения организаций
        logger.warning("Server API не поддерживает получение организаций")
        return None

    async def get_server_products(self, types: str = "DISH") -> Optional[List[Dict[Any, Any]]]:
        """Получение продуктов (Server API)"""
        params = {}
        if types:
            params["types"] = types
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/v2/entities/products/list",
            params=params if params else None
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
        """Получение департаментов (Server API) - возвращает XML"""
        # Получаем токен
        token = await self._get_server_token()
        if not token:
            logger.error("Не удалось получить токен для Server API")
            return None
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.server_base_url}/resto/api/corporation/departments"
                params = {"key": token}
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    # Server API возвращает XML, нужно парсить его
                    xml_content = response.text
                    return await self._parse_xml_departments(xml_content)
                else:
                    logger.error(f"HTTP ошибка server API: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Ошибка получения департаментов: {e}")
            logger.debug(f"Traceback:\n{traceback.format_exc()}")
            return None

    async def _parse_xml_departments(self, xml_content: str) -> Optional[List[Dict[Any, Any]]]:
        """Парсинг XML ответа с департаментами"""
        try:
            root = ET.fromstring(xml_content)
            departments = []
            
            # Ищем все corporateItemDto с type="DEPARTMENT"
            for item_elem in root.findall('.//corporateItemDto'):
                item_type = item_elem.find('type')
                if item_type is None or item_type.text != 'DEPARTMENT':
                    continue
                
                dept_data = {}
                
                # Основные поля
                dept_id = item_elem.find('id')
                dept_data['id'] = dept_id.text if dept_id is not None else None
                
                parent_id = item_elem.find('parentId')
                dept_data['parentId'] = parent_id.text if parent_id is not None else None
                
                code = item_elem.find('code')
                dept_data['code'] = code.text if code is not None else None
                
                name = item_elem.find('name')
                dept_data['name'] = name.text.strip() if name is not None and name.text else None
                
                taxpayer_id = item_elem.find('taxpayerIdNumber')
                dept_data['taxpayerIdNumber'] = taxpayer_id.text if taxpayer_id is not None else None
                
                departments.append(dept_data)
            
            logger.info(f"Парсинг XML департаментов: {len(departments)} записей (type=DEPARTMENT)")
            return departments
            
        except ET.ParseError as e:
            logger.error(f"Ошибка парсинга XML департаментов: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка обработки XML департаментов: {e}")
            logger.debug(f"Traceback:\n{traceback.format_exc()}")
            return None

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
        """Получение транзакций (Server API) за период. Разбивается по дням."""
        if not from_date or not to_date:
            logger.warning("Не указаны даты для получения транзакций")
            return None

        assert_iiko_date_window(from_date, to_date, "get_transactions")

        all_transactions = []
        current_date = from_date.date()
        end_date = to_date.date()

        logger.info(f"Начало получения транзакций: разбивка на дни с {current_date} по {end_date}")

        while current_date <= end_date:
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date + timedelta(days=1), datetime.min.time())

            try:
                params = data_frames.iiko_transactions_data_frame.copy()
                # iiko API использует полуоткрытый интервал [from, to)
                params["filters"]["DateTime.DateTyped"]["from"] = day_start.strftime('%Y-%m-%d')
                params["filters"]["DateTime.DateTyped"]["to"] = day_end.strftime('%Y-%m-%d')

                result = await self.get_server_transactions_report(params)
                if result and "data" in result:
                    all_transactions.extend(result["data"])
                    logger.debug(f"Получено {len(result['data'])} транзакций за {current_date}")
                else:
                    logger.warning(f"Не получено данных транзакций за {current_date}")
            except Exception as e:
                logger.error(f"Ошибка при получении транзакций за {current_date}: {e}")
                logger.debug(f"Traceback для ошибки за {current_date}:\n{traceback.format_exc()}")

            current_date += timedelta(days=1)

        logger.info(f"Всего получено {len(all_transactions)} транзакций за период с {from_date.strftime('%Y-%m-%d')} по {to_date.strftime('%Y-%m-%d')}")
        return all_transactions if all_transactions else None

    async def get_sales(self, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None) -> Optional[List[Dict[Any, Any]]]:
        """Получение продаж (Server API) за период. Разбивается по дням."""
        if not from_date or not to_date:
            logger.warning("Не указаны даты для получения продаж")
            return None

        assert_iiko_date_window(from_date, to_date, "get_sales")

        all_sales = []
        current_date = from_date.date()
        end_date = to_date.date()

        logger.info(f"Начало получения продаж: разбивка на дни с {current_date} по {end_date}")

        while current_date <= end_date:
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date + timedelta(days=1), datetime.min.time())

            try:
                params = data_frames.iiko_sales_data_frame.copy()
                # iiko API использует полуоткрытый интервал [from, to)
                params["filters"]["OpenDate.Typed"]["from"] = day_start.strftime('%Y-%m-%d')
                params["filters"]["OpenDate.Typed"]["to"] = day_end.strftime('%Y-%m-%d')

                result = await self.get_server_sales_report(params)
                if result and "data" in result:
                    all_sales.extend(result["data"])
                    logger.debug(f"Получено {len(result['data'])} продаж за {current_date}")
                else:
                    logger.warning(f"Не получено данных продаж за {current_date}")
            except Exception as e:
                logger.error(f"Ошибка при получении продаж за {current_date}: {e}")
                logger.debug(f"Traceback для ошибки за {current_date}:\n{traceback.format_exc()}")

            current_date += timedelta(days=1)

        logger.info(f"Всего получено {len(all_sales)} продаж за период с {from_date.strftime('%Y-%m-%d')} по {to_date.strftime('%Y-%m-%d')}")
        return all_sales if all_sales else None

    async def get_transactions_by_modification_date(self, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None) -> Optional[List[Dict[Any, Any]]]:
        """
        Получение транзакций, измененных за период (по DateSecondary.DateTyped).
        Оптимизировано: разбивает запрос на запросы по дням для избежания таймаутов.
        """
        if not from_date or not to_date:
            logger.warning("Не указаны даты для получения транзакций по дате изменения")
            return None

        assert_iiko_date_window(from_date, to_date, "get_transactions_by_modification_date")

        all_transactions = []
        current_date = from_date.date()
        end_date = to_date.date()

        # Фильтр по дате создания транзакции — окно 60 дней (iiko: лимит 65 дней по памяти "открытого периода").
        # Этим окном защищаем iiko OLAP от перегруза. Правки на транзакции старше 60 дней этим синком не ловятся.
        date_created_from = (to_date - timedelta(days=60)).strftime('%Y-%m-%d')
        date_created_to = (to_date + timedelta(days=1)).strftime('%Y-%m-%d')  # +1 день для включения последнего дня

        logger.info(f"Начало получения транзакций по дате изменения: разбивка на дни с {current_date} по {end_date}")
        logger.info(f"Фильтр по дате создания транзакции: с {date_created_from} по {date_created_to} (окно 60 дней)")
        
        # Разбиваем период на дни и делаем запросы по каждому дню
        while current_date <= end_date:
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date + timedelta(days=1), datetime.min.time())
            
            # Для последнего дня включаем верхнюю границу
            is_last_day = current_date == end_date
            
            try:
                params = data_frames.iiko_transactions_by_modification_data_frame.copy()
                
                # Фильтр по дате изменения (DateSecondary.DateTyped) - разбиваем по дням
                params["filters"]["DateSecondary.DateTyped"]["from"] = day_start.strftime('%Y-%m-%d')
                params["filters"]["DateSecondary.DateTyped"]["to"] = day_end.strftime('%Y-%m-%d')
                params["filters"]["DateSecondary.DateTyped"]["includeLow"] = True
                params["filters"]["DateSecondary.DateTyped"]["includeHigh"] = is_last_day  # Включаем последний день
                
                # Фильтр по дате создания транзакции (DateTime.DateTyped) - окно 60 дней
                params["filters"]["DateTime.DateTyped"]["from"] = date_created_from
                params["filters"]["DateTime.DateTyped"]["to"] = date_created_to
                params["filters"]["DateTime.DateTyped"]["includeLow"] = True
                params["filters"]["DateTime.DateTyped"]["includeHigh"] = False
                
                logger.debug(f"Запрос транзакций, измененных за {current_date} (дата создания: {date_created_from} - {date_created_to})")
                result = await self.get_server_transactions_report(params)
                
                if result and "data" in result:
                    day_transactions = result["data"]
                    all_transactions.extend(day_transactions)
                    logger.info(f"Получено {len(day_transactions)} транзакций, измененных за {current_date}")
                else:
                    logger.warning(f"Не получено данных транзакций за {current_date}")
                    
            except Exception as e:
                logger.error(f"Ошибка при получении транзакций за {current_date}: {e}")
                # Продолжаем обработку следующих дней даже при ошибке
                logger.debug(f"Traceback для ошибки за {current_date}:\n{traceback.format_exc()}")
            
            # Переходим к следующему дню
            current_date += timedelta(days=1)
        
        logger.info(f"Всего получено {len(all_transactions)} транзакций, измененных за период с {from_date.strftime('%Y-%m-%d')} по {to_date.strftime('%Y-%m-%d')}")
        return all_transactions if all_transactions else None

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
        """Получение отчета по расходу продуктов (Server API).

        Аггрегированный отчёт за период, не чанкуется по дням (потеряет агрегацию).
        Окно ограничено MAX_IIKO_DATE_WINDOW_DAYS, чтобы не уронить iiko по памяти.
        """
        try:
            assert_iiko_date_window(date_from, date_to, label="get_server_product_expense_report")
        except ValueError as e:
            logger.error(str(e))
            return None
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

    async def get_restaurant_sections(self, organization_id: Optional[str] = None, prefer_cloud: bool = True, terminals_data=None) -> Optional[List[Dict[Any, Any]]]:
        """Получение секций ресторана (пробует Cloud, затем Server)"""
        if prefer_cloud:
            result = await self.get_cloud_restaurant_sections(organization_id, terminals_data=terminals_data)
            if result:
                return result
            # Server API не имеет прямого аналога для секций
            return None
        else:
            result = await self.get_cloud_restaurant_sections(organization_id, terminals_data=terminals_data)
            if result:
                return result
            return None

    async def get_tables(self, organization_id: Optional[str] = None, prefer_cloud: bool = True, terminals_data=None) -> Optional[List[Dict[Any, Any]]]:
        """Получение столов (пробует Cloud, затем Server)"""
        if prefer_cloud:
            result = await self.get_cloud_tables(organization_id, terminals_data=terminals_data)
            if result:
                return result
            # Server API не имеет прямого аналога для столов
            return None
        else:
            result = await self.get_cloud_tables(organization_id, terminals_data=terminals_data)
            if result:
                return result
            return None

    async def get_terminal_groups(self, organization_id: Optional[str] = None, prefer_cloud: bool = True) -> Optional[List[Dict[Any, Any]]]:
        """Получение групп терминалов (пробует Cloud, затем Server)"""
        if prefer_cloud:
            result = await self.get_cloud_terminal_groups(organization_id)
            if result:
                return result
            # Server API не имеет прямого аналога для групп терминалов
            return None
        else:
            result = await self.get_cloud_terminal_groups(organization_id)
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

    async def get_server_accounts(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение счетов (Server API)"""
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/v2/entities/accounts/list"
        )

    async def get_accounts(self, prefer_cloud: bool = False) -> Optional[List[Dict[Any, Any]]]:
        """Получение счетов (только Server API)"""
        return await self.get_server_accounts()

    async def get_server_salaries(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение окладов сотрудников (Server API) - возвращает XML"""
        # Получаем токен
        token = await self._get_server_token()
        if not token:
            logger.error("Не удалось получить токен для Server API")
            return None
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.server_base_url}/resto/api/employees/salary"
                params = {"key": token}
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    # Server API возвращает XML, нужно парсить его
                    xml_content = response.text
                    return await self._parse_xml_salaries(xml_content)
                else:
                    logger.error(f"HTTP ошибка server API: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка запроса к server API: {e}")
            return None

    async def _parse_xml_salaries(self, xml_content: str) -> Optional[List[Dict[Any, Any]]]:
        """Парсинг XML ответа с окладами"""
        try:
            root = ET.fromstring(xml_content)
            salaries = []
            
            for salary_elem in root.findall('salary'):
                salary_data = {}
                
                # Основные поля
                salary_data['employeeId'] = salary_elem.find('employeeId').text if salary_elem.find('employeeId') is not None else None
                salary_data['dateFrom'] = salary_elem.find('dateFrom').text if salary_elem.find('dateFrom') is not None else None
                salary_data['dateTo'] = salary_elem.find('dateTo').text if salary_elem.find('dateTo') is not None else None
                salary_data['payment'] = salary_elem.find('payment').text if salary_elem.find('payment') is not None else None
                
                salaries.append(salary_data)
            
            logger.info(f"Распарсено {len(salaries)} окладов из XML")
            return salaries
            
        except Exception as e:
            logger.error(f"Ошибка парсинга XML окладов: {e}")
            return None

    async def get_salaries(self, prefer_cloud: bool = False) -> Optional[List[Dict[Any, Any]]]:
        """Получение окладов (только Server API)"""
        return await self.get_server_salaries()

    async def _get_server_shifts_one_day(
        self, day_from: str, day_to: str, employee_id: Optional[str], token: str
    ) -> Optional[List[Dict[Any, Any]]]:
        """Один-дневный запрос смен (XML). Возвращает list или None при ошибке."""
        try:
            params_with_key = {"key": token, "from": day_from, "to": day_to}
            if employee_id:
                params_with_key["employeeId"] = employee_id
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.server_base_url}/resto/api/employees/attendance"
                response = await client.get(url, params=params_with_key)
                if response.status_code == 200:
                    return await self._parse_xml_shifts(response.text)
                logger.error(
                    f"HTTP ошибка server API при получении смен {day_from}: "
                    f"{response.status_code} - {response.text[:200]}"
                )
                return None
        except Exception as e:
            logger.error(f"Ошибка запроса смен за {day_from}: {e}")
            return None

    async def get_server_shifts(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        employee_id: Optional[str] = None
    ) -> Optional[List[Dict[Any, Any]]]:
        """
        Получение данных о сменах сотрудников (Server API) — чанкуется по дням,
        максимальное окно — MAX_IIKO_DATE_WINDOW_DAYS дней.

        Args:
            date_from: Дата начала периода в формате YYYY-MM-DD
            date_to: Дата конца периода в формате YYYY-MM-DD
            employee_id: ID сотрудника (опционально)

        Returns:
            Список смен сотрудников (объединённый по всем дням периода)
        """
        if not date_from:
            date_from = datetime.now().strftime("%Y-%m-%d")
        if not date_to:
            date_to = datetime.now().strftime("%Y-%m-%d")

        token = await self._get_server_token()
        if not token:
            logger.error("Не удалось получить токен для Server API")
            return None

        all_shifts: List[Dict[Any, Any]] = []
        try:
            chunks = list(iter_day_chunks(date_from, date_to))
        except ValueError as e:
            logger.error(f"get_server_shifts: невалидный диапазон: {e}")
            return None

        logger.info(f"Запрос смен: разбивка на {len(chunks)} дн. с {date_from} по {date_to}")
        for day_start, day_end_exclusive in chunks:
            day_from_str = day_start.strftime("%Y-%m-%d")
            day_to_str = day_start.strftime("%Y-%m-%d")  # iiko shifts: from==to для одного дня
            shifts = await self._get_server_shifts_one_day(
                day_from_str, day_to_str, employee_id, token
            )
            if shifts:
                all_shifts.extend(shifts)

        logger.info(f"Получено {len(all_shifts)} смен за период {date_from} — {date_to}")
        return all_shifts if all_shifts else None

    async def _parse_xml_shifts(self, xml_content: str) -> Optional[List[Dict[Any, Any]]]:
        """Парсинг XML ответа со сменами"""
        try:
            root = ET.fromstring(xml_content)
            shifts = []
            
            # Ищем элементы attendance (корневой элемент - attendances)
            attendance_elems = root.findall('.//attendance')
            
            for attendance_elem in attendance_elems:
                shift_data = {}
                
                # Основные поля из XML структуры iiko
                id_elem = attendance_elem.find('id')
                shift_data['iiko_id'] = id_elem.text if id_elem is not None else None
                
                employee_id_elem = attendance_elem.find('employeeId')
                shift_data['employee_id'] = employee_id_elem.text if employee_id_elem is not None else None
                
                # В XML используются dateFrom и dateTo, а не startTime/endTime
                date_from_elem = attendance_elem.find('dateFrom')
                shift_data['start_time'] = date_from_elem.text if date_from_elem is not None else None
                
                date_to_elem = attendance_elem.find('dateTo')
                shift_data['end_time'] = date_to_elem.text if date_to_elem is not None else None
                
                attendance_type_id_elem = attendance_elem.find('attendanceTypeId')
                shift_data['attendance_type_id'] = attendance_type_id_elem.text if attendance_type_id_elem is not None else None
                
                # Дополнительные поля, которые могут быть полезны
                role_id_elem = attendance_elem.find('roleId')
                if role_id_elem is not None:
                    shift_data['role_id'] = role_id_elem.text
                
                user_id_elem = attendance_elem.find('userId')
                if user_id_elem is not None:
                    shift_data['user_id'] = user_id_elem.text
                
                shifts.append(shift_data)
            
            logger.info(f"Распарсено {len(shifts)} смен из XML")
            return shifts if shifts else None
            
        except ET.ParseError as e:
            logger.error(f"Ошибка парсинга XML смен (ParseError): {e}")
            logger.debug(f"XML содержимое (первые 500 символов): {xml_content[:500]}")
            return None
        except Exception as e:
            logger.error(f"Ошибка парсинга XML смен: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    async def get_writeoff_documents(
        self,
        date_from: str,
        date_to: str,
        status: Optional[str] = None
    ) -> Optional[Dict[Any, Any]]:
        """Получение актов списания (Server API). Разбивается по дням."""
        assert_iiko_date_window(date_from, date_to, "get_writeoff_documents")
        try:
            token = await self._get_server_token()
            if not token:
                logger.error("Не удалось получить токен для Server API")
                return None

            from datetime import date as date_type
            current = datetime.strptime(date_from, "%Y-%m-%d").date()
            end = datetime.strptime(date_to, "%Y-%m-%d").date()

            all_items: List[Any] = []
            logger.info(f"Получение актов списания: разбивка по дням с {current} по {end}")

            while current <= end:
                next_day = current + timedelta(days=1)
                params: Dict[str, Any] = {
                    "key": token,
                    "dateFrom": current.strftime("%Y-%m-%d"),
                    "dateTo": next_day.strftime("%Y-%m-%d"),
                }
                if status:
                    params["status"] = status

                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.get(
                            f"{self.server_base_url}/resto/api/v2/documents/writeoff",
                            params=params,
                        )
                        response.raise_for_status()
                        day_data = response.json()

                    if day_data:
                        items = day_data.get("response", []) if isinstance(day_data, dict) else day_data
                        if items:
                            all_items.extend(items)
                            logger.info(f"Акты списания за {current}: {len(items)} документов")
                        else:
                            logger.debug(f"Акты списания за {current}: нет данных")
                except Exception as day_err:
                    logger.error(f"Ошибка получения актов списания за {current}: {day_err}")

                current = next_day

            logger.info(f"Всего актов списания за период: {len(all_items)}")
            return {"response": all_items} if all_items else None

        except Exception as e:
            logger.error(f"Ошибка получения актов списания: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    async def create_writeoff_document(
        self,
        document_data: Dict[Any, Any]
    ) -> Optional[Dict[Any, Any]]:
        """
        Создание акта списания (Server API)
        
        Args:
            document_data: Данные акта списания в формате iiko API:
                {
                    "dateIncoming": str,  # "yyyy-MM-ddTHH:mm" (например, "2021-11-16T23:00")
                    "status": Optional[str],  # По умолчанию "NEW"
                    "comment": Optional[str],
                    "storeId": str,  # GUID склада
                    "accountId": str,  # GUID счета
                    "documentNumber": Optional[str],  # Если не указан, генерируется автоматически
                    "items": [
                        {
                            "productId": str,  # GUID товара (обязательное)
                            "amount": float  # Количество (обязательное)
                        }
                    ]
                }
        
        Returns:
            JSON ответ от iiko API с созданным документом
        """
        try:
            token = await self._get_server_token()
            if not token:
                logger.error("Не удалось получить токен для Server API")
                return None
            
            params = {
                "key": token
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.server_base_url}/resto/api/v2/documents/writeoff",
                    params=params,
                    json=document_data
                )
                response.raise_for_status()
                result = response.json()
                logger.debug(f"Ответ от iiko API при создании акта списания: {result}")
                return result
                
        except httpx.HTTPStatusError as e:
            error_detail = None
            try:
                error_detail = e.response.json()
            except:
                error_detail = e.response.text
            logger.error(f"HTTP ошибка при создании акта списания: {e.response.status_code} - {error_detail}")
            return None
        except Exception as e:
            logger.error(f"Ошибка создания акта списания: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    def _build_incoming_invoice_xml(self, invoice_data: Dict[Any, Any]) -> str:
        """
        Построение XML для приходной накладной
        
        Args:
            invoice_data: Данные приходной накладной
        
        Returns:
            XML строка
        """
        root = ET.Element("document")
        
        # Основные поля документа
        if invoice_data.get("id"):
            ET.SubElement(root, "id").text = str(invoice_data["id"])
        if invoice_data.get("conception"):
            ET.SubElement(root, "conception").text = str(invoice_data["conception"])
        if invoice_data.get("conceptionCode"):
            ET.SubElement(root, "conceptionCode").text = str(invoice_data["conceptionCode"])
        if invoice_data.get("comment"):
            ET.SubElement(root, "comment").text = str(invoice_data["comment"])
        if invoice_data.get("documentNumber"):
            ET.SubElement(root, "documentNumber").text = str(invoice_data["documentNumber"])
        if invoice_data.get("dateIncoming"):
            ET.SubElement(root, "dateIncoming").text = str(invoice_data["dateIncoming"])
        if invoice_data.get("invoice"):
            ET.SubElement(root, "invoice").text = str(invoice_data["invoice"])
        if invoice_data.get("defaultStore"):
            ET.SubElement(root, "defaultStore").text = str(invoice_data["defaultStore"])
        if invoice_data.get("supplier"):
            ET.SubElement(root, "supplier").text = str(invoice_data["supplier"])
        if invoice_data.get("dueDate"):
            ET.SubElement(root, "dueDate").text = str(invoice_data["dueDate"])
        if invoice_data.get("incomingDate"):
            ET.SubElement(root, "incomingDate").text = str(invoice_data["incomingDate"])
        if invoice_data.get("useDefaultDocumentTime") is not None:
            ET.SubElement(root, "useDefaultDocumentTime").text = str(invoice_data["useDefaultDocumentTime"]).lower()
        if invoice_data.get("status"):
            ET.SubElement(root, "status").text = str(invoice_data["status"])
        if invoice_data.get("incomingDocumentNumber"):
            ET.SubElement(root, "incomingDocumentNumber").text = str(invoice_data["incomingDocumentNumber"])
        if invoice_data.get("employeePassToAccount"):
            ET.SubElement(root, "employeePassToAccount").text = str(invoice_data["employeePassToAccount"])
        if invoice_data.get("transportInvoiceNumber"):
            ET.SubElement(root, "transportInvoiceNumber").text = str(invoice_data["transportInvoiceNumber"])
        
        # Позиции документа
        if invoice_data.get("items"):
            items_elem = ET.SubElement(root, "items")
            for item in invoice_data["items"]:
                item_elem = ET.SubElement(items_elem, "item")
                
                # num - обязательное поле (minOccurs="1")
                num_value = item.get("num")
                if num_value is None:
                    # Если num не указан, используем индекс (начиная с 1)
                    num_value = invoice_data["items"].index(item) + 1
                ET.SubElement(item_elem, "num").text = str(num_value)
                
                if item.get("amount") is not None:
                    ET.SubElement(item_elem, "amount").text = str(item["amount"])
                if item.get("supplierProduct"):
                    ET.SubElement(item_elem, "supplierProduct").text = str(item["supplierProduct"])
                if item.get("supplierProductArticle"):
                    ET.SubElement(item_elem, "supplierProductArticle").text = str(item["supplierProductArticle"])
                if item.get("product"):
                    ET.SubElement(item_elem, "product").text = str(item["product"])
                if item.get("productArticle"):
                    ET.SubElement(item_elem, "productArticle").text = str(item["productArticle"])
                if item.get("producer"):
                    ET.SubElement(item_elem, "producer").text = str(item["producer"])
                if item.get("containerId"):
                    ET.SubElement(item_elem, "containerId").text = str(item["containerId"])
                if item.get("amountUnit"):
                    ET.SubElement(item_elem, "amountUnit").text = str(item["amountUnit"])
                if item.get("actualUnitWeight") is not None:
                    ET.SubElement(item_elem, "actualUnitWeight").text = str(item["actualUnitWeight"])
                # sum - обязательное поле (minOccurs="1")
                sum_value = item.get("sum")
                if sum_value is None:
                    # Если sum не указан, вычисляем из amount * price
                    amount = item.get("amount", 0)
                    price = item.get("price", 0)
                    sum_value = float(amount) * float(price) if amount and price else 0
                ET.SubElement(item_elem, "sum").text = str(sum_value)
                if item.get("discountSum") is not None:
                    ET.SubElement(item_elem, "discountSum").text = str(item["discountSum"])
                if item.get("vatPercent") is not None:
                    ET.SubElement(item_elem, "vatPercent").text = str(item["vatPercent"])
                if item.get("vatSum") is not None:
                    ET.SubElement(item_elem, "vatSum").text = str(item["vatSum"])
                if item.get("priceUnit"):
                    ET.SubElement(item_elem, "priceUnit").text = str(item["priceUnit"])
                if item.get("price") is not None:
                    ET.SubElement(item_elem, "price").text = str(item["price"])
                if item.get("priceWithoutVat") is not None:
                    ET.SubElement(item_elem, "priceWithoutVat").text = str(item["priceWithoutVat"])
                if item.get("code"):
                    ET.SubElement(item_elem, "code").text = str(item["code"])
                if item.get("store"):
                    ET.SubElement(item_elem, "store").text = str(item["store"])
                if item.get("customsDeclarationNumber"):
                    ET.SubElement(item_elem, "customsDeclarationNumber").text = str(item["customsDeclarationNumber"])
                if item.get("actualAmount") is not None:
                    ET.SubElement(item_elem, "actualAmount").text = str(item["actualAmount"])
        
        # Преобразуем в строку
        ET.indent(root, space="  ")
        xml_str = ET.tostring(root, encoding="UTF-8", xml_declaration=True).decode("utf-8")
        return xml_str

    def _build_outgoing_invoice_xml(self, invoice_data: Dict[Any, Any]) -> str:
        """
        Построение XML для расходной накладной
        
        Args:
            invoice_data: Данные расходной накладной
        
        Returns:
            XML строка
        """
        root = ET.Element("document")
        
        # Основные поля документа
        if invoice_data.get("id"):
            ET.SubElement(root, "id").text = str(invoice_data["id"])
        if invoice_data.get("conceptionId"):
            ET.SubElement(root, "conceptionId").text = str(invoice_data["conceptionId"])
        if invoice_data.get("conceptionCode"):
            ET.SubElement(root, "conceptionCode").text = str(invoice_data["conceptionCode"])
        if invoice_data.get("comment"):
            ET.SubElement(root, "comment").text = str(invoice_data["comment"])
        if invoice_data.get("documentNumber"):
            ET.SubElement(root, "documentNumber").text = str(invoice_data["documentNumber"])
        if invoice_data.get("dateIncoming"):
            ET.SubElement(root, "dateIncoming").text = str(invoice_data["dateIncoming"])
        if invoice_data.get("defaultStoreId"):
            ET.SubElement(root, "defaultStoreId").text = str(invoice_data["defaultStoreId"])
        if invoice_data.get("accountToCode"):
            ET.SubElement(root, "accountToCode").text = str(invoice_data["accountToCode"])
        if invoice_data.get("revenueAccountCode"):
            ET.SubElement(root, "revenueAccountCode").text = str(invoice_data["revenueAccountCode"])
        if invoice_data.get("counteragentId"):
            ET.SubElement(root, "counteragentId").text = str(invoice_data["counteragentId"])
        if invoice_data.get("counteragentCode"):
            ET.SubElement(root, "counteragentCode").text = str(invoice_data["counteragentCode"])
        if invoice_data.get("useDefaultDocumentTime") is not None:
            ET.SubElement(root, "useDefaultDocumentTime").text = str(invoice_data["useDefaultDocumentTime"]).lower()
        if invoice_data.get("status"):
            ET.SubElement(root, "status").text = str(invoice_data["status"])
        
        # Позиции документа
        if invoice_data.get("items"):
            items_elem = ET.SubElement(root, "items")
            for item in invoice_data["items"]:
                item_elem = ET.SubElement(items_elem, "item")
                
                # num - обязательное поле
                num_value = item.get("num")
                if num_value is None:
                    num_value = invoice_data["items"].index(item) + 1
                ET.SubElement(item_elem, "num").text = str(num_value)
                
                # productId - обязательное поле для расходной накладной
                if item.get("productId"):
                    ET.SubElement(item_elem, "productId").text = str(item["productId"])
                
                # amount - обязательное поле
                if item.get("amount") is not None:
                    ET.SubElement(item_elem, "amount").text = str(item["amount"])
                
                # sum - обязательное поле
                sum_value = item.get("sum")
                if sum_value is None:
                    # Если sum не указан, вычисляем из amount * price
                    amount = item.get("amount", 0)
                    price = item.get("price", 0)
                    sum_value = float(amount) * float(price) if amount and price else 0
                ET.SubElement(item_elem, "sum").text = str(sum_value)
                
                # Остальные опциональные поля
                if item.get("price") is not None:
                    ET.SubElement(item_elem, "price").text = str(item["price"])
                if item.get("discountSum") is not None:
                    ET.SubElement(item_elem, "discountSum").text = str(item["discountSum"])
                if item.get("vatPercent") is not None:
                    ET.SubElement(item_elem, "vatPercent").text = str(item["vatPercent"])
                if item.get("vatSum") is not None:
                    ET.SubElement(item_elem, "vatSum").text = str(item["vatSum"])
        
        # Преобразуем в строку
        ET.indent(root, space="  ")
        xml_str = ET.tostring(root, encoding="UTF-8", xml_declaration=True).decode("utf-8")
        return xml_str

    def _build_inventory_xml(self, inventory_data: Dict[Any, Any]) -> str:
        """
        Построение XML для инвентаризации
        
        Args:
            inventory_data: Данные инвентаризации
        
        Returns:
            XML строка
        """
        root = ET.Element("document")
        
        # Основные поля документа
        if inventory_data.get("documentNumber"):
            ET.SubElement(root, "documentNumber").text = str(inventory_data["documentNumber"])
        if inventory_data.get("dateIncoming"):
            ET.SubElement(root, "dateIncoming").text = str(inventory_data["dateIncoming"])
        if inventory_data.get("useDefaultDocumentTime") is not None:
            ET.SubElement(root, "useDefaultDocumentTime").text = str(inventory_data["useDefaultDocumentTime"]).lower()
        if inventory_data.get("status"):
            ET.SubElement(root, "status").text = str(inventory_data["status"])
        if inventory_data.get("accountSurplusCode"):
            ET.SubElement(root, "accountSurplusCode").text = str(inventory_data["accountSurplusCode"])
        if inventory_data.get("accountShortageCode"):
            ET.SubElement(root, "accountShortageCode").text = str(inventory_data["accountShortageCode"])
        if inventory_data.get("storeId"):
            ET.SubElement(root, "storeId").text = str(inventory_data["storeId"])
        if inventory_data.get("storeCode"):
            ET.SubElement(root, "storeCode").text = str(inventory_data["storeCode"])
        if inventory_data.get("conceptionId"):
            ET.SubElement(root, "conceptionId").text = str(inventory_data["conceptionId"])
        if inventory_data.get("conceptionCode"):
            ET.SubElement(root, "conceptionCode").text = str(inventory_data["conceptionCode"])
        if inventory_data.get("comment"):
            ET.SubElement(root, "comment").text = str(inventory_data["comment"])
        
        # Позиции документа
        if inventory_data.get("items"):
            items_elem = ET.SubElement(root, "items")
            for item in inventory_data["items"]:
                item_elem = ET.SubElement(items_elem, "item")
                
                # status - опциональное поле
                if item.get("status"):
                    ET.SubElement(item_elem, "status").text = str(item["status"])
                
                # recalculationNumber - опциональное поле
                if item.get("recalculationNumber") is not None:
                    ET.SubElement(item_elem, "recalculationNumber").text = str(item["recalculationNumber"])
                
                # productId - опциональное, но нужно хотя бы productId или productArticle
                if item.get("productId"):
                    ET.SubElement(item_elem, "productId").text = str(item["productId"])
                if item.get("productArticle"):
                    ET.SubElement(item_elem, "productArticle").text = str(item["productArticle"])
                
                # containerId и containerCode - опциональные
                if item.get("containerId"):
                    ET.SubElement(item_elem, "containerId").text = str(item["containerId"])
                if item.get("containerCode"):
                    ET.SubElement(item_elem, "containerCode").text = str(item["containerCode"])
                
                # amountContainer - опциональное
                if item.get("amountContainer") is not None:
                    ET.SubElement(item_elem, "amountContainer").text = str(item["amountContainer"])
                
                # amountGross - опциональное
                if item.get("amountGross") is not None:
                    ET.SubElement(item_elem, "amountGross").text = str(item["amountGross"])
                
                # producerId - опциональное
                if item.get("producerId"):
                    ET.SubElement(item_elem, "producerId").text = str(item["producerId"])
                
                # comment - опциональное
                if item.get("comment"):
                    ET.SubElement(item_elem, "comment").text = str(item["comment"])
        
        # Преобразуем в строку
        ET.indent(root, space="  ")
        xml_str = ET.tostring(root, encoding="UTF-8", xml_declaration=True).decode("utf-8")
        return xml_str

    async def create_incoming_invoice(
        self,
        invoice_data: Dict[Any, Any]
    ) -> Optional[Dict[Any, Any]]:
        """
        Создание приходной накладной (Server API) - использует XML формат
        
        Args:
            invoice_data: Данные приходной накладной в формате словаря
        
        Returns:
            XML ответ от iiko API с результатом валидации (documentValidationResult)
        """
        try:
            token = await self._get_server_token()
            if not token:
                logger.error("Не удалось получить токен для Server API")
                return None
            
            # Строим XML из данных
            xml_content = self._build_incoming_invoice_xml(invoice_data)
            logger.debug(f"XML для приходной накладной:\n{xml_content}")
            
            params = {
                "key": token
            }
            
            headers = {
                "Content-Type": "application/xml"
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.server_base_url}/resto/api/documents/import/incomingInvoice",
                    params=params,
                    content=xml_content,
                    headers=headers
                )
                response.raise_for_status()
                
                # Парсим XML ответ
                xml_response = response.text
                logger.debug(f"XML ответ от iiko API при создании приходной накладной: {xml_response}")
                
                # Парсим documentValidationResult
                root = ET.fromstring(xml_response)
                result = {
                    "valid": root.find("valid").text.lower() == "true" if root.find("valid") is not None else False,
                    "warning": root.find("warning").text.lower() == "true" if root.find("warning") is not None else False,
                    "documentNumber": root.find("documentNumber").text if root.find("documentNumber") is not None else None,
                    "otherSuggestedNumber": root.find("otherSuggestedNumber").text if root.find("otherSuggestedNumber") is not None else None,
                    "errorMessage": root.find("errorMessage").text if root.find("errorMessage") is not None else None,
                    "additionalInfo": root.find("additionalInfo").text if root.find("additionalInfo") is not None else None,
                }
                
                return result
                
        except httpx.HTTPStatusError as e:
            error_detail = None
            try:
                error_detail = e.response.text
            except:
                error_detail = str(e)
            logger.error(f"HTTP ошибка при создании приходной накладной: {e.response.status_code} - {error_detail}")
            return None
        except Exception as e:
            logger.error(f"Ошибка создания приходной накладной: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    async def create_outgoing_invoice(
        self,
        invoice_data: Dict[Any, Any]
    ) -> Optional[Dict[Any, Any]]:
        """
        Создание расходной накладной (Server API) - использует XML формат
        
        Args:
            invoice_data: Данные расходной накладной в формате словаря
        
        Returns:
            JSON ответ от iiko API с результатом валидации/создания
        """
        try:
            token = await self._get_server_token()
            if not token:
                logger.error("Не удалось получить токен для Server API")
                return None
            
            # Строим XML из данных
            xml_content = self._build_outgoing_invoice_xml(invoice_data)
            logger.debug(f"XML для расходной накладной: {xml_content}")
            
            params = {
                "key": token
            }
            
            headers = {
                "Content-Type": "application/xml"
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.server_base_url}/resto/api/documents/import/outgoingInvoice",
                    params=params,
                    content=xml_content,
                    headers=headers
                )
                response.raise_for_status()
                
                # Server API возвращает XML с результатом валидации
                xml_response = response.text
                logger.debug(f"XML ответ от iiko API при создании расходной накладной: {xml_response}")
                
                # Парсим XML ответ
                try:
                    root = ET.fromstring(xml_response)
                    result = {}
                    
                    # Извлекаем основные поля из XML
                    if root.find("valid") is not None:
                        result["valid"] = root.find("valid").text.lower() == "true"
                    if root.find("warning") is not None:
                        result["warning"] = root.find("warning").text.lower() == "true"
                    if root.find("documentNumber") is not None:
                        result["documentNumber"] = root.find("documentNumber").text
                    if root.find("errorMessage") is not None:
                        result["errorMessage"] = root.find("errorMessage").text
                    if root.find("additionalInfo") is not None:
                        result["additionalInfo"] = root.find("additionalInfo").text
                    if root.find("id") is not None:
                        result["id"] = root.find("id").text
                    
                    return result
                except ET.ParseError as e:
                    logger.error(f"Ошибка парсинга XML ответа: {e}")
                    # Если не удалось распарсить, возвращаем текст
                    return {"raw_response": xml_response}
                
        except httpx.HTTPStatusError as e:
            error_detail = None
            try:
                error_detail = e.response.text
            except:
                error_detail = str(e)
            logger.error(f"HTTP ошибка при создании расходной накладной: {e.response.status_code} - {error_detail}")
            return None
        except Exception as e:
            logger.error(f"Ошибка создания расходной накладной: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    async def create_inventory(
        self,
        inventory_data: Dict[Any, Any]
    ) -> Optional[Dict[Any, Any]]:
        """
        Создание инвентаризации (Server API) - использует XML формат
        
        Args:
            inventory_data: Данные инвентаризации в формате словаря
        
        Returns:
            Результат валидации (incomingInventoryValidationResult)
        """
        try:
            token = await self._get_server_token()
            if not token:
                logger.error("Не удалось получить токен для Server API")
                return None
            
            # Строим XML из данных
            xml_content = self._build_inventory_xml(inventory_data)
            logger.debug(f"XML для инвентаризации: {xml_content}")
            
            params = {
                "key": token
            }
            
            headers = {
                "Content-Type": "application/xml"
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.server_base_url}/resto/api/documents/import/incomingInventory",
                    params=params,
                    content=xml_content,
                    headers=headers
                )
                response.raise_for_status()
                
                # Server API возвращает XML с результатом валидации
                xml_response = response.text
                logger.debug(f"XML ответ от iiko API при создании инвентаризации: {xml_response}")
                
                # Парсим XML ответ (incomingInventoryValidationResult)
                try:
                    root = ET.fromstring(xml_response)
                    result = {}
                    
                    # Общие поля результата валидации
                    if root.find("valid") is not None:
                        result["valid"] = root.find("valid").text.lower() == "true"
                    if root.find("warning") is not None:
                        result["warning"] = root.find("warning").text.lower() == "true"
                    if root.find("documentNumber") is not None:
                        result["documentNumber"] = root.find("documentNumber").text
                    if root.find("otherSuggestedNumber") is not None:
                        result["otherSuggestedNumber"] = root.find("otherSuggestedNumber").text
                    if root.find("errorMessage") is not None:
                        result["errorMessage"] = root.find("errorMessage").text
                    if root.find("additionalInfo") is not None:
                        result["additionalInfo"] = root.find("additionalInfo").text
                    
                    # Специфичные для инвентаризации поля
                    store_elem = root.find("store")
                    if store_elem is not None:
                        result["store"] = {
                            "id": store_elem.find("id").text if store_elem.find("id") is not None else None,
                            "code": store_elem.find("code").text if store_elem.find("code") is not None else None,
                            "name": store_elem.find("name").text if store_elem.find("name") is not None else None,
                        }
                    
                    if root.find("date") is not None:
                        result["date"] = root.find("date").text
                    
                    # Парсим items
                    items_elem = root.find("items")
                    if items_elem is not None:
                        result["items"] = []
                        for item_elem in items_elem.findall("item"):
                            product_elem = item_elem.find("product")
                            item_result = {
                                "product": {
                                    "id": product_elem.find("id").text if product_elem is not None and product_elem.find("id") is not None else None,
                                    "code": product_elem.find("code").text if product_elem is not None and product_elem.find("code") is not None else None,
                                    "name": product_elem.find("name").text if product_elem is not None and product_elem.find("name") is not None else None,
                                } if product_elem is not None else None,
                                "expectedAmount": float(item_elem.find("expectedAmount").text) if item_elem.find("expectedAmount") is not None else None,
                                "expectedSum": float(item_elem.find("expectedSum").text) if item_elem.find("expectedSum") is not None else None,
                                "actualAmount": float(item_elem.find("actualAmount").text) if item_elem.find("actualAmount") is not None else None,
                                "differenceAmount": float(item_elem.find("differenceAmount").text) if item_elem.find("differenceAmount") is not None else None,
                                "differenceSum": float(item_elem.find("differenceSum").text) if item_elem.find("differenceSum") is not None else None,
                            }
                            result["items"].append(item_result)
                    
                    return result
                except ET.ParseError as e:
                    logger.error(f"Ошибка парсинга XML ответа: {e}")
                    # Если не удалось распарсить, возвращаем текст
                    return {"raw_response": xml_response}
                
        except httpx.HTTPStatusError as e:
            error_detail = None
            try:
                error_detail = e.response.text
            except:
                error_detail = str(e)
            logger.error(f"HTTP ошибка при создании инвентаризации: {e.response.status_code} - {error_detail}")
            return None
        except Exception as e:
            logger.error(f"Ошибка создания инвентаризации: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    async def get_incoming_invoices(
        self,
        date_from: str,
        date_to: str
    ) -> Optional[List[Dict[Any, Any]]]:
        """Получение приходных накладных (Server API). Разбивается по дням."""
        assert_iiko_date_window(date_from, date_to, "get_incoming_invoices")
        try:
            token = await self._get_server_token()
            if not token:
                logger.error("Не удалось получить токен для Server API")
                return None

            current = datetime.strptime(date_from, "%Y-%m-%d").date()
            end = datetime.strptime(date_to, "%Y-%m-%d").date()

            all_invoices: List[Dict[Any, Any]] = []
            logger.info(f"Получение приходных накладных: разбивка по дням с {current} по {end}")

            while current <= end:
                next_day = current + timedelta(days=1)
                params = {
                    "key": token,
                    "from": current.strftime("%Y-%m-%d"),
                    "to": next_day.strftime("%Y-%m-%d"),
                }

                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.get(
                            f"{self.server_base_url}/resto/api/documents/export/incomingInvoice",
                            params=params,
                        )
                        response.raise_for_status()
                        xml_content = response.text

                    day_invoices = await self._parse_xml_incoming_invoices(xml_content)
                    if day_invoices:
                        all_invoices.extend(day_invoices)
                        logger.info(f"Приходные накладные за {current}: {len(day_invoices)} документов")
                    else:
                        logger.debug(f"Приходные накладные за {current}: нет данных")
                except Exception as day_err:
                    logger.error(f"Ошибка получения приходных накладных за {current}: {day_err}")

                current = next_day

            logger.info(f"Всего приходных накладных за период: {len(all_invoices)}")
            return all_invoices if all_invoices else None

        except Exception as e:
            logger.error(f"Ошибка получения приходных накладных: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    async def get_outgoing_invoices(
        self,
        date_from: str,
        date_to: str
    ) -> Optional[List[Dict[Any, Any]]]:
        """Получение расходных накладных (Server API). Разбивается по дням."""
        assert_iiko_date_window(date_from, date_to, "get_outgoing_invoices")
        try:
            token = await self._get_server_token()
            if not token:
                logger.error("Не удалось получить токен для Server API")
                return None

            current = datetime.strptime(date_from, "%Y-%m-%d").date()
            end = datetime.strptime(date_to, "%Y-%m-%d").date()

            all_invoices: List[Dict[Any, Any]] = []
            logger.info(f"Получение расходных накладных: разбивка по дням с {current} по {end}")

            while current <= end:
                next_day = current + timedelta(days=1)
                params = {
                    "key": token,
                    "from": current.strftime("%Y-%m-%d"),
                    "to": next_day.strftime("%Y-%m-%d"),
                }

                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.get(
                            f"{self.server_base_url}/resto/api/documents/export/outgoingInvoice",
                            params=params,
                        )
                        response.raise_for_status()
                        xml_content = response.text

                    day_invoices = await self._parse_xml_outgoing_invoices(xml_content)
                    if day_invoices:
                        all_invoices.extend(day_invoices)
                        logger.info(f"Расходные накладные за {current}: {len(day_invoices)} документов")
                    else:
                        logger.debug(f"Расходные накладные за {current}: нет данных")
                except Exception as day_err:
                    logger.error(f"Ошибка получения расходных накладных за {current}: {day_err}")

                current = next_day

            logger.info(f"Всего расходных накладных за период: {len(all_invoices)}")
            return all_invoices if all_invoices else None

        except Exception as e:
            logger.error(f"Ошибка получения расходных накладных: {e}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    async def _parse_xml_incoming_invoices(self, xml_content: str) -> Optional[List[Dict[Any, Any]]]:
        """Парсинг XML ответа с приходными накладными"""
        try:
            root = ET.fromstring(xml_content)
            invoices = []
            
            # Ищем элементы document (корневой элемент может быть разным, ищем все document)
            document_elems = root.findall('.//document') if root.tag != 'document' else [root]
            
            for doc_elem in document_elems:
                invoice_data = {}
                
                # Основные поля документа
                id_elem = doc_elem.find('id')
                invoice_data['id'] = id_elem.text if id_elem is not None else None
                
                conception_elem = doc_elem.find('conception')
                invoice_data['conception'] = conception_elem.text if conception_elem is not None else None
                
                conception_code_elem = doc_elem.find('conceptionCode')
                invoice_data['conception_code'] = conception_code_elem.text if conception_code_elem is not None else None
                
                comment_elem = doc_elem.find('comment')
                invoice_data['comment'] = comment_elem.text if comment_elem is not None else None
                
                document_number_elem = doc_elem.find('documentNumber')
                invoice_data['document_number'] = document_number_elem.text if document_number_elem is not None else None
                
                date_incoming_elem = doc_elem.find('dateIncoming')
                invoice_data['date_incoming'] = date_incoming_elem.text if date_incoming_elem is not None else None
                
                invoice_elem = doc_elem.find('invoice')
                invoice_data['invoice'] = invoice_elem.text if invoice_elem is not None else None
                
                default_store_elem = doc_elem.find('defaultStore')
                invoice_data['default_store'] = default_store_elem.text if default_store_elem is not None else None
                
                supplier_elem = doc_elem.find('supplier')
                invoice_data['supplier'] = supplier_elem.text if supplier_elem is not None else None
                
                due_date_elem = doc_elem.find('dueDate')
                invoice_data['due_date'] = due_date_elem.text if due_date_elem is not None else None
                
                incoming_date_elem = doc_elem.find('incomingDate')
                invoice_data['incoming_date'] = incoming_date_elem.text if incoming_date_elem is not None else None
                
                use_default_document_time_elem = doc_elem.find('useDefaultDocumentTime')
                invoice_data['use_default_document_time'] = use_default_document_time_elem.text.lower() == 'true' if use_default_document_time_elem is not None else False
                
                status_elem = doc_elem.find('status')
                invoice_data['status'] = status_elem.text if status_elem is not None else None
                
                incoming_document_number_elem = doc_elem.find('incomingDocumentNumber')
                invoice_data['incoming_document_number'] = incoming_document_number_elem.text if incoming_document_number_elem is not None else None
                
                employee_pass_to_account_elem = doc_elem.find('employeePassToAccount')
                invoice_data['employee_pass_to_account'] = employee_pass_to_account_elem.text if employee_pass_to_account_elem is not None else None
                
                transport_invoice_number_elem = doc_elem.find('transportInvoiceNumber')
                invoice_data['transport_invoice_number'] = transport_invoice_number_elem.text if transport_invoice_number_elem is not None else None
                
                linked_outgoing_invoice_id_elem = doc_elem.find('linkedOutgoingInvoiceId')
                invoice_data['linked_outgoing_invoice_id'] = linked_outgoing_invoice_id_elem.text if linked_outgoing_invoice_id_elem is not None else None
                
                distribution_algorithm_elem = doc_elem.find('distributionAlgorithm')
                invoice_data['distribution_algorithm'] = distribution_algorithm_elem.text if distribution_algorithm_elem is not None else None
                
                # Парсим organization_id (может быть в разных форматах)
                organization_id_elem = doc_elem.find('organizationId')
                if organization_id_elem is None:
                    organization_id_elem = doc_elem.find('organization_id')
                invoice_data['organization_id'] = organization_id_elem.text if organization_id_elem is not None else None
                
                # Позиции документа
                items = []
                items_elem = doc_elem.find('items')
                if items_elem is not None:
                    for item_elem in items_elem.findall('item'):
                        item_data = await self._parse_xml_incoming_invoice_item(item_elem)
                        items.append(item_data)
                
                invoice_data['items'] = items
                invoices.append(invoice_data)
            
            logger.info(f"Распарсено {len(invoices)} приходных накладных из XML")
            return invoices if invoices else None
            
        except ET.ParseError as e:
            logger.error(f"Ошибка парсинга XML приходных накладных (ParseError): {e}")
            logger.debug(f"XML содержимое (первые 500 символов): {xml_content[:500]}")
            return None
        except Exception as e:
            logger.error(f"Ошибка парсинга XML приходных накладных: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    async def _parse_xml_incoming_invoice_item(self, item_elem) -> Dict[Any, Any]:
        """Парсинг позиции приходной накладной"""
        item_data = {}
        
        is_additional_expense_elem = item_elem.find('isAdditionalExpense')
        item_data['is_additional_expense'] = is_additional_expense_elem.text.lower() == 'true' if is_additional_expense_elem is not None else False
        
        amount_elem = item_elem.find('amount')
        item_data['amount'] = amount_elem.text if amount_elem is not None else None
        
        supplier_product_elem = item_elem.find('supplierProduct')
        item_data['supplier_product'] = supplier_product_elem.text if supplier_product_elem is not None else None
        
        supplier_product_article_elem = item_elem.find('supplierProductArticle')
        item_data['supplier_product_article'] = supplier_product_article_elem.text if supplier_product_article_elem is not None else None
        
        product_elem = item_elem.find('product')
        item_data['product'] = product_elem.text if product_elem is not None else None
        
        product_article_elem = item_elem.find('productArticle')
        item_data['product_article'] = product_article_elem.text if product_article_elem is not None else None
        
        producer_elem = item_elem.find('producer')
        item_data['producer'] = producer_elem.text if producer_elem is not None else None
        
        num_elem = item_elem.find('num')
        item_data['num'] = int(num_elem.text) if num_elem is not None and num_elem.text else None
        
        container_id_elem = item_elem.find('containerId')
        item_data['container_id'] = container_id_elem.text if container_id_elem is not None else None
        
        amount_unit_elem = item_elem.find('amountUnit')
        item_data['amount_unit'] = amount_unit_elem.text if amount_unit_elem is not None else None
        
        actual_unit_weight_elem = item_elem.find('actualUnitWeight')
        item_data['actual_unit_weight'] = actual_unit_weight_elem.text if actual_unit_weight_elem is not None else None
        
        sum_elem = item_elem.find('sum')
        item_data['sum'] = sum_elem.text if sum_elem is not None else None
        
        discount_sum_elem = item_elem.find('discountSum')
        item_data['discount_sum'] = discount_sum_elem.text if discount_sum_elem is not None else None
        
        vat_percent_elem = item_elem.find('vatPercent')
        item_data['vat_percent'] = vat_percent_elem.text if vat_percent_elem is not None else None
        
        vat_sum_elem = item_elem.find('vatSum')
        item_data['vat_sum'] = vat_sum_elem.text if vat_sum_elem is not None else None
        
        price_unit_elem = item_elem.find('priceUnit')
        item_data['price_unit'] = price_unit_elem.text if price_unit_elem is not None else None
        
        price_elem = item_elem.find('price')
        item_data['price'] = price_elem.text if price_elem is not None else None
        
        price_without_vat_elem = item_elem.find('priceWithoutVat')
        item_data['price_without_vat'] = price_without_vat_elem.text if price_without_vat_elem is not None else None
        
        code_elem = item_elem.find('code')
        item_data['code'] = code_elem.text if code_elem is not None else None
        
        store_elem = item_elem.find('store')
        item_data['store'] = store_elem.text if store_elem is not None else None
        
        customs_declaration_number_elem = item_elem.find('customsDeclarationNumber')
        item_data['customs_declaration_number'] = customs_declaration_number_elem.text if customs_declaration_number_elem is not None else None
        
        actual_amount_elem = item_elem.find('actualAmount')
        item_data['actual_amount'] = actual_amount_elem.text if actual_amount_elem is not None else None
        
        return item_data

    async def _parse_xml_outgoing_invoices(self, xml_content: str) -> Optional[List[Dict[Any, Any]]]:
        """Парсинг XML ответа с расходными накладными"""
        try:
            root = ET.fromstring(xml_content)
            invoices = []
            
            # Ищем элементы document
            document_elems = root.findall('.//document') if root.tag != 'document' else [root]
            
            for doc_elem in document_elems:
                invoice_data = {}
                
                # Основные поля документа
                id_elem = doc_elem.find('id')
                invoice_data['id'] = id_elem.text if id_elem is not None else None
                
                document_number_elem = doc_elem.find('documentNumber')
                invoice_data['document_number'] = document_number_elem.text if document_number_elem is not None else None
                
                date_incoming_elem = doc_elem.find('dateIncoming')
                invoice_data['date_incoming'] = date_incoming_elem.text if date_incoming_elem is not None else None
                
                use_default_document_time_elem = doc_elem.find('useDefaultDocumentTime')
                invoice_data['use_default_document_time'] = use_default_document_time_elem.text.lower() == 'true' if use_default_document_time_elem is not None else False
                
                status_elem = doc_elem.find('status')
                invoice_data['status'] = status_elem.text if status_elem is not None else None
                
                account_to_code_elem = doc_elem.find('accountToCode')
                invoice_data['account_to_code'] = account_to_code_elem.text if account_to_code_elem is not None else None
                
                revenue_account_code_elem = doc_elem.find('revenueAccountCode')
                invoice_data['revenue_account_code'] = revenue_account_code_elem.text if revenue_account_code_elem is not None else None
                
                default_store_id_elem = doc_elem.find('defaultStoreId')
                invoice_data['default_store_id'] = default_store_id_elem.text if default_store_id_elem is not None else None
                
                default_store_code_elem = doc_elem.find('defaultStoreCode')
                invoice_data['default_store_code'] = default_store_code_elem.text if default_store_code_elem is not None else None
                
                counteragent_id_elem = doc_elem.find('counteragentId')
                invoice_data['counteragent_id'] = counteragent_id_elem.text if counteragent_id_elem is not None else None
                
                counteragent_code_elem = doc_elem.find('counteragentCode')
                invoice_data['counteragent_code'] = counteragent_code_elem.text if counteragent_code_elem is not None else None
                
                conception_id_elem = doc_elem.find('conceptionId')
                invoice_data['conception_id'] = conception_id_elem.text if conception_id_elem is not None else None
                
                conception_code_elem = doc_elem.find('conceptionCode')
                invoice_data['conception_code'] = conception_code_elem.text if conception_code_elem is not None else None
                
                comment_elem = doc_elem.find('comment')
                invoice_data['comment'] = comment_elem.text if comment_elem is not None else None
                
                linked_outgoing_invoice_id_elem = doc_elem.find('linkedOutgoingInvoiceId')
                invoice_data['linked_outgoing_invoice_id'] = linked_outgoing_invoice_id_elem.text if linked_outgoing_invoice_id_elem is not None else None
                
                # Позиции документа
                items = []
                items_elem = doc_elem.find('items')
                if items_elem is not None:
                    for item_elem in items_elem.findall('item'):
                        item_data = await self._parse_xml_outgoing_invoice_item(item_elem)
                        items.append(item_data)
                
                invoice_data['items'] = items
                invoices.append(invoice_data)
            
            logger.info(f"Распарсено {len(invoices)} расходных накладных из XML")
            return invoices if invoices else None
            
        except ET.ParseError as e:
            logger.error(f"Ошибка парсинга XML расходных накладных (ParseError): {e}")
            logger.debug(f"XML содержимое (первые 500 символов): {xml_content[:500]}")
            return None
        except Exception as e:
            logger.error(f"Ошибка парсинга XML расходных накладных: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    async def _parse_xml_outgoing_invoice_item(self, item_elem) -> Dict[Any, Any]:
        """Парсинг позиции расходной накладной"""
        item_data = {}
        
        product_id_elem = item_elem.find('productId')
        item_data['product_id'] = product_id_elem.text if product_id_elem is not None else None
        
        product_article_elem = item_elem.find('productArticle')
        item_data['product_article'] = product_article_elem.text if product_article_elem is not None else None
        
        store_id_elem = item_elem.find('storeId')
        item_data['store_id'] = store_id_elem.text if store_id_elem is not None else None
        
        store_code_elem = item_elem.find('storeCode')
        item_data['store_code'] = store_code_elem.text if store_code_elem is not None else None
        
        container_id_elem = item_elem.find('containerId')
        item_data['container_id'] = container_id_elem.text if container_id_elem is not None else None
        
        container_code_elem = item_elem.find('containerCode')
        item_data['container_code'] = container_code_elem.text if container_code_elem is not None else None
        
        price_elem = item_elem.find('price')
        item_data['price'] = price_elem.text if price_elem is not None else None
        
        price_without_vat_elem = item_elem.find('priceWithoutVat')
        item_data['price_without_vat'] = price_without_vat_elem.text if price_without_vat_elem is not None else None
        
        amount_elem = item_elem.find('amount')
        item_data['amount'] = amount_elem.text if amount_elem is not None else None
        
        sum_elem = item_elem.find('sum')
        item_data['sum'] = sum_elem.text if sum_elem is not None else None
        
        discount_sum_elem = item_elem.find('discountSum')
        item_data['discount_sum'] = discount_sum_elem.text if discount_sum_elem is not None else None
        
        vat_percent_elem = item_elem.find('vatPercent')
        item_data['vat_percent'] = vat_percent_elem.text if vat_percent_elem is not None else None
        
        vat_sum_elem = item_elem.find('vatSum')
        item_data['vat_sum'] = vat_sum_elem.text if vat_sum_elem is not None else None
        
        return item_data

    def clear_tokens(self):
        """Очистка токенов (для принудительного обновления)"""
        self.cloud_token = None
        self.server_token = None
        self.cloud_token_expires = None
        self.server_token_expires = None
        logger.info("Токены iiko API очищены")

    async def get_server_stores(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение списка складов (Server API) - возвращает XML"""
        # Получаем токен
        token = await self._get_server_token()
        if not token:
            logger.error("Не удалось получить токен для Server API")
            return None
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.server_base_url}/resto/api/corporation/stores/"
                params = {"key": token}
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    # Server API возвращает XML, нужно парсить его
                    xml_content = response.text
                    logger.debug(f"XML ответ от iiko API (первые 1000 символов): {xml_content[:1000]}")
                    return await self._parse_xml_stores(xml_content)
                else:
                    logger.error(f"HTTP ошибка server API: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка запроса к server API: {e}")
            return None

    async def _parse_xml_stores(self, xml_content: str) -> Optional[List[Dict[Any, Any]]]:
        """Парсинг XML ответа со складами"""
        try:
            if not xml_content or not xml_content.strip():
                logger.warning("Получен пустой XML ответ от iiko API")
                return []
            
            root = ET.fromstring(xml_content)
            stores = []
            
            logger.debug(f"Корневой элемент XML: tag={root.tag}, attrib={root.attrib}")
            
            # Пробуем разные варианты поиска элементов складов
            # Вариант 1: ищем все элементы store (включая вложенные)
            store_elems = root.findall('.//store')
            
            # Вариант 2: если не нашли, пробуем найти элементы с другими тегами
            if not store_elems:
                # Пробуем найти элементы с тегом, содержащим "store" (case-insensitive)
                for elem in root.iter():
                    if 'store' in elem.tag.lower():
                        store_elems.append(elem)
            
            # Вариант 3: если корневой элемент сам является store
            if not store_elems and root.tag.lower() == 'store':
                store_elems = [root]
            
            # Вариант 4: пробуем найти все дочерние элементы корня
            if not store_elems:
                store_elems = list(root)
                logger.debug(f"Найдено дочерних элементов: {len(store_elems)}, теги: {[e.tag for e in store_elems[:5]]}")
            
            logger.debug(f"Найдено элементов store: {len(store_elems)}")
            
            for store_elem in store_elems:
                store_data = {}
                
                # Основные поля - пробуем разные варианты
                # Вариант 1: ищем дочерние элементы
                id_elem = store_elem.find('id')
                if id_elem is not None:
                    store_data['id'] = id_elem.text
                else:
                    # Вариант 2: пробуем найти атрибут id
                    store_data['id'] = store_elem.get('id')
                
                name_elem = store_elem.find('name')
                if name_elem is not None:
                    store_data['name'] = name_elem.text
                else:
                    # Пробуем атрибут name
                    store_data['name'] = store_elem.get('name')
                
                code_elem = store_elem.find('code')
                if code_elem is not None:
                    store_data['code'] = code_elem.text
                else:
                    # Пробуем атрибут code
                    store_data['code'] = store_elem.get('code')

                # parentId — iiko_id департамента-владельца (для маппинга в organization)
                parent_elem = store_elem.find('parentId')
                if parent_elem is not None:
                    store_data['parent_id'] = parent_elem.text
                else:
                    store_data['parent_id'] = store_elem.get('parentId')

                # Если id не найден, пробуем использовать text элемента или другие варианты
                if not store_data['id']:
                    # Пробуем использовать text самого элемента
                    if store_elem.text and store_elem.text.strip():
                        store_data['id'] = store_elem.text.strip()
                    # Пробуем найти любой атрибут, который может быть id
                    for attr_name, attr_value in store_elem.attrib.items():
                        if 'id' in attr_name.lower() or attr_name.lower() == 'uuid':
                            store_data['id'] = attr_value
                            break
                
                # Если все еще нет id, логируем предупреждение и пропускаем
                if not store_data['id']:
                    logger.warning(f"Склад без id найден: tag={store_elem.tag}, attrib={store_elem.attrib}, text={store_elem.text}")
                    continue
                
                stores.append(store_data)
            
            logger.info(f"Парсинг XML складов: {len(stores)} записей")
            if len(stores) == 0:
                logger.warning(f"Не найдено складов в XML. Структура XML: tag={root.tag}, дочерние элементы: {[e.tag for e in list(root)[:10]]}")
                logger.debug(f"Полный XML (первые 2000 символов): {xml_content[:2000]}")
            
            return stores
            
        except ET.ParseError as e:
            logger.error(f"Ошибка парсинга XML складов (ParseError): {e}")
            logger.debug(f"XML содержимое (первые 2000 символов): {xml_content[:2000]}")
            return None
        except Exception as e:
            logger.error(f"Ошибка парсинга XML складов: {e}", exc_info=True)
            logger.debug(f"XML содержимое (первые 2000 символов): {xml_content[:2000]}")
            return None

    async def get_server_balance_stores(self, timestamp: Optional[str] = None) -> Optional[List[Dict[Any, Any]]]:
        """
        Получение остатков товаров по складам (Server API)
        
        Args:
            timestamp: Дата и время в формате ISO (например, "2025-12-27T12:20:00")
                      Если не указано, используется текущее время
        """
        params = {}
        if timestamp:
            params["timestamp"] = timestamp
        else:
            # Используем текущее время в формате ISO
            from datetime import datetime
            params["timestamp"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/v2/reports/balance/stores",
            params=params
        )

    async def get_server_conceptions(self) -> Optional[List[Dict[Any, Any]]]:
        """
        Получение концепций (Server API)

        Правильный эндпоинт:
        /resto/api/v2/entities/list?rootType=Conception&includeDeleted=true

        Возвращает массив объектов:
        {
            "rootType": "Conception",
            "id": "...",
            "deleted": false,
            "code": "15",
            "name": "NEW Фабрика"
        }
        """
        params = {
            "rootType": "Conception",
            "includeDeleted": "true",
        }
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/v2/entities/list",
            params=params,
        )

    async def get_server_suppliers(self) -> Optional[List[Dict[Any, Any]]]:
        """
        Получение поставщиков (Server API)

        Правильный эндпоинт:
        /resto/api/suppliers

        Возвращает XML вида:
        <employees>
            <employee>
                <id>...</id>
                <code>...</code>
                <name>...</name>
                ...
                <supplier>true</supplier>
            </employee>
        </employees>
        """
        # Получаем токен
        token = await self._get_server_token()
        if not token:
            logger.error("Не удалось получить токен для Server API")
            return None

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.server_base_url}/resto/api/suppliers"
                params = {"key": token}
                response = await client.get(url, params=params)

                if response.status_code != 200:
                    logger.error(f"HTTP ошибка server API (suppliers): {response.status_code} - {response.text}")
                    return None

                xml_content = response.text
                logger.debug(f"XML ответ от iiko suppliers (первые 1000 символов): {xml_content[:1000]}")

                # Парсим XML
                try:
                    root = ET.fromstring(xml_content)
                except ET.ParseError as e:
                    logger.error(f"Ошибка парсинга XML поставщиков: {e}")
                    return None

                suppliers: List[Dict[str, Any]] = []
                for employee_elem in root.findall(".//employee"):
                    supplier_flag = employee_elem.findtext("supplier")
                    if supplier_flag is not None and supplier_flag.strip().lower() != "true":
                        continue

                    supplier_data: Dict[str, Any] = {}
                    supplier_data["id"] = employee_elem.findtext("id")
                    supplier_data["code"] = employee_elem.findtext("code")
                    supplier_data["name"] = employee_elem.findtext("name")
                    supplier_data["taxpayerIdNumber"] = employee_elem.findtext("taxpayerIdNumber")

                    if supplier_data["id"]:
                        suppliers.append(supplier_data)

                logger.info(f"Парсинг XML поставщиков: {len(suppliers)} записей")
                return suppliers
        except Exception as e:
            logger.error(f"Ошибка запроса к server API (suppliers): {e}", exc_info=True)
            return None

    async def get_server_counteragents(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение контрагентов (Server API)"""
        # Пробуем стандартный эндпоинт для entities
        result = await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/v2/entities/counteragents/list"
        )
        if result:
            return result
        
        # Если не сработало, пробуем альтернативный эндпоинт
        logger.warning("Стандартный эндпоинт для контрагентов не сработал, пробуем альтернативный")
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/corporation/counteragents"
        )

    async def get_conceptions(self, prefer_cloud: bool = False) -> Optional[List[Dict[Any, Any]]]:
        """Получение концепций (только Server API)"""
        return await self.get_server_conceptions()

    async def get_suppliers(self, prefer_cloud: bool = False) -> Optional[List[Dict[Any, Any]]]:
        """Получение поставщиков (только Server API)"""
        return await self.get_server_suppliers()

    async def get_counteragents(self, prefer_cloud: bool = False) -> Optional[List[Dict[Any, Any]]]:
        """Получение контрагентов (только Server API)"""
        return await self.get_server_counteragents()

    async def get_pay_in_out_types(self, include_deleted: bool = False) -> Optional[List[Dict[Any, Any]]]:
        """
        Получение типов изъятий/внесений (Server API)
        
        Args:
            include_deleted: Включать ли удаленные типы
        
        Returns:
            Список типов изъятий/внесений
        """
        params = {
            "includeDeleted": str(include_deleted).lower()
        }
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/v2/entities/payInOutTypes/list",
            params=params
        )

    async def get_payrolls(
        self,
        date_from: str,
        date_to: str,
        department: Optional[str] = None,
        include_deleted: bool = False
    ) -> Optional[List[Dict[Any, Any]]]:
        """
        Получение платежных ведомостей (Server API) — чанкуется по дням,
        максимальное окно — MAX_IIKO_DATE_WINDOW_DAYS дней.

        Args:
            date_from: Начало периода в формате yyyy-MM-dd, включительно
            date_to: Окончание периода в формате yyyy-MM-dd, включительно
            department: UUID торгового предприятия (опционально)
            include_deleted: Включать ли удаленные ведомости

        Returns:
            Список платежных ведомостей (объединённый по всем дням)
        """
        try:
            chunks = list(iter_day_chunks(date_from, date_to))
        except ValueError as e:
            logger.error(f"get_payrolls: невалидный диапазон: {e}")
            return None

        all_payrolls: List[Dict[Any, Any]] = []
        logger.info(f"Запрос payrolls: разбивка на {len(chunks)} дн. с {date_from} по {date_to}")
        for day_start, _day_end_exclusive in chunks:
            day_str = day_start.strftime("%Y-%m-%d")
            params = {
                "dateFrom": day_str,
                "dateTo": day_str,  # iiko payrolls: оба включительно, на один день оба равны
                "includeDeleted": str(include_deleted).lower(),
            }
            if department:
                params["department"] = department
            try:
                result = await self._make_request(
                    IikoApiType.SERVER,
                    "/resto/api/v2/payrolls/list",
                    params=params,
                )
                if result and isinstance(result, list):
                    all_payrolls.extend(result)
            except Exception as e:
                logger.error(f"Ошибка при получении payrolls за {day_str}: {e}")

        logger.info(f"Получено {len(all_payrolls)} payrolls за период {date_from} — {date_to}")
        return all_payrolls if all_payrolls else None

    async def create_pay_out(self, pay_out_data: Dict[str, Any]) -> Optional[Dict[Any, Any]]:
        """
        Создание изъятия из кассы (Server API) - использует JSON формат
        
        Args:
            pay_out_data: Данные изъятия в формате словаря:
                {
                    "payOutTypeId": str,  # UUID типа изъятия
                    "payOutDate": str,  # Дата в формате yyyy-MM-dd
                    "counteragent": Optional[str],  # UUID контрагента
                    "departmentSumMap": Dict[str, float],  # department UUID -> сумма
                    "payrollId": Optional[str],  # UUID платежной ведомости
                    "comment": Optional[str]  # Комментарий
                }
        
        Returns:
            JSON ответ от iiko API с результатом:
            {
                "result": "SUCCESS" или "ERROR",
                "errors": List[Dict] или None,
                "payOutSettings" или "payOutSettingsDto": Dict
            }
        """
        try:
            token = await self._get_server_token()
            if not token:
                logger.error("Не удалось получить токен для Server API")
                return None
            
            params = {
                "key": token
            }
            
            # Для поддержки кириллицы в комментариях используем charset=UTF-8
            headers = {
                "Content-Type": "application/json;charset=UTF-8"
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.server_base_url}/resto/api/v2/payInOuts/addPayOut",
                    params=params,
                    json=pay_out_data,
                    headers=headers
                )
                response.raise_for_status()
                
                result = response.json()
                logger.debug(f"Ответ от iiko API при создании изъятия: {result}")
                
                return result
                
        except httpx.HTTPStatusError as e:
            error_detail = None
            try:
                error_detail = e.response.text
            except:
                error_detail = str(e)
            logger.error(f"HTTP ошибка при создании изъятия: {e.response.status_code} - {error_detail}")
            return None
        except Exception as e:
            logger.error(f"Ошибка создания изъятия: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    async def get_payment_types(self, organization_ids: List[str]) -> Optional[Dict]:
        """Получение видов оплат (Cloud API POST /api/1/payment_types).

        Возвращает только виды, привязанные к terminalGroups (~6 для нашего ресторана).
        Полная схема: paymentTypeKind, terminalGroups, combinable, paymentProcessingType.
        """
        try:
            data = {"organizationIds": organization_ids}
            result = await self._make_request(
                IikoApiType.CLOUD,
                "/api/1/payment_types",
                method="POST",
                data=data,
            )
            return result
        except Exception as e:
            logger.error(f"Ошибка получения видов оплат: {e}")
            return None

    async def get_server_payment_types(self) -> Optional[List[Dict[Any, Any]]]:
        """Получение полного справочника видов оплат (Server API entities/list).

        Возвращает ВСЕ виды (~43 для нашего ресторана), включая банковские и
        служебные. Схема минимальная: id, name, code, deleted. Никакого
        paymentTypeKind / terminalGroups — это нужно достраивать эвристиками.

        Используется в `sync_payment_types` как secondary источник, который
        мерджится с Cloud по iiko_id.
        """
        params = {
            "rootType": "PaymentType",
            "includeDeleted": "true",
        }
        return await self._make_request(
            IikoApiType.SERVER,
            "/resto/api/v2/entities/list",
            params=params,
        )

    async def get_server_jur_persons(self) -> Optional[List[Dict[str, Any]]]:
        """Получение списка юр.лиц (JURPERSON из corporate tree).

        Дёргает `/resto/api/corporation/departments`, парсит XML и возвращает
        ТОЛЬКО элементы type=JURPERSON: [{'id', 'name', 'parentId'}].

        Используется для маппинга вида оплаты с именем «Каспий банк ИП Шаяхметов»
        к набору организаций конкретного юр.лица.
        """
        token = await self._get_server_token()
        if not token:
            logger.error("Не удалось получить токен Server API для get_server_jur_persons")
            return None
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.server_base_url}/resto/api/corporation/departments"
                resp = await client.get(url, params={"key": token})
                if resp.status_code != 200:
                    logger.error(f"get_server_jur_persons: HTTP {resp.status_code} - {resp.text[:200]}")
                    return None
                root = ET.fromstring(resp.text)
                jur_persons = []
                for item in root.findall('.//corporateItemDto'):
                    type_el = item.find('type')
                    if type_el is None or type_el.text != 'JURPERSON':
                        continue
                    id_el = item.find('id')
                    name_el = item.find('name')
                    parent_el = item.find('parentId')
                    jur_persons.append({
                        'id': id_el.text if id_el is not None else None,
                        'name': (name_el.text or '').strip() if name_el is not None else None,
                        'parentId': parent_el.text if parent_el is not None else None,
                    })
                logger.info(f"Получено {len(jur_persons)} юр.лиц из corporate tree")
                return jur_persons
        except Exception as e:
            logger.error(f"Ошибка получения юр.лиц: {e}")
            return None


# Глобальный экземпляр сервиса
iiko_service = IikoService()
