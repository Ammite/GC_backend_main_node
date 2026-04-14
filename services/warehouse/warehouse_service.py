"""
Сервис для управления складскими документами (CRUD операции)
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import List, Optional
from datetime import datetime
from models.warehouse import WarehouseDocument, WarehouseDocumentItem
from models.transaction import Transaction
from models.account import Account
from models.item import Item
from schemas.warehouse import (
    CreateWarehouseDocumentRequest,
    WarehouseDocumentItemRequest,
    WarehouseDocumentResponse,
    WarehouseDocumentItemResponse,
    WarehouseDocumentsListResponse,
    WarehouseDocumentDetailResponse,
    UpdateWarehouseDocumentRequest,
)
import logging

logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> datetime:
    """Парсинг даты из строки DD.MM.YYYY или ISO формата"""
    try:
        # Пробуем формат DD.MM.YYYY
        if "." in date_str and len(date_str.split(".")) == 3:
            return datetime.strptime(date_str, "%d.%m.%Y")
        # Пробуем ISO формат
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception as e:
        logger.error(f"Ошибка парсинга даты {date_str}: {e}")
        raise ValueError(f"Неверный формат даты: {date_str}")


def format_date(dt: datetime) -> str:
    """Форматирование даты в ISO формат"""
    return dt.isoformat()


def _create_transactions_for_warehouse_document(
    db: Session,
    document: WarehouseDocument,
    items: List[WarehouseDocumentItemRequest],
    total_amount: float,
) -> None:
    """Создать транзакции для складского документа"""
    try:
        # Ищем счет склада (тип STORE)
        store_account = db.query(Account).filter(
            Account.type == "STORE",
            Account.deleted == False
        ).first()
        
        if not store_account:
            logger.warning("Не найден счет типа STORE для создания транзакции складского документа")
            return
        
        # Создаем транзакцию для каждой позиции документа
        for item_data in items:
            amount = item_data.amount
            if amount is None:
                if item_data.price is not None:
                    amount = float(item_data.price) * float(item_data.quantity)
                else:
                    amount = 0.0
            
            if amount == 0:
                continue
            
            # Определяем направление транзакции
            if document.document_type == "RECEIPT":
                amount_in = amount
                amount_out = 0
                transaction_side = "Дебет"
            else:  # WRITEOFF
                amount_in = 0
                amount_out = amount
                transaction_side = "Кредит"
            
            # Создаем транзакцию
            transaction = Transaction(
                document=document.document_number,
                amount=amount,
                amount_in=amount_in,
                amount_out=amount_out,
                transaction_side=transaction_side,
                account_id=store_account.iiko_id,
                account_name=store_account.name,
                account_type=store_account.type,
                date_typed=document.date,
                date_time_typed=document.date,
                organization_id=document.organization_id,
                comment=f"Складской документ {document.document_type}: {document.comment or ''}",
            )
            
            # Если указан товар, добавляем информацию о товаре
            if item_data.item_iiko_id:
                from models.item import Item
                item = db.query(Item).filter(Item.iiko_id == item_data.item_iiko_id).first()
                if item:
                    transaction.product_id = item.iiko_id
                    transaction.product_name = item.name
                    transaction.product_category = item.category.name if item.category else None
            
            db.add(transaction)
        
        db.commit()
        logger.debug(f"Создано транзакций для складского документа {document.id}: {len(items)}")
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка создания транзакций для складского документа {document.id}: {e}")
        raise


def generate_document_number(db: Session, document_type: str) -> str:
    """Генерация номера документа, если не указан"""
    # Простая генерация: тип + дата + порядковый номер
    today = datetime.now().date()
    date_str = today.strftime("%Y%m%d")
    
    # Получаем количество документов за сегодня
    count = db.query(WarehouseDocument).filter(
        and_(
            WarehouseDocument.document_type == document_type,
            func.date(WarehouseDocument.date) == today
        )
    ).count()
    
    return f"{document_type}-{date_str}-{count + 1:04d}"


def create_warehouse_document(
    db: Session,
    document_data: CreateWarehouseDocumentRequest,
    user_id: Optional[int] = None,
) -> WarehouseDocument:
    """Создать новый складской документ"""
    try:
        document_date = parse_date(document_data.date)
        document_number = document_data.document_number or generate_document_number(db, document_data.document_type)
        
        # Создаем документ
        document = WarehouseDocument(
            document_type=document_data.document_type,
            document_number=document_number,
            date=document_date,
            organization_id=document_data.organization_id,
            store_id=document_data.store_id,
            comment=document_data.comment,
            created_by=user_id,
        )
        
        db.add(document)
        db.flush()  # Получаем ID документа
        
        # Создаем позиции документа
        total_amount = 0.0
        for item_data in document_data.items:
            # Рассчитываем сумму, если не указана
            amount = item_data.amount
            if amount is None:
                if item_data.price is not None:
                    amount = float(item_data.price) * float(item_data.quantity)
                else:
                    amount = 0.0
            
            expiry_date = None
            if item_data.expiry_date:
                expiry_date = parse_date(item_data.expiry_date)
            
            item = WarehouseDocumentItem(
                document_id=document.id,
                item_id=item_data.item_id,
                item_iiko_id=item_data.item_iiko_id,
                item_name=item_data.item_name,
                quantity=item_data.quantity,
                price=item_data.price,
                amount=amount,
                batch_number=item_data.batch_number,
                expiry_date=expiry_date,
            )
            
            db.add(item)
            total_amount += float(amount)
        
        db.commit()
        db.refresh(document)
        
        # Создаем транзакции для каждой позиции документа
        try:
            _create_transactions_for_warehouse_document(db, document, document_data.items, total_amount)
        except Exception as trans_err:
            logger.warning(f"Не удалось создать транзакции для складского документа {document.id}: {trans_err}")
            # Не прерываем выполнение, документ уже создан
        
        logger.info(f"Создан складской документ ID={document.id}, тип={document_data.document_type}, номер={document_number}")
        return document
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка создания складского документа: {e}")
        raise


def get_warehouse_documents(
    db: Session,
    organization_id: Optional[int] = None,
    document_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> WarehouseDocumentsListResponse:
    """Получить список складских документов с фильтрацией"""
    try:
        query = db.query(WarehouseDocument)
        
        # Фильтры
        if organization_id:
            query = query.filter(WarehouseDocument.organization_id == organization_id)
        if document_type:
            query = query.filter(WarehouseDocument.document_type == document_type)
        if from_date:
            from_dt = parse_date(from_date)
            query = query.filter(WarehouseDocument.date >= from_dt)
        if to_date:
            to_dt = parse_date(to_date)
            to_dt = to_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(WarehouseDocument.date <= to_dt)
        
        # Общее количество
        total = query.count()
        
        # Сортировка и пагинация
        documents = query.order_by(WarehouseDocument.date.desc()).offset(offset).limit(limit).all()
        
        # Собираем все item_iiko_id для оптимизации запросов
        all_item_iiko_ids = set()
        document_items_map = {}
        
        for doc in documents:
            items = db.query(WarehouseDocumentItem).filter(
                WarehouseDocumentItem.document_id == doc.id
            ).all()
            document_items_map[doc.id] = items
            for item in items:
                if item.item_iiko_id and not item.item_name:
                    all_item_iiko_ids.add(item.item_iiko_id)
        
        # Загружаем все товары одним запросом
        items_dict = {}
        if all_item_iiko_ids:
            items_from_db = db.query(Item).filter(Item.iiko_id.in_(all_item_iiko_ids)).all()
            items_dict = {item.iiko_id: item.name for item in items_from_db}
        
        document_responses = []
        for doc in documents:
            items = document_items_map[doc.id]
            
            item_responses = []
            for item in items:
                # Если есть item_iiko_id, но нет item_name, используем название из загруженных товаров
                item_name = item.item_name
                if not item_name and item.item_iiko_id:
                    item_name = items_dict.get(item.item_iiko_id)
                
                item_responses.append(
                    WarehouseDocumentItemResponse(
                        id=item.id,
                        document_id=item.document_id,
                        item_id=item.item_id,
                        item_iiko_id=item.item_iiko_id,
                        item_name=item_name,
                        quantity=float(item.quantity),
                        price=float(item.price) if item.price else None,
                        amount=float(item.amount) if item.amount else None,
                        batch_number=item.batch_number,
                        expiry_date=format_date(item.expiry_date) if item.expiry_date else None,
                        created_at=format_date(item.created_at),
                        updated_at=format_date(item.updated_at),
                    )
                )
            
            document_responses.append(
                WarehouseDocumentResponse(
                    id=doc.id,
                    iiko_id=doc.iiko_id,
                    document_type=doc.document_type,
                    document_number=doc.document_number,
                    date=format_date(doc.date),
                    organization_id=doc.organization_id,
                    store_id=doc.store_id,
                    created_by=doc.created_by,
                    comment=doc.comment,
                    created_at=format_date(doc.created_at),
                    updated_at=format_date(doc.updated_at),
                    items=item_responses,
                )
            )
        
        return WarehouseDocumentsListResponse(
            success=True,
            message=f"Найдено документов: {len(document_responses)}",
            documents=document_responses,
            total=total,
        )
    except Exception as e:
        logger.error(f"Ошибка получения списка складских документов: {e}")
        raise


def get_warehouse_document_by_id(
    db: Session,
    document_id: int,
) -> Optional[WarehouseDocumentDetailResponse]:
    """Получить складской документ по ID"""
    try:
        document = db.query(WarehouseDocument).filter(WarehouseDocument.id == document_id).first()
        
        if not document:
            return None
        
        # Загружаем позиции документа
        items = db.query(WarehouseDocumentItem).filter(
            WarehouseDocumentItem.document_id == document.id
        ).all()
        
        # Собираем item_iiko_id для оптимизации запросов
        item_iiko_ids = [item.item_iiko_id for item in items if item.item_iiko_id and not item.item_name]
        
        # Загружаем все товары одним запросом
        items_dict = {}
        if item_iiko_ids:
            items_from_db = db.query(Item).filter(Item.iiko_id.in_(item_iiko_ids)).all()
            items_dict = {item.iiko_id: item.name for item in items_from_db}
        
        item_responses = []
        for item in items:
            # Если есть item_iiko_id, но нет item_name, используем название из загруженных товаров
            item_name = item.item_name
            if not item_name and item.item_iiko_id:
                item_name = items_dict.get(item.item_iiko_id)
            
            item_responses.append(
                WarehouseDocumentItemResponse(
                    id=item.id,
                    document_id=item.document_id,
                    item_id=item.item_id,
                    item_iiko_id=item.item_iiko_id,
                    item_name=item_name,
                    quantity=float(item.quantity),
                    price=float(item.price) if item.price else None,
                    amount=float(item.amount) if item.amount else None,
                    batch_number=item.batch_number,
                    expiry_date=format_date(item.expiry_date) if item.expiry_date else None,
                    created_at=format_date(item.created_at),
                    updated_at=format_date(item.updated_at),
                )
            )
        
        document_response = WarehouseDocumentResponse(
            id=document.id,
            iiko_id=document.iiko_id,
            document_type=document.document_type,
            document_number=document.document_number,
            date=format_date(document.date),
            organization_id=document.organization_id,
            store_id=document.store_id,
            created_by=document.created_by,
            comment=document.comment,
            created_at=format_date(document.created_at),
            updated_at=format_date(document.updated_at),
            items=item_responses,
        )
        
        return WarehouseDocumentDetailResponse(
            success=True,
            message="Документ найден",
            document=document_response,
        )
    except Exception as e:
        logger.error(f"Ошибка получения складского документа ID={document_id}: {e}")
        raise


def update_warehouse_document(
    db: Session,
    document_id: int,
    document_data: UpdateWarehouseDocumentRequest,
) -> WarehouseDocument:
    """Обновить складской документ"""
    try:
        document = db.query(WarehouseDocument).filter(WarehouseDocument.id == document_id).first()
        
        if not document:
            raise ValueError(f"Складской документ с ID={document_id} не найден")
        
        # Обновляем поля документа
        if document_data.document_type is not None:
            document.document_type = document_data.document_type
        if document_data.document_number is not None:
            document.document_number = document_data.document_number
        if document_data.date is not None:
            document.date = parse_date(document_data.date)
        if document_data.store_id is not None:
            document.store_id = document_data.store_id
        if document_data.comment is not None:
            document.comment = document_data.comment
        
        # Если указаны позиции, заменяем все позиции
        if document_data.items is not None:
            # Удаляем старые позиции
            db.query(WarehouseDocumentItem).filter(
                WarehouseDocumentItem.document_id == document_id
            ).delete()
            
            # Создаем новые позиции
            for item_data in document_data.items:
                amount = item_data.amount
                if amount is None:
                    if item_data.price is not None:
                        amount = float(item_data.price) * float(item_data.quantity)
                    else:
                        amount = 0.0
                
                expiry_date = None
                if item_data.expiry_date:
                    expiry_date = parse_date(item_data.expiry_date)
                
                item = WarehouseDocumentItem(
                    document_id=document.id,
                    item_id=item_data.item_id,
                    item_iiko_id=item_data.item_iiko_id,
                    item_name=item_data.item_name,
                    quantity=item_data.quantity,
                    price=item_data.price,
                    amount=amount,
                    batch_number=item_data.batch_number,
                    expiry_date=expiry_date,
                )
                
                db.add(item)
        
        document.updated_at = datetime.now()
        
        db.commit()
        db.refresh(document)
        
        logger.info(f"Обновлен складской документ ID={document_id}")
        return document
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка обновления складского документа ID={document_id}: {e}")
        raise


def delete_warehouse_document(
    db: Session,
    document_id: int,
) -> bool:
    """Удалить складской документ"""
    try:
        document = db.query(WarehouseDocument).filter(WarehouseDocument.id == document_id).first()
        
        if not document:
            raise ValueError(f"Складской документ с ID={document_id} не найден")
        
        # Позиции удалятся автоматически благодаря cascade="all, delete-orphan"
        db.delete(document)
        db.commit()
        
        logger.info(f"Удален складской документ ID={document_id}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка удаления складского документа ID={document_id}: {e}")
        raise

