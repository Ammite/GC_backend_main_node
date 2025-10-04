from fastapi import Depends
from sqlalchemy.orm import Session
from database.database import get_db
from models import User, Roles
from schemas.auth import LoginRequest, LoginResponse
import logging



def get_all_users(db: Session = Depends(get_db)):
    ...
    return []