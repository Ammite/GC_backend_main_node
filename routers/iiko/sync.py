"""
Роутер для синхронизации с iiko API
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from database.database import get_db
from services.iiko import iiko_sync
from schemas.users import UserArrayResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/organizations")
async def sync_organizations(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Синхронизация организаций с iiko API
    """
    try:
        logger.info("Запуск синхронизации организаций")
        result = await iiko_sync.sync_organizations(db)
        
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
    Синхронизация транзакций с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации транзакций для организации")
        result = await iiko_sync.sync_transactions(db, from_date, to_date)
        
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
    Синхронизация продаж с iiko API
    """
    try:
        logger.info(f"Запуск синхронизации продаж")
        result = await iiko_sync.sync_sales(db, from_date, to_date)
        
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