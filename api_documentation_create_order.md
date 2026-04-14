Ниже черновик документа по эндпоинту **Create order** (POST `/api/1/orders/create` / аналогичный, если у вас другой путь — просто подставьте его в заголовок и пример). Структуру можно вставить в Confluence/Notion/README и допилить под ваш формат. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

***

## 1. Назначение метода

Метод предназначен для создания заказа доставки/самовывоза в iikoCloud (iikoFront) из внешней системы. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
Запрос формирует новый заказ с составом блюд, типом заказа, клиентом, адресом доставки и оплатами и отправляет его в нужную терминальную группу. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

***

## 2. HTTP‑интерфейс

- **HTTP‑метод:** `POST`  
- **URL:** `/api/1/orders/create` (уточнить по вашим спекам, возможен другой путь в разделе Orders). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- **Content-Type:** `application/json`  
- **Аутентификация:** заголовок `Authorization: Bearer {token}` (получен через `/api/1/access_token`). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

### 2.1. Заголовки

- `Authorization` (string, required) – токен авторизации в формате `Bearer {token}`. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `Timeout` (integer, optional, default 15) – таймаут запроса в секундах. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

***

## 3. Тело запроса

### 3.1. Общая структура

```json
{
  "organizationId": "string",
  "terminalGroupId": "string",
  "order": {
    "externalNumber": "string",
    "phone": "string",
    "customer": { ... },
    "sourceKey": "string",
    "orderTypeId": "string",
    "deliveryPoint": { ... },
    "items": [ ... ],
    "payments": [ ... ],
    "comment": "string",
    "marketingSourceId": "string",
    "coupon": "string",
    "guests": { ... }
  },
  "createPaymentIfNotExists": false,
  "checkStopList": true
}
```

Ниже — поля по смысловым блокам (типы и назначение). Структуры полей берутся из разделов **Organizations**, **Terminal groups**, **Dictionaries – Order types/Payment types/Marketing sources**, **Menu – Nomenclature/Combo**, **Addresses/Deliveries** и т.д. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

### 3.2. Поля верхнего уровня

- `organizationId` (string, required, uuid) – идентификатор организации, для которой создаётся заказ; берётся из `/api/1/organizations`. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `terminalGroupId` (string, required, uuid) – ID терминальной группы, куда будет отправлен заказ; берётся из `/api/1/terminal_groups`. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `createPaymentIfNotExists` (boolean, optional) – создавать ли новый платёжный документ, если тип оплаты не найден в фронте (поведение зависит от ваших бизнес‑настроек, опция для интеграции). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `checkStopList` (boolean, optional) – если `true`, перед созданием заказа позиции проверяются по стоп‑листу (аналогично `/api/1/stop_lists/check`). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

### 3.3. Блок `order`

#### 3.3.1. Основные поля заказа

- `externalNumber` (string, optional) – внешний номер заказа во вашей системе (для последующей сверки).  
- `phone` (string, optional) – телефон клиента в свободном формате, чаще всего используется для идентификации и поиска клиента.  
- `orderTypeId` (string, required, uuid) – тип заказа (доставка, самовывоз и т.п.); берётся из `/api/1/deliveries/order_types`. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `sourceKey` (string, optional) – источник заказа (канал: сайт, мобильное приложение и т.п.); берётся из раздела **Marketing sources**. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `comment` (string, optional) – текстовый комментарий к заказу, отображается на фронте курьерам/операторам. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `marketingSourceId` (string, optional, uuid) – маркетинговый источник (если используется справочник Marketing sources). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `coupon` (string, optional) – промокод/купон, который должен быть применён к заказу (при использовании лояльности/акций). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

#### 3.3.2. Клиент `customer`

```json
"customer": {
  "id": "string",
  "name": "string",
  "surName": "string",
  "comment": "string",
  "email": "string",
  "sex": "NotSpecified | Male | Female",
  "birthdate": "yyyy-MM-dd",
  "loyaltyCustomerId": "string"
}
```

- `id` (string, optional, uuid) – существующий ID клиента в iiko; если не указан, клиент может быть создан по телефону/имени. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `name`, `surName` (string, optional) – имя и фамилия клиента.  
- `email` (string, optional) – email клиента (для чеков/рассылок).  
- `comment` (string, optional) – внутренний комментарий по клиенту.  
- `sex`, `birthdate` (optional) – дополнительные данные клиента, могут использоваться в лояльности. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `loyaltyCustomerId` (string, optional) – ID клиента в системе лояльности, если она интегрирована. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

#### 3.3.3. Адрес доставки `deliveryPoint` (для доставки)

```json
"deliveryPoint": {
  "street": {
    "id": "string",
    "name": "string"
  },
  "house": "string",
  "flat": "string",
  "entrance": "string",
  "floor": "string",
  "doorphone": "string",
  "comment": "string",
  "latitude": 0,
  "longitude": 0,
  "cityId": "string"
}
```

- `street.id` (string, uuid, optional) – справочный ID улицы, если используется адресный справочник (`Addresses`/`Delivery restrictions`). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `street.name` (string, optional) – текстовое название улицы, если ID не используется.  
- `house` (string, required для доставки) – номер дома.  
- `flat`, `entrance`, `floor`, `doorphone` (string, optional) – уточняющие данные доставки.  
- `comment` (string, optional) – комментарий к адресу (ориентиры).  
- `latitude`, `longitude` (number, optional) – координаты точки доставки, используются в модуле логистики/курьеров. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `cityId` (string, optional, uuid) – идентификатор города, если в организации включено «UseBusinessHoursAndMapping» и/или задано `DefaultDeliveryCityId`. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

Для самовывоза `deliveryPoint` может отсутствовать или быть пустым, в зависимости от требований конкретной конфигурации iiko. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

#### 3.3.4. Состав заказа `items`

```json
"items": [
  {
    "productId": "string",
    "type": "Product | Modificator",
    "amount": 1,
    "price": 0,
    "comment": "string",
    "modifiers": [ ... ],
    "comboInformation": { ... },
    "sizeId": "string"
  }
]
```

- `productId` (string, required, uuid) – ID блюда/товара из меню (`/api/1/nomenclature`). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `type` (string, required) – тип строки: основное блюдо или модификатор (если используется различение). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `amount` (number, required) – количество единиц позиции (целое или дробное, если разрешено).  
- `price` (number, optional) – итоговая цена за единицу; если не указана, рассчитывается по меню/акциям, если указана – возможен режим фиксированной цены (зависит от настроек). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `sizeId` (string, optional, uuid) – размер блюда (`sizes` из `/api/1/nomenclature`). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `comment` (string, optional) – комментарий к позиции (например, «без лука»).  
- `modifiers` (array, optional) – список модификаторов (каждый по той же схеме: `productId`, `amount`, `price`). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `comboInformation` (object, optional) – информация о включении позиции в комбо (ID спецификации, группы, и т.д.) при работе с `/api/1/combo` и `/api/1/combo/calculate`. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

#### 3.3.5. Оплаты `payments`

```json
"payments": [
  {
    "paymentTypeId": "string",
    "sum": 0,
    "isProcessedExternally": false,
    "paymentAdditionalData": "string"
  }
]
```

- `paymentTypeId` (string, required, uuid) – тип оплаты из `/api/1/payment_types` (наличные, карта, онлайн‑оплата и т.п.). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `sum` (number, required) – сумма оплаты.  
- `isProcessedExternally` (boolean, optional) – признак, что оплата уже проведена во внешней системе (например, онлайн‑эквайринг) и не должна проводиться кассой повторно. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `paymentAdditionalData` (string, optional) – дополнительные данные об оплате (ID транзакции эквайринга и т.п.). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

#### 3.3.6. Гости `guests`

```json
"guests": {
  "count": 1,
  "splitBetweenPersons": false
}
```

- `count` (integer, optional) – количество гостей (для зала или доставки, если важно).  
- `splitBetweenPersons` (boolean, optional) – использовать ли разнесение по гостям в чеке (зависит от фронта). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

***

## 4. Ответ

### 4.1. Успешный ответ `200 OK`

```json
{
  "correlationId": "string",
  "orderId": "string",
  "number": "string",
  "fullSum": 0,
  "creationStatus": "Success | InProgress | Failed"
}
```

- `correlationId` (string, required) – ID операции, который можно использовать в `/api/1/commands/status` для отслеживания обработки. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `orderId` (string, required, uuid) – внутренний ID созданного заказа в iiko.  
- `number` (string, optional) – номер заказа во фронте (отображается кассирам/курьерам).  
- `fullSum` (number, optional) – итоговая сумма заказа с учётом скидок, модификаторов и т.п.  
- `creationStatus` (string, optional) – итоговый статус создания (например, создан сразу либо отправлен на обработку). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

### 4.2. Ошибки

- `400 Bad Request` – неверные или неполные данные запроса (например, несуществующий `organizationId`, пустой список `items`, неверный `orderTypeId`). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `401 Unauthorized` – невалидный или отсутствующий токен `Authorization`. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `408 Request Timeout` – превышен таймаут. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- `500 Server Error` – внутренняя ошибка сервера iiko. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

Формат тела ошибки соответствует общему формату ошибок iikoCloud: код, описание, возможно – список проблемных полей (уточнить по вашей инсталляции/логам). [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

***

## 5. Требуемые предварительные данные

Перед использованием метода необходимо: [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

- Получить токен через `/api/1/access_token` по `apiLogin`. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- Получить список организаций `/api/1/organizations` и сохранить `organizationId` для работы. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- Получить терминальные группы `/api/1/terminal_groups` для нужной организации и выбрать `terminalGroupId`. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- Получить типы заказов `/api/1/deliveries/order_types` для выбора `orderTypeId`. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- Получить номенклатуру `/api/1/nomenclature` для `productId`, `sizeId`. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- Получить типы оплат `/api/1/payment_types` для `paymentTypeId`. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)
- При использовании доставки по зонам/ограничениям – ориентироваться на разделы `Addresses` и `Delivery restrictions`. [api-ru.iiko](https://api-ru.iiko.services/docs#tag/Drafts/paths/~1api~11~1deliveries~1drafts~1unlock/post)

***

Если хочешь, могу отдельно сделать JSON‑пример «боевого» заказа под ваш конкретный кейс (доставка/самовывоз, нал/онлайн‑оплата и т.п.), чтобы можно было сразу дать интеграторам.