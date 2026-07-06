# Архитектура информационной системы

Серверная часть (backend) информационной системы для управления сетью ресторанов
с интеграцией iiko. Документ описывает контекст системы, слоистую архитектуру
backend-приложения, схему базы данных и логику внешних интеграций.

- **Стек:** Python 3.12, FastAPI, SQLAlchemy (sync ORM), PostgreSQL
- **Внешние интеграции:** iiko Cloud API, iiko Server API, Telegram (алерты)
- **Клиенты:** мобильное приложение для персонала, мобильное приложение для управляющих

---

## 1. Контекст системы (System Context)

```mermaid
flowchart TB
    staffApp["📱 Мобильное приложение<br/>персонала"]
    mgrApp["📱 Мобильное приложение<br/>управляющих"]

    subgraph backend["Backend (FastAPI, порт 8008)"]
        api["REST API + Swagger /docs"]
    end

    db[("🗄️ PostgreSQL<br/>(собственная БД)")]
    iikoCloud["☁️ iiko Cloud API"]
    iikoServer["🖥️ iiko Server API"]
    tg["✈️ Telegram<br/>(алерты об ошибках)"]

    staffApp -->|"HTTPS / JWT"| api
    mgrApp -->|"HTTPS / JWT"| api
    api -->|"SQLAlchemy"| db
    api -->|"синхронизация / заказы"| iikoCloud
    api -->|"номенклатура, документы, отчёты"| iikoServer
    api -->|"уведомления об ошибках"| tg
```

Система выступает промежуточным слоем между мобильными приложениями и iiko:
данные из iiko синхронизируются в собственную БД, а клиентские приложения
работают только с backend-API, не обращаясь к iiko напрямую.

---

## 2. Слоистая архитектура backend

```mermaid
flowchart TB
    subgraph client["Клиенты"]
        c["Мобильные приложения<br/>(персонал / управляющие)"]
    end

    subgraph app["FastAPI приложение (main.py)"]
        direction TB
        sec["Безопасность: JWT (OAuth2 Bearer),<br/>hash_password (sha256), get_current_user"]

        subgraph routers["Слой routers/ (HTTP-эндпоинты)"]
            r["auth · users · employees · profile · orders<br/>menu · goods · warehouse · documents · expenses<br/>salary · shifts · payment_types · organizations<br/>departments · rooms · conceptions · tasks · quests<br/>analytics · reports · profit_loss · popular_dishes<br/>cache · iiko (sync)"]
        end

        subgraph services["Слой services/ (бизнес-логика)"]
            s["orders · menu · goods · warehouse · expenses<br/>salary · shifts · employees · users · profile<br/>organizations · departments · rooms · tasks · quests<br/>fines · cash · analytics · reports · profit_loss<br/>popular_dishes · transactions_and_statistics"]
            iiko["services/iiko/<br/>iiko_service · iiko_sync · iiko_parser"]
        end

        subgraph schemas["Слой schemas/ (Pydantic — валидация I/O)"]
            sc["auth · users · employees · orders · menu · goods<br/>warehouse · salary · shifts · ... (по доменам)"]
        end

        subgraph models["Слой models/ (SQLAlchemy ORM)"]
            m["User · Employee · Organization · Order · Sales<br/>Item · Menu · Store · Transaction · Salary · Shift · ..."]
        end
    end

    db[("PostgreSQL")]
    iikoExt["iiko Cloud / Server API"]
    tg["Telegram"]

    c -->|HTTPS| sec
    sec --> routers
    routers --> services
    services --> schemas
    services --> models
    models -->|ORM| db
    iiko --> iikoExt
    iiko -.->|при ошибках| tg
    services --> iiko
```

**Принцип:** запрос проходит `router → service → model/schema`.
Routers отвечают только за HTTP и авторизацию, бизнес-логика сосредоточена в
services, доступ к данным — через ORM-модели, контракты API описаны схемами Pydantic.

---

## 3. Схема базы данных (основные сущности)

> У каждой сущности есть собственный `id`, у многих — `iiko_id` (UUID из iiko)
> для сопоставления с данными iiko.

```mermaid
erDiagram
    ORGANIZATION ||--o{ DEPARTMENT : "включает"
    ORGANIZATION ||--o{ EMPLOYEE : "штат"
    ORGANIZATION ||--o{ ORDER : "заказы"
    ORGANIZATION ||--o{ STORE : "склады"

    USER }o--|| ROLE : "имеет роль"
    USER ||--o| EMPLOYEE : "связан через iiko_id"

    EMPLOYEE ||--o{ SHIFT : "смены"
    EMPLOYEE ||--o{ USER_SALARY : "начисления"
    EMPLOYEE ||--o{ PENALTY : "штрафы"
    EMPLOYEE ||--o{ USER_REWARD : "награды"
    EMPLOYEE ||--o{ WAITER_SALES_PERCENT : "процент с продаж"

    ORDER ||--o{ SALES : "позиции продаж"
    ORDER }o--|| ORDER_TYPE : "тип"
    ORDER ||--o{ TRANSACTION : "оплаты"
    TRANSACTION }o--|| PAYMENT_TYPE : "способ оплаты"

    ITEM }o--|| CATEGORY : "категория"
    ITEM }o--|| PRODUCT_GROUP : "группа"
    MENU_CATEGORY ||--o{ ITEM : "блюда меню"
    ITEM ||--o{ MODIFIER : "модификаторы"

    STORE ||--o{ WAREHOUSE : "остатки"
    SUPPLIER ||--o{ INCOME : "поставки"

    USER {
        int id PK
        string login
        string password "sha256"
        string iiko_id
        int roles_id FK
    }
    EMPLOYEE {
        int id PK
        string name
        string iiko_id
        int preferred_organization_id
        string main_role_code
    }
    ORGANIZATION {
        int id PK
        string iiko_id
        text address
        numeric latitude
        numeric longitude
    }
    ORDER {
        int id PK
        string iiko_id
        int organization_id FK
    }
```

> Диаграмма отражает ключевые сущности и связи доменной модели; полный перечень
> таблиц — в каталоге `models/` (~40 моделей), детали миграций — в `migrations/`.

---

## 4. Логика интеграции с iiko

Клиент iiko (`services/iiko/iiko_service.py`) работает с тремя типами API
(перечисление `IikoApiType`):

| Тип | Назначение | Авторизация |
|-----|-----------|-------------|
| `CLOUD` | стандартный iiko Cloud API | Bearer-токен (apiLogin) |
| `CLOUD_OLD` | старый ключ Cloud API (для заказов) | Bearer-токен |
| `SERVER` | iiko Server API (номенклатура, документы, отчёты) | логин/пароль |

```mermaid
sequenceDiagram
    participant App as Мобильное приложение
    participant API as Backend (FastAPI)
    participant DB as PostgreSQL
    participant IIKO as iiko Cloud / Server
    participant TG as Telegram

    Note over API,IIKO: Синхронизация (routers/iiko/sync.py)
    API->>IIKO: запрос данных (номенклатура, продажи, документы)
    IIKO-->>API: данные (JSON)
    API->>DB: upsert по iiko_id (iiko_sync / iiko_parser)

    Note over App,DB: Обычный запрос клиента
    App->>API: HTTPS + JWT
    API->>DB: чтение/запись через ORM
    DB-->>API: данные
    API-->>App: JSON-ответ

    Note over API,TG: Обработка ошибок iiko
    API->>IIKO: команда (напр. создание заказа)
    alt Ошибка / таймаут
        API->>TG: алерт об ошибке
    end
```

**Ключевые особенности интеграции:**
- Данные iiko синхронизируются в собственную БД и сопоставляются по `iiko_id`.
- Между запросами к iiko выдерживаются задержки (`*_REQUEST_DELAY`), чтобы не
  перегружать кассовый контур.
- После команд в iiko Cloud выполняется поллинг статуса; при ошибке/таймауте
  отправляется Telegram-алерт.

---

## 5. Безопасность и доступ

- Аутентификация — JWT (OAuth2 Bearer), выдача токена через `create_access_token`.
- Пароли хранятся как `sha256`-хеш (`hash_password`).
- Зависимость `get_current_user` защищает эндпоинты, требующие авторизации.
- Swagger UI (`/docs`), ReDoc (`/redoc`) и `/openapi.json` закрыты Basic Auth.
- Ролевая модель доступа — через `roles` / `main_role_code` (персонал vs управляющие).
