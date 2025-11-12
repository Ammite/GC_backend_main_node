"""
Роутер для управления индексами базы данных
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from database.database import get_db
from utils.db_indexes import create_indexes, drop_indexes, recreate_indexes, optimize_indexes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/db", tags=["database"])


@router.post("/indexes/create")
async def create_db_indexes(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Создать все индексы для оптимизации запросов
    """
    try:
        logger.info("Запуск создания индексов")
        result = create_indexes(db)
        
        return {
            "success": True,
            "message": "Создание индексов завершено",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Ошибка создания индексов: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка создания индексов: {str(e)}"
        )


@router.post("/indexes/drop")
async def drop_db_indexes(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Удалить все индексы (используется для пересоздания)
    """
    try:
        logger.info("Запуск удаления индексов")
        result = drop_indexes(db)
        
        return {
            "success": True,
            "message": "Удаление индексов завершено",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Ошибка удаления индексов: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка удаления индексов: {str(e)}"
        )


@router.post("/indexes/recreate")
async def recreate_db_indexes(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Пересоздать все индексы (удалить и создать заново)
    Полезно после массовых операций синхронизации
    """
    try:
        logger.info("Запуск пересоздания индексов")
        result = recreate_indexes(db)
        
        return {
            "success": True,
            "message": "Пересоздание индексов завершено",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Ошибка пересоздания индексов: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка пересоздания индексов: {str(e)}"
        )


@router.post("/indexes/optimize")
async def optimize_db_indexes(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Оптимизировать индексы (ANALYZE для PostgreSQL, VACUUM для SQLite)
    Полезно вызывать после массовых операций синхронизации
    """
    try:
        logger.info("Запуск оптимизации индексов")
        result = optimize_indexes(db)
        
        return {
            "success": True,
            "message": "Оптимизация индексов завершена",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Ошибка оптимизации индексов: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка оптимизации индексов: {str(e)}"
        )

