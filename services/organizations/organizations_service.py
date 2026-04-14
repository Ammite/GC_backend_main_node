from sqlalchemy.orm import Session
from typing import List, Optional
from utils.cache import cached
from models.organization import Organization
from schemas.organizations import OrganizationResponse


# @cached(ttl_seconds=900, key_prefix="organizations")  # Кэш на 15 минут - ВРЕМЕННО ОТКЛЮЧЕН
def get_organizations(
    db: Session,
    name: Optional[str] = None,
    code: Optional[str] = None,
    is_active: Optional[bool] = None,
    include_legacy: bool = False,
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
    if not include_legacy:
        # По умолчанию скрываем legacy-организации (остатки от старой iiko до миграции
        # ~28-29.01.2026). Чтобы их вернуть, передавай include_legacy=true.
        query = query.filter(Organization.is_legacy == False)  # noqa: E712

    orgs = query.offset(offset).limit(limit).all()
    return [
        OrganizationResponse(
            id=o.id,
            name=o.name,
            code=o.code,
            is_active=o.is_active,
            address=o.address,
            latitude=float(o.latitude) if o.latitude is not None else None,
            longitude=float(o.longitude) if o.longitude is not None else None,
        )
        for o in orgs
    ]
