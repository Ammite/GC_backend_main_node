from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import logging

from utils.security import get_current_user
from database.database import get_db
from services.departments.departments_service import (
    sync_departments_from_iiko,
    get_all_departments,
    get_department_by_id,
    get_department_by_iiko_id,
)
from schemas.departments import (
    DepartmentResponse,
    DepartmentListResponse,
    SyncDepartmentsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["departments"])


@router.post("/departments/sync", response_model=SyncDepartmentsResponse)
async def sync_departments(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Синхронизировать департаменты из iiko API.
    
    Получает все департаменты (type=DEPARTMENT) из iiko и сохраняет/обновляет их в БД.
    """
    try:
        result = await sync_departments_from_iiko(db=db)
        return SyncDepartmentsResponse(**result)
    except Exception as e:
        logger.error(f"Ошибка синхронизации департаментов: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.get("/departments", response_model=DepartmentListResponse)
def get_departments(
    is_active: Optional[bool] = Query(default=None, description="Фильтр по активности"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Получить список всех департаментов.
    
    **Query Parameters:**
    - `is_active` (optional): Фильтр по активности (true/false)
    """
    try:
        departments = get_all_departments(db=db, is_active=is_active)
        return DepartmentListResponse(
            success=True,
            message=f"Получено {len(departments)} департаментов",
            departments=[DepartmentResponse.model_validate(dept) for dept in departments],
            total=len(departments),
        )
    except Exception as e:
        logger.error(f"Ошибка получения департаментов: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.get("/departments/{department_id}", response_model=DepartmentResponse)
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Получить департамент по ID.
    
    **Path Parameters:**
    - `department_id`: ID департамента в нашей БД
    """
    try:
        department = get_department_by_id(db=db, department_id=department_id)
        if not department:
            raise HTTPException(status_code=404, detail=f"Department with id {department_id} not found")
        return DepartmentResponse.model_validate(department)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения департамента: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.get("/departments/iiko/{iiko_id}", response_model=DepartmentResponse)
def get_department_by_iiko_id_endpoint(
    iiko_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Получить департамент по iiko_id.
    
    **Path Parameters:**
    - `iiko_id`: ID департамента в iiko
    """
    try:
        department = get_department_by_iiko_id(db=db, iiko_id=iiko_id)
        if not department:
            raise HTTPException(status_code=404, detail=f"Department with iiko_id {iiko_id} not found")
        return DepartmentResponse.model_validate(department)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения департамента: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )
