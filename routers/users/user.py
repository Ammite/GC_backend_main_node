from fastapi import APIRouter
from schemas import UserArrayResponse
import logging
from services import users as user_services


logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/users", response_model=UserArrayResponse) # TODO write response model
def get_users():
    users = user_services.get_all_users() # TODO write import
    return {
        "success": True,
        "message": "got users",
        "users": users
    }