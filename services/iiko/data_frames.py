# Оптимизированные OLAP data frames для iiko API
#
# Убраны:
# - Иерархии-дубли (Product.TopParent/SecondParent/ThirdParent и т.д.) — вычисляются в парсере из *.Hierarchy
# - Производные от даты (DateTime.Year/Quarter/Month/...) — вычисляются в парсере из DateTime.Typed
# - Неиспользуемые поля: алкоголь, Department.Category1-5, Contr-Product детали, теги
# - В sales: Delivery.* (кроме IsDelivery), Cooking.*, OrderTime.*, DishSize детали, PriceCategory, PublicExternalData

# ─── Общий список полей для TRANSACTIONS (используется в обоих фреймах) ───

_transactions_group_by_row_fields = [
    # Идентификаторы
    "Session.GroupId",
    "OrderId",
    "Product.Category.Id",
    "Counteragent.Id",
    "Account.Id",
    "Product.Id",
    "Product.Num",
    "Product.AccountingCategory",

    # Сессии и группы
    "Session.Group",
    "Contr-Account.Group",
    "Account.Group",

    # Даты (основные — остальные вычисляются в парсере)
    "DateTime.Typed",
    "DateSecondary.DateTimeTyped",
    "DateSecondary.DateTyped",
    "DateTime.DateTyped",

    # Транзакция
    "TransactionSide",
    "TransactionType",
    "TransactionType.Code",

    # Номенклатура
    "Product.MeasureUnit",
    "Product.Hierarchy",       # → парсер вычисляет TopParent/SecondParent/ThirdParent
    "Product.Category",
    "Product.CookingPlaceType",
    "Product.Type",
    "Product.Name",

    # Счета
    "Account.AccountHierarchyFull",  # → парсер вычисляет Top/Second/Third
    "Account.Name",
    "Account.Code",
    "Account.Type",
    "Account.StoreOrAccount",
    "Account.CounteragentType",
    "Account.IsCashFlowAccount",

    # Корреспондентские счета
    "Contr-Account.Name",
    "Contr-Account.Code",
    "Contr-Account.Type",

    # Корреспондент-продукт (только иерархия)
    "Contr-Product.Hierarchy",  # → парсер вычисляет TopParent/SecondParent/ThirdParent

    # Движение денежных средств
    "CashFlowCategory",
    "CashFlowCategory.Type",
    "CashFlowCategory.Hierarchy",  # → парсер вычисляет HierarchyLevel1/2/3

    # Контрагенты
    "Counteragent.Name",

    # Организация
    "Department",
    "Department.Code",
    "Department.JurPerson",

    # Сессии и кассы
    "Session.CashRegister",
    "Session.RestaurantSection",

    # Концепции
    "Conception",
    "Conception.Code",

    # Склады
    "Store",

    # Документы
    "Document",
    "OrderNum",

    # Комментарии
    "Comment",
]

_transactions_aggregate_fields = [
    "Amount.Out",
    "Amount.In",
    "Sum.Outgoing",
    "Sum.Incoming",
    "Sum.ResignedSum",
]


iiko_transactions_data_frame = {
    "reportType": "TRANSACTIONS",
    "groupByRowFields": _transactions_group_by_row_fields,
    "groupByColFields": [],
    "aggregateFields": _transactions_aggregate_fields,
    "filters": {
        "DateTime.DateTyped": {
            "filterType": "DateRange",
            "periodType": "CUSTOM",
            "from": "2025-09-29",
            "to": "2025-09-30",
            "includeLow": True,
            "includeHigh": False,
        }
    },
}

iiko_sales_data_frame = {
    "reportType": "SALES",
    "groupByRowFields": [
        # Идентификаторы (критично для уникальности строк)
        "ItemSaleEvent.Id",
        "AuthUser.Id",
        "DishId",
        "WaiterTeam.Id",
        "DishCategory.Accounting.Id",
        "RestorauntGroup.Id",
        "DishGroup.Id",
        "UniqOrderId.Id",
        "Cashier.Id",
        "SessionID",
        "DishCategory.Id",
        "CookingPlace.Id",
        "SoldWithDish.Id",
        "RestaurantSection.Id",
        "WaiterName.ID",
        "OrderWaiter.Id",
        "Department.Id",
        "SoldWithItem.Id",
        "PaymentTransaction.Id",
        "PaymentTransaction.Ids",
        "DishSize.Id",
        "Store.Id",
        "OrderType.Id",
        "PayTypes.GUID",
        "OrderIncrease.Type.IDs",
        "OrderDiscount.Type.IDs",

        # Текстовые/именные поля
        "AuthUser",
        "Banquet",
        "NonCashPaymentType",
        "DishName",
        "DeletedWithWriteoff",
        "WaiterTeam.Name",
        "DishCategory.Accounting",
        "Currencies.Currency",
        "ExternalNumber",
        "Storned",

        # Время (основные — остальные вычисляются в парсере из OpenTime/CloseTime)
        "CloseTime",
        "OpenTime",
        "PrechequeTime",
        "OpenDate.Typed",

        # Заказ
        "OrderDiscount.GuestCard",
        "OrderDeleted",
        "OrderComment",
        "Comment",
        "DeletionComment",
        "OrderNum",
        "OperationType",
        "OrderServiceType",

        # Ресторан
        "RestorauntGroup",
        "Department",
        "Department.Code",
        "RestaurantSection",
        "CashRegisterName",
        "CashRegisterName.Number",
        "CashRegisterName.CashRegisterSerialNumber",
        "SessionNum",
        "TableNum",
        "CashLocation",
        "JurName",
        "Conception",
        "Conception.Code",

        # Блюдо/товар
        "DishGroup",
        "DishGroup.Hierarchy",  # → парсер вычисляет TopParent/SecondParent/ThirdParent
        "DishGroup.Num",
        "DishMeasureUnit",
        "DishCode",
        "DishCode.Quick",
        "DishForeignName",
        "DishFullName",
        "DishType",
        "DishAmountInt",
        "DishCategory",
        "CookingPlace",
        "CookingPlaceType",

        # Доставка (только флаг)
        "Delivery.IsDelivery",

        # Платежи
        "PayTypes.Group",
        "PayTypes",
        "PayTypes.Combo",
        "PayTypes.IsPrintCheque",

        # Карты
        "Card",
        "CardOwner",
        "CardType",
        "CardTypeName",
        "CardNumber",
        "Bonus.CardNumber",
        "Bonus.Type",

        # Фискальный чек
        "FiscalChequeNumber",

        # Валюты
        "Currencies.CurrencyRate",

        # Налоги
        "VAT.Percent",

        # Другое
        "OriginName",
        "Counteragent.Name",
        "ItemSaleEventDiscountType",
        "NonCashPaymentType.DocumentType",
        "OrderType",
        "OrderIncrease.Type",
        "OrderDiscount.Type",
        "GuestNum",

        # Финансовое
        "DishReturnSum",
        "IncreaseSum",
        "IncreasePercent",
        "DiscountPercent",

        # Официант/кассир
        "WaiterName",
        "OrderWaiter.Name",
        "Cashier",
        "Cashier.Code",

        # Склад
        "Store.Name",
        "StoreTo",

        # Списание
        "WriteoffReason",
        "WriteoffUser",
        "RemovalType",

        # Продано с блюдом
        "SoldWithDish",

        # Печать
        "DishServicePrintTime",
    ],
    "groupByColFields": [],
    "aggregateFields": [
        # Количества
        "UniqOrderId.OrdersCount",
        "DishAmountInt",
        "GuestNum",
        "OrderItems",
        "OrderNum",
        "PayTypes.VoucherNum",
        "GuestNum.Avg",

        # Скидки и наценки
        "ItemSaleEventDiscountType.DiscountAmount",
        "ItemSaleEventDiscountType.ComboAmount",
        "IncreasePercent",
        "DiscountPercent",

        # НДС
        "VAT.Sum",
        "VAT.Percent",

        # Стоимость продукта
        "ProductCostBase.Profit",
        "ProductCostBase.MarkUp",
        "ProductCostBase.ProductCost",
        "ProductCostBase.PercentWithoutVAT",
        "ProductCostBase.OneItem",
        "ProductCostBase.Percent",

        # Стимулирующая сумма
        "IncentiveSumBase.Sum",

        # Суммы
        "fullSum",
        "DishSumInt",
        "DishSumInt.averagePriceWithVAT",
        "DishDiscountSumInt",
        "DishDiscountSumInt.withoutVAT",
        "DishDiscountSumInt.average",
        "DishDiscountSumInt.averageWithoutVAT",
        "DishDiscountSumInt.averagePriceWithVAT",
        "DishDiscountSumInt.averagePrice",
        "DishDiscountSumInt.averageByGuest",
        "DishReturnSum",
        "DishReturnSum.withoutVAT",
        "IncreaseSum",
        "DiscountSum",
        "discountWithoutVAT",
        "sumAfterDiscountWithoutVAT",
        "Bonus.Sum",
        "Currencies.SumInCurrency",
        "UniqOrderId",

        # Печать
        "DishServicePrintTime.Max",
        "DishServicePrintTime.OpenToLastPrintDuration",
    ],
    "filters": {
        "OpenDate.Typed": {
            "filterType": "DateRange",
            "periodType": "CUSTOM",
            "from": "2025-09-29",
            "to": "2025-09-30",
            "includeLow": True,
            "includeHigh": False,
        }
    },
}

iiko_transactions_by_modification_data_frame = {
    "reportType": "TRANSACTIONS",
    "groupByRowFields": _transactions_group_by_row_fields,
    "groupByColFields": [],
    "aggregateFields": _transactions_aggregate_fields,
    "filters": {
        "DateSecondary.DateTyped": {
            "filterType": "DateRange",
            "periodType": "CUSTOM",
            "from": "2025-09-29",
            "to": "2025-09-30",
            "includeLow": True,
            "includeHigh": False,
        },
        "DateTime.DateTyped": {
            "filterType": "DateRange",
            "periodType": "CUSTOM",
            "from": "2025-09-29",
            "to": "2025-09-30",
            "includeLow": True,
            "includeHigh": False,
        },
    },
}
