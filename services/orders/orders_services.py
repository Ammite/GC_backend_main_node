from fastapi import Depends
from sqlalchemy.orm import Session
from database.database import get_db
from models import User
from models import Role
from schemas.auth import LoginRequest, LoginResponse
import logging

def get_all_orders(db: Session = Depends(get_db)):
    ...
    return []

def get_order_by_id(db: Session = Depends(get_db)):
    ...
    return []

def get_order_by_user(db: Session = Depends(get_db)):
    ...
    return []

def get_order_by_state(db: Session = Depends(get_db)):
    ...
    return []