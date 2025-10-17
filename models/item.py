from sqlalchemy import Column, Integer, String, Text, ForeignKey, Numeric, Boolean, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database.database import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    iiko_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    code = Column(String(50), nullable=True)
    num = Column(String(50), nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    deleted = Column(Boolean, default=False)
    
    # Новые поля для организации и источника данных
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    organization = relationship("Organization", back_populates="items")
    is_duplicate = Column(Boolean, default=False)  # Флаг дубликата
    data_source = Column(String(20), nullable=True)  # "cloud" или "server"
    
    # Дополнительные поля из Cloud API
    fat_amount = Column(Numeric(10, 3), nullable=True)
    proteins_amount = Column(Numeric(10, 3), nullable=True)
    carbohydrates_amount = Column(Numeric(10, 3), nullable=True)
    energy_amount = Column(Numeric(10, 3), nullable=True)
    fat_full_amount = Column(Numeric(10, 3), nullable=True)
    proteins_full_amount = Column(Numeric(10, 3), nullable=True)
    carbohydrates_full_amount = Column(Numeric(10, 3), nullable=True)
    energy_full_amount = Column(Numeric(10, 3), nullable=True)
    weight = Column(Numeric(10, 3), nullable=True)
    group_id = Column(String(50), nullable=True)
    product_category_id = Column(String(50), nullable=True)
    type = Column(String(50), nullable=True)
    order_item_type = Column(String(50), nullable=True)
    modifier_schema_id = Column(String(50), nullable=True)
    modifier_schema_name = Column(String(255), nullable=True)
    splittable = Column(Boolean, default=False)
    measure_unit = Column(String(50), nullable=True)
    parent_group = Column(String(50), nullable=True)
    order_position = Column(Integer, nullable=True)
    full_name_english = Column(String(255), nullable=True)
    use_balance_for_sell = Column(Boolean, default=False)
    can_set_open_price = Column(Boolean, default=False)
    payment_subject = Column(String(100), nullable=True)
    additional_info = Column(Text, nullable=True)
    is_deleted_cloud = Column(Boolean, default=False)
    seo_description = Column(Text, nullable=True)
    seo_text = Column(Text, nullable=True)
    seo_keywords = Column(Text, nullable=True)
    seo_title = Column(String(255), nullable=True)
    
    # Дополнительные поля из Server API
    parent = Column(String(50), nullable=True)
    tax_category = Column(String(50), nullable=True)
    category_server = Column(String(50), nullable=True)
    accounting_category = Column(String(50), nullable=True)
    color_red = Column(Integer, nullable=True)
    color_green = Column(Integer, nullable=True)
    color_blue = Column(Integer, nullable=True)
    font_color_red = Column(Integer, nullable=True)
    font_color_green = Column(Integer, nullable=True)
    font_color_blue = Column(Integer, nullable=True)
    front_image_id = Column(String(50), nullable=True)
    position_server = Column(Integer, nullable=True)
    main_unit = Column(String(50), nullable=True)
    excluded_sections = Column(Text, nullable=True)
    default_sale_price = Column(Numeric(10, 2), nullable=True)
    place_type = Column(String(50), nullable=True)
    default_included_in_menu = Column(Boolean, default=False)
    type_server = Column(String(50), nullable=True)
    unit_weight = Column(Numeric(10, 3), nullable=True)
    unit_capacity = Column(Numeric(10, 3), nullable=True)
    product_scale_id = Column(String(50), nullable=True)
    cold_loss_percent = Column(Numeric(5, 2), nullable=True)
    hot_loss_percent = Column(Numeric(5, 2), nullable=True)
    allergen_groups = Column(Text, nullable=True)
    estimated_purchase_price = Column(Numeric(10, 2), nullable=True)
    not_in_store_movement = Column(Boolean, default=False)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    category = relationship("Category", back_populates="items")

    menu_category_id = Column(Integer, ForeignKey("menu_categories.id"), nullable=True)
    menu_category = relationship("MenuCategory", back_populates="items")

    product_group_id = Column(Integer, ForeignKey("product_groups.id"), nullable=True)
    product_group = relationship("ProductGroup", back_populates="items")

    modifiers = relationship("Modifier", back_populates="item")
