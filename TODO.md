# Задачи и их выполнение

# Задачи от 09.04.2026

## Lazy-sync аналитики по запросу
**Идея:** когда юзер заходит в аналитику за конкретный день, бэк отдаёт текущие данные сразу + параллельно (фоном) запускает sync_sales/sync_transactions за этот день. Юзер обновит страницу — увидит свежие.

**Подводные камни (из обсуждения 09.04.2026):**
- **Гонки**: два юзера одновременно → два параллельных sync → DELETE+INSERT друг друга, потеря данных. Нужен per-day lock (`asyncio.Lock` если 1 worker, или PG advisory lock / Redis если несколько workers).
- **Throttling**: «не чаще 1 раза в N секунд для этого дня» (предлагал 60 сек). Хранить `last_sync_at[(method, day)]` в памяти.
- **Eligibility**: только сегодня + последние 2-3 дня. Старые дни не синкать (статичны, бесполезная нагрузка на iiko OLAP).
- **Что синкать**: sales+transactions всегда, либо передавать из эндпоинта что нужно (`sync_targets={'sales','transactions'}`).
- **Сессия БД**: для фоновой задачи нужна СВОЯ сессия (не та, что из эндпоинта — она закроется).

**Архитектура:** отдельный модуль `services/iiko/lazy_sync.py` с функцией `trigger_lazy_sync(db_factory, day, sync_sales=True, sync_transactions=True, max_age_seconds=60, max_day_age_days=3)`. Подключать в начало аналитических эндпоинтов: analytics/profit_loss/reports/shifts/salary.

## Виды оплат: расхождение с iikoFront
**Проблема:** На кассе iikoFront у кассира один набор видов оплат, а у нас в БД (синканных через `/api/1/payment_types` Cloud API) другой — намного меньше. Cloud-эндпоинт возвращает ~6 видов (только привязанные к terminalGroups: CASH/BONUS/Glovo/Wolt/Yandex/Starter), а на терминале реально доступны намного больше — банковские (БЦК/Каспий/Халык), Сертификаты, и т.д.

**Где искать:**
- iiko Chain: говорят, там есть полный справочник видов оплат. Возможно, через Server API `/resto/api/v2/entities/list?rootType=PaymentType` (мы пробовали — отдаёт ~40 объектов, но без `paymentTypeKind`/`terminalGroups`/`paymentProcessingType`).
- Возможно, есть отдельный Server-эндпоинт `/resto/api/v2/entities/payment_types/list` с расширенными полями.
- Возможно, нужно идти через iikoChain API (другая авторизация).

**Что нужно:**
1. Полный справочник видов оплат с `paymentTypeKind`, `paymentProcessingType`, и привязкой к точкам/терминалам.
2. Фильтрация по конкретной точке (organization) — чтобы фронт показывал именно те виды, которые доступны на этой точке, как iikoFront.
3. После получения полного списка — пересмотреть `sync_payment_types` и эндпоинт `/payment-types?organization_id=...`.

## Миграция со старой iiko (январь-февраль 2026)
**Контекст:** Ресторан мигрировал с одной iiko-системы на другую где-то в январе-феврале 2026. У нас в БД сохранились данные из СТАРОЙ iiko, и это создаёт несколько проблем:

- В `organizations` 4 «орфана» от старой системы: `Магазин Цех` (db_id=3), `72 Блок` (db_id=4), `Премьера` (db_id=8), `Магазин ET-KZ` (db_id=11). Они отсутствуют в Cloud `/api/1/organizations` и в Server `/resto/api/corporation/departments`, но имеют исторические `sales`/`transactions` в БД.
- У некоторых из них совпадают `code` с текущими ресторанами (`code='4'` у Магазин Цех и 7ГК Площадь, `code='5'` у Магазин ET-KZ и 3ГК Highvill, `code='13'` у 72 Блок и Премьера) — из-за этого LEFT JOIN в аналитике даёт дубли.
- Также возможны старые столы, секции, типы оплат, сотрудники и т.д.

**Что нужно:**
1. Не удалять старые данные — они нужны для исторических отчётов.
2. Добавить в `organizations` поле `is_legacy=True` (или `archived_at=<дата миграции>`) для разделения старых и текущих точек.
3. В аналитике по умолчанию JOIN'ить по `organization_id` (стабильно), а не по `code` (нестабильно из-за дублей).
4. Если показ исторических данных нужен — отдельный режим, который тянет старые точки.

# Задачи от 20.01.2026

1) Я сделал эндпоинты заказов, и создания изъятий. Надо их проверить
2) Дописываю департаменты, надо где-то держать список департаментов, организаций, концепций, типов изъятий. 
3) Надо проверить эндпоинты заказов хорошенько
4) Проверил изъятия вручную, через postman. Они работают, но не все типы есть. К примеру, ремонт создался, но нет для оборудования. Там структура так работает. Есть аккаунты, это счета условные. Между ними проходят все транзакции (Касса точки -> расход на оборудование). И Типы изъятий это как раз все типы таких транзакций с одного места в другое. И надо понять как создавать типы. Потому что нельзя создать сейчас все типы, хотя большинство доступны.


### Тестирование заказов:
{
  "organizationId": 1,
  "tableId": 5,
  "waiterId": 322256,
  "guests": 2,
  "items": [
    {
      "productId": 2239,
      "amount": 2.0,
      "price": 1500.0,
      "sum": 3000.0,
      "comment": "Без лука"
    },
    {
      "productId": 2259,
      "amount": 1.0,
      "price": 2500.0,
      "sum": 2500.0,
      "comment": "Острое"
    }
  ],
  "comment": "Столик у окна"
}


# Задачи от 27.01.2026

## Часть 1. Исправления.

1) Изменить работу сервиса создания и работы с документами: Списания, приходных накладных, расходных накладных, инвенторизации:
  - documents/writeoff: 
    Склад
    Концепция
    Дата
    Счет с которого списать
    Комментарий
  - /documents/incoming-invoice
    Склад
    Концепция
    Дата
    Комментарий
    Поставщик
  - /documents/outgoing-invoice
    Склад
    Концепция
    Дата
    Счет выручки
    Комментарий
    Расходный счет
    Поставщик
  - /documents/inventory
    Склад
    Дата
    Комментарий
  - Для уточнения:
    - Счета все у нас в accounts, им надо добавить поле типа, потому что есть тип счет расходов, есть тип счет как баланс филиалов. Но пока заполнять это поле типа не надо, пока только создать поле с типом text
2) Правильно имлементировать систему изъятий.
  - Мы берем тип изъятия
  - Мы создаем по api /resto/api/v2/payInOuts/addPayOut
  - Такие данные передаем:
    {
      "payOutTypeId": "e1dfc294-e8b5-4fab-9fd3-9aca43231570", // Мы берем Guid типа изъятия в базе iiko
      "payOutDate": "2026-01-21", // Приводим дату к формату yyyy-MM-dd
      "counteragent": null, // Guid контрагента в базе iiko. В зависимости от типа изъятия.
      "departmentSumMap": { // Торговое предприятие -> сумма изъятия
          "1141b712-e78f-4be2-aebf-a9ad9ca3ffe7": 1516 // Мы тут ставим id department и сумму 
      },
      "payrollId": "", // Guid платежной ведомости в базе iiko. Указывается если изъятие происходит на счет
(т.е. корр.счет) "Текущие расчеты с сотрудниками".
      "comment": "Тестирование" // Поле для комментария
  }

3) Нужно добавить фильтр на эндпоинт получения квестов по дате
4) Когда у employee открывается смена, она почему-то не возвращается что открытая при получении статуса текущего смены и списка смен, надо проверить почему.
5) Нужно скрыть эндпоинты:
  - POST и GET /warehouse/documents
  - /warehouse/writeoff-documents 
  - PUT GET DELETE /warehouse/documents/{document_id}

## Часть 2. Нововведения.

1) Сделать на ответ логина возвращение "name" работника из таблицы employee по полю iiko_id у user
2) Добавить (и если они есть поправить по нужде) эндпоинты, схему, таблицу в базе на сущности Концепция, Поставщик:
  - Для этих сущностей важны 3 вещи:
    - Name
    - iiko_id
    - id наш, который мы назначаем
    - Комментарий
  - Сбор концепций по resto/api/v2/entities/list?rootType=Conception&includeDeleted=true
3) Добавить сущность Тип изъятия. Для него нужно создать схему, сервис запроса в iiko, чтобы получать все типы, хранить у нас все эти данные. Подробнее: 
  - Берем их с iiko server используя /resto/api/v2/entities/payInOutTypes/list?includeDeleted=true
  - Мы получаем массив таких объектов:
    {
        "id": "7c4a6655-9543-42cd-bb6d-265813cdf65e",
        "chiefAccount": null,
        "account": "a889796f-97d4-48af-a21b-b11e49d45148",
        "counteragentType": "NONE",
        "transactionType": "PAYIN",
        "cashFlowCategory": {
            "id": "5832d60a-1836-465a-811c-b9bfc19fcc28",
            "code": "19",
            "parentCategoryId": null,
            "type": "OPERATIONAL"
        },
        "conception": null,
        "limit": 0,
        "comment": "",
        "mandatoryFrontComment": true,
        "isDeleted": false
    },
    Тут важны все поля, и важно понимать какое поле как связать с нашими данными в базе:
      - account и chiefAccount это таблица accounts_list
      - 
  - У типа должны быть все эти поля, они все важны
  - Мы должны открыть эндпоинт, который будет возвращать список этих типов:
    - Список объектов:
      - id
      - название счета (account -> accounts_list.name)
4) Доработать создание заказа на стороне iiko:
  - Эндпоинт iiko cloud /api/1/order/create
  - Данные которые мы передаем: 
    {
      "organizationId": "7bc05553-4b68-44e8-b7bc-37be63c6d9e9",
      "terminalGroupId": "4fab19a5-203c-4bf5-94eb-f572aa8b117b",
      "order": {
        "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
        "externalNumber": "string",
        "tableIds": [
          "497f6eca-6276-4993-bfeb-53cbbbba6f08"
        ],
        "customer": {
          "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
          "name": "string",
          "surname": "string",
          "comment": "string",
          "birthdate": "2019-08-24 14:15:22.123",
          "email": "string",
          "shouldReceivePromoActionsInfo": true,
          "shouldReceiveOrderStatusNotifications": true,
          "gender": "NotSpecified",
          "type": "string"
        },
        "phone": "string",
        "guestCount": 0,
        "guests": {
          "count": 0
        },
        "tabName": "string",
        "menuId": null,
        "priceCategoryId": "e658c457-170e-4909-a4a8-49eeaee12035",
        "items": [
          {
            "type": "string",
            "amount": 0,
            "productSizeId": "b4513563-032a-4dbc-8894-4b05c402f7de",
            "comboInformation": {
              "comboId": "1fa22bdf-8ea5-4d3f-a6cf-3abb16e9aa74",
              "comboSourceId": "dd3c663c-f4a0-4960-be17-31d91758b3a4",
              "comboGroupId": "2cb9710d-2ed9-4514-8333-275a9727b4dd",
              "comboGroupName": "string"
            },
            "comment": "string"
          }
        ],
        "combos": [
          {
            "id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
            "name": "string",
            "amount": 0,
            "price": 0,
            "sourceId": "797f5a94-3689-4ac8-82fd-d749511ea2b2",
            "programId": "bc59f66b-913a-48ec-ae2b-7ee29d7bcfbb",
            "sizeId": "f98600f7-1d0f-4a64-936e-93e133055658"
          }
        ],
        "payments": [
          {
            "paymentTypeKind": "string",
            "sum": 0,
            "paymentTypeId": "a681b746-24d1-4f1c-aa71-6af3f1e19567",
            "isProcessedExternally": true,
            "paymentAdditionalData": {
              "type": "string"
            },
            "isFiscalizedExternally": true,
            "isPrepay": true
          }
        ],
        "tips": [
          {
            "paymentTypeKind": "string",
            "tipsTypeId": "e8b7f419-5ea5-4f5b-b897-d30febf1d59c",
            "sum": 0,
            "paymentTypeId": "a681b746-24d1-4f1c-aa71-6af3f1e19567",
            "isProcessedExternally": true,
            "paymentAdditionalData": {
              "type": "string"
            },
            "isFiscalizedExternally": true,
            "isPrepay": true
          }
        ],
        "sourceKey": "string",
        "discountsInfo": {
          "card": {
            "track": "string"
          },
          "discounts": [
            {
              "type": "string"
            }
          ],
          "fixedLoyaltyDiscounts": true
        },
        "loyaltyInfo": {
          "coupon": "string",
          "applicableManualConditions": [
            "497f6eca-6276-4993-bfeb-53cbbbba6f08"
          ],
          "dynamicDiscounts": [
            {
              "manualConditionId": "a998fc1e-67e4-4f5e-84a2-1eb4586505a3",
              "sum": 0
            }
          ]
        },
        "orderTypeId": "c21c7b56-cdb7-4141-bc14-77df36146699",
        "chequeAdditionalInfo": {
          "needReceipt": true,
          "email": "string",
          "settlementPlace": "string",
          "phone": "stringst",
          "retailAddress": "string",
          "isInternetPayment": true
        },
        "externalData": [
          {
            "key": "string",
            "value": "string",
            "isPublic": true
          }
        ]
      },
      "createOrderSettings": {
        "servicePrint": false,
        "transportToFrontTimeout": 0,
        "checkStopList": false
      }
    }
  - Описание данных: [файл](api_documentation_create_order.md) 
  - Самое важное это required поля, а потом дополнительно что нужно, надо проанализировать
  - Сейчас важно прописать чтобы использовалась определенная точка(филиал/департамент/концепция) для тестов. 





# Тестирование заказов 
{
    "organizationId": "7bc05553-4b68-44e8-b7bc-37be63c6d9e9",
    "terminalGroupId": "4fab19a5-203c-4bf5-94eb-f572aa8b117b",
    "createPaymentIfNotExists": false,
    "checkStopList": false,
    "order": {
        "externalNumber": "72732",
        "phone": null,
        "orderTypeId": "c21c7b56-cdb7-4141-bc14-77df36146699",
        "comment": "Столик у окна",
        "guests": {
            "count": 2
        },
        "items": [
            {
                "productId": "6668b714-c55b-4fe6-87b1-8f63c48c9b05",
                "type": "Product",
                "amount": 2.0,
                "price": 1500.0,
                "comment": "Без лука"
            },
            {
                "productId": "5b9a3857-7218-407f-9de1-6d9125360966",
                "type": "Product",
                "amount": 1.0,
                "price": 2500.0,
                "comment": "Острое"
            }
        ],
        "payments": []
    }
}



# Задачи от 25.02.2026

1) Сделать чтобы создание заказов и работа с заказами работало используя старый api 
В .env фале лежат:
IIKO_OLD_CLOUD_API_URL=https://api-ru.iiko.services
IIKO_OLD_LOGIN_KEY=e21c5274d7df44449134cc03d97510b7
Надо используя их делать запрос в iiko на создание заказа

2) Нужно создать на каждого employee сущность user, чтобы могли авторизоваться, используя их name. Потом сделать эндпоинт change_password, который работает только для роли менеджера и владельца, чтобы они могли юзерам менять пароль, принимают id employee, новый пароль и менять пароль
3) И тянуть информацию о user по его id и давать там же id employee из нашей таблицы в этом ответе

4) Вот точки ресторанов:
5ГК Шарль де Голль	ИП Шаяхметов	Astana, Astana, Шарль де Голль, 1а
7ГК Площадь	ИП Акжан	Astana, Astana, Кабанбай батыр проспект, 34	
ФАБРИКА	ИП Амиржан	Astana, Astana, Шарль де голя	
1ГК Бокейхана	ИП Акжан	Astana, Astana, Улица Алихан Бокейхан, 8	
4ГК Expo	ИП Акжан	Astana, Astana, Кабанбай батыр проспект, 58Б	
2ГК Мангилик	ИП Шаяхметов	Astana, Astana, Мангилик Ел, 50	
8ГК Мухамедханова	ИП Амиржан	Astana, Astana, Кайым Мухамедханов, 5	
6ГК Нурсая	ИП Амиржан	Astana, Astana, Динмухамед Конаев, 14	
3ГК Highvill	ИП Амиржан	Astana, Astana, Ракымжан Кошкарбаев, 8
Надо по этим точкам в наши организации добавить три поля, адрес, и координаты (long lat) чтобы возвращал апи организаций
Найди в интернете координаты достаточно точные, до 10 метров точности, чтобы записать в базу.

Там же нужна миграция, чтобы добавить новые поля
5) Нужна доп оптимизация на получение документов из iiko, чтобы мы дробили запросы по частям, не сразу за месяц, а по дням разбивать запросы и по очереди выполнять.
Проверить все запросы в iiko где есть from и to даты 




# Задачи от 25.02.2026 Часть 2
6) При оплате заказа (POST /orders/{id}/pay) нужно также вызывать iiko API для закрытия заказа:
  - Endpoint: POST /api/1/order/close
  - Требует: organizationId (string, iiko uuid), orderId (string, iiko uuid = order.iiko_id)
  - Опционально: chequeAdditionalInfo
  - Использовать IikoApiType.CLOUD_OLD (тот же ключ что и для создания заказа)
  - Вызывать только если order.iiko_id не None (заказ был синкнут/создан в iiko)
  - Обрабатывать ошибку мягко — если iiko вернул ошибку, всё равно сохранять PAID статус локально, но логировать
