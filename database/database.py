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
    from models import User  # noqa: F401
    from models.role import Role  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Наполнение таблицы ролей
    from sqlalchemy.orm import Session
    session = Session(bind=engine)
    try:
        default_roles = [
            {"name": "Админ", "code": "admin"},
            {"name": "Менеджер", "code": "manager"},
            {"name": "Официант", "code": "waiter"},
        ]
        for r in default_roles:
            exists = session.query(Role).filter(Role.code == r["code"]).first()
            if not exists:
                session.add(Role(name=r["name"], code=r["code"]))
        session.commit()
    finally:
        session.close()