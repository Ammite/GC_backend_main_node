from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user
from database.database import get_db
from services.employees.employees_service import get_employees
from schemas.employees import EmployeeArrayResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["employees"])


@router.get("/employees", response_model=EmployeeArrayResponse)
def list_employees(
    name: Optional[str] = Query(default=None),
    login: Optional[str] = Query(default=None),
    organization_id: Optional[int] = Query(default=None),
    role_code: Optional[str] = Query(default=None),
    deleted: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    employees = get_employees(
        db=db,
        name=name,
        login=login,
        organization_id=organization_id,
        role_code=role_code,
        deleted=deleted,
        limit=limit,
        offset=offset,
    )
    return {
        "success": True,
        "message": "got employees",
        "employees": employees,
    }
