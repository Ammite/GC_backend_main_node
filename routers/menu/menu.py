from fastapi import APIRouter
from schemas import MenuArrayResponse
import logging
from services import menu as menu_services


logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/menu", response_model=MenuArrayResponse) # TODO write response model
def get_menu():
    menu = menu_services.get_all_menu_items() # TODO write import
    return {
        "success": True,
        "message": "got orders",
        "menu": menu
    }