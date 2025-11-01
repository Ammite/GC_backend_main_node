from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user
from database.database import get_db
from services.rooms.rooms_service import get_rooms, get_tables
from schemas.rooms import RoomsArrayResponse, TablesArrayResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["rooms"])


@router.get("/rooms", response_model=RoomsArrayResponse)
def get_rooms_endpoint(
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить список помещений (секций ресторана)
    
    **Query Parameters:**
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - Список помещений с их столами
    - Каждое помещение содержит: ID, название, вместимость, список столов
    """
    try:
        rooms = get_rooms(db=db, organization_id=organization_id)
        return RoomsArrayResponse(rooms=rooms)
    except Exception as e:
        logger.error(f"Error getting rooms: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/tables", response_model=TablesArrayResponse)
def get_tables_endpoint(
    room_id: Optional[int] = Query(default=None, description="ID помещения для фильтрации"),
    status: Optional[str] = Query(default=None, description="Статус стола: available, occupied, disabled, all"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить список столов
    
    **Query Parameters:**
    - `room_id` (optional): ID помещения для фильтрации
    - `status` (optional): Статус стола ("available" | "occupied" | "disabled" | "all")
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - Список столов с их статусами
    - Каждый стол содержит: ID, номер, помещение, вместимость, статус, текущий заказ, назначенный официант
    """
    try:
        tables = get_tables(
            db=db,
            room_id=room_id,
            status=status,
            organization_id=organization_id
        )
        return TablesArrayResponse(tables=tables)
    except Exception as e:
        logger.error(f"Error getting tables: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

