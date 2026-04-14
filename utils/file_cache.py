"""
Утилита для файлового кэширования результатов функций
Хранит кеш на диске в JSON файлах для экономии ОЗУ
"""
import os
import json
import hashlib
import logging
from typing import Any, Callable, Optional
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

logger = logging.getLogger(__name__)

# Базовая директория для кеша (используем абсолютный путь)
PROJECT_ROOT = Path(__file__).parent.parent
CACHE_DIR = PROJECT_ROOT / "cache" / "statistics"


class FileCacheManager:
    """Менеджер файлового кэша с поддержкой TTL"""
    
    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Если нет прав, используем временную директорию
            import tempfile
            temp_cache = Path(tempfile.gettempdir()) / "backend_cache" / "statistics"
            temp_cache.mkdir(parents=True, exist_ok=True)
            self.cache_dir = temp_cache
            logger.warning(f"Не удалось создать кеш в {cache_dir}, используем {temp_cache}")
    
    def _get_cache_path(self, key: str, function_name: str) -> Path:
        """Получить путь к файлу кеша"""
        # Создаем подпапку для функции
        func_dir = self.cache_dir / function_name
        func_dir.mkdir(parents=True, exist_ok=True)
        
        # Используем хеш ключа для имени файла
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return func_dir / f"{key_hash}.json"
    
    def get(self, key: str, function_name: str) -> Optional[Any]:
        """Получить значение из кэша"""
        cache_path = self._get_cache_path(key, function_name)
        
        if not cache_path.exists():
            logger.debug(f"Cache MISS: {function_name}:{key[:16]}...")
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Проверяем TTL
            expires_at = datetime.fromisoformat(cache_data['expires_at'])
            if datetime.now() >= expires_at:
                logger.debug(f"Cache EXPIRED: {function_name}:{key[:16]}...")
                cache_path.unlink()  # Удаляем устаревший кеш
                return None
            
            logger.debug(f"Cache HIT: {function_name}:{key[:16]}...")
            return cache_data['value']
        
        except (json.JSONDecodeError, KeyError, ValueError, OSError) as e:
            logger.warning(f"Ошибка чтения кеша {cache_path}: {e}")
            # Удаляем поврежденный файл
            try:
                if cache_path.exists():
                    cache_path.unlink()
            except OSError:
                pass
            return None
    
    def set(self, key: str, function_name: str, value: Any, ttl_seconds: int = 300):
        """Сохранить значение в кэш с TTL"""
        cache_path = self._get_cache_path(key, function_name)
        
        try:
            cache_data = {
                'value': value,
                'created_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat(),
                'ttl_seconds': ttl_seconds
            }
            
            # Сохраняем во временный файл, затем переименовываем (атомарная операция)
            temp_path = cache_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            temp_path.replace(cache_path)
            logger.debug(f"Cache SET: {function_name}:{key[:16]}... (TTL: {ttl_seconds}s)")
        
        except Exception as e:
            logger.error(f"Ошибка сохранения кеша {cache_path}: {e}")
            # Удаляем временный файл при ошибке
            if temp_path.exists():
                temp_path.unlink()
    
    def invalidate(self, key: str, function_name: str):
        """Инвалидировать конкретный ключ"""
        cache_path = self._get_cache_path(key, function_name)
        if cache_path.exists():
            cache_path.unlink()
            logger.debug(f"Cache INVALIDATE: {function_name}:{key[:16]}...")
    
    def invalidate_function(self, function_name: str):
        """Инвалидировать весь кеш функции"""
        func_dir = self.cache_dir / function_name
        if func_dir.exists():
            count = 0
            for cache_file in func_dir.glob("*.json"):
                cache_file.unlink()
                count += 1
            logger.info(f"Cache INVALIDATE FUNCTION: {function_name} ({count} files)")
    
    def invalidate_pattern(self, pattern: str):
        """Инвалидировать все ключи, содержащие паттерн"""
        count = 0
        for func_dir in self.cache_dir.iterdir():
            if func_dir.is_dir():
                for cache_file in func_dir.glob("*.json"):
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                            # Проверяем содержимое кеша на паттерн
                            cache_str = json.dumps(cache_data.get('value', {}))
                            if pattern in cache_str:
                                cache_file.unlink()
                                count += 1
                    except Exception:
                        pass
        logger.info(f"Cache INVALIDATE PATTERN: {pattern} ({count} files)")
    
    def cleanup_expired(self):
        """Удалить устаревшие записи из кэша"""
        now = datetime.now()
        count = 0
        
        for func_dir in self.cache_dir.iterdir():
            if func_dir.is_dir():
                for cache_file in func_dir.glob("*.json"):
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                            expires_at = datetime.fromisoformat(cache_data['expires_at'])
                            if now >= expires_at:
                                cache_file.unlink()
                                count += 1
                    except Exception:
                        # Удаляем поврежденные файлы
                        cache_file.unlink()
                        count += 1
        
        if count > 0:
            logger.debug(f"Cache CLEANUP: {count} expired files removed")
    
    def get_stats(self) -> dict:
        """Получить статистику по кешу"""
        total_files = 0
        valid_files = 0
        expired_files = 0
        total_size = 0
        now = datetime.now()
        
        for func_dir in self.cache_dir.iterdir():
            if func_dir.is_dir():
                for cache_file in func_dir.glob("*.json"):
                    total_files += 1
                    total_size += cache_file.stat().st_size
                    
                    try:
                        with open(cache_file, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                            expires_at = datetime.fromisoformat(cache_data['expires_at'])
                            if now < expires_at:
                                valid_files += 1
                            else:
                                expired_files += 1
                    except Exception:
                        expired_files += 1
        
        return {
            "total_files": total_files,
            "valid_files": valid_files,
            "expired_files": expired_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }


# Глобальный экземпляр менеджера кеша
file_cache_manager = FileCacheManager()


def generate_cache_key(*args, **kwargs) -> str:
    """
    Генерирует уникальный ключ кэша на основе аргументов функции
    
    Исключает объекты Session и другие несериализуемые объекты
    """
    key_parts = []
    
    # Добавляем позиционные аргументы
    for arg in args:
        if isinstance(arg, datetime):
            key_parts.append(f"dt:{arg.isoformat()}")
        elif isinstance(arg, (str, int, float, bool, type(None))):
            key_parts.append(str(arg))
        elif hasattr(arg, 'id'):  # Для объектов с id
            key_parts.append(f"id:{arg.id}")
        # Пропускаем объекты Session и другие сложные объекты
    
    # Добавляем именованные аргументы (сортируем для стабильности)
    for key, value in sorted(kwargs.items()):
        # Пропускаем объекты БД и другие несериализуемые объекты
        if key in ['db', 'user']:
            continue
        
        if isinstance(value, datetime):
            key_parts.append(f"{key}:dt:{value.isoformat()}")
        elif isinstance(value, (str, int, float, bool, type(None))):
            key_parts.append(f"{key}:{value}")
        elif isinstance(value, list):
            # Для списков создаем хеш содержимого
            list_str = json.dumps(value, sort_keys=True)
            key_parts.append(f"{key}:list:{hashlib.md5(list_str.encode()).hexdigest()}")
        elif hasattr(value, 'id'):
            key_parts.append(f"{key}:id:{value.id}")
    
    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def file_cached(ttl_seconds: int = 300, key_prefix: str = ""):
    """
    Декоратор для файлового кэширования результатов функций
    
    Args:
        ttl_seconds: время жизни кэша в секундах (по умолчанию 5 минут)
        key_prefix: префикс для ключа кэша
    
    Пример использования:
        @file_cached(ttl_seconds=600, key_prefix="revenue")
        def get_revenue_by_category(db: Session, start_date: datetime, end_date: datetime):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Очищаем устаревшие записи периодически (каждый 10-й вызов)
            import random
            if random.randint(1, 10) == 1:
                file_cache_manager.cleanup_expired()
            
            # Генерируем ключ кэша
            cache_key = generate_cache_key(*args, **kwargs)
            full_key = f"{key_prefix}:{cache_key}" if key_prefix else cache_key
            
            # Проверяем кеш
            cached_value = file_cache_manager.get(full_key, func.__name__)
            if cached_value is not None:
                return cached_value
            
            # Вызываем функцию и кэшируем результат
            result = func(*args, **kwargs)
            file_cache_manager.set(full_key, func.__name__, result, ttl_seconds)
            
            return result
        
        return wrapper
    return decorator


def invalidate_file_cache(function_name: Optional[str] = None, pattern: Optional[str] = None):
    """
    Инвалидировать файловый кеш
    
    Args:
        function_name: имя функции для инвалидации (если None - все функции)
        pattern: паттерн для поиска в кеше
    """
    if function_name:
        file_cache_manager.invalidate_function(function_name)
    elif pattern:
        file_cache_manager.invalidate_pattern(pattern)
    else:
        # Очищаем весь кеш
        for func_dir in file_cache_manager.cache_dir.iterdir():
            if func_dir.is_dir():
                file_cache_manager.invalidate_function(func_dir.name)


def get_file_cache_stats() -> dict:
    """Получить статистику файлового кеша"""
    return file_cache_manager.get_stats()

