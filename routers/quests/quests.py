from fastapi import APIRouter, Depends, Query, HTTPException, Path, Body
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from utils.security import get_current_user, require_role, require_self_or_role
from database.database import get_db
from services.quests.quests_service import (
    get_waiter_quests,
    get_quest_detail,
    create_quest,
    get_active_quests,
    update_quest,
    delete_quest
)
from schemas.quests import (
    QuestsArrayResponse,
    QuestDetailResponse,
    CreateQuestRequest,
    CreateQuestResponse,
    UpdateQuestRequest,
    UpdateQuestResponse,
    DeleteQuestResponse,
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
    user = Depends(require_self_or_role("waiter_id", "Менеджер")),
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


@router.post("/quests", response_model=CreateQuestResponse)
def create_quest_endpoint(
    quest_data: CreateQuestRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
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


@router.get("/quests/active", response_model=QuestsArrayResponse)
def get_active_quests_endpoint(
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY (legacy — одна дата)"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    date_from: Optional[str] = Query(default=None, description="DD.MM.YYYY — нижняя граница окна (приоритет над date)"),
    date_to: Optional[str] = Query(default=None, description="DD.MM.YYYY — верхняя граница окна (приоритет над date)"),
    include_expired: bool = Query(default=False, description="Включать ли уже истёкшие квесты (для истории)"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить список активных квестов (или истории — с `include_expired=true`).

    **Query Parameters:**
    - `date_from` / `date_to` (optional): DD.MM.YYYY — интервал по периоду квеста.
      Если ни одна дата не задана — по умолчанию **последние 7 дней**.
    - `date` (optional, legacy): одна дата — оставлено для обратной совместимости.
    - `organization_id` (optional): ID организации для фильтрации прогресса.
    - `include_expired` (optional, default false): по умолчанию выкидываем истёкшие квесты.
      Поставь `true`, чтобы получить историю.

    **Response:** массив квестов с базовой информацией и прогрессом.
    """
    try:
        # Если фронт ничего не передал по датам — дефолт «последние 7 дней» + показываем истёкшие.
        if not any([date, date_from, date_to]):
            today = datetime.now().date()
            date_to = today.strftime("%d.%m.%Y")
            date_from = (today - timedelta(days=7)).strftime("%d.%m.%Y")
            include_expired = True

        quests = get_active_quests(
            db=db,
            date=date,
            organization_id=organization_id,
            date_from=date_from,
            date_to=date_to,
            include_expired=include_expired,
        )
        return QuestsArrayResponse(quests=quests)
    except Exception as e:
        logger.error(f"Error getting active quests: {str(e)}")
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


@router.get("/quests/{quest_id}/progress", response_model=QuestDetailResponse)
def get_quest_progress_endpoint(
    quest_id: int = Path(..., description="ID квеста"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить развернутый список квеста с прогрессом всех сотрудников - список прогресса всех сотрудников внутри квеста
    
    **Path Parameters:**
    - `quest_id`: ID квеста
    
    **Query Parameters:**
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - Детальная информация о квесте
    - employeeProgress: массив с прогрессом каждого сотрудника
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
        logger.error(f"Error getting quest progress: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/quests/{quest_id}", response_model=UpdateQuestResponse)
def update_quest_endpoint(
    quest_id: int = Path(..., description="ID квеста"),
    quest_data: UpdateQuestRequest = Body(...),
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Изменить квест
    
    **Path Parameters:**
    - `quest_id`: ID квеста
    
    **Request Body:**
    ```json
    {
      "title": "Новое название",  // Опционально
      "description": "Новое описание",  // Опционально
      "reward": 20000,  // Опционально
      "target": 20,  // Опционально
      "unit": "десерт",  // Опционально
      "date": "15.01.2025",  // Опционально
      "employeeIds": ["1", "2", "3"]  // Опционально
    }
    ```
    
    **Response:**
    - success, message, quest
    """
    try:
        # Преобразуем UpdateQuestRequest в CreateQuestRequest для совместимости
        create_quest_data = CreateQuestRequest(
            title=quest_data.title or "Квест",
            description=quest_data.description or "",
            reward=quest_data.reward or 0,
            target=quest_data.target or 0,
            unit=quest_data.unit or "единиц",
            date=quest_data.date or datetime.now().strftime("%d.%m.%Y"),
            employeeIds=quest_data.employeeIds
        )
        
        updated_reward = update_quest(
            db=db,
            quest_id=quest_id,
            quest_data=create_quest_data
        )
        
        # Получаем информацию о блюде
        from models.item import Item
        item = db.query(Item).filter(Item.id == updated_reward.item_id).first()
        unit = item.name if item else "единиц"
        
        # Формируем ответ
        quest_response = QuestResponse(
            id=str(updated_reward.id),
            title=create_quest_data.title,
            description=create_quest_data.description,
            reward=float(updated_reward.prize_sum),
            current=0,
            target=updated_reward.end_goal,
            unit=unit,
            completed=False,
            progress=0.0,
            expiresAt=updated_reward.end_date.isoformat() if updated_reward.end_date else None
        )
        
        return UpdateQuestResponse(
            success=True,
            message="Quest updated successfully",
            quest=quest_response
        )
    except ValueError as e:
        logger.error(f"Error updating quest: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating quest: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/quests/{quest_id}", response_model=DeleteQuestResponse)
def delete_quest_endpoint(
    quest_id: int = Path(..., description="ID квеста"),
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Удалить квест
    
    **Path Parameters:**
    - `quest_id`: ID квеста
    
    **Response:**
    - success, message
    """
    try:
        result = delete_quest(db=db, quest_id=quest_id)
        return DeleteQuestResponse(**result)
    except ValueError as e:
        logger.error(f"Error deleting quest: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting quest: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

