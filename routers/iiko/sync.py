"""
Роутер для синхронизации с iiko API.

Все sync-операции выполняются в отдельных потоках (через run_sync_in_thread / run_sync_in_background),
чтобы не блокировать основной event loop FastAPI и не замораживать остальные API-запросы.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta, date

from services.iiko import iiko_sync
from services.iiko.iiko_service import iiko_service
from services.transactions_and_statistics.daily_aggregates_service import (
    recalculate_daily_metrics_for_date,
    recalculate_daily_employee_metrics_for_date
)
from services.warehouse.balance_service import sync_conceptions_from_iiko, sync_suppliers_from_iiko, sync_stores_from_iiko
from utils.cache import invalidate_cache
from utils.telegram_notify import send_telegram_alert
from utils.sync_runner import (
    run_sync_in_thread,
    run_sync_in_background,
    get_sync_status,
    get_all_sync_statuses,
)
import config

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Одиночные sync-эндпоинты ====================


@router.post("/organizations")
async def sync_organizations() -> Dict[str, Any]:
    """
    Синхронизация организаций с iiko API
    """
    try:
        logger.info("Запуск синхронизации организаций")
        result = await run_sync_in_thread(iiko_sync.sync_organizations)

        invalidate_cache("organizations")
        logger.info("Кэш организаций инвалидирован")

        return {
            "success": True,
            "message": "Синхронизация организаций завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации организаций: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации организаций: {str(e)}"
        )


@router.post("/organizations/cloud-ids")
async def sync_cloud_org_ids() -> Dict[str, Any]:
    """
    Синхронизация iiko_id_cloud для организаций.
    Матчит Cloud API организации по имени с локальными и сохраняет iiko_id_cloud.
    """
    try:
        result = await run_sync_in_thread(iiko_sync.sync_cloud_org_ids)
        return {
            "success": True,
            "message": "Синхронизация Cloud org IDs завершена",
            "data": result
        }
    except Exception as e:
        logger.error(f"Ошибка синхронизации Cloud org IDs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/employees")
async def sync_employees(
    organization_id: str = None,
) -> Dict[str, Any]:
    """
    Синхронизация сотрудников с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации сотрудников для организации: {organization_id}")
        result = await run_sync_in_thread(iiko_sync.sync_employees, organization_id)

        return {
            "success": True,
            "message": "Синхронизация сотрудников завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации сотрудников: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации сотрудников: {str(e)}"
        )


@router.post("/terminal-groups")
async def sync_terminal_groups(
    organization_id: str = None,
) -> Dict[str, Any]:
    """
    Синхронизация групп терминалов с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации групп терминалов для организации: {organization_id}")
        result = await run_sync_in_thread(iiko_sync.sync_terminal_groups, organization_id)

        return {
            "success": True,
            "message": "Синхронизация групп терминалов завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации групп терминалов: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации групп терминалов: {str(e)}"
        )


@router.post("/terminals")
async def sync_terminals(
    organization_id: str = None,
) -> Dict[str, Any]:
    """
    Синхронизация терминалов с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации терминалов для организации: {organization_id}")
        result = await run_sync_in_thread(iiko_sync.sync_terminals, organization_id)

        return {
            "success": True,
            "message": "Синхронизация терминалов завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации терминалов: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации терминалов: {str(e)}"
        )


@router.post("/roles")
async def sync_roles() -> Dict[str, Any]:
    """
    Синхронизация ролей с iiko API
    """
    try:
        logger.info("Запуск синхронизации ролей")
        result = await run_sync_in_thread(iiko_sync.sync_roles)

        return {
            "success": True,
            "message": "Синхронизация ролей завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации ролей: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации ролей: {str(e)}"
        )


@router.post("/attendance-types")
async def sync_attendance_types() -> Dict[str, Any]:
    """
    Синхронизация типов явок с iiko API
    """
    try:
        logger.info("Запуск синхронизации типов явок")
        result = await run_sync_in_thread(iiko_sync.sync_attendance_types)

        return {
            "success": True,
            "message": "Синхронизация типов явок завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации типов явок: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации типов явок: {str(e)}"
        )


@router.post("/restaurant-sections")
async def sync_restaurant_sections(
    organization_id: str = None,
) -> Dict[str, Any]:
    """
    Синхронизация секций ресторана с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации секций ресторана для организации: {organization_id}")
        result = await run_sync_in_thread(iiko_sync.sync_restaurant_sections, organization_id)

        return {
            "success": True,
            "message": "Синхронизация секций ресторана завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации секций ресторана: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации секций ресторана: {str(e)}"
        )


@router.post("/tables")
async def sync_tables(
    organization_id: str = None,
) -> Dict[str, Any]:
    """
    Синхронизация столов с iiko API.

    `organization_id` принимает либо наш внутренний id (число), либо iiko cloud uuid.
    Если передан числовой id — конвертируем в `organizations.iiko_id_cloud`.
    """
    try:
        # Если organization_id числовой — переводим в cloud uuid
        if organization_id and organization_id.isdigit():
            from database.database import SessionLocal
            from models.organization import Organization
            _db = SessionLocal()
            try:
                org = _db.query(Organization).filter(Organization.id == int(organization_id)).first()
                if not org:
                    raise HTTPException(status_code=404, detail=f"Organization with id {organization_id} not found")
                cloud_uuid = org.iiko_id_cloud or org.iiko_id
                if not cloud_uuid:
                    raise HTTPException(status_code=400, detail=f"Organization {organization_id} has no iiko_id_cloud/iiko_id")
                logger.info(f"sync_tables: внутренний id {organization_id} → cloud uuid {cloud_uuid}")
                organization_id = cloud_uuid
            finally:
                _db.close()

        logger.info(f"Запуск синхронизации столов для организации: {organization_id}")
        result = await run_sync_in_thread(iiko_sync.sync_tables, organization_id)

        return {
            "success": True,
            "message": "Синхронизация столов завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации столов: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации столов: {str(e)}"
        )


@router.post("/accounts")
async def sync_accounts() -> Dict[str, Any]:
    """
    Синхронизация счетов с iiko API (Server API)
    """
    try:
        logger.info("Запуск синхронизации счетов")
        result = await run_sync_in_thread(iiko_sync.sync_accounts)

        return {
            "success": True,
            "message": "Синхронизация счетов завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации счетов: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации счетов: {str(e)}"
        )


@router.post("/salaries")
async def sync_salaries() -> Dict[str, Any]:
    """
    Синхронизация окладов сотрудников с iiko API (Server API)
    """
    try:
        logger.info("Запуск синхронизации окладов")
        result = await run_sync_in_thread(iiko_sync.sync_salaries)

        return {
            "success": True,
            "message": "Синхронизация окладов завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации окладов: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации окладов: {str(e)}"
        )


@router.post("/payment-types")
async def sync_payment_types() -> Dict[str, Any]:
    """
    Синхронизация видов оплат с iiko API (Cloud API)
    """
    try:
        logger.info("Запуск синхронизации видов оплат")
        result = await run_sync_in_thread(iiko_sync.sync_payment_types)

        invalidate_cache("payment_types")
        logger.info("Кэш видов оплат инвалидирован")

        return {
            "success": True,
            "message": "Синхронизация видов оплат завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации видов оплат: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации видов оплат: {str(e)}"
        )


@router.post("/shifts")
async def sync_shifts(
    date_from: Optional[str] = Query(default=None, description="Дата начала в формате YYYY-MM-DD (по умолчанию 30 дней назад)"),
    date_to: Optional[str] = Query(default=None, description="Дата конца в формате YYYY-MM-DD (по умолчанию сегодня)"),
) -> Dict[str, Any]:
    """
    Синхронизация смен сотрудников с iiko API (Server API)
    """
    try:
        # Парсим даты
        from_dt = None
        to_dt = None

        if date_from:
            try:
                from_dt = datetime.strptime(date_from, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Неверный формат date_from: {date_from}. Ожидается YYYY-MM-DD")

        if date_to:
            try:
                to_dt = datetime.strptime(date_to, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Неверный формат date_to: {date_to}. Ожидается YYYY-MM-DD")

        async def _sync_shifts_with_employees(db, f_dt, t_dt):
            """Синхронизация сотрудников + смен в одном потоке с одной DB-сессией."""
            logger.info("Синхронизация сотрудников перед синхронизацией смен...")
            employees_result = await iiko_sync.sync_employees(db, organization_id=None)
            logger.info(f"Синхронизация сотрудников завершена: {employees_result}")

            logger.info(f"Запуск синхронизации смен с {f_dt or '30 дней назад'} по {t_dt or 'сегодня'}")
            return await iiko_sync.sync_shifts(db, f_dt, t_dt)

        result = await run_sync_in_thread(_sync_shifts_with_employees, from_dt, to_dt)

        return {
            "success": True,
            "message": "Синхронизация смен завершена",
            "data": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка синхронизации смен: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации смен: {str(e)}"
        )


@router.post("/menu")
async def sync_menu(
    organization_id: str = None,
) -> Dict[str, Any]:
    """
    Синхронизация меню с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации меню для организации: {organization_id}")

        async def _sync_menu_with_indexes(db, org_id):
            result = await iiko_sync.sync_menu(db, org_id)
            try:
                from utils.db_indexes import optimize_indexes
                optimize_indexes(db)
                logger.info("Индексы оптимизированы после синхронизации меню")
            except Exception as e:
                logger.warning(f"Не удалось оптимизировать индексы: {e}")
            return result

        result = await run_sync_in_thread(_sync_menu_with_indexes, organization_id)

        invalidate_cache("menu")
        invalidate_cache("goods")
        logger.info("Кэш меню и товаров инвалидирован")

        return {
            "success": True,
            "message": "Синхронизация меню завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации меню: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации меню: {str(e)}"
        )


@router.post("/all")
async def sync_all(
    organization_id: str = None,
) -> Dict[str, Any]:
    """
    Полная синхронизация всех данных с iiko API
    """
    try:
        logger.info(f"Запуск полной синхронизации для организации: {organization_id}")

        async def _sync_all_with_indexes(db, org_id):
            result = await iiko_sync.sync_all(db, org_id)
            try:
                from utils.db_indexes import optimize_indexes
                optimize_indexes(db)
                logger.info("Индексы оптимизированы после полной синхронизации")
            except Exception as e:
                logger.warning(f"Не удалось оптимизировать индексы: {e}")
            return result

        result = await run_sync_in_thread(_sync_all_with_indexes, organization_id)

        return {
            "success": True,
            "message": "Полная синхронизация завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка полной синхронизации: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка полной синхронизации: {str(e)}"
        )


@router.post("/organizations-employees-terminals")
async def sync_organizations_employees_terminals(
    organization_id: str = None,
) -> Dict[str, Any]:
    """
    Синхронизация организаций, сотрудников и терминалов с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации организаций, сотрудников и терминалов для организации: {organization_id}")

        async def _sync_org_emp_term(db, org_id):
            results = {}

            logger.info("Синхронизация организаций...")
            org_result = await iiko_sync.sync_organizations(db)
            results["organizations"] = org_result

            logger.info("Синхронизация сотрудников...")
            emp_result = await iiko_sync.sync_employees(db, org_id)
            results["employees"] = emp_result

            logger.info("Синхронизация терминалов...")
            term_result = await iiko_sync.sync_terminals(db, org_id)
            results["terminals"] = term_result

            total_created = org_result.get("created", 0) + emp_result.get("created", 0) + term_result.get("created", 0)
            total_updated = org_result.get("updated", 0) + emp_result.get("updated", 0) + term_result.get("updated", 0)
            total_errors = org_result.get("errors", 0) + emp_result.get("errors", 0) + term_result.get("errors", 0)

            return {
                "results": results,
                "summary": {
                    "total_created": total_created,
                    "total_updated": total_updated,
                    "total_errors": total_errors
                }
            }

        data = await run_sync_in_thread(_sync_org_emp_term, organization_id)

        return {
            "success": True,
            "message": "Синхронизация организаций, сотрудников и терминалов завершена",
            "data": data
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации организаций, сотрудников и терминалов: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации: {str(e)}"
        )


@router.post("/transactions")
async def sync_transactions(
    from_date: str = None,
    to_date: str = None,
) -> Dict[str, Any]:
    """
    Синхронизация транзакций с iiko API (последовательная обработка дней из-за блокирующей авторизации)
    """
    try:
        if from_date is None:
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d") + "T00:00:00.000"
        if to_date is None:
            to_date = datetime.now().strftime("%Y-%m-%d") + "T00:00:00.000"

        async def _sync_transactions(db, f_date, t_date):
            # Сначала синхронизируем счета
            logger.info("Запуск синхронизации счетов")
            try:
                accounts_result = await iiko_sync.sync_accounts(db)
                logger.info(f"Синхронизация счетов завершена: {accounts_result}")
            except Exception as e:
                logger.error(f"Ошибка синхронизации счетов: {e}")

            result = {
                "created": 0,
                "updated": 0,
                "errors": 0,
                "deleted": 0
            }

            from_dt = datetime.fromisoformat(f_date.replace('Z', '+00:00'))
            to_dt = datetime.fromisoformat(t_date.replace('Z', '+00:00'))

            current_date = from_dt.date()
            end_date = to_dt.date()

            while current_date < end_date:
                day_from = datetime.combine(current_date, datetime.min.time())
                day_to = datetime.combine(current_date + timedelta(days=1), datetime.min.time())

                logger.info(f"Синхронизация транзакций за {current_date.strftime('%Y-%m-%d')}...")

                sync_result = await iiko_sync.sync_transactions(db, day_from, day_to)
                result["created"] += sync_result.get("created", 0)
                result["updated"] += sync_result.get("updated", 0)
                result["errors"] += sync_result.get("errors", 0)
                result["deleted"] += sync_result.get("deleted", 0)

                logger.info(
                    f"День {current_date.strftime('%Y-%m-%d')}: создано {sync_result.get('created', 0)}, "
                    f"удалено {sync_result.get('deleted', 0)}, "
                    f"ошибок {sync_result.get('errors', 0)}"
                )

                current_date += timedelta(days=1)

            try:
                from utils.db_indexes import optimize_indexes
                optimize_indexes(db)
                logger.info("Индексы оптимизированы после синхронизации транзакций")
            except Exception as e:
                logger.warning(f"Не удалось оптимизировать индексы: {e}")

            return result

        result = await run_sync_in_thread(_sync_transactions, from_date, to_date)

        return {
            "success": True,
            "message": "Синхронизация транзакций завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации транзакций: {e}")
        return {
            "success": False,
            "message": f"Ошибка синхронизации транзакций: {str(e)}",
            "data": None
        }


@router.post("/sales")
async def sync_sales(
    from_date: str = None,
    to_date: str = None,
) -> Dict[str, Any]:
    """
    Синхронизация продаж с iiko API (последовательная обработка дней из-за блокирующей авторизации)
    """
    try:
        if from_date is None:
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d") + "T00:00:00.000"
        if to_date is None:
            to_date = datetime.now().strftime("%Y-%m-%d") + "T00:00:00.000"

        async def _sync_sales(db, f_date, t_date):
            result = {
                "created": 0,
                "updated": 0,
                "errors": 0,
                "deleted": 0
            }
            from_dt = datetime.fromisoformat(f_date.replace('Z', '+00:00'))
            to_dt = datetime.fromisoformat(t_date.replace('Z', '+00:00'))

            current_date = from_dt.date()
            end_date = to_dt.date()

            while current_date < end_date:
                day_from = datetime.combine(current_date, datetime.min.time())
                day_to = datetime.combine(current_date + timedelta(days=1), datetime.min.time())

                logger.info(f"Синхронизация продаж за {current_date.strftime('%Y-%m-%d')}...")

                sync_result = await iiko_sync.sync_sales(db, day_from, day_to)
                result["created"] += sync_result.get("created", 0)
                result["updated"] += sync_result.get("updated", 0)
                result["errors"] += sync_result.get("errors", 0)
                result["deleted"] += sync_result.get("deleted", 0)

                logger.info(
                    f"День {current_date.strftime('%Y-%m-%d')}: создано {sync_result.get('created', 0)}, "
                    f"удалено {sync_result.get('deleted', 0)}, "
                    f"ошибок {sync_result.get('errors', 0)}"
                )

                current_date += timedelta(days=1)

            try:
                from utils.db_indexes import optimize_indexes
                optimize_indexes(db)
                logger.info("Индексы оптимизированы после синхронизации продаж")
            except Exception as e:
                logger.warning(f"Не удалось оптимизировать индексы: {e}")

            return result

        result = await run_sync_in_thread(_sync_sales, from_date, to_date)

        invalidate_cache("reports")
        invalidate_cache("analytics")
        invalidate_cache("popular_dishes")
        logger.info("Кэш отчетов и аналитики инвалидирован")

        return {
            "success": True,
            "message": "Синхронизация продаж завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации продаж: {e}")
        return {
            "success": False,
            "message": f"Ошибка синхронизации продаж: {str(e)}",
            "data": None
        }


@router.post("/by-modification-date")
async def sync_by_modification_date(
    from_date: str = None,
    to_date: str = None,
) -> Dict[str, Any]:
    """
    Синхронизация по дате изменения транзакций.
    """
    try:
        if from_date is None:
            from_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d") + "T00:00:00.000"
        if to_date is None:
            to_date = datetime.now().strftime("%Y-%m-%d") + "T00:00:00.000"

        async def _sync_by_mod_date(db, f_date, t_date):
            # Сначала синхронизируем счета
            logger.info("Запуск синхронизации счетов")
            try:
                accounts_result = await iiko_sync.sync_accounts(db)
                logger.info(f"Синхронизация счетов завершена: {accounts_result}")
            except Exception as e:
                logger.error(f"Ошибка синхронизации счетов: {e}")

            from_dt = datetime.fromisoformat(f_date.replace('Z', '+00:00'))
            to_dt = datetime.fromisoformat(t_date.replace('Z', '+00:00'))

            return await iiko_sync.sync_by_modification_date(db, from_dt, to_dt)

        result = await run_sync_in_thread(_sync_by_mod_date, from_date, to_date)

        invalidate_cache("reports")
        invalidate_cache("analytics")
        invalidate_cache("popular_dishes")
        logger.info("Кэш отчетов и аналитики инвалидирован")

        return {
            "success": True,
            "message": "Синхронизация по дате изменения завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации по дате изменения: {e}")
        return {
            "success": False,
            "message": f"Ошибка синхронизации по дате изменения: {str(e)}",
            "data": None
        }


@router.post("/items/cloud")
async def sync_items_cloud_all() -> Dict[str, Any]:
    """
    Синхронизация товаров из Cloud API для всех организаций
    """
    try:
        logger.info("Запуск синхронизации товаров Cloud API для всех организаций")
        result = await run_sync_in_thread(iiko_sync.sync_items_cloud)

        invalidate_cache("menu")
        invalidate_cache("goods")
        logger.info("Кэш меню и товаров инвалидирован")

        return {
            "success": True,
            "message": "Синхронизация товаров Cloud API для всех организаций завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации товаров Cloud API: {e}")
        return {
            "success": False,
            "message": f"Ошибка синхронизации товаров Cloud API: {str(e)}",
            "data": None
        }


@router.post("/items/cloud/{organization_id}")
async def sync_items_cloud_org(organization_id: int) -> Dict[str, Any]:
    """
    Синхронизация товаров из Cloud API для конкретной организации
    """
    try:
        logger.info(f"Запуск синхронизации товаров Cloud API для организации {organization_id}")
        result = await run_sync_in_thread(iiko_sync.sync_items_cloud, organization_id)

        return {
            "success": True,
            "message": f"Синхронизация товаров Cloud API для организации {organization_id} завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации товаров Cloud API: {e}")
        return {
            "success": False,
            "message": f"Ошибка синхронизации товаров Cloud API: {str(e)}",
            "data": None
        }


@router.post("/items/server")
async def sync_items_server() -> Dict[str, Any]:
    """
    Синхронизация товаров из Server API
    """
    try:
        logger.info("Запуск синхронизации товаров Server API")
        result = await run_sync_in_thread(iiko_sync.sync_items_server)

        return {
            "success": True,
            "message": "Синхронизация товаров Server API завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации товаров Server API: {e}")
        return {
            "success": False,
            "message": f"Ошибка синхронизации товаров Server API: {str(e)}",
            "data": None
        }


@router.post("/recalculate-daily-metrics")
async def recalculate_daily_metrics(
    from_date: Optional[str] = Query(default=None, description="Начальная дата в формате YYYY-MM-DD (если не указана, используется to_date)"),
    to_date: Optional[str] = Query(default=None, description="Конечная дата в формате YYYY-MM-DD (если не указана, используется сегодня)"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации (если не указан, пересчитываются для всех)"),
) -> Dict[str, Any]:
    """
    Пересчитать дневные метрики (таблица daily_analytics) за указанный период.
    """
    try:
        # Определяем даты
        if to_date:
            try:
                end_date = datetime.strptime(to_date, '%Y-%m-%d').date()
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Неверный формат даты to_date: {to_date}. Используйте формат YYYY-MM-DD"
                )
        else:
            end_date = datetime.now().date()

        if from_date:
            try:
                start_date = datetime.strptime(from_date, '%Y-%m-%d').date()
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Неверный формат даты from_date: {from_date}. Используйте формат YYYY-MM-DD"
                )
        else:
            start_date = end_date

        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="from_date не может быть больше to_date"
            )

        logger.info(f"Запуск пересчета дневных метрик с {start_date} по {end_date}" + (f" для организации {organization_id}" if organization_id else " для всех организаций"))

        async def _recalculate(db, s_date, e_date, org_id):
            dates_processed = []
            errors = []
            current = s_date

            while current <= e_date:
                try:
                    result = recalculate_daily_metrics_for_date(db, current, org_id)
                    dates_processed.append({
                        "date": current.strftime('%Y-%m-%d'),
                        "success": True,
                        "metrics": result
                    })
                except Exception as e:
                    logger.error(f"Ошибка пересчета метрик за {current}: {str(e)}")
                    errors.append({"date": current.strftime('%Y-%m-%d'), "error": str(e)})
                    dates_processed.append({"date": current.strftime('%Y-%m-%d'), "success": False, "error": str(e)})

                current += timedelta(days=1)

            return {
                "dates_processed": dates_processed,
                "total_dates": len(dates_processed),
                "errors": errors if errors else None,
                "from_date": s_date.strftime('%Y-%m-%d'),
                "to_date": e_date.strftime('%Y-%m-%d'),
                "organization_id": org_id
            }

        data = await run_sync_in_thread(_recalculate, start_date, end_date, organization_id)

        invalidate_cache("analytics")
        invalidate_cache("reports")
        logger.info("Кэш аналитики и отчетов инвалидирован")

        errors = data.get("errors")
        return {
            "success": True,
            "message": f"Пересчет дневных метрик завершен. Обработано {data['total_dates']} дат, ошибок: {len(errors) if errors else 0}",
            "data": data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка пересчета дневных метрик: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка пересчета дневных метрик: {str(e)}"
        )


@router.post("/recalculate-employee-metrics")
async def recalculate_employee_metrics(
    from_date: Optional[str] = Query(default=None, description="Начальная дата в формате YYYY-MM-DD (если не указана, используется to_date)"),
    to_date: Optional[str] = Query(default=None, description="Конечная дата в формате YYYY-MM-DD (если не указана, используется сегодня)"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации (если не указан, пересчитываются для всех)"),
) -> Dict[str, Any]:
    """
    Пересчитать метрики по сотрудникам (таблица daily_employee_analytics) за указанный период.
    """
    try:
        if to_date:
            try:
                end_date = datetime.strptime(to_date, '%Y-%m-%d').date()
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Неверный формат даты to_date: {to_date}. Используйте формат YYYY-MM-DD"
                )
        else:
            end_date = datetime.now().date()

        if from_date:
            try:
                start_date = datetime.strptime(from_date, '%Y-%m-%d').date()
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Неверный формат даты from_date: {from_date}. Используйте формат YYYY-MM-DD"
                )
        else:
            start_date = end_date

        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="from_date не может быть больше to_date"
            )

        logger.info(f"Запуск пересчета метрик по сотрудникам с {start_date} по {end_date}" + (f" для организации {organization_id}" if organization_id else " для всех организаций"))

        async def _recalculate_emp(db, s_date, e_date, org_id):
            dates_processed = []
            errors = []
            total_employees_processed = 0
            current = s_date

            while current <= e_date:
                try:
                    result = recalculate_daily_employee_metrics_for_date(db, current, org_id)
                    employees_count = result.get("processed_employees", 0)
                    total_employees_processed += employees_count
                    dates_processed.append({
                        "date": current.strftime('%Y-%m-%d'),
                        "success": True,
                        "employees_processed": employees_count
                    })
                except Exception as e:
                    logger.error(f"Ошибка пересчета метрик по сотрудникам за {current}: {str(e)}", exc_info=True)
                    errors.append({"date": current.strftime('%Y-%m-%d'), "error": str(e)})
                    dates_processed.append({"date": current.strftime('%Y-%m-%d'), "success": False, "error": str(e)})

                current += timedelta(days=1)

            return {
                "dates_processed": dates_processed,
                "total_dates": len(dates_processed),
                "total_employees_processed": total_employees_processed,
                "errors": errors if errors else None,
                "from_date": s_date.strftime('%Y-%m-%d'),
                "to_date": e_date.strftime('%Y-%m-%d'),
                "organization_id": org_id
            }

        data = await run_sync_in_thread(_recalculate_emp, start_date, end_date, organization_id)

        total_emp = data["total_employees_processed"]
        errors = data.get("errors")
        logger.info(f"Пересчет метрик по сотрудникам завершен. Обработано {data['total_dates']} дат, {total_emp} сотрудников, ошибок: {len(errors) if errors else 0}")

        return {
            "success": True,
            "message": f"Пересчет метрик по сотрудникам завершен. Обработано {data['total_dates']} дат, {total_emp} сотрудников, ошибок: {len(errors) if errors else 0}",
            "data": data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка пересчета метрик по сотрудникам: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка пересчета метрик по сотрудникам: {str(e)}"
        )


@router.post("/writeoff-documents")
async def sync_writeoff_documents(
    from_date: Optional[str] = Query(default=None, description="Дата начала в формате YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="Дата конца в формате YYYY-MM-DD"),
    status: Optional[str] = Query(default=None, description="Статус документа (опционально)"),
) -> Dict[str, Any]:
    """
    Синхронизация актов списания с iiko API
    """
    try:
        if not from_date:
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")

        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")

        logger.info(f"Запуск синхронизации актов списания с {from_date} по {to_date}")
        result = await run_sync_in_thread(iiko_sync.sync_writeoff_documents, from_dt, to_dt, status)

        return {
            "success": True,
            "message": "Синхронизация актов списания завершена",
            "data": result
        }

    except ValueError as e:
        logger.error(f"Ошибка формата даты: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Неверный формат даты: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Ошибка синхронизации актов списания: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации актов списания: {str(e)}"
        )


@router.post("/incoming-invoices")
async def sync_incoming_invoices(
    from_date: Optional[str] = Query(default=None, description="Дата начала в формате YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="Дата конца в формате YYYY-MM-DD"),
) -> Dict[str, Any]:
    """
    Синхронизация приходных накладных с iiko API
    """
    try:
        if not from_date:
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")

        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")

        logger.info(f"Запуск синхронизации приходных накладных с {from_date} по {to_date}")
        result = await run_sync_in_thread(iiko_sync.sync_incoming_invoices, from_dt, to_dt)

        return {
            "success": True,
            "message": "Синхронизация приходных накладных завершена",
            "data": result
        }

    except ValueError as e:
        logger.error(f"Ошибка формата даты: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Неверный формат даты: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Ошибка синхронизации приходных накладных: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации приходных накладных: {str(e)}"
        )


@router.post("/outgoing-invoices")
async def sync_outgoing_invoices(
    from_date: Optional[str] = Query(default=None, description="Дата начала в формате YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="Дата конца в формате YYYY-MM-DD"),
) -> Dict[str, Any]:
    """
    Синхронизация расходных накладных с iiko API
    """
    try:
        if not from_date:
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")

        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")

        logger.info(f"Запуск синхронизации расходных накладных с {from_date} по {to_date}")
        result = await run_sync_in_thread(iiko_sync.sync_outgoing_invoices, from_dt, to_dt)

        return {
            "success": True,
            "message": "Синхронизация расходных накладных завершена",
            "data": result
        }

    except ValueError as e:
        logger.error(f"Ошибка формата даты: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Неверный формат даты: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Ошибка синхронизации расходных накладных: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации расходных накладных: {str(e)}"
        )


@router.post("/all-documents")
async def sync_all_documents(
    from_date: Optional[str] = Query(default=None, description="Дата начала в формате YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="Дата конца в формате YYYY-MM-DD"),
    status: Optional[str] = Query(default=None, description="Статус для актов списания (опционально)"),
) -> Dict[str, Any]:
    """
    Синхронизация всех типов документов (акты списания, приходные и расходные накладные) с iiko API
    """
    try:
        if not from_date:
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")

        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")

        logger.info(f"Запуск синхронизации всех документов с {from_date} по {to_date}")
        result = await run_sync_in_thread(iiko_sync.sync_all_documents, from_dt, to_dt, status)

        return {
            "success": True,
            "message": "Синхронизация всех документов завершена",
            "data": result
        }

    except ValueError as e:
        logger.error(f"Ошибка формата даты: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Неверный формат даты: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Ошибка синхронизации всех документов: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации всех документов: {str(e)}"
        )


@router.post("/conceptions")
async def sync_conceptions() -> Dict[str, Any]:
    """
    Синхронизация концепций с iiko API
    """
    try:
        logger.info("Запуск синхронизации концепций")
        result = await run_sync_in_thread(sync_conceptions_from_iiko)

        invalidate_cache("conceptions")
        logger.info("Кэш концепций инвалидирован")

        return {
            "success": True,
            "message": "Синхронизация концепций завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации концепций: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации концепций: {str(e)}"
        )


@router.post("/suppliers")
async def sync_suppliers() -> Dict[str, Any]:
    """
    Синхронизация поставщиков с iiko API
    """
    try:
        logger.info("Запуск синхронизации поставщиков")
        result = await run_sync_in_thread(sync_suppliers_from_iiko)

        invalidate_cache("suppliers")
        logger.info("Кэш поставщиков инвалидирован")

        return {
            "success": True,
            "message": "Синхронизация поставщиков завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации поставщиков: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации поставщиков: {str(e)}"
        )


@router.post("/stores")
async def sync_stores() -> Dict[str, Any]:
    """
    Синхронизация складов с iiko API
    """
    try:
        logger.info("Запуск синхронизации складов")
        result = await run_sync_in_thread(sync_stores_from_iiko)

        invalidate_cache("stores")
        logger.info("Кэш складов инвалидирован")

        return {
            "success": True,
            "message": "Синхронизация складов завершена",
            "data": result
        }

    except Exception as e:
        logger.error(f"Ошибка синхронизации складов: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка синхронизации складов: {str(e)}"
        )


# ==================== Cron-эндпоинты (fire-and-forget) ====================


async def _cron_sync_job(db):
    """
    Основная логика cron sync — выполняется в фоновом потоке с собственной DB-сессией.
    """
    logger.info("Запуск автоматической синхронизации через cron эндпоинт")

    # Синхронизация счетов
    logger.info("Синхронизация счетов...")
    accounts_result = await iiko_sync.sync_accounts(db)
    logger.info(f"Синхронизация счетов завершена: {accounts_result}")

    # Синхронизация по дате изменения
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    logger.info(f"Синхронизация: дата изменения = сегодня ({today.strftime('%Y-%m-%d')})")
    modification_result = await iiko_sync.sync_by_modification_date(db, today, today)

    # Синхронизация сотрудников перед синхронизацией смен
    logger.info("Синхронизация сотрудников перед синхронизацией смен...")
    employees_result = await iiko_sync.sync_employees(db, organization_id=None)
    logger.info(f"Синхронизация сотрудников завершена: {employees_result}")

    # Синхронизация смен за последние 7 дней
    logger.info("Синхронизация смен за последние 7 дней")
    shifts_from = datetime.now() - timedelta(days=7)
    shifts_result = await iiko_sync.sync_shifts(db, shifts_from, today)
    logger.info(f"Синхронизация смен завершена: {shifts_result}")

    # Инвалидируем кэш
    invalidate_cache("reports")
    invalidate_cache("analytics")
    invalidate_cache("popular_dishes")
    logger.info("Кэш отчетов и аналитики инвалидирован")

    # Собираем все даты для пересчета метрик
    dates_to_recalculate = set()

    if modification_result and "dates_synced" in modification_result:
        for date_str in modification_result["dates_synced"]:
            try:
                if isinstance(date_str, str):
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                else:
                    date_obj = date_str if isinstance(date_str, date) else date_str.date()
                dates_to_recalculate.add(date_obj)
            except (ValueError, AttributeError) as e:
                logger.warning(f"Не удалось распарсить дату из dates_synced: {date_str}, ошибка: {e}")

    today_date = datetime.now().date()
    dates_to_recalculate.add(today_date)

    # Пересчет метрик по сотрудникам
    dates_processed = []
    total_employees_processed = 0

    if dates_to_recalculate:
        logger.info(f"Пересчет метрик по сотрудникам за {len(dates_to_recalculate)} дней: {sorted(dates_to_recalculate)}")

        for recalc_date in sorted(dates_to_recalculate):
            try:
                employee_metrics_result = recalculate_daily_employee_metrics_for_date(db, recalc_date, organization_id=None)
                employees_count = employee_metrics_result.get("processed_employees", 0)
                total_employees_processed += employees_count
                dates_processed.append({
                    "date": recalc_date.strftime('%Y-%m-%d'),
                    "employees_processed": employees_count
                })
                logger.info(f"Пересчет метрик по сотрудникам за {recalc_date.strftime('%Y-%m-%d')} завершен: обработано {employees_count} сотрудников")
            except Exception as emp_metrics_err:
                logger.error(f"Ошибка пересчета метрик по сотрудникам за {recalc_date.strftime('%Y-%m-%d')}: {emp_metrics_err}", exc_info=True)
                dates_processed.append({
                    "date": recalc_date.strftime('%Y-%m-%d'),
                    "error": str(emp_metrics_err)
                })

        logger.info(f"Пересчет метрик по сотрудникам завершен: обработано {len(dates_processed)} дат, {total_employees_processed} сотрудников")

    # Telegram уведомления
    error_parts = []
    if modification_result and isinstance(modification_result, dict):
        tx_errors = modification_result.get("transactions", {}).get("errors", 0) if isinstance(modification_result.get("transactions"), dict) else 0
        sales_errors = modification_result.get("sales", {}).get("errors", 0) if isinstance(modification_result.get("sales"), dict) else 0
        if tx_errors > 0:
            error_parts.append(f"Транзакции: {tx_errors} ошибок")
        if sales_errors > 0:
            error_parts.append(f"Продажи: {sales_errors} ошибок")

    if error_parts:
        await send_telegram_alert(
            f"⚠️ <b>CRON SYNC завершён с ошибками</b>\n\n" + "\n".join(error_parts)
        )
    else:
        await send_telegram_alert(
            f"✅ <b>CRON SYNC OK</b>\n"
            f"Дат пересчитано: {len(dates_processed)}, сотрудников: {total_employees_processed}"
        )

    return {
        "accounts": accounts_result,
        "modification_sync": modification_result,
        "shifts": shifts_result,
        "employee_metrics": {
            "dates_processed": dates_processed,
            "total_dates": len(dates_processed),
            "total_employees_processed": total_employees_processed
        }
    }


async def _daily_sync_job(db):
    """
    Основная логика daily sync — выполняется в фоновом потоке с собственной DB-сессией.
    """
    logger.info("=" * 60)
    logger.info("Запуск ежедневной синхронизации (daily-sync)")
    logger.info("=" * 60)

    # Очищаем кеш iiko API перед началом sync-сессии
    iiko_service.clear_sync_cache()

    results = {}

    # ==================== СПРАВОЧНИКИ ====================

    # 1. Организации
    logger.info("[daily-sync] Синхронизация организаций...")
    try:
        results["organizations"] = await iiko_sync.sync_organizations(db)
        invalidate_cache("organizations")
    except Exception as e:
        logger.error(f"[daily-sync] Ошибка синхронизации организаций: {e}")
        results["organizations"] = {"error": str(e)}

    # 2. Cloud Org IDs
    logger.info("[daily-sync] Синхронизация cloud org IDs...")
    try:
        results["cloud_org_ids"] = await iiko_sync.sync_cloud_org_ids(db)
    except Exception as e:
        logger.error(f"[daily-sync] Ошибка синхронизации cloud org IDs: {e}")
        results["cloud_org_ids"] = {"error": str(e)}

    # 3. Роли
    logger.info("[daily-sync] Синхронизация ролей...")
    try:
        results["roles"] = await iiko_sync.sync_roles(db)
    except Exception as e:
        logger.error(f"[daily-sync] Ошибка синхронизации ролей: {e}")
        results["roles"] = {"error": str(e)}

    # 4. Меню (items cloud)
    logger.info("[daily-sync] Синхронизация меню (items cloud)...")
    try:
        results["items_cloud"] = await iiko_sync.sync_items_cloud(db)
        invalidate_cache("menu")
    except Exception as e:
        logger.error(f"[daily-sync] Ошибка синхронизации меню: {e}")
        results["items_cloud"] = {"error": str(e)}

    # 5. Терминальные группы
    logger.info("[daily-sync] Синхронизация терминальных групп...")
    try:
        results["terminal_groups"] = await iiko_sync.sync_terminal_groups(db)
    except Exception as e:
        logger.error(f"[daily-sync] Ошибка синхронизации терминальных групп: {e}")
        results["terminal_groups"] = {"error": str(e)}

    # 6. Терминалы
    logger.info("[daily-sync] Синхронизация терминалов...")
    try:
        results["terminals"] = await iiko_sync.sync_terminals(db)
    except Exception as e:
        logger.error(f"[daily-sync] Ошибка синхронизации терминалов: {e}")
        results["terminals"] = {"error": str(e)}

    # 7. Секции ресторана
    logger.info("[daily-sync] Синхронизация секций ресторана...")
    try:
        results["restaurant_sections"] = await iiko_sync.sync_restaurant_sections(db)
    except Exception as e:
        logger.error(f"[daily-sync] Ошибка синхронизации секций ресторана: {e}")
        results["restaurant_sections"] = {"error": str(e)}

    # 8. Столы
    logger.info("[daily-sync] Синхронизация столов...")
    try:
        results["tables"] = await iiko_sync.sync_tables(db, skip_sections_sync=True)
    except Exception as e:
        logger.error(f"[daily-sync] Ошибка синхронизации столов: {e}")
        results["tables"] = {"error": str(e)}

    # 9. Концепции
    logger.info("[daily-sync] Синхронизация концепций...")
    try:
        results["conceptions"] = await sync_conceptions_from_iiko(db)
    except Exception as e:
        logger.error(f"[daily-sync] Ошибка синхронизации концепций: {e}")
        results["conceptions"] = {"error": str(e)}

    # 10. Поставщики
    logger.info("[daily-sync] Синхронизация поставщиков...")
    try:
        results["suppliers"] = await sync_suppliers_from_iiko(db)
    except Exception as e:
        logger.error(f"[daily-sync] Ошибка синхронизации поставщиков: {e}")
        results["suppliers"] = {"error": str(e)}

    # 11. Склады
    logger.info("[daily-sync] Синхронизация складов...")
    try:
        results["stores"] = await sync_stores_from_iiko(db)
    except Exception as e:
        logger.error(f"[daily-sync] Ошибка синхронизации складов: {e}")
        results["stores"] = {"error": str(e)}

    # ==================== ДАННЫЕ С ДАТАМИ ====================

    # 12. Зарплаты
    logger.info("[daily-sync] Синхронизация зарплат...")
    try:
        results["salaries"] = await iiko_sync.sync_salaries(db)
    except Exception as e:
        logger.error(f"[daily-sync] Ошибка синхронизации зарплат: {e}")
        results["salaries"] = {"error": str(e)}

    # 13. Складские документы за вчера
    yesterday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    logger.info(f"[daily-sync] Синхронизация складских документов за {yesterday.strftime('%Y-%m-%d')}...")
    try:
        results["documents"] = await iiko_sync.sync_all_documents(db, yesterday, today)
    except Exception as e:
        logger.error(f"[daily-sync] Ошибка синхронизации складских документов: {e}")
        results["documents"] = {"error": str(e)}

    # Очищаем кеш iiko API после sync-сессии
    iiko_service.clear_sync_cache()

    # Инвалидируем кэши
    invalidate_cache("reports")
    invalidate_cache("analytics")
    invalidate_cache("popular_dishes")
    invalidate_cache("stores")

    logger.info("=" * 60)
    logger.info("Ежедневная синхронизация (daily-sync) завершена")
    logger.info("=" * 60)

    # Telegram уведомления
    error_steps = [name for name, res in results.items() if isinstance(res, dict) and "error" in res]
    if error_steps:
        await send_telegram_alert(
            f"⚠️ <b>DAILY SYNC завершён с ошибками</b>\n\n"
            f"Проблемные шаги: {', '.join(error_steps)}\n\n"
            + "\n".join(f"• {step}: {results[step]['error'][:200]}" for step in error_steps)
        )
    else:
        await send_telegram_alert(
            f"✅ <b>DAILY SYNC OK</b>\n{len(results)} шагов выполнено"
        )

    return results


@router.post("/cron/sync")
async def sync_cron(
    apikey: str = Query(..., description="API ключ для авторизации"),
) -> Dict[str, Any]:
    """
    Эндпоинт для автоматической синхронизации через cron.
    Запускается в фоне, возвращает task_id немедленно.

    Требует API ключ в параметре запроса: ?apikey=YOUR_API_KEY
    """
    if not config.API_VALID_TOKEN:
        logger.error("API_VALID_TOKEN не настроен в конфигурации")
        raise HTTPException(
            status_code=500,
            detail="API key authentication is not configured"
        )

    if apikey != config.API_VALID_TOKEN:
        logger.warning("Попытка доступа с неверным API ключом")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    task_id = run_sync_in_background(_cron_sync_job, name="cron-sync")

    return {
        "success": True,
        "message": "Синхронизация запущена в фоне",
        "task_id": task_id
    }


@router.post("/cron/daily-sync")
async def sync_daily_cron(
    apikey: str = Query(..., description="API ключ для авторизации"),
) -> Dict[str, Any]:
    """
    Ежедневная синхронизация справочников и документов.
    Запускается в фоне, возвращает task_id немедленно.

    Требует API ключ: ?apikey=YOUR_API_KEY
    """
    if not config.API_VALID_TOKEN:
        logger.error("API_VALID_TOKEN не настроен в конфигурации")
        raise HTTPException(status_code=500, detail="API key authentication is not configured")

    if apikey != config.API_VALID_TOKEN:
        logger.warning("Попытка доступа к daily-sync с неверным API ключом")
        raise HTTPException(status_code=401, detail="Invalid API key")

    task_id = run_sync_in_background(_daily_sync_job, name="daily-sync")

    return {
        "success": True,
        "message": "Ежедневная синхронизация запущена в фоне",
        "task_id": task_id
    }


# ==================== Статус-эндпоинты ====================


@router.get("/status")
async def get_all_statuses() -> Dict[str, Any]:
    """
    Получить статусы всех фоновых sync-задач
    """
    statuses = get_all_sync_statuses()
    return {
        "success": True,
        "data": statuses
    }


@router.get("/status/{task_id}")
async def get_status(task_id: str) -> Dict[str, Any]:
    """
    Получить статус фоновой sync-задачи по task_id
    """
    status = get_sync_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Задача {task_id} не найдена")
    return {
        "success": True,
        "data": status
    }
