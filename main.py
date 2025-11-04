import fastapi
from fastapi import Request, HTTPException, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import logging
import importlib
import pkgutil
from contextlib import asynccontextmanager
import config
from utils.security import decode_access_token
from database.database import init_db
import secrets


# Логирование
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Настройки для базовой авторизации документации
DOCS_USERNAME = config.DOCS_USERNAME
DOCS_PASSWORD = config.DOCS_PASSWORD
security = HTTPBasic()

def verify_docs_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Проверка учетных данных для доступа к документации"""
    is_correct_username = secrets.compare_digest(credentials.username, DOCS_USERNAME)
    is_correct_password = secrets.compare_digest(credentials.password, DOCS_PASSWORD)
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Автоматичкски инициализирует нужные файлы (бд, рауты)
@asynccontextmanager
async def lifespan(application: fastapi.FastAPI):
    init_db()
    include_routers(application)
    yield

# Приложение FastAPI (отключаем автоматическую документацию)
app = fastapi.FastAPI(
    lifespan=lifespan,
    docs_url=None,  # Отключаем автоматический /docs
    redoc_url=None,  # Отключаем автоматический /redoc
    openapi_url=None  # Отключаем автоматический /openapi.json
)

# Добавляем схему безопасности для токена
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    openapi_schema = get_openapi(
        title="GC Backend API",
        version="1.0.0",
        description="API для системы управления рестораном с интеграцией iiko",
        routes=app.routes,
    )
    
    # Добавляем схему безопасности
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Введите токен авторизации"
        },
        "QueryToken": {
            "type": "apiKey",
            "in": "query",
            "name": "token",
            "description": "Токен авторизации в параметрах запроса"
        }
    }
    
    # Применяем схему безопасности ко всем эндпоинтам (кроме документации)
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            if path not in ["/docs", "/redoc", "/openapi.json"]:
                openapi_schema["paths"][path][method]["security"] = [
                    {"BearerAuth": []},
                    {"QueryToken": []}
                ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Защищенные эндпоинты документации
@app.get("/docs", include_in_schema=False)
async def get_documentation(username: str = Depends(verify_docs_credentials)):
    """Защищенная документация Swagger UI с поддержкой токена"""
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(
        openapi_url="/openapi.json", 
        title="API Documentation",
        swagger_ui_parameters={
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "tryItOutEnabled": True
        }
    )

@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(username: str = Depends(verify_docs_credentials)):
    """Защищенная документация ReDoc"""
    from fastapi.openapi.docs import get_redoc_html
    return get_redoc_html(openapi_url="/openapi.json", title="API Documentation")

@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_schema(username: str = Depends(verify_docs_credentials)):
    """Защищенная OpenAPI схема"""
    return app.openapi()
# CORS - разрешаем все origins для работы с клиентскими приложениями на разных IP
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",  # Разрешаем любые HTTP/HTTPS origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
    expose_headers=["*"],
)


@app.middleware("http")
async def check_token(request: Request, call_next):
    # Пропускаем авторизацию для документации, статических файлов и OPTIONS запросов (CORS preflight)
    if request.method == "OPTIONS":
        # Возвращаем явный ответ для OPTIONS запросов с CORS заголовками
        origin = request.headers.get("origin")
        headers = {
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, Origin, X-Requested-With",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "3600"
        }
        if origin:
            headers["Access-Control-Allow-Origin"] = origin
        return Response(status_code=200, headers=headers)
    
    if request.url.path in ["/login", "/register", "/docs", "/redoc", "/openapi.json"] or request.url.path.startswith("/static/"):
        response = await call_next(request)
        return response
    
    try:
        auth_header = request.headers.get("Authorization")
        bearer_token = None
        if auth_header and auth_header.startswith("Bearer "):
            bearer_token = auth_header.split(" ")[1]

        query_token = request.query_params.get("token")

        # Разрешаем либо валидный JWT, либо валидный API токен из конфига
        jwt_ok = False
        if bearer_token:
            try:
                payload = decode_access_token(bearer_token)
                jwt_ok = payload is not None
            except Exception:
                jwt_ok = False

        api_token_ok = query_token == config.API_VALID_TOKEN or (auth_header == config.API_VALID_TOKEN)

        if not (jwt_ok or api_token_ok):
            # Добавляем CORS заголовки даже при ошибке авторизации
            origin = request.headers.get("origin")
            if origin:
                raise HTTPException(
                    status_code=401, 
                    detail="Token missing or expired",
                    headers={
                        "Access-Control-Allow-Origin": origin,
                        "Access-Control-Allow-Credentials": "true"
                    }
                )
            raise HTTPException(status_code=401, detail="Token missing or expired")

        response = await call_next(request)
        # Добавляем CORS заголовки ко всем ответам
        origin = request.headers.get("origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
        
    except HTTPException:
        # Пробрасываем HTTPException дальше (это наши 401 ошибки)
        raise
    except Exception as e:
        # Любые другие ошибки при проверке токена возвращаем как 401
        logger.error(f"Ошибка при проверке токена: {str(e)}")
        origin = request.headers.get("origin")
        if origin:
            raise HTTPException(
                status_code=401,
                detail="Token missing or expired",
                headers={
                    "Access-Control-Allow-Origin": origin,
                    "Access-Control-Allow-Credentials": "true"
                }
            )
        raise HTTPException(status_code=401, detail="Token missing or expired")


def include_routers(application: fastapi.FastAPI) -> None:
    # Автоматически подключаем все роутеры из пакета routers
    try:
        import routers
    except ImportError:
        logger.warning("Пакет routers не найден")
        return

    package = importlib.import_module("routers")
    logger.info("Начинаем поиск роутеров...")
    
    for finder, name, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        logger.info(f"Найден модуль: {name}, ispkg: {ispkg}")
        
        if name.endswith(".auth.auth") or name.endswith(".auth"):
            # поддержка текущей структуры routers/auth/auth.py
            module_name = name
        else:
            module_name = name
            
        try:
            module = importlib.import_module(module_name)
            logger.info(f"Модуль {module_name} импортирован успешно")
        except Exception as e:
            logger.warning(f"Не удалось импортировать модуль {module_name}: {e}")
            continue

        router = getattr(module, "router", None)
        if router is not None:
            logger.info(f"Подключаем роутер из модуля {module_name}")
            application.include_router(router)
        else:
            logger.warning(f"Роутер не найден в модуле {module_name}")
    
    logger.info("Поиск роутеров завершен")
    
    # Временное прямое подключение iiko роутера для тестирования
    try:
        from routers.iiko import router as iiko_router
        logger.info("Прямое подключение iiko роутера")
        application.include_router(iiko_router, prefix="/sync", tags=["iiko-sync"])
    except Exception as e:
        logger.warning(f"Не удалось подключить iiko роутер напрямую: {e}")



# Точка входа для локального запуска, в будущем будем менять тут настройки
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)



'''

TODO list:
1) Исправить эндпоинты: 
    - /menu - там чисто список названий, а остального нет
    - /orders - там чисто список названий (и то, не правильно), а остального нет
2) Доработать аналитику: 
    - Не все данные правильно считаются (не те поля)
    - Нет некоторых подсчетов, которые нужны
3) Не работает salary
4) Не работает правильно создание квестов. Там систему надо обсуждать



1) Order эндпоинт фильтр по дате нужен +
2) Expenses эндпоинт нужен +
3) Goods эндпоинт нужен +
'''