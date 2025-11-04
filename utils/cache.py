"""
Утилита для кэширования результатов эндпоинтов
"""
from typing import Any, Callable, Optional
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Менеджер кэша с поддержкой TTL (time-to-live)"""
    
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
        
    def get(self, key: str) -> Optional[Any]:
        """Получить значение из кэша"""
        if key in self._cache:
            logger.debug(f"Cache HIT: {key}")
            return self._cache[key]
        logger.debug(f"Cache MISS: {key}")
        return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        """Сохранить значение в кэш с TTL"""
        self._cache[key] = value
        self._timestamps[key] = datetime.now() + timedelta(seconds=ttl_seconds)
        logger.debug(f"Cache SET: {key} (TTL: {ttl_seconds}s)")
    
    def is_valid(self, key: str) -> bool:
        """Проверить, актуален ли кэш"""
        if key not in self._timestamps:
            return False
        return datetime.now() < self._timestamps[key]
    
    def invalidate(self, key: str):
        """Инвалидировать конкретный ключ"""
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache INVALIDATE: {key}")
        if key in self._timestamps:
            del self._timestamps[key]
    
    def invalidate_pattern(self, pattern: str):
        """Инвалидировать все ключи, содержащие паттерн"""
        keys_to_delete = [key for key in self._cache.keys() if pattern in key]
        for key in keys_to_delete:
            self.invalidate(key)
        logger.info(f"Cache INVALIDATE PATTERN: {pattern} ({len(keys_to_delete)} keys)")
    
    def clear(self):
        """Очистить весь кэш"""
        count = len(self._cache)
        self._cache.clear()
        self._timestamps.clear()
        logger.info(f"Cache CLEARED: {count} keys removed")
    
    def cleanup_expired(self):
        """Удалить устаревшие записи из кэша"""
        now = datetime.now()
        expired_keys = [
            key for key, timestamp in self._timestamps.items()
            if now >= timestamp
        ]
        for key in expired_keys:
            self.invalidate(key)
        if expired_keys:
            logger.debug(f"Cache CLEANUP: {len(expired_keys)} expired keys removed")


# Глобальный экземпляр менеджера кэша
cache_manager = CacheManager()


def generate_cache_key(*args, **kwargs) -> str:
    """
    Генерирует уникальный ключ кэша на основе аргументов
    """
    # Создаем строку из всех аргументов
    key_parts = []
    
    # Добавляем позиционные аргументы
    for arg in args:
        if hasattr(arg, 'id'):  # Для объектов с id (например, user)
            key_parts.append(f"id:{arg.id}")
        else:
            key_parts.append(str(arg))
    
    # Добавляем именованные аргументы (сортируем для стабильности)
    for key, value in sorted(kwargs.items()):
        # Пропускаем объекты БД и пользователя
        if key in ['db', 'user']:
            continue
        key_parts.append(f"{key}:{value}")
    
    # Создаем хеш для компактности
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def cached(ttl_seconds: int = 300, key_prefix: str = ""):
    """
    Декоратор для кэширования результатов функций
    
    Args:
        ttl_seconds: время жизни кэша в секундах (по умолчанию 5 минут)
        key_prefix: префикс для ключа кэша
    
    Пример использования:
        @cached(ttl_seconds=600, key_prefix="goods")
        def get_goods_by_categories(db: Session):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Очищаем устаревшие записи
            cache_manager.cleanup_expired()
            
            # Генерируем ключ кэша
            cache_key = f"{key_prefix}:{func.__name__}:{generate_cache_key(*args, **kwargs)}"
            
            # Проверяем, есть ли валидный кэш
            if cache_manager.is_valid(cache_key):
                cached_value = cache_manager.get(cache_key)
                if cached_value is not None:
                    return cached_value
            
            # Вызываем функцию и кэшируем результат
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl_seconds)
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(pattern: str = ""):
    """
    Инвалидирует кэш по паттерну
    
    Args:
        pattern: паттерн для поиска ключей (пустая строка = очистить весь кэш)
    
    Пример:
        invalidate_cache("goods")  # Очистит все ключи с "goods"
        invalidate_cache()  # Очистит весь кэш
    """
    if pattern:
        cache_manager.invalidate_pattern(pattern)
    else:
        cache_manager.clear()


def get_cache_stats() -> dict:
    """Получить статистику по кэшу"""
    now = datetime.now()
    valid_keys = sum(1 for ts in cache_manager._timestamps.values() if now < ts)
    expired_keys = len(cache_manager._cache) - valid_keys
    
    return {
        "total_keys": len(cache_manager._cache),
        "valid_keys": valid_keys,
        "expired_keys": expired_keys,
    }

