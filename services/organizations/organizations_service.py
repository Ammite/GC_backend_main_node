from sqlalchemy.orm import Session
from typing import List, Optional
from models.organization import Organization
from schemas.organizations import OrganizationResponse


def get_organizations(
    db: Session,
    name: Optional[str] = None,
    code: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[OrganizationResponse]:
    query = db.query(Organization)
    if name:
        query = query.filter(Organization.name.ilike(f"%{name}%"))
    if code:
        query = query.filter(Organization.code.ilike(f"%{code}%"))
    if is_active is not None:
        query = query.filter(Organization.is_active == is_active)

    orgs = query.offset(offset).limit(limit).all()
    return [
        OrganizationResponse(
            id=o.id,
            name=o.name,
            code=o.code,
            is_active=o.is_active,
        )
        for o in orgs
    ]
