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
    Base.metadata.create_all(bind=engine)