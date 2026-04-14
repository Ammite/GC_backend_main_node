from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import timedelta
from utils.security import hash_password, verify_password, create_access_token, get_current_user
from database.database import get_db
from models import User, Employees
from schemas.auth import LoginRequest, LoginResponse, ChangePasswordRequest
import logging


logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])


def _get_employee_name_for_user(db: Session, user: User) -> str | None:
    """
    Возвращает имя сотрудника для пользователя.

    Приоритет:
    1. Ищем сотрудника по iiko_id (User.iiko_id -> Employees.iiko_id).
    2. Если сотрудник не найден, используем поле User.name, если оно заполнено.
    """
    try:
        if user.iiko_id:
            employee = (
                db.query(Employees)
                .filter(Employees.iiko_id == user.iiko_id)
                .first()
            )
            if employee:
                # Если есть явное поле name — используем его
                if employee.name:
                    return employee.name

                # Иначе пробуем собрать ФИО
                parts = [
                    part
                    for part in [
                        employee.first_name,
                        employee.middle_name,
                        employee.last_name,
                    ]
                    if part
                ]
                if parts:
                    return " ".join(parts)

        # Фолбэк на имя пользователя, если оно заполнено
        if getattr(user, "name", None):
            return user.name
    except Exception as e:
        logger.error(f"Error getting employee name for user {user.id}: {e}", exc_info=True)

    return None


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Авторизация пользователя.

    Возвращает JWT токен (срок действия 5 дней), user_id (внутренний), роль и имя сотрудника.
    При ошибке возвращает HTTP 200 с success=false (не 401).
    """
    user = db.query(User).filter(User.login == request.login).first()
    if not user or not verify_password(request.password, user.password):
        return {"success": False, "message": "Invalid credentials"}

    access_token = create_access_token(
        data={"sub": user.login},
        expires_delta=timedelta(days=5),
    )

    name = _get_employee_name_for_user(db=db, user=user)

    return {
        "success": True,
        "message": "Login successful",
        "user_id": user.id,
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.app_role,
        "name": name,
    }


@router.post("/register", response_model=LoginResponse)
def register(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Регистрация нового пользователя.

    Возвращает JWT токен и user_id (внутренний). При ошибке — HTTP 200 с success=false.
    """
    existing_user = db.query(User).filter(User.login == request.login).first()
    if existing_user:
        return {"success": False, "message": "User already exists"}

    hashed_password = hash_password(request.password)
    new_user = User(login=request.login, password=hashed_password)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token = create_access_token(
        data={"sub": new_user.login},
        expires_delta=timedelta(days=5),
    )

    # Для только что зарегистрированного пользователя имени сотрудника, как правило, ещё нет
    return {
        "success": True,
        "message": "User registered successfully",
        "user_id": new_user.id,
        "access_token": access_token,
        "token_type": "bearer",
        "role": None,
        "name": None,
    }


@router.put("/change-password")
def change_password(
    request: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Сменить пароль сотруднику (по employee_id).

    Требуется авторизация (manager или owner).
    """
    employee = db.query(Employees).filter(Employees.id == request.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if not employee.iiko_id:
        raise HTTPException(status_code=422, detail="Employee has no iiko_id, cannot locate user account")

    user = db.query(User).filter(User.iiko_id == employee.iiko_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found for this employee")

    user.password = hash_password(request.new_password)
    db.commit()

    logger.info(f"Password changed for employee {request.employee_id} (user {user.id}) by user {current_user.id}")
    return {"success": True, "message": "Password updated successfully"}
