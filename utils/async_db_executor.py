"""
Утилиты для параллельного выполнения запросов к БД
Использует asyncio для параллельного выполнения независимых запросов
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, List, Tuple
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# Глобальный пул потоков для выполнения синхронных запросов к БД
_executor = ThreadPoolExecutor(max_workers=10)


def run_in_thread(func: Callable) -> Any:
    """
    Выполнить синхронную функцию в отдельном потоке
    
    Args:
        func: синхронная функция для выполнения
        
    Returns:
        результат выполнения функции
    """
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(_executor, func)


async def gather_db_queries(*queries: Callable) -> Tuple[Any, ...]:
    """
    Выполнить несколько запросов к БД параллельно
    
    Args:
        *queries: функции-запросы к БД (синхронные)
        
    Returns:
        кортеж с результатами запросов в том же порядке
    """
    tasks = [run_in_thread(query) for query in queries]
    return await asyncio.gather(*tasks)


def async_db_query(func: Callable) -> Callable:
    """
    Декоратор для преобразования синхронной функции запроса к БД в асинхронную
    
    Args:
        func: синхронная функция запроса к БД
        
    Returns:
        асинхронная обертка функции
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await run_in_thread(lambda: func(*args, **kwargs))
    return wrapper

