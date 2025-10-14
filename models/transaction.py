from sqlalchemy import Column, String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from database.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    # Основные поля
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=True)  # ID транзакции в iiko
    order_id = Column(String(50), nullable=True)  # OrderId
    order_num = Column(String(100), nullable=True)  # OrderNum
    document = Column(String(100), nullable=True)  # Document
    
    # Финансовые поля
    amount = Column(Numeric(15, 2), nullable=True)  # Amount
    sum_resigned = Column(Numeric(15, 2), nullable=True)  # Sum.ResignedSum
    sum_incoming = Column(Numeric(15, 2), nullable=True)  # Sum.Incoming
    sum_outgoing = Column(Numeric(15, 2), nullable=True)  # Sum.Outgoing
    sum_part_of_income = Column(Numeric(5, 2), nullable=True)  # Sum.PartOfIncome (процент)
    sum_part_of_total_income = Column(Numeric(5, 2), nullable=True)  # Sum.PartOfTotalIncome (процент)
    
    # Остатки
    start_balance_money = Column(Numeric(15, 2), nullable=True)  # StartBalance.Money
    final_balance_money = Column(Numeric(15, 2), nullable=True)  # FinalBalance.Money
    start_balance_amount = Column(Numeric(15, 2), nullable=True)  # StartBalance.Amount
    final_balance_amount = Column(Numeric(15, 2), nullable=True)  # FinalBalance.Amount
    
    # Приход/расход
    amount_in = Column(Numeric(15, 2), nullable=True)  # Amount.In
    amount_out = Column(Numeric(15, 2), nullable=True)  # Amount.Out
    contr_amount = Column(Numeric(15, 2), nullable=True)  # Contr-Amount
    
    # Типы и категории
    transaction_type = Column(String(100), nullable=True)  # TransactionType
    transaction_type_code = Column(String(50), nullable=True)  # TransactionType.Code
    transaction_side = Column(String(20), nullable=True)  # TransactionSide (Дебет/Кредит)
    
    # Номенклатура
    product_id = Column(String(50), nullable=True)  # Product.Id
    product_name = Column(String(255), nullable=True)  # Product.Name
    product_num = Column(String(100), nullable=True)  # Product.Num
    product_category_id = Column(String(50), nullable=True)  # Product.Category.Id
    product_category = Column(String(255), nullable=True)  # Product.Category
    product_type = Column(String(50), nullable=True)  # Product.Type
    product_measure_unit = Column(String(50), nullable=True)  # Product.MeasureUnit
    product_avg_sum = Column(Numeric(15, 2), nullable=True)  # Product.AvgSum
    product_cooking_place_type = Column(String(100), nullable=True)  # Product.CookingPlaceType
    product_accounting_category = Column(String(100), nullable=True)  # Product.AccountingCategory
    
    # Иерархия номенклатуры
    product_top_parent = Column(String(255), nullable=True)  # Product.TopParent
    product_second_parent = Column(String(255), nullable=True)  # Product.SecondParent
    product_third_parent = Column(String(255), nullable=True)  # Product.ThirdParent
    product_hierarchy = Column(Text, nullable=True)  # Product.Hierarchy
    
    # Пользовательские свойства номенклатуры
    product_tag_id = Column(String(50), nullable=True)  # Product.Tag.Id
    product_tag_name = Column(String(255), nullable=True)  # Product.Tag.Name
    product_tags_ids_combo = Column(Text, nullable=True)  # Product.Tags.IdsCombo
    product_tags_names_combo = Column(Text, nullable=True)  # Product.Tags.NamesCombo
    
    # Алкогольная продукция
    product_alcohol_class = Column(String(100), nullable=True)  # Product.AlcoholClass
    product_alcohol_class_code = Column(String(50), nullable=True)  # Product.AlcoholClass.Code
    product_alcohol_class_group = Column(String(100), nullable=True)  # Product.AlcoholClass.Group
    product_alcohol_class_type = Column(String(50), nullable=True)  # Product.AlcoholClass.Type
    
    # Корреспондент (контрагент)
    contr_product_id = Column(String(50), nullable=True)  # Contr-Product.Id
    contr_product_name = Column(String(255), nullable=True)  # Contr-Product.Name
    contr_product_num = Column(String(100), nullable=True)  # Contr-Product.Num
    contr_product_category_id = Column(String(50), nullable=True)  # Contr-Product.Category.Id
    contr_product_category = Column(String(255), nullable=True)  # Contr-Product.Category
    contr_product_type = Column(String(50), nullable=True)  # Contr-Product.Type
    contr_product_measure_unit = Column(String(50), nullable=True)  # Contr-Product.MeasureUnit
    contr_product_accounting_category = Column(String(100), nullable=True)  # Contr-Product.AccountingCategory
    
    # Иерархия корреспондента
    contr_product_top_parent = Column(String(255), nullable=True)  # Contr-Product.TopParent
    contr_product_second_parent = Column(String(255), nullable=True)  # Contr-Product.SecondParent
    contr_product_third_parent = Column(String(255), nullable=True)  # Contr-Product.ThirdParent
    contr_product_hierarchy = Column(Text, nullable=True)  # Contr-Product.Hierarchy
    
    # Пользовательские свойства корреспондента
    contr_product_tags_ids_combo = Column(Text, nullable=True)  # Contr-Product.Tags.IdsCombo
    contr_product_tags_names_combo = Column(Text, nullable=True)  # Contr-Product.Tags.NamesCombo
    
    # Алкогольная продукция корреспондента
    contr_product_alcohol_class = Column(String(100), nullable=True)  # Contr-Product.AlcoholClass
    contr_product_alcohol_class_code = Column(String(50), nullable=True)  # Contr-Product.AlcoholClass.Code
    contr_product_alcohol_class_group = Column(String(100), nullable=True)  # Contr-Product.AlcoholClass.Group
    contr_product_alcohol_class_type = Column(String(50), nullable=True)  # Contr-Product.AlcoholClass.Type
    contr_product_cooking_place_type = Column(String(100), nullable=True)  # Contr-Product.CookingPlaceType
    
    # Счета
    account_id = Column(String(50), nullable=True)  # Account.Id
    account_name = Column(String(255), nullable=True)  # Account.Name
    account_code = Column(String(50), nullable=True)  # Account.Code
    account_type = Column(String(50), nullable=True)  # Account.Type
    account_group = Column(String(50), nullable=True)  # Account.Group
    account_store_or_account = Column(String(50), nullable=True)  # Account.StoreOrAccount
    account_counteragent_type = Column(String(50), nullable=True)  # Account.CounteragentType
    account_is_cash_flow_account = Column(String(50), nullable=True)  # Account.IsCashFlowAccount
    
    # Иерархия счетов
    account_hierarchy_top = Column(String(255), nullable=True)  # Account.AccountHierarchyTop
    account_hierarchy_second = Column(String(255), nullable=True)  # Account.AccountHierarchySecond
    account_hierarchy_third = Column(String(255), nullable=True)  # Account.AccountHierarchyThird
    account_hierarchy_full = Column(Text, nullable=True)  # Account.AccountHierarchyFull
    
    # Корреспондентские счета
    contr_account_name = Column(String(255), nullable=True)  # Contr-Account.Name
    contr_account_code = Column(String(50), nullable=True)  # Contr-Account.Code
    contr_account_type = Column(String(50), nullable=True)  # Contr-Account.Type
    contr_account_group = Column(String(50), nullable=True)  # Contr-Account.Group
    
    # Контрагенты
    counteragent_id = Column(String(50), nullable=True)  # Counteragent.Id
    counteragent_name = Column(String(255), nullable=True)  # Counteragent.Name
    
    # Организация и подразделения
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    organization = relationship("Organization", back_populates="transactions")
    
    department = Column(String(255), nullable=True)  # Department
    department_code = Column(String(50), nullable=True)  # Department.Code
    department_jur_person = Column(String(255), nullable=True)  # Department.JurPerson
    department_category1 = Column(String(100), nullable=True)  # Department.Category1
    department_category2 = Column(String(100), nullable=True)  # Department.Category2
    department_category3 = Column(String(100), nullable=True)  # Department.Category3
    department_category4 = Column(String(100), nullable=True)  # Department.Category4
    department_category5 = Column(String(100), nullable=True)  # Department.Category5
    
    # Сессии и кассы
    session_group_id = Column(String(50), nullable=True)  # Session.GroupId
    session_group = Column(String(255), nullable=True)  # Session.Group
    session_cash_register = Column(String(255), nullable=True)  # Session.CashRegister
    session_restaurant_section = Column(String(255), nullable=True)  # Session.RestaurantSection
    
    # Концепции
    conception = Column(String(255), nullable=True)  # Conception
    conception_code = Column(String(50), nullable=True)  # Conception.Code
    
    # Склады
    store = Column(String(255), nullable=True)  # Store
    
    # Движение денежных средств
    cash_flow_category = Column(String(255), nullable=True)  # CashFlowCategory
    cash_flow_category_type = Column(String(50), nullable=True)  # CashFlowCategory.Type
    cash_flow_category_hierarchy = Column(Text, nullable=True)  # CashFlowCategory.Hierarchy
    cash_flow_category_hierarchy_level1 = Column(String(255), nullable=True)  # CashFlowCategory.HierarchyLevel1
    cash_flow_category_hierarchy_level2 = Column(String(255), nullable=True)  # CashFlowCategory.HierarchyLevel2
    cash_flow_category_hierarchy_level3 = Column(String(255), nullable=True)  # CashFlowCategory.HierarchyLevel3
    
    # Даты и время
    date_time = Column(DateTime, nullable=True)  # DateTime.Typed
    date_time_typed = Column(DateTime, nullable=True)  # DateTime.Typed
    date_typed = Column(DateTime, nullable=True)  # DateTime.DateTyped
    date_secondary_date_time_typed = Column(DateTime, nullable=True)  # DateSecondary.DateTimeTyped
    date_secondary_date_typed = Column(DateTime, nullable=True)  # DateSecondary.DateTyped
    
    # Временные группировки
    date_time_year = Column(String(10), nullable=True)  # DateTime.Year
    date_time_quarter = Column(String(10), nullable=True)  # DateTime.Quarter
    date_time_month = Column(String(20), nullable=True)  # DateTime.Month
    date_time_week_in_year = Column(String(10), nullable=True)  # DateTime.WeekInYear
    date_time_week_in_month = Column(String(10), nullable=True)  # DateTime.WeekInMonth
    date_time_day_of_week = Column(String(20), nullable=True)  # DateTime.DayOfWeak
    date_time_hour = Column(String(10), nullable=True)  # DateTime.Hour
    
    # Комментарии и дополнительные данные
    comment = Column(Text, nullable=True)  # Comment
    
    # JSON поля для дополнительных данных
    additional_data = Column(JSON, nullable=True)  # Для хранения дополнительных полей
    
    # Системные поля
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = Column(Boolean, default=True)
