"""
Утилита для логирования времени выполнения функций и операций.

Предоставляет декораторы и контекстные менеджеры для автоматического
логирования производительности кода.
"""

import time
import logging
from typing import Optional, Callable, Any
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def log_execution_time(func_name: Optional[str] = None):
    """
    Декоратор для логирования времени выполнения синхронных функций.
    
    Args:
        func_name: Опциональное имя функции для логирования (по умолчанию используется __name__)
    
    Пример:
        @log_execution_time
        def my_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = func_name or func.__name__
            logger.debug(f"[PERF] {name} START")
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                logger.info(f"[PERF] {name} took {elapsed:.3f}s")
                logger.debug(f"[PERF] {name} END ({elapsed:.3f}s)")
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start
                logger.error(f"[PERF] {name} FAILED after {elapsed:.3f}s: {e}")
                raise
        return wrapper
    
    # Если декоратор вызван без скобок (@log_execution_time)
    if callable(func_name):
        func = func_name
        func_name = None
        return decorator(func)
    
    return decorator


def log_async_execution_time(func_name: Optional[str] = None):
    """
    Декоратор для логирования времени выполнения асинхронных функций.
    
    Args:
        func_name: Опциональное имя функции для логирования (по умолчанию используется __name__)
    
    Пример:
        @log_async_execution_time
        async def my_async_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            name = func_name or func.__name__
            logger.debug(f"[PERF] {name} START")
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                elapsed = time.perf_counter() - start
                logger.info(f"[PERF] {name} took {elapsed:.3f}s")
                logger.debug(f"[PERF] {name} END ({elapsed:.3f}s)")
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start
                logger.error(f"[PERF] {name} FAILED after {elapsed:.3f}s: {e}")
                raise
        return wrapper
    
    # Если декоратор вызван без скобок (@log_async_execution_time)
    if callable(func_name):
        func = func_name
        func_name = None
        return decorator(func)
    
    return decorator


@contextmanager
def log_execution(operation_name: str):
    """
    Контекстный менеджер для логирования времени выполнения блока кода.
    
    Args:
        operation_name: Имя операции для логирования
    
    Пример:
        with log_execution("database_query"):
            result = db.query(...)
    """
    logger.debug(f"[PERF] {operation_name} START")
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info(f"[PERF] {operation_name} took {elapsed:.3f}s")
        logger.debug(f"[PERF] {operation_name} END ({elapsed:.3f}s)")

