"""
Фикстуры для тестов
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, TypeDecorator, String
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from datetime import datetime, timedelta, date
from typing import Generator
import json

from database.database import Base, get_db
from main import app
from models import (
    User, Employees, Shift, Penalty, Reward, Organization, Roles,
    AttendanceType, Item, DOrder, TOrder, UserReward, UserSalary,
    Table, RestaurantSection, TerminalGroup,
    Expense, WarehouseDocument, WarehouseDocumentItem,
    Department, Conception, Supplier, Store, Account,
    DailyAnalytics, DailyEmployeeAnalytics, MenuCategory,
    WaiterSalesPercent,
)
from utils.security import hash_password, create_access_token, get_current_user

# Обеспечиваем, что роутеры инициализируются один раз для всех тестов
import main as _main_module
# Форсируем загрузку роутеров сразу при импорте conftest (для всей test session)
with TestClient(app):
    pass  # lifespan вызовет include_routers один раз
# Теперь _routers_included=True, повторные TestClient не будут дублировать роутеры


# Патч для ARRAY типа в SQLite - конвертируем в JSON
class JSONList(TypeDecorator):
    """Тип для хранения списков в SQLite как JSON"""
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return value

# Заменяем ARRAY на JSONList для тестовой БД
from sqlalchemy import ARRAY

# Флаг для отслеживания патчинга
_array_patched = False

# Патчим ARRAY колонки в модели Employees один раз при импорте
def patch_array_columns_once():
    """Заменяет ARRAY колонки на JSONList для SQLite один раз при импорте"""
    global _array_patched
    if _array_patched:
        return

    from models.employees import Employees

    if hasattr(Employees, '__table__'):
        for column in Employees.__table__.columns:
            if isinstance(column.type, ARRAY):
                # Заменяем на JSONList только если еще не заменено
                if not isinstance(column.type, JSONList):
                    column.type = JSONList()
        _array_patched = True

# Вызываем патч один раз
try:
    patch_array_columns_once()
except Exception:
    pass  # Игнорируем ошибки патчинга

# Тестовая БД в памяти
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Настройка SQLite для тестов
@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Настройка SQLite для тестов"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """
    Фикстура для тестовой БД.
    Создает таблицы перед каждым тестом и удаляет после.
    """
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def test_client(test_db, test_user) -> Generator[TestClient, None, None]:
    """
    Фикстура для TestClient FastAPI.
    """
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def unauthenticated_client(test_db) -> Generator[TestClient, None, None]:
    """
    Клиент без авторизации (для тестов auth).
    """
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    # НЕ переопределяем get_current_user

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_user(test_db) -> User:
    """
    Фикстура для тестового пользователя.
    """
    user = User(
        login="test_user",
        password=hash_password("test_password"),
        name="Test User"
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_token(test_user) -> str:
    """
    Фикстура для токена авторизации.
    """
    return create_access_token(data={"sub": test_user.login})


@pytest.fixture(scope="function")
def test_organization(test_db) -> Organization:
    """
    Фикстура для тестовой организации.
    """
    org = Organization(
        iiko_id="test_org_id",
        name="Test Organization"
    )
    test_db.add(org)
    test_db.commit()
    test_db.refresh(org)
    return org


@pytest.fixture(scope="function")
def test_role(test_db) -> Roles:
    """
    Фикстура для тестовой роли.
    """
    role = Roles(
        iiko_id="test_role_id",
        code="WAITER",
        name="Официант"
    )
    test_db.add(role)
    test_db.commit()
    test_db.refresh(role)
    return role


@pytest.fixture(scope="function")
def test_attendance_type(test_db) -> AttendanceType:
    """
    Фикстура для типа посещаемости.
    """
    att_type = AttendanceType(
        iiko_id="test_attendance_id",
        code="WORK",
        name="Работа"
    )
    test_db.add(att_type)
    test_db.commit()
    test_db.refresh(att_type)
    return att_type


@pytest.fixture(scope="function")
def sample_employee(test_db, test_organization, test_role) -> Employees:
    """
    Фикстура для тестового сотрудника.
    """
    employee = Employees(
        iiko_id="test_employee_iiko_id",
        name="Аслан Аманов",
        first_name="Аслан",
        last_name="Аманов",
        login="test_employee",
        main_role_id=test_role.id,
        main_role_code="WAITER",
        preferred_organization_id=test_organization.id
    )
    test_db.add(employee)
    test_db.commit()
    test_db.refresh(employee)
    return employee


@pytest.fixture(scope="function")
def linked_employee_user(test_db, test_organization, test_role):
    """
    Связанный сотрудник+пользователь через iiko_id.
    Возвращает кортеж (employee, user).
    """
    shared_iiko_id = "linked_iiko_id_123"
    employee = Employees(
        iiko_id=shared_iiko_id,
        name="Linked Employee",
        first_name="Linked",
        last_name="Employee",
        login="linked_emp",
        main_role_id=test_role.id,
        main_role_code="WAITER",
        preferred_organization_id=test_organization.id
    )
    test_db.add(employee)
    test_db.commit()
    test_db.refresh(employee)

    user = User(
        login="linked_user",
        password=hash_password("linked_pass"),
        name="Linked User",
        iiko_id=shared_iiko_id
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return employee, user


@pytest.fixture(scope="function")
def sample_shift(
    test_db,
    sample_employee,
    test_user,
    test_attendance_type
) -> Shift:
    """
    Фикстура для тестовой смены.
    """
    start_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(hours=8)  # 8-часовая смена
    shift = Shift(
        iiko_id="test_shift_id",
        start_time=start_time,
        end_time=end_time,
        employee_id=sample_employee.id,
        user_id=test_user.id,
        attendance_type_id=test_attendance_type.id
    )
    test_db.add(shift)
    test_db.commit()
    test_db.refresh(shift)
    return shift


@pytest.fixture(scope="function")
def active_shift(
    test_db,
    sample_employee,
    test_user,
    test_attendance_type
) -> Shift:
    """
    Фикстура для активной смены (без end_time).
    """
    start_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    shift = Shift(
        iiko_id="active_shift_id",
        start_time=start_time,
        end_time=None,
        employee_id=sample_employee.id,
        user_id=test_user.id,
        attendance_type_id=test_attendance_type.id
    )
    test_db.add(shift)
    test_db.commit()
    test_db.refresh(shift)
    return shift


@pytest.fixture(scope="function")
def sample_penalty(test_db, sample_employee, test_user) -> Penalty:
    """
    Фикстура для тестового штрафа.
    """
    penalty = Penalty(
        penalty_sum=5000.00,
        description="Опоздание на работу",
        employee_id=sample_employee.id,
        user_id=test_user.id
    )
    test_db.add(penalty)
    test_db.commit()
    test_db.refresh(penalty)
    return penalty


@pytest.fixture(scope="function")
def test_item(test_db) -> Item:
    """
    Фикстура для тестового товара (для квеста).
    """
    item = Item(
        iiko_id="test_item_id",
        name="Тестовый товар",
        price=1000.00,
        deleted=False
    )
    test_db.add(item)
    test_db.commit()
    test_db.refresh(item)
    return item


@pytest.fixture(scope="function")
def sample_reward(test_db, test_item) -> Reward:
    """
    Фикстура для тестового квеста.
    """
    start_date = datetime.now()
    end_date = start_date + timedelta(days=7)
    reward = Reward(
        start_date=start_date,
        end_date=end_date,
        item_id=test_item.id,
        end_goal=15,
        prize_sum=15000.00
    )
    test_db.add(reward)
    test_db.commit()
    test_db.refresh(reward)
    return reward


@pytest.fixture(scope="function")
def sample_user_reward(test_db, test_user, sample_reward, sample_employee) -> UserReward:
    """
    Фикстура для привязки квеста к пользователю.
    """
    user_reward = UserReward(
        reward_id=sample_reward.id,
        user_id=test_user.id,
        employee_id=sample_employee.id,
        current_progress=5
    )
    test_db.add(user_reward)
    test_db.commit()
    test_db.refresh(user_reward)
    return user_reward


@pytest.fixture(scope="function")
def sample_order(test_db, test_user, test_organization) -> DOrder:
    """
    Фикстура для тестового заказа (state=CREATED).
    """
    order = DOrder(
        organization_id=test_organization.id,
        user_id=test_user.id,
        state_order="CREATED",
        sum_order=5000.00,
        guest_count=2,
        time_order=datetime.now(),
        items=json.dumps([]),
        external_number="TEST-001"
    )
    test_db.add(order)
    test_db.commit()
    test_db.refresh(order)
    return order


@pytest.fixture(scope="function")
def paid_order(test_db, test_user, test_organization) -> DOrder:
    """
    Фикстура для оплаченного заказа (state=PAID).
    """
    order = DOrder(
        organization_id=test_organization.id,
        user_id=test_user.id,
        state_order="PAID",
        sum_order=7500.00,
        guest_count=3,
        time_order=datetime.now(),
        items=json.dumps([]),
        external_number="TEST-002"
    )
    test_db.add(order)
    test_db.commit()
    test_db.refresh(order)
    return order


@pytest.fixture(scope="function")
def sample_t_order(test_db, sample_order, test_item) -> TOrder:
    """
    Фикстура для позиции заказа.
    """
    t_order = TOrder(
        item_id=test_item.id,
        count_order=2,
        order_id=sample_order.id,
        time_order=datetime.now()
    )
    test_db.add(t_order)
    test_db.commit()
    test_db.refresh(t_order)
    return t_order


@pytest.fixture(scope="function")
def sample_table(test_db, test_organization):
    """
    Фикстура для стола (с секцией и терминал-группой).
    """
    terminal_group = TerminalGroup(
        iiko_id="test_tg_id",
        name="Test Terminal Group",
        organization_id=test_organization.id
    )
    test_db.add(terminal_group)
    test_db.commit()
    test_db.refresh(terminal_group)

    section = RestaurantSection(
        iiko_id="test_section_id",
        name="Test Section",
        terminal_group_id=terminal_group.id
    )
    test_db.add(section)
    test_db.commit()
    test_db.refresh(section)

    table = Table(
        iiko_id="test_table_id",
        number=5,
        name="Table 5",
        section_id=section.id
    )
    test_db.add(table)
    test_db.commit()
    test_db.refresh(table)
    return table


@pytest.fixture(scope="function")
def sample_expense(test_db, test_organization, test_user) -> Expense:
    """
    Фикстура для тестового расхода.
    """
    expense = Expense(
        organization_id=test_organization.id,
        expense_type="RENT",
        amount=50000.00,
        date=datetime.now(),
        comment="Аренда помещения",
        created_by=test_user.id
    )
    test_db.add(expense)
    test_db.commit()
    test_db.refresh(expense)
    return expense


@pytest.fixture(scope="function")
def sample_warehouse_document(test_db, test_organization, test_user) -> WarehouseDocument:
    """
    Фикстура для складского документа.
    """
    doc = WarehouseDocument(
        document_type="RECEIPT",
        document_number="RECEIPT-20260314-0001",
        date=datetime.now(),
        organization_id=test_organization.id,
        created_by=test_user.id,
        status="NEW"
    )
    test_db.add(doc)
    test_db.commit()
    test_db.refresh(doc)
    return doc


@pytest.fixture(scope="function")
def sample_department(test_db) -> Department:
    """
    Фикстура для тестового департамента.
    """
    dept = Department(
        iiko_id="test_dept_iiko_id",
        name="Test Department",
        code="DEPT01",
        is_active=True
    )
    test_db.add(dept)
    test_db.commit()
    test_db.refresh(dept)
    return dept


@pytest.fixture(scope="function")
def sample_conception(test_db) -> Conception:
    """
    Фикстура для тестовой концепции.
    """
    conception = Conception(
        iiko_id="test_conception_iiko_id",
        name="Test Conception",
        code="CONC01",
        is_active=True
    )
    test_db.add(conception)
    test_db.commit()
    test_db.refresh(conception)
    return conception


@pytest.fixture(scope="function")
def sample_supplier(test_db) -> Supplier:
    """
    Фикстура для тестового поставщика.
    """
    supplier = Supplier(
        iiko_id="test_supplier_iiko_id",
        name="Test Supplier",
        code="SUP01",
        is_active=True
    )
    test_db.add(supplier)
    test_db.commit()
    test_db.refresh(supplier)
    return supplier


@pytest.fixture(scope="function")
def sample_store(test_db, test_organization) -> Store:
    """
    Фикстура для тестового склада.
    """
    store = Store(
        iiko_id="test_store_iiko_id",
        name="Test Store",
        code="STORE01",
        organization_id=test_organization.id,
        is_active=True
    )
    test_db.add(store)
    test_db.commit()
    test_db.refresh(store)
    return store


@pytest.fixture(scope="function")
def sample_account(test_db) -> Account:
    """
    Фикстура для тестового счёта.
    """
    account = Account(
        iiko_id="test_account_iiko_id",
        name="Test Account",
        code="ACC01",
        type="EXPENSE"
    )
    test_db.add(account)
    test_db.commit()
    test_db.refresh(account)
    return account


@pytest.fixture(scope="function")
def sample_daily_analytics(test_db, test_organization) -> DailyAnalytics:
    """
    Фикстура для тестовой аналитики.
    """
    analytics = DailyAnalytics(
        date=date.today(),
        organization_id=test_organization.id,
        metric_key="revenue",
        metric_subkey="total",
        value=150000.00
    )
    test_db.add(analytics)
    test_db.commit()
    test_db.refresh(analytics)
    return analytics


@pytest.fixture(scope="function")
def sample_daily_employee_analytics(test_db, sample_employee, test_organization) -> DailyEmployeeAnalytics:
    """
    Фикстура для тестовой аналитики сотрудника.
    """
    analytics = DailyEmployeeAnalytics(
        date=date.today(),
        employee_id=sample_employee.id,
        organization_id=test_organization.id,
        revenue=50000.00,
        checks_count=10,
        returns_count=1,
        average_check=5000.00
    )
    test_db.add(analytics)
    test_db.commit()
    test_db.refresh(analytics)
    return analytics


@pytest.fixture(scope="function")
def sample_menu_category(test_db) -> MenuCategory:
    """
    Фикстура для тестовой категории меню.
    """
    category = MenuCategory(
        iiko_id="test_menu_cat_id",
        name="Горячие блюда",
        is_deleted=False
    )
    test_db.add(category)
    test_db.commit()
    test_db.refresh(category)
    return category


@pytest.fixture(scope="function")
def sample_menu_item(test_db, test_organization, sample_menu_category) -> Item:
    """
    Фикстура для тестового товара с категорией меню.
    """
    item = Item(
        iiko_id="test_menu_item_id",
        name="Стейк",
        price=2500.00,
        deleted=False,
        organization_id=test_organization.id,
        menu_category_id=sample_menu_category.id
    )
    test_db.add(item)
    test_db.commit()
    test_db.refresh(item)
    return item
