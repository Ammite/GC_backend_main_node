from fastapi import APIRouter
from schemas import OrderArrayResponse
import logging
from services import orders as order_services


logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/orders", response_model=OrderArrayResponse) # TODO write response model
def get_orders():
    orders = order_services.get_all_orders() # TODO write import
    return {
        "success": True,
        "message": "got orders",
        "orders": orders
    }