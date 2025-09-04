import fastapi
from fastapi.middleware.cors import CORSMiddleware
import logging
import importlib
import pkgutil
from contextlib import asynccontextmanager
from database.database import init_db


# Логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Автоматичкски инициализирует нужные файлы (бд, рауты)
@asynccontextmanager
async def lifespan(application: fastapi.FastAPI):
    init_db()
    include_routers(application)
    yield

# Приложение FastAPI
app = fastapi.FastAPI(lifespan=lifespan)
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


def include_routers(application: fastapi.FastAPI) -> None:
    # Автоматически подключаем все роутеры из пакета routers
    try:
        import routers
    except ImportError:
        logger.warning("Пакет routers не найден")
        return

    package = importlib.import_module("routers")
    for finder, name, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        if name.endswith(".auth.auth") or name.endswith(".auth"):
            # поддержка текущей структуры routers/auth/auth.py
            module_name = name
        else:
            module_name = name
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.warning(f"Не удалось импортировать модуль {module_name}: {e}")
            continue

        router = getattr(module, "router", None)
        if router is not None:
            application.include_router(router)


# Точка входа для локального запуска, в будущем будем менять тут настройки
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
