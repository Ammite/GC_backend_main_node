from fastapi import Depends
from sqlalchemy.orm import Session
from database.database import get_db
from models import User
from models import Role
from schemas.auth import LoginRequest, LoginResponse
import logging



def get_all_users(db: Session = Depends(get_db)):
    ...
    return []