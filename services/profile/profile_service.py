from typing import Optional

from sqlalchemy.orm import Session

from models.user import User
from models.employees import Employees
from schemas.profile import UserProfileResponse, UserProfileStats
from services.employees.employees_service import get_employee_summary


def _build_profile_response(
    db: Session,
    user: User,
) -> UserProfileResponse:
    organization_id: Optional[int] = None
    stats: Optional[UserProfileStats] = None

    # Пытаемся найти связанного сотрудника (официанта) по iiko_id
    if user.iiko_id:
        employee = (
            db.query(Employees)
            .filter(Employees.iiko_id == user.iiko_id, Employees.deleted == False)  # noqa: E712
            .first()
        )
    else:
        employee = None

    employee_id: Optional[int] = None

    if employee:
        employee_id = employee.id
        organization_id = employee.preferred_organization_id

        # Используем уже реализованную сводку по сотруднику
        try:
            summary = get_employee_summary(
                db=db,
                employee_id=employee.id,
                date=None,
                organization_id=organization_id,
            )

            stats = UserProfileStats(
                shiftDuration=summary.get("shiftDuration"),
                totalAmount=summary.get("totalAmount"),
                ordersCount=summary.get("ordersCount"),
            )
        except Exception:
            stats = None

    return UserProfileResponse(
        id=user.id,
        name=user.name,
        login=user.login,
        role=user.app_role,
        organization_id=organization_id,
        employee_id=employee_id,
        stats=stats,
    )


def get_user_profile(db: Session, user: User) -> UserProfileResponse:
    """Профиль текущего пользователя (по токену)"""
    return _build_profile_response(db, user)


def get_user_profile_by_id(db: Session, user_id: int) -> Optional[UserProfileResponse]:
    """Профиль пользователя по user_id (для владельца/менеджера)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    return _build_profile_response(db, user)

