"""
Роутер для синхронизации с iiko API
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging
from datetime import datetime, timedelta

from database.database import get_db
from services.iiko import iiko_sync
from schemas.users import UserArrayResponse
from utils.cache import invalidate_cache

logger = logging.getLogger(__name__)

router = APIRouter(tags=["iiko_sync"])


@router.post("/organizations")
async def sync_organizations(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Синхронизация организаций с iiko API
    """
    try:
        logger.info("Запуск синхронизации организаций")
        result = await iiko_sync.sync_organizations(db)
        
        # Инвалидируем кэш организаций
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


@router.post("/employees")
async def sync_employees(
    organization_id: str = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Синхронизация сотрудников с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации сотрудников для организации: {organization_id}")
        result = await iiko_sync.sync_employees(db, organization_id)
        
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
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Синхронизация групп терминалов с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации групп терминалов для организации: {organization_id}")
        result = await iiko_sync.sync_terminal_groups(db, organization_id)
        
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
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Синхронизация терминалов с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации терминалов для организации: {organization_id}")
        result = await iiko_sync.sync_terminals(db, organization_id)
        
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
async def sync_roles(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Синхронизация ролей с iiko API
    """
    try:
        logger.info("Запуск синхронизации ролей")
        result = await iiko_sync.sync_roles(db)
        
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


@router.post("/restaurant-sections")
async def sync_restaurant_sections(
    organization_id: str = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Синхронизация секций ресторана с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации секций ресторана для организации: {organization_id}")
        result = await iiko_sync.sync_restaurant_sections(db, organization_id)
        
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
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Синхронизация столов с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации столов для организации: {organization_id}")
        result = await iiko_sync.sync_tables(db, organization_id)
        
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
async def sync_accounts(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Синхронизация счетов с iiko API (Server API)
    """
    try:
        logger.info("Запуск синхронизации счетов")
        result = await iiko_sync.sync_accounts(db)
        
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
async def sync_salaries(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Синхронизация окладов сотрудников с iiko API (Server API)
    """
    try:
        logger.info("Запуск синхронизации окладов")
        result = await iiko_sync.sync_salaries(db)
        
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


@router.post("/menu")
async def sync_menu(
    organization_id: str = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Синхронизация меню с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации меню для организации: {organization_id}")
        result = await iiko_sync.sync_menu(db, organization_id)
        
        # Инвалидируем кэш меню и товаров
        invalidate_cache("menu")
        invalidate_cache("goods")
        logger.info("Кэш меню и товаров инвалидирован")
        
        # Оптимизируем индексы после синхронизации меню
        try:
            from utils.db_indexes import optimize_indexes
            optimize_indexes(db)
            logger.info("Индексы оптимизированы после синхронизации меню")
        except Exception as e:
            logger.warning(f"Не удалось оптимизировать индексы: {e}")
        
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
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Полная синхронизация всех данных с iiko API
    """
    try:
        logger.info(f"Запуск полной синхронизации для организации: {organization_id}")
        result = await iiko_sync.sync_all(db, organization_id)
        
        # Оптимизируем индексы после полной синхронизации
        try:
            from utils.db_indexes import optimize_indexes
            optimize_indexes(db)
            logger.info("Индексы оптимизированы после полной синхронизации")
        except Exception as e:
            logger.warning(f"Не удалось оптимизировать индексы: {e}")
        
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
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Синхронизация организаций, сотрудников и терминалов с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации организаций, сотрудников и терминалов для организации: {organization_id}")
        
        results = {}
        
        # Синхронизация организаций
        logger.info("Синхронизация организаций...")
        org_result = await iiko_sync.sync_organizations(db)
        results["organizations"] = org_result
        
        # Синхронизация сотрудников
        logger.info("Синхронизация сотрудников...")
        emp_result = await iiko_sync.sync_employees(db, organization_id)
        results["employees"] = emp_result
        
        # Синхронизация терминалов
        logger.info("Синхронизация терминалов...")
        term_result = await iiko_sync.sync_terminals(db, organization_id)
        results["terminals"] = term_result
        
        # Подсчет общих результатов
        total_created = org_result.get("created", 0) + emp_result.get("created", 0) + term_result.get("created", 0)
        total_updated = org_result.get("updated", 0) + emp_result.get("updated", 0) + term_result.get("updated", 0)
        total_errors = org_result.get("errors", 0) + emp_result.get("errors", 0) + term_result.get("errors", 0)
        
        return {
            "success": True,
            "message": "Синхронизация организаций, сотрудников и терминалов завершена",
            "data": {
                "results": results,
                "summary": {
                    "total_created": total_created,
                    "total_updated": total_updated,
                    "total_errors": total_errors
                }
            }
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
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Синхронизация транзакций с iiko API (последовательная обработка дней из-за блокирующей авторизации)
    """
    try:
        logger.info("Запуск синхронизации счетов")
        result = await iiko_sync.sync_accounts(db)
        logger.info(f"Синхронизация счетов завершена: {result}")
    except Exception as e:
        logger.error(f"Ошибка синхронизации счетов: {e}")

    try:
        logger.info(f"Запуск синхронизации транзакций для организации")
        if from_date is None:
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d") + "T00:00:00.000"
        if to_date is None:
            to_date = datetime.now().strftime("%Y-%m-%d") + "T00:00:00.000"
        
        result = {
            "created": 0,
            "updated": 0,
            "errors": 0,
            "deleted": 0
        }
        
        # Преобразуем в datetime для работы
        from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        
        # Работаем по дням, чтобы избежать накладывания
        # iiko API использует полуоткрытый интервал [from, to) - включая from, не включая to
        current_date = from_dt.date()
        end_date = to_dt.date()
        
        # Последовательная обработка дней (авторизация блокирующая)
        while current_date < end_date:
            # Для получения данных за один день передаем:
            # from = текущий день, to = следующий день
            # Например: from="2025-10-01", to="2025-10-02" → данные только за 1 октября
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
            
            # Переходим к следующему дню
            current_date += timedelta(days=1)
        
        # Оптимизируем индексы после массовой синхронизации
        try:
            from utils.db_indexes import optimize_indexes
            optimize_indexes(db)
            logger.info("Индексы оптимизированы после синхронизации транзакций")
        except Exception as e:
            logger.warning(f"Не удалось оптимизировать индексы: {e}")
        
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
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Синхронизация продаж с iiko API (последовательная обработка дней из-за блокирующей авторизации)
    2025-09-30T00:00:00.000
    """
    try:
        logger.info(f"Запуск синхронизации продаж")

        if from_date is None:
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d") + "T00:00:00.000"
        if to_date is None:
            to_date = datetime.now().strftime("%Y-%m-%d") + "T00:00:00.000"
        result = {
            "created": 0,
            "updated": 0,
            "errors": 0,
            "deleted": 0
        }
        # Преобразуем в datetime для работы
        from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        
        # Работаем по дням, чтобы избежать накладывания
        # iiko API использует полуоткрытый интервал [from, to) - включая from, не включая to
        current_date = from_dt.date()
        end_date = to_dt.date()
        
        # Последовательная обработка дней (авторизация блокирующая)
        while current_date < end_date:
            # Для получения данных за один день передаем:
            # from = текущий день, to = следующий день
            # Например: from="2025-10-01", to="2025-10-02" → данные только за 1 октября
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
            
            # Переходим к следующему дню
            current_date += timedelta(days=1)
        
        # Инвалидируем кэш отчетов и аналитики
        invalidate_cache("reports")
        invalidate_cache("analytics")
        invalidate_cache("popular_dishes")
        logger.info("Кэш отчетов и аналитики инвалидирован")
        
        # Оптимизируем индексы после массовой синхронизации
        try:
            from utils.db_indexes import optimize_indexes
            optimize_indexes(db)
            logger.info("Индексы оптимизированы после синхронизации продаж")
        except Exception as e:
            logger.warning(f"Не удалось оптимизировать индексы: {e}")
        
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


@router.post("/items/cloud")
async def sync_items_cloud_all(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Синхронизация товаров из Cloud API для всех организаций
    """
    try:
        logger.info("Запуск синхронизации товаров Cloud API для всех организаций")
        result = await iiko_sync.sync_items_cloud(db)
        
        # Инвалидируем кэш меню и товаров
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
async def sync_items_cloud_org(organization_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Синхронизация товаров из Cloud API для конкретной организации
    """
    try:
        logger.info(f"Запуск синхронизации товаров Cloud API для организации {organization_id}")
        result = await iiko_sync.sync_items_cloud(db, organization_id)
        
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
async def sync_items_server(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Синхронизация товаров из Server API
    """
    try:
        logger.info("Запуск синхронизации товаров Server API")
        result = await iiko_sync.sync_items_server(db)
        
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