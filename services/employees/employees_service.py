from sqlalchemy.orm import Session
from typing import List, Optional
from models.employees import Employees
from schemas.employees import EmployeeResponse, EmployeeWithShiftsResponse


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
    """
    
    array of objects:
        {
            id: "1",
            name: "Аслан Аманов",
            role: "Оффицант",
            avatarUrl:
                "https://api.builder.io/api/v1/image/assets/TEMP/3a1a0f795dd6cebc375ac2f7fbeab6a0d791efc8?width=80",
            totalAmount: "56 897 тг",
            shiftTime: "00:56:25",
            isActive: true,
        }
    """
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

def get_employees_with_shifts(
    db: Session,
    organization_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[EmployeeWithShiftsResponse]:
    """
    """
    employees = db.query(Employees).offset(offset).limit(limit).all()


    return [
        EmployeeWithShiftsResponse(
            id=e.id,
            name=e.name,
            deleted=e.deleted,
            role="", # TODO: get role with employee_id
            avatarUrl="",
            totalAmount="", # TODO: get total amount with employee_id
            shiftTime="", # TODO: get shift time with employee_id
            isActive=False, # TODO: get is active with employee_id
        )
        for e in employees
    ]