import fastapi
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.orm import sessionmaker, Session, declarative_base
import os
import hashlib
import logging
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DB_URL")

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Pydantic models
class LoginRequest(BaseModel):
    login: str
    password: str

# Fastapi
app = fastapi.FastAPI()
# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем все домены для разработки
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# database
# SQLite подключение (по умолчанию)
os.makedirs("database", exist_ok=True)

# PostgreSQL подключение (раскомментировать для использования PostgreSQL)
# DATABASE_URL = "postgresql://username:password@localhost:5432/database_name"
# Пример: DATABASE_URL = "postgresql://myuser:mypass@localhost:5432/gruzin_cuisine"

# Создаем engine с разными параметрами для SQLite и PostgreSQL
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Для PostgreSQL не нужен check_same_thread
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    login = Column(String, unique=True, index=True)
    password_hash = Column(String)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed_password: str) -> bool:
    return hash_password(password) == hashed_password

@app.post("/login")
def login(request: LoginRequest, db: Session = fastapi.Depends(get_db)):
    logger.info(f"Login attempt for user: {request.login}")
    
    user = db.query(User).filter(User.login == request.login).first()
    
    if not user:
        logger.warning(f"User not found: {request.login}")
        return {"success": False, "message": "Invalid credentials"}
    
    # Хешируем пришедший пароль и сравниваем с хешем из БД
    if not verify_password(request.password, user.password_hash):
        logger.warning(f"Invalid password for user: {request.login}")
        return {"success": False, "message": "Invalid credentials"}
    
    logger.info(f"Successful login for user: {request.login}")
    return {"success": True, "message": "Login successful", "user_id": user.id}

@app.post("/register")
def register(request: LoginRequest, db: Session = fastapi.Depends(get_db)):
    logger.info(f"Registration attempt for user: {request.login}")
    
    existing_user = db.query(User).filter(User.login == request.login).first()
    if existing_user:
        logger.warning(f"User already exists: {request.login}")
        return {"success": False, "message": "User already exists"}
    
    hashed_password = hash_password(request.password)
    new_user = User(login=request.login, password_hash=hashed_password)
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"User registered successfully: {request.login}")
    return {"success": True, "message": "User registered successfully", "user_id": new_user.id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
