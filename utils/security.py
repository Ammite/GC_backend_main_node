import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database.database import get_db
from models import User
import config

logger = logging.getLogger(__name__)


JWT_SECRET_KEY = config.JWT_SECRET_KEY
JWT_ALGORITHM = config.JWT_ALGORITHM
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed_password: str) -> bool:
    return hash_password(password) == hashed_password

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    login = payload["sub"]
    user: User | None = db.query(User).filter(User.login == login).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


# ============================================================================
# Role-based access control (task 10)
# ============================================================================

ROLE_HIERARCHY = {
    "Официант": 1,
    "Менеджер": 2,
    "Владелец": 3,
}


def _user_role_level(user: User) -> int:
    return ROLE_HIERARCHY.get(user.app_role or "", 0)


def require_role(min_role: str):
    """Минимальная роль для эндпоинта. Владелец проходит везде.

    Иерархия: Официант < Менеджер < Владелец.
    Флаг config.ENFORCE_ROLES=false отключает проверку (для аварийного отката).
    """
    required_level = ROLE_HIERARCHY.get(min_role, 99)

    def dep(user: User = Depends(get_current_user)) -> User:
        if not config.ENFORCE_ROLES:
            return user
        if _user_role_level(user) < required_level:
            logger.warning(
                f"[require_role] DENY user_id={user.id} login={user.login} "
                f"role={user.app_role!r} требуется {min_role!r}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Требуется роль: {min_role}",
            )
        return user

    return dep


def require_self_or_role(waiter_id_param: str, min_role: str):
    """Self-only (по {waiter_id} в URL) ИЛИ роль >= min_role.

    Используется на /waiter/{waiter_id}/* — официант видит только свои данные,
    менеджер/владелец — всех.

    waiter_id_param: имя path-параметра ('waiter_id' обычно).
    Сравнение: requested == user.id (фронт шлёт User.id).
    """
    required_level = ROLE_HIERARCHY.get(min_role, 99)

    def dep(request: Request, user: User = Depends(get_current_user)) -> User:
        if not config.ENFORCE_ROLES:
            return user

        raw = request.path_params.get(waiter_id_param)
        try:
            requested_id = int(raw) if raw is not None else None
        except (TypeError, ValueError):
            requested_id = None

        # Self ok — либо по User.id, либо по своему Employee.id
        # (фронт иногда подставляет employee_id из /profile вместо user.id)
        if requested_id is not None and requested_id == user.id:
            return user
        if requested_id is not None and user.iiko_id:
            from database.database import get_db as _get_db
            from models.employees import Employees
            db_session = next(_get_db())
            try:
                emp = (
                    db_session.query(Employees)
                    .filter(Employees.iiko_id == user.iiko_id)
                    .first()
                )
                if emp and emp.id == requested_id:
                    return user
            finally:
                db_session.close()

        # Иначе нужна роль >=
        if _user_role_level(user) >= required_level:
            return user

        logger.warning(
            f"[require_self_or_role] DENY user_id={user.id} login={user.login} "
            f"role={user.app_role!r} requested={requested_id} требуется self или {min_role!r}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к чужим данным",
        )

    return dep
