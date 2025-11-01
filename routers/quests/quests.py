from fastapi import APIRouter, Depends, Query, HTTPException, Path
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user
from database.database import get_db
from services.quests.quests_service import (
    get_waiter_quests,
    get_quest_detail,
    create_quest
)
from schemas.quests import (
    QuestsArrayResponse,
    QuestDetailResponse,
    CreateQuestRequest,
    CreateQuestResponse,
    QuestResponse
)
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["quests"])


@router.get("/waiter/{waiter_id}/quests", response_model=QuestsArrayResponse)
def get_waiter_quests_endpoint(
    waiter_id: int = Path(..., description="ID официанта"),
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить квесты официанта на определенную дату
    
    **Query Parameters:**
    - `date` (optional): Дата в формате "DD.MM.YYYY" - дата для получения квестов
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - Список квестов с прогрессом выполнения
    """
    try:
        quests = get_waiter_quests(
            db=db,
            waiter_id=waiter_id,
            date=date,
            organization_id=organization_id
        )
        return QuestsArrayResponse(quests=quests)
    except Exception as e:
        logger.error(f"Error getting waiter quests: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/quests/{quest_id}", response_model=QuestDetailResponse)
def get_quest_detail_endpoint(
    quest_id: int = Path(..., description="ID квеста"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить детальную информацию о квесте (для CEO)
    
    **Query Parameters:**
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - Детальная информация о квесте с прогрессом всех сотрудников
    """
    try:
        quest_detail = get_quest_detail(
            db=db,
            quest_id=quest_id,
            organization_id=organization_id
        )
        
        if not quest_detail:
            raise HTTPException(status_code=404, detail="Quest not found")
        
        return quest_detail
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quest detail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/quests", response_model=CreateQuestResponse)
def create_quest_endpoint(
    quest_data: CreateQuestRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Создать новый квест (для CEO)
    
    **Request Body:**
    ```json
    {
      "title": "Продай 15 десерт",
      "description": "Продай 15 десерт за смену",
      "reward": 15000,
      "target": 15,
      "unit": "десерт",
      "date": "15.01.2025",
      "employeeIds": ["1", "2", "3"],  // Опционально
      "organization_id": 1  // Опционально
    }
    ```
    
    **Response:**
    - Информация о созданном квесте
    """
    try:
        new_reward = create_quest(db=db, quest_data=quest_data)
        
        # Формируем ответ
        quest_response = QuestResponse(
            id=str(new_reward.id),
            title=quest_data.title,
            description=quest_data.description,
            reward=float(new_reward.prize_sum),
            current=0,
            target=new_reward.end_goal,
            unit=quest_data.unit,
            completed=False,
            progress=0.0,
            expiresAt=new_reward.end_date.isoformat() if new_reward.end_date else None
        )
        
        return CreateQuestResponse(
            success=True,
            message="Quest created successfully",
            quest=quest_response
        )
    except Exception as e:
        logger.error(f"Error creating quest: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

