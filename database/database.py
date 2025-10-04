from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import config


DATABASE_URL = config.DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Инициализация схем БД (создание таблиц)
def init_db():
    # Импортируем все модели для создания таблиц
    from models import (
        User, Roles, AttendanceType, Category, DOrder, Employees, Item,
        MenuCategory, Modifier, OrderType, Order, Organization, Penalty,
        ProductGroup, RestaurantSection, Reward, ScheduleType, Shift,
        TOrder, Table, TerminalGroup, Terminal, UserReward, UserSalary
    )
    Base.metadata.create_all(bind=engine)

    # Наполнение таблиц тестовыми данными
    from sqlalchemy.orm import Session
    session = Session(bind=engine)
    try:
        # 1. Роли
        default_roles = [
            {"name": "Admin", "code": "admin", "iiko_id": "admin-role-uuid"},
            {"name": "Manager", "code": "manager", "iiko_id": "manager-role-uuid"},
            {"name": "Waiter", "code": "waiter", "iiko_id": "waiter-role-uuid"},
        ]
        for r in default_roles:
            exists = session.query(Roles).filter(Roles.code == r["code"]).first()
            if not exists:
                session.add(Roles(name=r["name"], code=r["code"], iiko_id=r["iiko_id"]))
        
        # 2. Типы посещаемости
        attendance_types = [
            {"code": "work", "name": "Рабочий день", "pay_rate": 1.0},
            {"code": "overtime", "name": "Сверхурочные", "pay_rate": 1.5},
            {"code": "holiday", "name": "Праздничный день", "pay_rate": 2.0},
        ]
        for at in attendance_types:
            exists = session.query(AttendanceType).filter(AttendanceType.code == at["code"]).first()
            if not exists:
                session.add(AttendanceType(**at, iiko_id=f"attendance-{at['code']}-uuid"))
        
        # 3. Типы расписания
        schedule_types = [
            {"code": "morning", "name": "Утренняя смена", "start_time": "08:00", "length_minutes": 480},
            {"code": "evening", "name": "Вечерняя смена", "start_time": "16:00", "length_minutes": 480},
            {"code": "night", "name": "Ночная смена", "start_time": "00:00", "length_minutes": 480},
        ]
        for st in schedule_types:
            exists = session.query(ScheduleType).filter(ScheduleType.code == st["code"]).first()
            if not exists:
                session.add(ScheduleType(**st, iiko_id=f"schedule-{st['code']}-uuid"))
        
        # 4. Организации
        organizations = [
            {"name": "Ресторан 'Уют'", "code": "restaurant-1"},
            {"name": "Кафе 'Кофе и Кексы'", "code": "cafe-1"},
        ]
        for org in organizations:
            exists = session.query(Organization).filter(Organization.code == org["code"]).first()
            if not exists:
                session.add(Organization(**org, iiko_id=f"org-{org['code']}-uuid"))
        
        # 5. Группы терминалов
        terminal_groups = [
            {"organization_id": 1, "iiko_id": "terminal-group-1-uuid"},
            {"organization_id": 2, "iiko_id": "terminal-group-2-uuid"},
        ]
        for tg in terminal_groups:
            exists = session.query(TerminalGroup).filter(TerminalGroup.iiko_id == tg["iiko_id"]).first()
            if not exists:
                session.add(TerminalGroup(**tg))
        
        # 6. Терминалы
        terminals = [
            {"name": "Касса 1", "address": "Зал 1", "time_zone": "UTC+3", "organization_id": 1, "terminal_group_id": 1},
            {"name": "Касса 2", "address": "Зал 2", "time_zone": "UTC+3", "organization_id": 1, "terminal_group_id": 1},
            {"name": "Касса кафе", "address": "Кафе", "time_zone": "UTC+3", "organization_id": 2, "terminal_group_id": 2},
        ]
        for term in terminals:
            exists = session.query(Terminal).filter(Terminal.name == term["name"]).first()
            if not exists:
                session.add(Terminal(**term, iiko_id=f"terminal-{term['name'].lower().replace(' ', '-')}-uuid"))
        
        # 7. Секции ресторана
        restaurant_sections = [
            {"name": "Основной зал", "terminal_group_id": 1},
            {"name": "VIP зал", "terminal_group_id": 1},
            {"name": "Терраса", "terminal_group_id": 2},
        ]
        for rs in restaurant_sections:
            exists = session.query(RestaurantSection).filter(RestaurantSection.name == rs["name"]).first()
            if not exists:
                session.add(RestaurantSection(**rs, iiko_id=f"section-{rs['name'].lower().replace(' ', '-')}-uuid"))
        
        # 8. Столы
        tables = [
            {"number": 1, "name": "Стол 1", "section_id": 1},
            {"number": 2, "name": "Стол 2", "section_id": 1},
            {"number": 3, "name": "VIP стол 1", "section_id": 2},
            {"number": 4, "name": "Стол на террасе", "section_id": 3},
        ]
        for table in tables:
            exists = session.query(Table).filter(Table.number == table["number"], Table.section_id == table["section_id"]).first()
            if not exists:
                session.add(Table(**table, iiko_id=f"table-{table['number']}-uuid"))
        
        # 9. Категории
        categories = [
            {"name": "Горячие блюда", "iiko_id": "category-hot-uuid"},
            {"name": "Холодные закуски", "iiko_id": "category-cold-uuid"},
            {"name": "Напитки", "iiko_id": "category-drinks-uuid"},
        ]
        for cat in categories:
            exists = session.query(Category).filter(Category.iiko_id == cat["iiko_id"]).first()
            if not exists:
                session.add(Category(**cat))
        
        # 10. Группы продуктов
        product_groups = [
            {"name": "Основные блюда", "description": "Основные горячие блюда", "iiko_id": "product-group-main-uuid"},
            {"name": "Закуски", "description": "Холодные и горячие закуски", "iiko_id": "product-group-appetizers-uuid"},
            {"name": "Безалкогольные напитки", "description": "Соки, вода, чай, кофе", "iiko_id": "product-group-drinks-uuid"},
        ]
        for pg in product_groups:
            exists = session.query(ProductGroup).filter(ProductGroup.iiko_id == pg["iiko_id"]).first()
            if not exists:
                session.add(ProductGroup(**pg))
        
        # 11. Категории меню
        menu_categories = [
            {"name": "Завтрак", "iiko_id": "menu-breakfast-uuid"},
            {"name": "Обед", "iiko_id": "menu-lunch-uuid"},
            {"name": "Ужин", "iiko_id": "menu-dinner-uuid"},
        ]
        for mc in menu_categories:
            exists = session.query(MenuCategory).filter(MenuCategory.iiko_id == mc["iiko_id"]).first()
            if not exists:
                session.add(MenuCategory(**mc))
        
        # 12. Типы заказов
        order_types = [
            {"name": "Доставка", "iiko_id": "order-type-delivery-uuid"},
            {"name": "Самовывоз", "iiko_id": "order-type-pickup-uuid"},
            {"name": "В зале", "iiko_id": "order-type-dine-in-uuid"},
        ]
        for ot in order_types:
            exists = session.query(OrderType).filter(OrderType.iiko_id == ot["iiko_id"]).first()
            if not exists:
                session.add(OrderType(**ot))
        
        # 13. Блюда
        items = [
            {"name": "Борщ украинский", "description": "Классический украинский борщ", "price": 250.00, "category_id": 1, "menu_category_id": 2, "product_group_id": 1},
            {"name": "Цезарь с курицей", "description": "Салат Цезарь с куриной грудкой", "price": 320.00, "category_id": 2, "menu_category_id": 2, "product_group_id": 2},
            {"name": "Кофе американо", "description": "Классический американо", "price": 120.00, "category_id": 3, "menu_category_id": 1, "product_group_id": 3},
        ]
        for item in items:
            exists = session.query(Item).filter(Item.name == item["name"]).first()
            if not exists:
                session.add(Item(**item, iiko_id=f"item-{item['name'].lower().replace(' ', '-')}-uuid"))
        
        # 14. Модификаторы
        modifiers = [
            {"iiko_id": "modifier-size-uuid", "item_id": 1},
            {"iiko_id": "modifier-spice-uuid", "item_id": 1},
            {"iiko_id": "modifier-dressing-uuid", "item_id": 2},
        ]
        for mod in modifiers:
            exists = session.query(Modifier).filter(Modifier.iiko_id == mod["iiko_id"]).first()
            if not exists:
                session.add(Modifier(**mod))
        
        # 15. Сотрудники
        employees = [
            {"first_name": "Иван", "last_name": "Петров", "phone": "+7-900-123-45-67", "main_role_id": 1},
            {"first_name": "Мария", "last_name": "Сидорова", "phone": "+7-900-234-56-78", "main_role_id": 2},
            {"first_name": "Алексей", "last_name": "Козлов", "phone": "+7-900-345-67-89", "main_role_id": 3},
        ]
        for emp in employees:
            exists = session.query(Employees).filter(Employees.first_name == emp["first_name"], Employees.last_name == emp["last_name"]).first()
            if not exists:
                session.add(Employees(**emp, iiko_id=f"employee-{emp['first_name'].lower()}-{emp['last_name'].lower()}-uuid"))
        
        # 16. Пользователи
        users = [
            {"name": "Администратор", "login": "admin", "password": "admin123", "roles_id": 1},
            {"name": "Менеджер", "login": "manager", "password": "manager123", "roles_id": 2},
            {"name": "Официант", "login": "waiter", "password": "waiter123", "roles_id": 3},
        ]
        for user in users:
            exists = session.query(User).filter(User.login == user["login"]).first()
            if not exists:
                session.add(User(**user, iiko_id=f"user-{user['login']}-uuid"))
        
        # 17. Смены
        from datetime import datetime
        shifts = [
            {"start_time": datetime(2024, 1, 1, 8, 0, 0), "end_time": datetime(2024, 1, 1, 16, 0, 0), "roles_id": 1, "attendance_type_id": 1, "employee_id": 1},
            {"start_time": datetime(2024, 1, 1, 16, 0, 0), "end_time": datetime(2024, 1, 2, 0, 0, 0), "roles_id": 2, "attendance_type_id": 1, "employee_id": 2},
        ]
        for shift in shifts:
            exists = session.query(Shift).filter(Shift.start_time == shift["start_time"], Shift.employee_id == shift["employee_id"]).first()
            if not exists:
                session.add(Shift(**shift, iiko_id=f"shift-{shift['employee_id']}-2024-01-01-uuid"))
        
        # 18. Заказы
        orders = [
            {"iiko_id": "order-1-uuid", "organization_id": 1, "terminal_group_id": 1, "phone": "+7-900-111-11-11", "guest_count": 2, "order_type_id": 3},
            {"iiko_id": "order-2-uuid", "organization_id": 1, "terminal_group_id": 1, "phone": "+7-900-222-22-22", "guest_count": 1, "order_type_id": 1},
        ]
        for order in orders:
            exists = session.query(Order).filter(Order.iiko_id == order["iiko_id"]).first()
            if not exists:
                session.add(Order(**order))
        
        # 19. Заказы D (детали заказов)
        d_orders = [
            {"sum_order": 570.00, "user_id": 1, "state_order": "completed", "discount": 50.00, "service": 0.00},
            {"sum_order": 320.00, "user_id": 2, "state_order": "pending", "discount": 0.00, "service": 30.00},
        ]
        for d_order in d_orders:
            exists = session.query(DOrder).filter(DOrder.sum_order == d_order["sum_order"]).first()
            if not exists:
                session.add(DOrder(**d_order, iiko_id=f"d-order-{d_order['sum_order']}-uuid"))
        
        # 20. Заказы T (товары в заказах)
        t_orders = [
            {"item_id": 1, "count_order": 2, "order_id": 1, "comment_order": "Без сметаны"},
            {"item_id": 2, "count_order": 1, "order_id": 1, "comment_order": ""},
            {"item_id": 3, "count_order": 1, "order_id": 2, "comment_order": ""},
        ]
        for t_order in t_orders:
            exists = session.query(TOrder).filter(TOrder.item_id == t_order["item_id"], TOrder.order_id == t_order["order_id"]).first()
            if not exists:
                session.add(TOrder(**t_order, iiko_id=f"t-order-{t_order['item_id']}-{t_order['order_id']}-uuid"))
        
        # 21. Награды
        rewards = [
            {"item_id": 1, "end_goal": 100, "prize_sum": 1000.00, "start_date": datetime(2024, 1, 1, 0, 0, 0), "end_date": datetime(2024, 12, 31, 23, 59, 59)},
            {"item_id": 2, "end_goal": 50, "prize_sum": 500.00, "start_date": datetime(2024, 1, 1, 0, 0, 0), "end_date": datetime(2024, 12, 31, 23, 59, 59)},
        ]
        for reward in rewards:
            exists = session.query(Reward).filter(Reward.item_id == reward["item_id"]).first()
            if not exists:
                session.add(Reward(**reward, iiko_id=f"reward-{reward['item_id']}-uuid"))
        
        # 22. Штрафы
        penalties = [
            {"penalty_sum": 500.00, "description": "Опоздание на работу", "roles_id": 1},
            {"penalty_sum": 300.00, "description": "Нарушение дресс-кода", "roles_id": 2},
        ]
        for penalty in penalties:
            exists = session.query(Penalty).filter(Penalty.description == penalty["description"]).first()
            if not exists:
                session.add(Penalty(**penalty, iiko_id=f"penalty-{penalty['description'].lower().replace(' ', '-')}-uuid"))
        
        # 23. Награды пользователей
        user_rewards = [
            {"reward_id": 1, "user_id": 1, "current_progress": 25},
            {"reward_id": 2, "user_id": 2, "current_progress": 10},
        ]
        for ur in user_rewards:
            exists = session.query(UserReward).filter(UserReward.reward_id == ur["reward_id"], UserReward.user_id == ur["user_id"]).first()
            if not exists:
                session.add(UserReward(**ur, iiko_id=f"user-reward-{ur['reward_id']}-{ur['user_id']}-uuid"))
        
        # 24. Зарплаты пользователей
        user_salaries = [
            {"user_id": 1, "salary": 50000.00},
            {"user_id": 2, "salary": 40000.00},
            {"user_id": 3, "salary": 35000.00},
        ]
        for us in user_salaries:
            exists = session.query(UserSalary).filter(UserSalary.user_id == us["user_id"]).first()
            if not exists:
                session.add(UserSalary(**us, iiko_id=f"user-salary-{us['user_id']}-uuid"))
        
        session.commit()
        print("All tables filled with test data!")
        
    except Exception as e:
        print(f"Error filling tables: {e}")
        session.rollback()
    finally:
        session.close()