from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime
from models.restaurant_sections import RestaurantSection
from models.tables import Table
from models.d_order import DOrder
from models.terminal_groups import TerminalGroup
from schemas.rooms import RoomResponse, TableResponse


def get_rooms(
    db: Session,
    organization_id: Optional[int] = None,
) -> List[RoomResponse]:
    """
    Получить список помещений (секций ресторана)
    
    Args:
        db: сессия БД
        organization_id: ID организации (фильтр)
    
    Returns:
        Список помещений с их столами
    """
    # Получаем секции ресторана
    query = db.query(RestaurantSection)
    
    if organization_id:
        # Фильтруем по организации через terminal_group
        query = query.join(
            TerminalGroup, TerminalGroup.id == RestaurantSection.terminal_group_id
        ).filter(TerminalGroup.organization_id == organization_id)
    
    sections = query.all()
    
    rooms = []
    for section in sections:
        # Получаем столы для этой секции
        tables_query = db.query(Table).filter(
            and_(
                Table.section_id == section.id,
                Table.is_deleted == False
            )
        )
        tables = tables_query.all()
        
        # Формируем список столов
        table_responses = []
        for table in tables:
            # Проверяем, есть ли активный заказ на этом столе
            # TODO: Добавить связь между столом и заказом
            # Пока используем примерную логику
            status = "available"  # По умолчанию доступен
            current_order_id = None
            assigned_employee_id = None
            
            table_response = TableResponse(
                id=str(table.id),
                number=str(table.number),
                roomId=str(section.id),
                roomName=section.name,
                capacity=4,  # TODO: Добавить поле capacity в модель Table
                status=status,
                currentOrderId=current_order_id,
                assignedEmployeeId=assigned_employee_id
            )
            table_responses.append(table_response)
        
        # Формируем помещение
        room = RoomResponse(
            id=str(section.id),
            name=section.name,
            capacity=len(tables) * 4,  # Примерная вместимость
            tables=table_responses
        )
        rooms.append(room)
    
    return rooms


def get_tables(
    db: Session,
    room_id: Optional[int] = None,
    status: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> List[TableResponse]:
    """
    Получить список столов
    
    Args:
        db: сессия БД
        room_id: ID помещения (фильтр)
        status: статус стола ("available" | "occupied" | "disabled" | "all")
        organization_id: ID организации (фильтр)
    
    Returns:
        Список столов
    """
    # Получаем столы
    query = db.query(Table).filter(Table.is_deleted == False)
    
    if room_id:
        query = query.filter(Table.section_id == room_id)
    
    if organization_id:
        # Фильтруем по организации через section и terminal_group
        query = query.join(
            RestaurantSection, RestaurantSection.id == Table.section_id
        ).join(
            TerminalGroup, TerminalGroup.id == RestaurantSection.terminal_group_id
        ).filter(TerminalGroup.organization_id == organization_id)
    
    tables = query.all()
    
    # Формируем список столов
    table_responses = []
    for table in tables:
        # Получаем секцию (помещение)
        section = db.query(RestaurantSection).filter(
            RestaurantSection.id == table.section_id
        ).first()
        
        # Проверяем статус стола
        # TODO: Добавить реальную логику проверки статуса
        table_status = "available"  # По умолчанию
        current_order_id = None
        assigned_employee_id = None
        
        # Фильтруем по статусу, если указан
        if status and status != "all":
            if table_status != status:
                continue
        
        table_response = TableResponse(
            id=str(table.id),
            number=str(table.number),
            roomId=str(section.id) if section else None,
            roomName=section.name if section else None,
            capacity=4,  # TODO: Добавить поле capacity в модель Table
            status=table_status,
            currentOrderId=current_order_id,
            assignedEmployeeId=assigned_employee_id
        )
        table_responses.append(table_response)
    
    return table_responses

