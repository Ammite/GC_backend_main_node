from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, JSON, Date
from sqlalchemy.orm import relationship
from datetime import datetime

from database.database import Base


class Sales(Base):
    __tablename__ = "sales"

    # Основные поля
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    item_sale_event_id = Column(String(50), nullable=True)  # ItemSaleEvent.Id
    
    # Организация и подразделения
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    organization = relationship("Organization", back_populates="sales")
    
    department = Column(String(255), nullable=True)  # Department
    department_code = Column(String(50), nullable=True)  # Department.Code
    department_id = Column(String(50), nullable=True)  # Department.Id
    department_category1 = Column(String(100), nullable=True)  # Department.Category1
    department_category2 = Column(String(100), nullable=True)  # Department.Category2
    department_category3 = Column(String(100), nullable=True)  # Department.Category3
    department_category4 = Column(String(100), nullable=True)  # Department.Category4
    department_category5 = Column(String(100), nullable=True)  # Department.Category5
    
    # Концепция
    conception = Column(String(255), nullable=True)  # Conception
    conception_code = Column(String(50), nullable=True)  # Conception.Code
    
    # Заказ
    order_id = Column(String(50), nullable=True)  # UniqOrderId.Id
    order_num = Column(Integer, nullable=True)  # OrderNum
    order_items = Column(Integer, nullable=True)  # OrderItems
    order_type = Column(String(50), nullable=True)  # OrderType
    order_type_id = Column(String(50), nullable=True)  # OrderType.Id
    order_service_type = Column(String(50), nullable=True)  # OrderServiceType
    order_comment = Column(Text, nullable=True)  # OrderComment
    order_deleted = Column(String(50), nullable=True)  # OrderDeleted
    
    # Время заказа
    open_time = Column(DateTime, nullable=True)  # OpenTime
    close_time = Column(DateTime, nullable=True)  # CloseTime
    precheque_time = Column(DateTime, nullable=True)  # PrechequeTime
    open_date_typed = Column(Date, nullable=True)  # OpenDate.Typed
    
    # Временные группировки
    year_open = Column(String(50), nullable=True)  # YearOpen
    quarter_open = Column(String(50), nullable=True)  # QuarterOpen
    month_open = Column(String(50), nullable=True)  # Mounth
    week_in_year_open = Column(String(50), nullable=True)  # WeekInYearOpen
    week_in_month_open = Column(String(50), nullable=True)  # WeekInMonthOpen
    day_of_week_open = Column(String(50), nullable=True)  # DayOfWeekOpen
    hour_open = Column(String(50), nullable=True)  # HourOpen
    hour_close = Column(String(50), nullable=True)  # HourClose
    
    # Блюдо/товар
    dish_id = Column(String(50), nullable=True)  # DishId
    dish_name = Column(String(255), nullable=True)  # DishName
    dish_code = Column(String(50), nullable=True)  # DishCode
    dish_code_quick = Column(String(50), nullable=True)  # DishCode.Quick
    dish_foreign_name = Column(String(255), nullable=True)  # DishForeignName
    dish_full_name = Column(String(255), nullable=True)  # DishFullName
    dish_type = Column(String(50), nullable=True)  # DishType
    dish_measure_unit = Column(String(50), nullable=True)  # DishMeasureUnit
    dish_amount_int = Column(Integer, nullable=True)  # DishAmountInt
    dish_amount_int_per_order = Column(Integer, nullable=True)  # DishAmountInt.PerOrder
    
    # Категория блюда
    dish_category = Column(String(255), nullable=True)  # DishCategory
    dish_category_id = Column(String(50), nullable=True)  # DishCategory.Id
    dish_category_accounting = Column(String(100), nullable=True)  # DishCategory.Accounting
    dish_category_accounting_id = Column(String(50), nullable=True)  # DishCategory.Accounting.Id
    
    # Группа блюда
    dish_group = Column(String(255), nullable=True)  # DishGroup
    dish_group_id = Column(String(50), nullable=True)  # DishGroup.Id
    dish_group_num = Column(String(50), nullable=True)  # DishGroup.Num
    dish_group_hierarchy = Column(Text, nullable=True)  # DishGroup.Hierarchy
    dish_group_top_parent = Column(String(255), nullable=True)  # DishGroup.TopParent
    dish_group_second_parent = Column(String(255), nullable=True)  # DishGroup.SecondParent
    dish_group_third_parent = Column(String(255), nullable=True)  # DishGroup.ThirdParent
    
    # Теги блюда
    dish_tag_id = Column(String(50), nullable=True)  # DishTag.Id
    dish_tag_name = Column(String(255), nullable=True)  # DishTag.Name
    dish_tags_ids_combo = Column(Text, nullable=True)  # DishTags.IdsCombo
    dish_tags_names_combo = Column(Text, nullable=True)  # DishTags.NamesCombo
    
    # Налоговая категория
    dish_tax_category_id = Column(String(50), nullable=True)  # DishTaxCategory.Id
    dish_tax_category_name = Column(String(255), nullable=True)  # DishTaxCategory.Name
    
    # Размер блюда
    dish_size_id = Column(String(50), nullable=True)  # DishSize.Id
    dish_size_name = Column(String(255), nullable=True)  # DishSize.Name
    dish_size_short_name = Column(String(255), nullable=True)  # DishSize.ShortName
    dish_size_priority = Column(Integer, nullable=True)  # DishSize.Priority
    dish_size_scale_id = Column(String(50), nullable=True)  # DishSize.Scale.Id
    dish_size_scale_name = Column(String(255), nullable=True)  # DishSize.Scale.Name
    
    # Финансовые поля
    dish_sum_int = Column(Numeric(15, 2), nullable=True)  # DishSumInt
    dish_sum_int_average_price_with_vat = Column(Numeric(15, 2), nullable=True)  # DishSumInt.averagePriceWithVAT
    dish_discount_sum_int = Column(Numeric(15, 2), nullable=True)  # DishDiscountSumInt
    dish_discount_sum_int_average = Column(Numeric(15, 2), nullable=True)  # DishDiscountSumInt.average
    dish_discount_sum_int_average_by_guest = Column(Numeric(15, 2), nullable=True)  # DishDiscountSumInt.averageByGuest
    dish_discount_sum_int_average_price = Column(Numeric(15, 2), nullable=True)  # DishDiscountSumInt.averagePrice
    dish_discount_sum_int_average_price_with_vat = Column(Numeric(15, 2), nullable=True)  # DishDiscountSumInt.averagePriceWithVAT
    dish_discount_sum_int_average_without_vat = Column(Numeric(15, 2), nullable=True)  # DishDiscountSumInt.averageWithoutVAT
    dish_discount_sum_int_without_vat = Column(Numeric(15, 2), nullable=True)  # DishDiscountSumInt.withoutVAT
    dish_return_sum = Column(Numeric(15, 2), nullable=True)  # DishReturnSum
    dish_return_sum_without_vat = Column(Numeric(15, 2), nullable=True)  # DishReturnSum.withoutVAT
    
    # Скидки и наценки
    discount_percent = Column(Numeric(5, 2), nullable=True)  # DiscountPercent
    discount_sum = Column(Numeric(15, 2), nullable=True)  # DiscountSum
    discount_without_vat = Column(Numeric(15, 2), nullable=True)  # discountWithoutVAT
    increase_percent = Column(Numeric(5, 2), nullable=True)  # IncreasePercent
    increase_sum = Column(Numeric(15, 2), nullable=True)  # IncreaseSum
    full_sum = Column(Numeric(15, 2), nullable=True)  # fullSum
    sum_after_discount_without_vat = Column(Numeric(15, 2), nullable=True)  # sumAfterDiscountWithoutVAT
    
    # НДС
    vat_percent = Column(Numeric(5, 2), nullable=True)  # VAT.Percent
    vat_sum = Column(Numeric(15, 2), nullable=True)  # VAT.Sum
    
    # Сессия и касса
    session_id = Column(String(50), nullable=True)  # SessionID
    session_num = Column(Integer, nullable=True)  # SessionNum
    cash_register_name = Column(String(255), nullable=True)  # CashRegisterName
    cash_register_name_serial_number = Column(String(50), nullable=True)  # CashRegisterName.CashRegisterSerialNumber
    cash_register_name_number = Column(Integer, nullable=True)  # CashRegisterName.Number
    
    # Ресторанная секция
    restaurant_section = Column(String(255), nullable=True)  # RestaurantSection
    restaurant_section_id = Column(String(50), nullable=True)  # RestaurantSection.Id
    
    # Стол
    table_num = Column(Integer, nullable=True)  # TableNum
    
    # Гости
    guest_num = Column(Integer, nullable=True)  # GuestNum
    guest_num_avg = Column(Numeric(10, 2), nullable=True)  # GuestNum.Avg
    
    # Официант
    waiter_name = Column(String(255), nullable=True)  # WaiterName
    waiter_name_id = Column(String(50), nullable=True)  # WaiterName.ID
    order_waiter_id = Column(String(50), nullable=True)  # OrderWaiter.Id
    order_waiter_name = Column(String(255), nullable=True)  # OrderWaiter.Name
    waiter_team_id = Column(String(50), nullable=True)  # WaiterTeam.Id
    waiter_team_name = Column(String(255), nullable=True)  # WaiterTeam.Name
    
    # Кассир
    cashier = Column(String(255), nullable=True)  # Cashier
    cashier_code = Column(String(50), nullable=True)  # Cashier.Code
    cashier_id = Column(String(50), nullable=True)  # Cashier.Id
    
    # Пользователь авторизации
    auth_user = Column(String(255), nullable=True)  # AuthUser
    auth_user_id = Column(String(50), nullable=True)  # AuthUser.Id
    
    # Платежи
    pay_types = Column(String(255), nullable=True)  # PayTypes
    pay_types_combo = Column(String(255), nullable=True)  # PayTypes.Combo
    pay_types_guid = Column(String(50), nullable=True)  # PayTypes.GUID
    pay_types_group = Column(String(50), nullable=True)  # PayTypes.Group
    pay_types_is_print_cheque = Column(String(50), nullable=True)  # PayTypes.IsPrintCheque
    pay_types_voucher_num = Column(Integer, nullable=True)  # PayTypes.VoucherNum
    
    # Карты
    card = Column(String(255), nullable=True)  # Card
    card_number = Column(String(255), nullable=True)  # CardNumber
    card_owner = Column(String(255), nullable=True)  # CardOwner
    card_type = Column(String(50), nullable=True)  # CardType
    card_type_name = Column(String(255), nullable=True)  # CardTypeName
    
    # Бонусы
    bonus_card_number = Column(String(50), nullable=True)  # Bonus.CardNumber
    bonus_sum = Column(Numeric(15, 2), nullable=True)  # Bonus.Sum
    bonus_type = Column(String(50), nullable=True)  # Bonus.Type
    
    # Фискальный чек
    fiscal_cheque_number = Column(String(255), nullable=True)  # FiscalChequeNumber может приходить как "19758, 23"
    
    # Валюты
    currencies_currency = Column(String(50), nullable=True)  # Currencies.Currency
    currencies_currency_rate = Column(Numeric(20, 4), nullable=True)  # Currencies.CurrencyRate (увеличено с 10 до 20)
    currencies_sum_in_currency = Column(Numeric(15, 2), nullable=True)  # Currencies.SumInCurrency
    
    # Готовка
    cooking_place = Column(String(255), nullable=True)  # CookingPlace
    cooking_place_id = Column(String(50), nullable=True)  # CookingPlace.Id
    cooking_place_type = Column(String(255), nullable=True)  # CookingPlaceType
    
    # Время готовки
    cooking_cooking_duration_avg = Column(Integer, nullable=True)  # Cooking.CookingDuration.Avg
    cooking_cooking1_duration_avg = Column(Integer, nullable=True)  # Cooking.Cooking1Duration.Avg
    cooking_cooking2_duration_avg = Column(Integer, nullable=True)  # Cooking.Cooking2Duration.Avg
    cooking_cooking3_duration_avg = Column(Integer, nullable=True)  # Cooking.Cooking3Duration.Avg
    cooking_cooking4_duration_avg = Column(Integer, nullable=True)  # Cooking.Cooking4Duration.Avg
    cooking_cooking_late_time_avg = Column(Integer, nullable=True)  # Cooking.CookingLateTime.Avg
    cooking_feed_late_time_avg = Column(Integer, nullable=True)  # Cooking.FeedLateTime.Avg
    cooking_guest_wait_time_avg = Column(Integer, nullable=True)  # Cooking.GuestWaitTime.Avg
    cooking_kitchen_time_avg = Column(Integer, nullable=True)  # Cooking.KitchenTime.Avg
    cooking_serve_number = Column(Integer, nullable=True)  # Cooking.ServeNumber
    cooking_serve_time_avg = Column(Integer, nullable=True)  # Cooking.ServeTime.Avg
    cooking_start_delay_time_avg = Column(Integer, nullable=True)  # Cooking.StartDelayTime.Avg
    
    # Время заказа
    order_time_average_order_time = Column(Integer, nullable=True)  # OrderTime.AverageOrderTime
    order_time_average_precheque_time = Column(Integer, nullable=True)  # OrderTime.AveragePrechequeTime
    order_time_order_length = Column(Integer, nullable=True)  # OrderTime.OrderLength
    order_time_order_length_sum = Column(Integer, nullable=True)  # OrderTime.OrderLengthSum
    order_time_precheque_length = Column(Integer, nullable=True)  # OrderTime.PrechequeLength
    
    # Доставка
    delivery_is_delivery = Column(String(50), nullable=True)  # Delivery.IsDelivery
    delivery_id = Column(String(50), nullable=True)  # Delivery.Id
    delivery_number = Column(String(50), nullable=True)  # Delivery.Number
    delivery_address = Column(Text, nullable=True)  # Delivery.Address
    delivery_city = Column(String(255), nullable=True)  # Delivery.City
    delivery_street = Column(String(255), nullable=True)  # Delivery.Street
    delivery_index = Column(String(20), nullable=True)  # Delivery.Index
    delivery_region = Column(String(255), nullable=True)  # Delivery.Region
    delivery_zone = Column(String(255), nullable=True)  # Delivery.Zone
    delivery_phone = Column(String(50), nullable=True)  # Delivery.Phone
    delivery_email = Column(String(255), nullable=True)  # Delivery.Email
    delivery_courier = Column(String(255), nullable=True)  # Delivery.Courier
    delivery_courier_id = Column(String(50), nullable=True)  # Delivery.Courier.Id
    delivery_operator = Column(String(255), nullable=True)  # Delivery.DeliveryOperator
    delivery_operator_id = Column(String(50), nullable=True)  # Delivery.DeliveryOperator.Id
    delivery_service_type = Column(String(50), nullable=True)  # Delivery.ServiceType
    delivery_expected_time = Column(DateTime, nullable=True)  # Delivery.ExpectedTime
    delivery_actual_time = Column(DateTime, nullable=True)  # Delivery.ActualTime
    delivery_close_time = Column(DateTime, nullable=True)  # Delivery.CloseTime
    delivery_cooking_finish_time = Column(DateTime, nullable=True)  # Delivery.CookingFinishTime
    delivery_send_time = Column(DateTime, nullable=True)  # Delivery.SendTime
    delivery_bill_time = Column(DateTime, nullable=True)  # Delivery.BillTime
    delivery_print_time = Column(DateTime, nullable=True)  # Delivery.PrintTime
    delivery_delay = Column(Integer, nullable=True)  # Delivery.Delay
    delivery_delay_avg = Column(Integer, nullable=True)  # Delivery.DelayAvg
    delivery_way_duration = Column(Integer, nullable=True)  # Delivery.WayDuration
    delivery_way_duration_avg = Column(Integer, nullable=True)  # Delivery.WayDurationAvg
    delivery_way_duration_sum = Column(Integer, nullable=True)  # Delivery.WayDurationSum
    delivery_cooking_to_send_duration = Column(Integer, nullable=True)  # Delivery.CookingToSendDuration
    delivery_diff_between_actual_delivery_time_and_predicted_delivery_time = Column(Integer, nullable=True)  # Delivery.DiffBetweenActualDeliveryTimeAndPredictedDeliveryTime
    delivery_predicted_cooking_complete_time = Column(DateTime, nullable=True)  # Delivery.PredictedCookingCompleteTime
    delivery_predicted_delivery_time = Column(DateTime, nullable=True)  # Delivery.PredictedDeliveryTime
    delivery_customer_name = Column(String(255), nullable=True)  # Delivery.CustomerName
    delivery_customer_phone = Column(String(50), nullable=True)  # Delivery.CustomerPhone
    delivery_customer_email = Column(String(255), nullable=True)  # Delivery.CustomerEmail
    delivery_customer_card_number = Column(String(50), nullable=True)  # Delivery.CustomerCardNumber
    delivery_customer_card_type = Column(String(50), nullable=True)  # Delivery.CustomerCardType
    delivery_customer_comment = Column(Text, nullable=True)  # Delivery.CustomerComment
    delivery_customer_created_date_typed = Column(DateTime, nullable=True)  # Delivery.CustomerCreatedDateTyped
    delivery_customer_marketing_source = Column(String(255), nullable=True)  # Delivery.CustomerMarketingSource
    delivery_customer_opinion_comment = Column(Text, nullable=True)  # Delivery.CustomerOpinionComment
    delivery_delivery_comment = Column(Text, nullable=True)  # Delivery.DeliveryComment
    delivery_cancel_cause = Column(String(255), nullable=True)  # Delivery.CancelCause
    delivery_cancel_comment = Column(Text, nullable=True)  # Delivery.CancelComment
    delivery_marketing_source = Column(String(255), nullable=True)  # Delivery.MarketingSource
    delivery_external_cartography_id = Column(String(50), nullable=True)  # Delivery.ExternalCartographyId
    delivery_source_key = Column(String(50), nullable=True)  # Delivery.SourceKey
    delivery_ecs_service = Column(String(255), nullable=True)  # Delivery.EcsService
    
    # Оценки доставки
    delivery_avg_mark = Column(Numeric(5, 2), nullable=True)  # Delivery.AvgMark
    delivery_avg_food_mark = Column(Numeric(5, 2), nullable=True)  # Delivery.AvgFoodMark
    delivery_avg_courier_mark = Column(Numeric(5, 2), nullable=True)  # Delivery.AvgCourierMark
    delivery_avg_operator_mark = Column(Numeric(5, 2), nullable=True)  # Delivery.AvgOperatorMark
    delivery_aggregated_avg_mark = Column(Numeric(5, 2), nullable=True)  # Delivery.AggregatedAvgMark
    delivery_aggregated_avg_food_mark = Column(Numeric(5, 2), nullable=True)  # Delivery.AggregatedAvgFoodMark
    delivery_aggregated_avg_courier_mark = Column(Numeric(5, 2), nullable=True)  # Delivery.AggregatedAvgCourierMark
    delivery_aggregated_avg_operator_mark = Column(Numeric(5, 2), nullable=True)  # Delivery.AggregatedAvgOperatorMark
    
    # Скидки заказа
    order_discount_guest_card = Column(String(255), nullable=True)  # OrderDiscount.GuestCard
    order_discount_type = Column(String(255), nullable=True)  # OrderDiscount.Type
    order_discount_type_ids = Column(String(255), nullable=True)  # OrderDiscount.Type.IDs
    
    # Наценки заказа
    order_increase_type = Column(String(255), nullable=True)  # OrderIncrease.Type
    order_increase_type_ids = Column(String(50), nullable=True)  # OrderIncrease.Type.IDs
    
    # Событие продажи товара
    item_sale_event_discount_type = Column(String(255), nullable=True)  # ItemSaleEventDiscountType
    item_sale_event_discount_type_combo_amount = Column(Integer, nullable=True)  # ItemSaleEventDiscountType.ComboAmount
    item_sale_event_discount_type_discount_amount = Column(Integer, nullable=True)  # ItemSaleEventDiscountType.DiscountAmount
    
    # Платежная транзакция
    payment_transaction_id = Column(String(50), nullable=True)  # PaymentTransaction.Id
    payment_transaction_ids = Column(String(255), nullable=True)  # PaymentTransaction.Ids
    
    # Тип операции
    operation_type = Column(String(50), nullable=True)  # OperationType
    
    # Контрагент
    counteragent_name = Column(String(255), nullable=True)  # Counteragent.Name
    
    # Кредитный пользователь
    credit_user = Column(String(255), nullable=True)  # CreditUser
    credit_user_company = Column(String(255), nullable=True)  # CreditUser.Company
    
    # Ценовая категория
    price_category = Column(String(255), nullable=True)  # PriceCategory
    price_category_card = Column(String(255), nullable=True)  # PriceCategoryCard
    price_category_discount_card_owner = Column(String(255), nullable=True)  # PriceCategoryDiscountCardOwner
    price_category_user_card_owner = Column(String(255), nullable=True)  # PriceCategoryUserCardOwner
    
    # Стоимость продукта
    product_cost_base_mark_up = Column(Numeric(20, 4), nullable=True)  # ProductCostBase.MarkUp (увеличено с 10 до 20)
    product_cost_base_one_item = Column(Numeric(15, 2), nullable=True)  # ProductCostBase.OneItem
    product_cost_base_percent = Column(Numeric(20, 4), nullable=True)  # ProductCostBase.Percent (увеличено с 10 до 20)
    product_cost_base_percent_without_vat = Column(Numeric(20, 4), nullable=True)  # ProductCostBase.PercentWithoutVAT (увеличено с 10 до 20)
    product_cost_base_product_cost = Column(Numeric(15, 2), nullable=True)  # ProductCostBase.ProductCost
    product_cost_base_profit = Column(Numeric(15, 2), nullable=True)  # ProductCostBase.Profit
    
    # Стимулирующая сумма
    incentive_sum_base_sum = Column(Numeric(15, 2), nullable=True)  # IncentiveSumBase.Sum
    
    # Процент от итога
    percent_of_summary_by_col = Column(Numeric(20, 4), nullable=True)  # PercentOfSummary.ByCol (увеличено с 10 до 20)
    percent_of_summary_by_row = Column(Numeric(20, 4), nullable=True)  # PercentOfSummary.ByRow (увеличено с 10 до 20)
    
    # Продано с блюдом
    sold_with_dish = Column(String(255), nullable=True)  # SoldWithDish
    sold_with_dish_id = Column(String(50), nullable=True)  # SoldWithDish.Id
    sold_with_item_id = Column(String(50), nullable=True)  # SoldWithItem.Id
    
    # Склад
    store_id = Column(String(50), nullable=True)  # Store.Id
    store_name = Column(String(255), nullable=True)  # Store.Name
    store_to = Column(String(255), nullable=True)  # StoreTo
    
    # Ресторанная группа
    restoraunt_group = Column(String(255), nullable=True)  # RestorauntGroup
    restoraunt_group_id = Column(String(50), nullable=True)  # RestorauntGroup.Id
    
    # Юридическое лицо
    jur_name = Column(String(255), nullable=True)  # JurName
    
    # Внешний номер
    external_number = Column(String(50), nullable=True)  # ExternalNumber
    
    # Происхождение
    origin_name = Column(String(255), nullable=True)  # OriginName
    
    # Тип удаления
    removal_type = Column(String(50), nullable=True)  # RemovalType
    
    # Списание
    writeoff_reason = Column(String(255), nullable=True)  # WriteoffReason
    writeoff_user = Column(String(255), nullable=True)  # WriteoffUser
    
    # Статусы
    banquet = Column(String(50), nullable=True)  # Banquet
    storned = Column(String(50), nullable=True)  # Storned
    deleted_with_writeoff = Column(String(50), nullable=True)  # DeletedWithWriteoff
    deletion_comment = Column(Text, nullable=True)  # DeletionComment
    
    # Тип безналичного платежа
    non_cash_payment_type = Column(String(255), nullable=True)  # NonCashPaymentType
    non_cash_payment_type_document_type = Column(String(50), nullable=True)  # NonCashPaymentType.DocumentType
    
    # Расположение наличных
    cash_location = Column(String(255), nullable=True)  # CashLocation
    
    # Время печати блюда
    dish_service_print_time = Column(DateTime, nullable=True)  # DishServicePrintTime
    dish_service_print_time_max = Column(DateTime, nullable=True)  # DishServicePrintTime.Max
    dish_service_print_time_open_to_last_print_duration = Column(Integer, nullable=True)  # DishServicePrintTime.OpenToLastPrintDuration
    
    # Временные группировки по минутам
    open_time_minutes15 = Column(String(50), nullable=True)  # OpenTime.Minutes15
    close_time_minutes15 = Column(String(50), nullable=True)  # CloseTime.Minutes15
    
    # Внешние данные
    public_external_data = Column(Text, nullable=True)  # PublicExternalData
    public_external_data_xml = Column(Text, nullable=True)  # PublicExternalData.Xml
    
    # Комиссия
    commission = Column(Numeric(5, 2), nullable=True)  # Комиссия в процентах
    
    # Системные поля
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = Column(Boolean, default=True)
