from fastapi import APIRouter, Depends
from utils.security import get_current_user
from utils.cache import invalidate_cache, get_cache_stats
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/stats")
def get_cache_statistics(
    user = Depends(get_current_user),
):
    """
    Получить статистику по кэшу
    
    Возвращает:
    - total_keys: общее количество ключей в кэше
    - valid_keys: количество актуальных ключей
    - expired_keys: количество устаревших ключей
    """
    try:
        stats = get_cache_stats()
        return {
            "success": True,
            "message": "Статистика кэша получена",
            "data": stats
        }
    except Exception as e:
        logger.error(f"Ошибка при получении статистики кэша: {str(e)}")
        return {
            "success": False,
            "message": f"Ошибка: {str(e)}",
            "data": {}
        }


@router.post("/clear")
def clear_cache(
    pattern: str = "",
    user = Depends(get_current_user),
):
    """
    Очистить кэш
    
    Query Parameters:
    - pattern (optional): паттерн для очистки конкретных ключей
      - Пустая строка = очистить весь кэш
      - "goods" = очистить только кэш товаров
      - "reports" = очистить только кэш отчетов
    
    Примеры:
    - POST /cache/clear - очистит весь кэш
    - POST /cache/clear?pattern=goods - очистит только кэш товаров
    - POST /cache/clear?pattern=reports_orders - очистит кэш отчетов по заказам
    """
    try:
        invalidate_cache(pattern)
        
        if pattern:
            message = f"Кэш очищен по паттерну: {pattern}"
        else:
            message = "Весь кэш очищен"
        
        return {
            "success": True,
            "message": message
        }
    except Exception as e:
        logger.error(f"Ошибка при очистке кэша: {str(e)}")
        return {
            "success": False,
            "message": f"Ошибка: {str(e)}"
        }

