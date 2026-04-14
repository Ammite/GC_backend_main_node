"""
Утилиты для запуска sync-операций в отдельных потоках,
чтобы не блокировать основной event loop FastAPI.
"""

import asyncio
import logging
import uuid
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional

from database.database import SessionLocal

logger = logging.getLogger(__name__)

# Пул потоков для sync-операций (макс 3 одновременных)
_sync_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="sync-worker")

# Хранилище статусов фоновых задач (in-memory, последние 50)
_sync_status: OrderedDict[str, Dict[str, Any]] = OrderedDict()
_status_lock = threading.Lock()
_MAX_STATUS_ENTRIES = 50


def _trim_statuses():
    """Удаляет старые записи, оставляя только последние _MAX_STATUS_ENTRIES."""
    while len(_sync_status) > _MAX_STATUS_ENTRIES:
        _sync_status.popitem(last=False)


def _run_async_in_new_thread(async_func: Callable, *args, **kwargs) -> Any:
    """
    Запускает async-функцию в новом event loop в текущем потоке.
    Создаёт свою DB-сессию и передаёт первым аргументом.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    db = SessionLocal()
    try:
        result = loop.run_until_complete(async_func(db, *args, **kwargs))
        return result
    finally:
        db.close()
        loop.close()


async def run_sync_in_thread(async_func: Callable, *args, **kwargs) -> Any:
    """
    Запускает async sync-функцию в отдельном потоке с собственной DB-сессией.
    Ожидает результат и возвращает его. Не блокирует основной event loop.

    Использование:
        result = await run_sync_in_thread(iiko_sync.sync_organizations)
        result = await run_sync_in_thread(iiko_sync.sync_shifts, from_dt, to_dt)
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _sync_executor,
        _run_async_in_new_thread,
        async_func,
        *args,
    )
    return result


def _background_worker(task_id: str, async_func: Callable, args: tuple, kwargs: dict):
    """Воркер для фоновой задачи — запускается в потоке из пула."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    db = SessionLocal()
    try:
        result = loop.run_until_complete(async_func(db, *args, **kwargs))
        with _status_lock:
            _sync_status[task_id].update({
                "status": "completed",
                "finished_at": datetime.now().isoformat(),
                "result": result,
            })
        logger.info(f"Фоновая задача {task_id} завершена успешно")
    except Exception as e:
        logger.error(f"Фоновая задача {task_id} завершилась с ошибкой: {e}", exc_info=True)
        with _status_lock:
            _sync_status[task_id].update({
                "status": "failed",
                "finished_at": datetime.now().isoformat(),
                "error": str(e),
            })
    finally:
        db.close()
        loop.close()


def run_sync_in_background(async_func: Callable, *args, name: str = "", **kwargs) -> str:
    """
    Запускает async sync-функцию в фоновом потоке. Возвращает task_id немедленно.

    Использование:
        task_id = run_sync_in_background(cron_sync_job, name="cron-sync")
    """
    task_id = str(uuid.uuid4())[:8]

    with _status_lock:
        _sync_status[task_id] = {
            "status": "running",
            "name": name or async_func.__name__,
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
            "result": None,
            "error": None,
        }
        _trim_statuses()

    _sync_executor.submit(_background_worker, task_id, async_func, args, kwargs)
    logger.info(f"Фоновая задача {task_id} ({name}) запущена")
    return task_id


def get_sync_status(task_id: str) -> Optional[Dict[str, Any]]:
    """Возвращает статус задачи по task_id или None."""
    with _status_lock:
        return _sync_status.get(task_id)


def get_all_sync_statuses() -> Dict[str, Dict[str, Any]]:
    """Возвращает статусы всех задач."""
    with _status_lock:
        return dict(_sync_status)
