from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging

from utils.security import get_current_user, require_role
from database.database import get_db
from models import Conception, Supplier
from schemas.reference import (
    ConceptionResponse,
    ConceptionListResponse,
    SyncConceptionsResponse,
    SupplierResponse,
    SupplierListResponse,
    SyncSuppliersResponse,
)
from services.warehouse.balance_service import (
    sync_conceptions_from_iiko,
    sync_suppliers_from_iiko,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["conceptions"])
router_suppliers = APIRouter(prefix="", tags=["suppliers"])


@router.post("/conceptions/sync", response_model=SyncConceptionsResponse)
async def sync_conceptions_endpoint(
    db: Session = Depends(get_db),
    user=Depends(require_role("Владелец")),
):
    """
    Синхронизировать концепции из iiko Server API.

    Использует `iiko_service.get_server_conceptions()` и сохраняет/обновляет
    записи в таблице `conceptions`.
    """
    try:
        result = await sync_conceptions_from_iiko(db=db)
        return SyncConceptionsResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            synced=result.get("synced", 0),
        )
    except Exception as e:
        logger.error(f"Ошибка синхронизации концепций: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.get("/conceptions", response_model=ConceptionListResponse)
def get_conceptions_endpoint(
    is_active: Optional[bool] = Query(
        default=None, description="Фильтр по активности (если поле используется)"
    ),
    db: Session = Depends(get_db),
    user=Depends(require_role("Менеджер")),
):
    """
    Получить список всех концепций.

    Возвращает базовую информацию: `id`, `iiko_id`, `name`, `code`, `comment`.
    """
    try:
        query = db.query(Conception)
        if is_active is not None and hasattr(Conception, "is_active"):
            query = query.filter(Conception.is_active == is_active)

        conceptions = query.order_by(Conception.name).all()
        return ConceptionListResponse(
            success=True,
            message=f"Получено концепций: {len(conceptions)}",
            conceptions=[ConceptionResponse.model_validate(c) for c in conceptions],
            total=len(conceptions),
        )
    except Exception as e:
        logger.error(f"Ошибка получения концепций: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router_suppliers.post("/suppliers/sync", response_model=SyncSuppliersResponse)
async def sync_suppliers_endpoint(
    db: Session = Depends(get_db),
    user=Depends(require_role("Владелец")),
):
    """
    Синхронизировать поставщиков из iiko Server API.

    Использует `iiko_service.get_server_suppliers()` и сохраняет/обновляет
    записи в таблице `suppliers`.
    """
    try:
        result = await sync_suppliers_from_iiko(db=db)
        return SyncSuppliersResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            synced=result.get("synced", 0),
        )
    except Exception as e:
        logger.error(f"Ошибка синхронизации поставщиков: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router_suppliers.get("/suppliers", response_model=SupplierListResponse)
def get_suppliers_endpoint(
    db: Session = Depends(get_db),
    user=Depends(require_role("Менеджер")),
):
    """
    Получить список всех поставщиков.

    Возвращает базовую информацию: `id`, `iiko_id`, `name`, `code`, `comment`.
    """
    try:
        suppliers = db.query(Supplier).order_by(Supplier.name).all()
        return SupplierListResponse(
            success=True,
            message=f"Получено поставщиков: {len(suppliers)}",
            suppliers=[SupplierResponse.model_validate(s) for s in suppliers],
            total=len(suppliers),
        )
    except Exception as e:
        logger.error(f"Ошибка получения поставщиков: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )
