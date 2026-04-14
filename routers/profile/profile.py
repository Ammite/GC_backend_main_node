from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from database.database import get_db
from utils.security import get_current_user
from schemas.profile import UserProfileResponse
from services.profile import get_user_profile, get_user_profile_by_id


router = APIRouter(prefix="", tags=["profile"])


@router.get("/profile", response_model=UserProfileResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Получить профиль текущего пользователя (по токену).
    """
    return get_user_profile(db=db, user=user)


@router.get("/users/{user_id}/profile", response_model=UserProfileResponse)
def get_user_profile_endpoint(
    user_id: int = Path(..., description="ID пользователя"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),  # noqa: U100 - для будущей проверки прав
):
    """
    Получить профиль пользователя по userId (для владельца/менеджера).
    """
    profile = get_user_profile_by_id(db=db, user_id=user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    return profile

