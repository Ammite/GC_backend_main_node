from sqlalchemy.orm import Session
from typing import List, Optional
from models.employees import Employees
from schemas.employees import EmployeeResponse


def get_employees(
    db: Session,
    name: Optional[str] = None,
    login: Optional[str] = None,
    organization_id: Optional[int] = None,
    role_code: Optional[str] = None,
    deleted: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[EmployeeResponse]:
    query = db.query(Employees)
    
    if name:
        query = query.filter(Employees.name.ilike(f"%{name}%"))
    if login:
        query = query.filter(Employees.login.ilike(f"%{login}%"))
    if organization_id is not None:
        query = query.filter(Employees.preferred_organization_id == organization_id)
    if role_code:
        query = query.filter(Employees.main_role_code == role_code)
    if deleted is not None:
        query = query.filter(Employees.deleted == deleted)

    employees = query.offset(offset).limit(limit).all()
    return [
        EmployeeResponse(
            id=e.id,
            iiko_id=e.iiko_id,
            name=e.name,
            login=e.login,
            first_name=e.first_name,
            last_name=e.last_name,
            phone=e.phone,
            email=e.email,
            main_role_code=e.main_role_code,
            preferred_organization_id=e.preferred_organization_id,
            deleted=e.deleted,
        )
        for e in employees
    ]
