from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from models.department import Department
from services.iiko.iiko_service import IikoService

logger = logging.getLogger(__name__)

iiko_service = IikoService()


async def sync_departments_from_iiko(db: Session) -> dict:
    """
    Синхронизация департаментов из iiko API.
    
    Получает все департаменты (type=DEPARTMENT) из iiko и сохраняет/обновляет их в БД.
    
    Returns:
        dict с результатами синхронизации:
        {
            "success": bool,
            "message": str,
            "created": int,
            "updated": int,
            "total": int
        }
    """
    try:
        # Получаем департаменты из iiko
        logger.info("Начало синхронизации департаментов из iiko API")
        iiko_departments = await iiko_service.get_server_departments()
        
        if not iiko_departments:
            return {
                "success": False,
                "message": "Не удалось получить департаменты из iiko API",
                "created": 0,
                "updated": 0,
                "total": 0
            }
        
        created_count = 0
        updated_count = 0
        
        # Обрабатываем каждый департамент
        for dept_data in iiko_departments:
            iiko_id = dept_data.get('id')
            if not iiko_id:
                logger.warning(f"Пропущен департамент без id: {dept_data}")
                continue
            
            # Ищем существующий департамент
            existing_dept = db.query(Department).filter(Department.iiko_id == iiko_id).first()
            
            if existing_dept:
                # Обновляем существующий
                existing_dept.parent_id = dept_data.get('parentId')
                existing_dept.code = dept_data.get('code')
                existing_dept.name = dept_data.get('name') or ''
                existing_dept.taxpayer_id_number = dept_data.get('taxpayerIdNumber')
                existing_dept.updated_at = datetime.now()
                updated_count += 1
                logger.debug(f"Обновлен департамент: {iiko_id} - {existing_dept.name}")
            else:
                # Создаем новый
                new_dept = Department(
                    iiko_id=iiko_id,
                    parent_id=dept_data.get('parentId'),
                    code=dept_data.get('code'),
                    name=dept_data.get('name') or '',
                    taxpayer_id_number=dept_data.get('taxpayerIdNumber'),
                    is_active=True,
                )
                db.add(new_dept)
                created_count += 1
                logger.debug(f"Создан департамент: {iiko_id} - {new_dept.name}")
        
        db.commit()
        
        total_count = len(iiko_departments)
        logger.info(
            f"Синхронизация департаментов завершена: создано {created_count}, "
            f"обновлено {updated_count}, всего {total_count}"
        )
        
        return {
            "success": True,
            "message": f"Синхронизация завершена: создано {created_count}, обновлено {updated_count}",
            "created": created_count,
            "updated": updated_count,
            "total": total_count
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка синхронизации департаментов: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"Ошибка синхронизации: {str(e)}",
            "created": 0,
            "updated": 0,
            "total": 0
        }


def get_all_departments(
    db: Session,
    is_active: Optional[bool] = None,
) -> List[Department]:
    """
    Получить все департаменты из БД.
    
    Args:
        db: сессия БД
        is_active: фильтр по активности (None = все)
    
    Returns:
        Список департаментов
    """
    query = db.query(Department)
    
    if is_active is not None:
        query = query.filter(Department.is_active == is_active)
    
    return query.order_by(Department.name).all()


def get_department_by_id(db: Session, department_id: int) -> Optional[Department]:
    """
    Получить департамент по ID.
    
    Args:
        db: сессия БД
        department_id: ID департамента в нашей БД
    
    Returns:
        Department или None
    """
    return db.query(Department).filter(Department.id == department_id).first()


def get_department_by_iiko_id(db: Session, iiko_id: str) -> Optional[Department]:
    """
    Получить департамент по iiko_id.
    
    Args:
        db: сессия БД
        iiko_id: ID департамента в iiko
    
    Returns:
        Department или None
    """
    return db.query(Department).filter(Department.iiko_id == iiko_id).first()
