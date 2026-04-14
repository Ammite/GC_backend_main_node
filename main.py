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
        description="""API для системы управления рестораном с интеграцией iiko.

## Авторизация

Большинство эндпоинтов требуют **JWT Bearer token**:
- **Header:** `Authorization: Bearer <token>`
- **Query param:** `?token=<token>`

Токен выдаётся при `/login` или `/register`, срок действия — **5 дней**.

**Без авторизации:** `/login`, `/register`, `/sync/cron/sync`, `/sync/cron/daily-sync` (apikey), `/db/*`

## Формат дат

| Контекст | Формат | Пример |
|----------|--------|--------|
| Query параметры (основные) | DD.MM.YYYY | `01.03.2026` |
| Query параметры (sync/admin) | YYYY-MM-DD | `2026-03-01` |
| Timestamps в ответах | ISO 8601 | `2026-03-01T12:00:00` |

## ID сущностей

В API используются **внутренние ID** (int из БД), если не указано иное. Система автоматически конвертирует их в iiko UUID при необходимости.

| Сущность | Внутренний ID | iiko ID | Примечания |
|----------|--------------|---------|------------|
| Organization | `id` (int) | `iiko_id`, `iiko_id_cloud` (str) | Cloud и Server API используют разные UUID |
| Employee | `id` (int) | `iiko_id` (str) | User связан через общий iiko_id |
| User | `id` (int) | `iiko_id` (str) | Связь User ↔ Employee через iiko_id |
| Order | `id` (int) | `iiko_id` (str) | iiko_id заполняется после синхронизации |
| Item (товар) | `id` (int) | `iiko_id` (str) | Используется в документах |
| Shift | `id` (int) | `iiko_id` (str) | |
| Table | `id` (int) | `iiko_id` (str) | |
| Department | `id` (int) | `iiko_id` (str) | |
| Conception | `id` (int) | `iiko_id` (str) | |
| Supplier | `id` (int) | `iiko_id` (str) | |

## Стандартный ответ

```json
{"success": true, "message": "описание результата", ...}
```

> **Важно:** `/login` и `/register` возвращают HTTP 200 даже при ошибке (`success: false`), а не 401.

## Ключевые особенности

- **Заказы:** `organizationId`, `tableId`, `waiterId`, `productId` в теле запроса — ВСЕ внутренние ID. Система сама конвертирует в iiko UUID.
- **Документы:** `items[].id` — внутренний Item.id, но `supplier` — это iiko UUID (строка).
- **Expenses:** экспортирует ДВА роутера: аналитика (`/reports/expenses`) и управление (`/expenses/*`).
- **iiko Sync:** все endpoints на `/sync/`, вызываются cron-задачами или администраторами.

Полная документация: [docs/API_REFERENCE.md](https://github.com/Ammite/backend_main_node/blob/main/docs/API_REFERENCE.md)
""",
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
    
    # Описания тегов для навигации в Swagger UI
    openapi_schema["tags"] = [
        {"name": "auth", "description": "Аутентификация — логин, регистрация, смена пароля"},
        {"name": "profile", "description": "Профиль — данные текущего пользователя"},
        {"name": "employees", "description": "Сотрудники и штрафы — список, сводка, детали, штрафы"},
        {"name": "orders", "description": "Заказы — создание, оплата, обновление, отмена"},
        {"name": "shifts", "description": "Смены — начало/конец смены, статус"},
        {"name": "quests", "description": "Квесты — создание, прогресс, управление"},
        {"name": "tasks", "description": "Задачи — создание, список, выполнение"},
        {"name": "salary", "description": "Зарплата — расчёт за день, продажи"},
        {"name": "reports", "description": "Отчёты — заказы, денежный поток, динамика продаж, персонал, P&L, популярные блюда, расходы"},
        {"name": "expenses", "description": "Расходы — CRUD управление расходами"},
        {"name": "organizations", "description": "Организации — список с фильтрацией"},
        {"name": "menu", "description": "Меню — позиции меню"},
        {"name": "goods", "description": "Товары — категории и товары (складские)"},
        {"name": "rooms", "description": "Залы и столы — помещения, столы, статусы"},
        {"name": "payment-types", "description": "Виды оплат — получение доступных видов оплат"},
        {"name": "conceptions", "description": "Концепции — синхронизация и список концепций из iiko"},
        {"name": "suppliers", "description": "Поставщики — синхронизация и список поставщиков из iiko"},
        {"name": "departments", "description": "Департаменты — синхронизация и получение"},
        {"name": "documents", "description": "Документы — акты списания, накладные, инвентаризация, изъятия"},
        {"name": "warehouse", "description": "Склад — документы, остатки, синхронизация"},
        {"name": "cache", "description": "Кэш — статистика и очистка"},
        {"name": "database", "description": "DB индексы — создание, удаление, оптимизация"},
        {"name": "iiko-sync", "description": "⚙️ iiko Sync (админ) — синхронизация данных из iiko API. Вызывается cron-задачами и администраторами."},
    ]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Защищенные эндпоинты документации (ВРЕМЕННО ОТКЛЮЧЕНА АВТОРИЗАЦИЯ)
@app.get("/privacy-policy", include_in_schema=False)
async def privacy_policy():
    """Политика конфиденциальности"""
    from fastapi.responses import HTMLResponse
    with open("temp_files/Privacy Policy.txt", "r", encoding="utf-8") as f:
        text = f.read()
    html = _text_to_html(text, "Политика конфиденциальности")
    return HTMLResponse(content=html)


@app.get("/terms-of-service", include_in_schema=False)
async def terms_of_service():
    """Пользовательское соглашение"""
    from fastapi.responses import HTMLResponse
    with open("temp_files/Terms of service.txt", "r", encoding="utf-8") as f:
        text = f.read()
    html = _text_to_html(text, "Пользовательское соглашение")
    return HTMLResponse(content=html)


def _text_to_html(text: str, title: str) -> str:
    """Конвертирует текст в оформленную HTML-страницу."""
    lines = text.strip().split("\n")
    body_parts = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("________"):
            body_parts.append("<hr>")
        elif line == lines[0].strip():
            # Заголовок документа — уже в <h1>
            continue
        elif line.startswith("Дата последнего обновления"):
            body_parts.append(f'<p class="date">{line}</p>')
        elif len(line) > 2 and line[0].isdigit() and line[1] == "." and line[2] == " ":
            body_parts.append(f"<h2>{line}</h2>")
        elif line.startswith("•\t") or line.startswith("• "):
            item_text = line.lstrip("•\t ")
            body_parts.append(f"<li>{item_text}</li>")
        elif line.startswith("Email:"):
            email = line.replace("Email:", "").strip().strip("[]")
            body_parts.append(f'<p><strong>Email:</strong> <a href="mailto:{email}">{email}</a></p>')
        else:
            body_parts.append(f"<p>{line}</p>")

    # Оборачиваем <li> в <ul>
    body_html = "\n".join(body_parts)
    body_html = body_html.replace("</p>\n<li>", "</p>\n<ul>\n<li>")
    body_html = body_html.replace("</li>\n<p>", "</li>\n</ul>\n<p>")
    body_html = body_html.replace("</li>\n<hr>", "</li>\n</ul>\n<hr>")
    body_html = body_html.replace("</li>\n<h2>", "</li>\n</ul>\n<h2>")

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — RestoAI</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.7;
            color: #333;
            background: #f8f9fa;
            padding: 20px;
        }}
        .container {{
            max-width: 800px;
            margin: 40px auto;
            background: #fff;
            border-radius: 12px;
            padding: 40px 48px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        h1 {{
            font-size: 28px;
            margin-bottom: 4px;
            color: #111;
        }}
        .date {{
            color: #888;
            font-size: 14px;
            margin-bottom: 24px;
        }}
        h2 {{
            font-size: 20px;
            margin-top: 28px;
            margin-bottom: 12px;
            color: #222;
        }}
        p {{
            margin-bottom: 10px;
        }}
        ul {{
            margin: 8px 0 12px 24px;
        }}
        li {{
            margin-bottom: 4px;
        }}
        hr {{
            border: none;
            border-top: 1px solid #e5e5e5;
            margin: 20px 0;
        }}
        a {{
            color: #2563eb;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        @media (max-width: 600px) {{
            .container {{
                padding: 24px 20px;
                margin: 16px auto;
            }}
            h1 {{ font-size: 22px; }}
            h2 {{ font-size: 17px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        {body_html}
    </div>
</body>
</html>"""


@app.get("/docs", include_in_schema=False)
async def get_documentation():
    """Документация Swagger UI с поддержкой токена"""
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="API Documentation",
        swagger_ui_parameters={
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "tryItOutEnabled": True,
            "docExpansion": "none",
            "filter": True,
            "tagsSorterFn": None,
        }
    )

@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation():
    """Документация ReDoc"""
    from fastapi.openapi.docs import get_redoc_html
    return get_redoc_html(openapi_url="/openapi.json", title="API Documentation")

@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_schema():
    """OpenAPI схема"""
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
    # ============================================
    # ВРЕМЕННО ОТКЛЮЧЕНА ПРОВЕРКА ТОКЕНА
    # ============================================
    # Обрабатываем OPTIONS запросы для CORS
    if request.method == "OPTIONS":
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
    
    # Пропускаем все запросы без проверки токена
    response = await call_next(request)
    
    # Добавляем CORS заголовки ко всем ответам
    origin = request.headers.get("origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response
    
    # ============================================
    # СТАРАЯ ЛОГИКА ПРОВЕРКИ ТОКЕНА (ЗАКОММЕНТИРОВАНА)
    # ============================================
    # # Пропускаем авторизацию для документации, статических файлов и OPTIONS запросов (CORS preflight)
    # if request.method == "OPTIONS":
    #     # Возвращаем явный ответ для OPTIONS запросов с CORS заголовками
    #     origin = request.headers.get("origin")
    #     headers = {
    #         "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
    #         "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, Origin, X-Requested-With",
    #         "Access-Control-Allow-Credentials": "true",
    #         "Access-Control-Max-Age": "3600"
    #     }
    #     if origin:
    #         headers["Access-Control-Allow-Origin"] = origin
    #     return Response(status_code=200, headers=headers)
    # 
    # if request.url.path in ["/login", "/register", "/docs", "/redoc", "/openapi.json"] or request.url.path.startswith("/static/"):
    #     response = await call_next(request)
    #     return response
    # 
    # try:
    #     auth_header = request.headers.get("Authorization")
    #     bearer_token = None
    #     if auth_header and auth_header.startswith("Bearer "):
    #         bearer_token = auth_header.split(" ")[1]
    #
    #     query_token = request.query_params.get("token")
    #
    #     # Разрешаем либо валидный JWT, либо валидный API токен из конфига
    #     jwt_ok = False
    #     if bearer_token:
    #         try:
    #             payload = decode_access_token(bearer_token)
    #             jwt_ok = payload is not None
    #         except Exception:
    #             jwt_ok = False
    #
    #     api_token_ok = query_token == config.API_VALID_TOKEN or (auth_header == config.API_VALID_TOKEN)
    #
    #     if not (jwt_ok or api_token_ok):
    #         # Добавляем CORS заголовки даже при ошибке авторизации
    #         origin = request.headers.get("origin")
    #         if origin:
    #             raise HTTPException(
    #                 status_code=401, 
    #                 detail="Token missing or expired",
    #                 headers={
    #                     "Access-Control-Allow-Origin": origin,
    #                     "Access-Control-Allow-Credentials": "true"
    #                 }
    #             )
    #         raise HTTPException(status_code=401, detail="Token missing or expired")
    #
    #     response = await call_next(request)
    #     # Добавляем CORS заголовки ко всем ответам
    #     origin = request.headers.get("origin")
    #     if origin:
    #         response.headers["Access-Control-Allow-Origin"] = origin
    #         response.headers["Access-Control-Allow-Credentials"] = "true"
    #     return response
    #     
    # except HTTPException:
    #     # Пробрасываем HTTPException дальше (это наши 401 ошибки)
    #     raise
    # except Exception as e:
    #     # Любые другие ошибки при проверке токена возвращаем как 401
    #     logger.error(f"Ошибка при проверке токена: {str(e)}")
    #     origin = request.headers.get("origin")
    #     if origin:
    #         raise HTTPException(
    #             status_code=401,
    #             detail="Token missing or expired",
    #             headers={
    #                 "Access-Control-Allow-Origin": origin,
    #                 "Access-Control-Allow-Credentials": "true"
    #             }
    #         )
    #     raise HTTPException(status_code=401, detail="Token missing or expired")


_routers_included = False

def include_routers(application: fastapi.FastAPI) -> None:
    global _routers_included
    if _routers_included:
        return
    _routers_included = True

    # Автоматически подключаем все роутеры из пакета routers
    try:
        import routers
    except ImportError:
        logger.warning("Пакет routers не найден")
        return

    package = importlib.import_module("routers")
    logger.info("Начинаем поиск роутеров...")

    # Собираем роутеры, исключая дубли:
    # walk_packages находит и пакет (routers.tasks) и модуль (routers.tasks.tasks),
    # оба экспортируют один и тот же router — берём только один из них.
    # Также iiko router подключаем вручную с prefix="/sync".
    seen_routers: set[int] = set()  # id() объектов роутеров для дедупликации

    for finder, name, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        # Пропускаем модуль iiko.sync — он подключается вручную ниже с prefix="/sync"
        if name == "routers.iiko.sync" or name == "routers.iiko":
            continue

        try:
            module = importlib.import_module(name)
        except Exception as e:
            logger.warning(f"Не удалось импортировать модуль {name}: {e}")
            continue

        router = getattr(module, "router", None)
        if router is not None and id(router) not in seen_routers:
            seen_routers.add(id(router))
            logger.info(f"Подключаем роутер из модуля {name}")
            application.include_router(router)

        # Проверяем наличие дополнительных роутеров (router_management, router_suppliers и т.д.)
        for extra_name in ("router_management", "router_suppliers"):
            extra_router = getattr(module, extra_name, None)
            if extra_router is not None and id(extra_router) not in seen_routers:
                seen_routers.add(id(extra_router))
                logger.info(f"Подключаем {extra_name} из модуля {name}")
                application.include_router(extra_router)

    logger.info("Поиск роутеров завершен")

    # Подключение iiko роутера с prefix="/sync"
    try:
        from routers.iiko.sync import router as iiko_router
        logger.info("Подключаем iiko роутер с prefix=/sync")
        application.include_router(iiko_router, prefix="/sync", tags=["iiko-sync"])
    except Exception as e:
        logger.warning(f"Не удалось подключить iiko роутер: {e}")



# Точка входа для локального запуска, в будущем будем менять тут настройки
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8008, workers=2)



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