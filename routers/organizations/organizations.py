from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user
from database.database import get_db
from services.organizations.organizations_service import get_organizations
from schemas.organizations import OrganizationArrayResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["organizations"])


@router.get("/organizations", response_model=OrganizationArrayResponse)
def list_organizations(
    name: Optional[str] = Query(default=None),
    code: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    organizations = get_organizations(
        db=db,
        name=name,
        code=code,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return {
        "success": True,
        "message": "got organizations",
        "organizations": organizations,
    }
