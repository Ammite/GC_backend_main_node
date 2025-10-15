from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import timedelta
from utils.security import hash_password, verify_password, create_access_token
from database.database import get_db
from models import User, Roles
from schemas.auth import LoginRequest, LoginResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.login == request.login).first()
    if not user or not verify_password(request.password, user.password):
        return {"success": False, "message": "Invalid credentials"}

    access_token = create_access_token(
        data={"sub": user.login},
        expires_delta=timedelta(minutes=30),
    )

    # Берём первую роль пользователя (если их несколько) для ответа
    return {
        "success": True,
        "message": "Login successful",
        "user_id": user.id,
        "access_token": access_token,
        "token_type": "bearer",
        "role": None,
    }

@router.post("/register", response_model=LoginResponse)
def register(request: LoginRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.login == request.login).first()
    if existing_user:
        return {"success": False, "message": "User already exists"}

    hashed_password = hash_password(request.password)
    new_user = User(login=request.login, password=hashed_password)
    

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token = create_access_token(
        data={"sub": new_user.login},
        expires_delta=timedelta(minutes=30),
    )

    
    return {
        "success": True,
        "message": "User registered successfully",
        "user_id": new_user.id,
        "access_token": access_token,
        "token_type": "bearer",
        "role": None,
    }
