from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from utils.security import get_current_user, require_role
from database.database import get_db
from schemas.warehouse import (
    SimpleWriteoffDocumentRequest,
    CreateWriteoffDocumentResponse,
    AccountResponse,
    AccountsListResponse,
    SimpleIncomingInvoiceRequest,
    SimpleOutgoingInvoiceRequest,
    SimpleInventoryRequest,
    CreateWarehouseDocumentResponse,
    CreateWarehouseDocumentRequest,
    WarehouseDocumentItemRequest,
)
from schemas.pay_out import (
    CreatePayOutRequest,
    CreatePayOutResponse,
    PayOutTypeResponse,
    PayrollResponse,
    SyncPayOutTypesResponse,
)
from models.account import Account
from models.store import Store
from models.item import Item
from models.supplier import Supplier
from services.warehouse.writeoff_service import create_writeoff_document_in_iiko, DEFAULT_STORE_IIKO_ID as WRITEOFF_STORE_ID
from services.warehouse.invoice_service import (
    create_incoming_invoice_in_iiko,
    create_outgoing_invoice_in_iiko,
    create_inventory_in_iiko,
    DEFAULT_STORE_IIKO_ID
)
from services.cash.pay_out_service import create_pay_out_in_iiko
from services.iiko.iiko_service import IikoService
from schemas.warehouse import CreateWriteoffDocumentRequest, CreateWriteoffItemRequest
from models.conception import Conception
import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/writeoff", response_model=CreateWriteoffDocumentResponse)
async def create_writeoff_document_endpoint(
    document_data: SimpleWriteoffDocumentRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Создать акт списания
    
    **Request Body:**
    ```json
    {
      "storeId": 1,
      "conceptionId": 1,
      "account_id": 1,
      "date": "2025-01-15T14:30",
      "comment": "Комментарий к документу",
      "items": [
        {
          "id": 3021,
          "amount": 10.0,
          "price": 100.0,
          "sum": 1000.0
        }
      ]
    }
    ```
    
    **Поля:**
    - `storeId`: ID склада из таблицы stores (опционально, в TESTING_MODE используется фиксированный)
    - `conceptionId`: ID концепции из таблицы conceptions (опционально)
    - `account_id`: ID счета из таблицы account_list
    - `date`: Дата со временем (ISO формат или YYYY-MM-DDTHH:MM)
    - `comment`: Комментарий к документу (опционально)
    - `items`: Список позиций документа
      - `id`: ID товара из таблицы items
      - `amount`: Количество товара
      - `price`: Цена за единицу (опционально)
      - `sum`: Сумма позиции (опционально, если не указана — рассчитывается как price * amount)
    """
    try:
        # Валидация account_id
        account = db.query(Account).filter(Account.id == document_data.account_id).first()
        if not account:
            raise HTTPException(
                status_code=404,
                detail=f"Счет с ID {document_data.account_id} не найден"
            )

        # Валидация товаров и получение organization_id
        if not document_data.items:
            raise HTTPException(
                status_code=400,
                detail="Список позиций не может быть пустым"
            )
        
        # Проверяем все товары и получаем organization_id
        item_ids = [item.id for item in document_data.items]
        items = db.query(Item).filter(Item.id.in_(item_ids)).all()
        
        if len(items) != len(item_ids):
            found_ids = {item.id for item in items}
            missing_ids = [item_id for item_id in item_ids if item_id not in found_ids]
            raise HTTPException(
                status_code=404,
                detail=f"Товары с ID {missing_ids} не найдены"
            )
        
        # Проверяем, что все товары принадлежат одной организации
        organization_ids = {item.organization_id for item in items if item.organization_id}
        if len(organization_ids) > 1:
            raise HTTPException(
                status_code=400,
                detail="Все товары должны принадлежать одной организации"
            )
        
        organization_id = organization_ids.pop() if organization_ids else None
        
        # Преобразуем упрощенный запрос в полный CreateWriteoffDocumentRequest
        writeoff_items = [
            CreateWriteoffItemRequest(
                item_id=item.id,
                amount=item.amount,
                cost=item.sum if item.sum is not None else (item.price * item.amount if item.price is not None else None),
            )
            for item in document_data.items
        ]
        
        # Определяем store_iiko_id в зависимости от TESTING_MODE
        store_iiko_id = WRITEOFF_STORE_ID  # Фиксированное значение по умолчанию
        store_id_for_schema = None
        
        if config.TESTING_MODE:
            # В тестовом режиме всегда используем фиксированный склад
            temp_store = db.query(Store).filter(Store.is_active == True).first()
            if not temp_store:
                raise HTTPException(
                    status_code=404,
                    detail="Не найден активный склад в БД"
                )
            store_id_for_schema = temp_store.id
        else:
            # В продакшен режиме используем переданный storeId
            if document_data.storeId:
                store = db.query(Store).filter(Store.id == document_data.storeId).first()
                if not store:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Склад с ID {document_data.storeId} не найден"
                    )
                if not store.iiko_id:
                    raise HTTPException(
                        status_code=400,
                        detail=f"У склада с ID {document_data.storeId} не указан iiko_id"
                    )
                store_iiko_id = store.iiko_id
                store_id_for_schema = store.id
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Поле storeId обязательно в продакшен режиме (TESTING_MODE=false)"
                )
        
        # Определяем conception_iiko_id (опционально)
        conception_iiko_id = None
        if document_data.conceptionId:
            conception = db.query(Conception).filter(Conception.id == document_data.conceptionId).first()
            if not conception:
                raise HTTPException(
                    status_code=404,
                    detail=f"Концепция с ID {document_data.conceptionId} не найдена"
                )
            conception_iiko_id = conception.iiko_id

        writeoff_request = CreateWriteoffDocumentRequest(
            date_incoming=document_data.date,
            store_id=store_id_for_schema or 1,
            store_iiko_id=store_iiko_id,
            account_id=document_data.account_id,
            organization_id=organization_id or 1,
            status="NEW",
            comment=document_data.comment,
            items=writeoff_items,
            conception_iiko_id=conception_iiko_id,
        )
        
        # Создаем документ через существующий сервис
        result = await create_writeoff_document_in_iiko(
            db=db,
            document_data=writeoff_request,
            user_id=user.id if hasattr(user, 'id') else None
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Ошибка создания акта списания")
            )
        
        return CreateWriteoffDocumentResponse(
            success=True,
            message=result.get("message", "Акт списания успешно создан"),
            iiko_id=result.get("iiko_id"),
            document_id=result.get("document_id")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating writeoff document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/incoming-invoice", response_model=CreateWarehouseDocumentResponse)
async def create_incoming_invoice_endpoint(
    document_data: SimpleIncomingInvoiceRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Создать приходную накладную
    
    **Request Body:**
    ```json
    {
      "storeId": 1,
      "conceptionId": 1,
      "dateIncoming": "28.12.2025",
      "comment": "Комментарий к документу",
      "supplier": "707a8ef8-60c0-f07e-018a-f452cbcd454b",
      "invoice": "INV-001",
      "items": [
        {
          "id": 3181,
          "amount": 10.0,
          "price": 100.0,
          "sum": 1000.0
        }
      ]
    }
    ```
    
    **Поля:**
    - `storeId`: ID склада из таблицы stores (опционально, в TESTING_MODE используется фиксированный)
    - `conceptionId`: ID концепции из таблицы conceptions (опционально)
    - `dateIncoming`: Дата в формате dd.mm.YYYY
    - `comment`: Комментарий к документу (опционально)
    - `supplier`: iiko_id поставщика (опционально)
    - `invoice`: Номер счет-фактуры (опционально)
    - `items`: Список позиций документа
      - `id`: ID товара из таблицы items (нашего)
      - `amount`: Количество товара
      - `price`: Цена за единицу
      - `sum`: Сумма позиции
    """
    try:
        from services.warehouse.invoice_service import (
            DEFAULT_STORE_IIKO_ID,
            DEFAULT_CONCEPTION_IIKO_ID,
            DEFAULT_CONCEPTION_CODE,
            DEFAULT_SUPPLIER_IIKO_ID
        )
        
        # Валидация товаров и получение organization_id
        if not document_data.items:
            raise HTTPException(
                status_code=400,
                detail="Список позиций не может быть пустым"
            )
        
        # Проверяем все товары и получаем organization_id и iiko_id
        item_ids = [item.id for item in document_data.items]
        items = db.query(Item).filter(Item.id.in_(item_ids)).all()
        
        if len(items) != len(item_ids):
            found_ids = {item.id for item in items}
            missing_ids = [item_id for item_id in item_ids if item_id not in found_ids]
            raise HTTPException(
                status_code=404,
                detail=f"Товары с ID {missing_ids} не найдены"
            )
        
        # Создаем словарь для быстрого доступа к товарам по id
        items_dict = {item.id: item for item in items}
        
        # Пытаемся определить organization_id из товаров (опционально)
        organization_ids = {item.organization_id for item in items if item.organization_id}
        if len(organization_ids) > 1:
            raise HTTPException(
                status_code=400,
                detail="Все товары должны принадлежать одной организации"
            )
        
        organization_id = organization_ids.pop() if organization_ids else None
        
        # Преобразуем упрощенный запрос в полный CreateWarehouseDocumentRequest
        invoice_items = [
            WarehouseDocumentItemRequest(
                item_id=item.id,
                item_iiko_id=items_dict[item.id].iiko_id,
                quantity=item.amount,
                price=item.price,
                amount=item.sum
            )
            for item in document_data.items
        ]
        
        # Определяем store_iiko_id в зависимости от TESTING_MODE
        if config.TESTING_MODE:
            store_iiko_id = DEFAULT_STORE_IIKO_ID
            conception_iiko_id = DEFAULT_CONCEPTION_IIKO_ID
        else:
            # В продакшен режиме используем переданные значения
            if document_data.storeId:
                store = db.query(Store).filter(Store.id == document_data.storeId).first()
                if not store:
                    raise HTTPException(status_code=404, detail=f"Склад с ID {document_data.storeId} не найден")
                if not store.iiko_id:
                    raise HTTPException(status_code=400, detail=f"У склада с ID {document_data.storeId} не указан iiko_id")
                store_iiko_id = store.iiko_id
            else:
                raise HTTPException(status_code=400, detail="Поле storeId обязательно в продакшен режиме (TESTING_MODE=false)")
            
            conception_iiko_id = None
            if document_data.conceptionId:
                conception = db.query(Conception).filter(Conception.id == document_data.conceptionId).first()
                if not conception:
                    raise HTTPException(status_code=404, detail=f"Концепция с ID {document_data.conceptionId} не найдена")
                conception_iiko_id = conception.iiko_id
        
        # Используем supplier из запроса или фиксированный
        supplier_iiko_id = document_data.supplier if document_data.supplier else DEFAULT_SUPPLIER_IIKO_ID
        
        invoice_request = CreateWarehouseDocumentRequest(
            document_type="INCOMING_INVOICE",
            date=document_data.dateIncoming,
            date_incoming=document_data.dateIncoming,
            organization_id=organization_id,
            store_iiko_id=store_iiko_id,
            conception_iiko_id=conception_iiko_id,
            comment=document_data.comment,
            supplier_iiko_id=supplier_iiko_id,
            invoice=document_data.invoice,
            items=invoice_items
        )
        
        # Создаем документ через существующий сервис
        result = await create_incoming_invoice_in_iiko(
            db=db,
            document_data=invoice_request,
            user_id=user.id if hasattr(user, 'id') else None
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Ошибка создания приходной накладной")
            )
        
        return CreateWarehouseDocumentResponse(
            success=True,
            message=result.get("message", "Приходная накладная успешно создана"),
            iiko_id=result.get("iiko_id"),
            document_id=result.get("document_id")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating incoming invoice: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/outgoing-invoice", response_model=CreateWarehouseDocumentResponse)
async def create_outgoing_invoice_endpoint(
    document_data: SimpleOutgoingInvoiceRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Создать расходную накладную
    
    **Request Body:**
    ```json
    {
      "storeId": 1,
      "conceptionId": 1,
      "dateIncoming": "28.12.2025",
      "comment": "Комментарий к документу",
      "accountToCode": "001",
      "supplier": "707a8ef8-60c0-f07e-018a-f452cbcd454b",
      "items": [
        {
          "id": 3181,
          "amount": 5.0,
          "price": 100.0,
          "sum": 500.0
        }
      ]
    }
    ```
    
    **Поля:**
    - `storeId`: ID склада из таблицы stores (опционально, в TESTING_MODE используется фиксированный)
    - `conceptionId`: ID концепции из таблицы conceptions (опционально)
    - `dateIncoming`: Дата в формате dd.mm.YYYY
    - `comment`: Комментарий к документу (опционально)
    - `accountToCode`: Код счета выручки (опционально)
    - `supplier`: iiko_id поставщика (опционально)
    - `items`: Список позиций документа
      - `id`: ID товара из таблицы items (нашего)
      - `amount`: Количество товара
      - `price`: Цена за единицу
      - `sum`: Сумма позиции
    """
    try:
        from services.warehouse.invoice_service import (
            DEFAULT_STORE_IIKO_ID,
            DEFAULT_CONCEPTION_IIKO_ID,
            DEFAULT_CONCEPTION_CODE
        )
        
        # Валидация товаров и получение organization_id
        if not document_data.items:
            raise HTTPException(
                status_code=400,
                detail="Список позиций не может быть пустым"
            )
        
        # Проверяем все товары и получаем organization_id и iiko_id
        item_ids = [item.id for item in document_data.items]
        items = db.query(Item).filter(Item.id.in_(item_ids)).all()
        
        if len(items) != len(item_ids):
            found_ids = {item.id for item in items}
            missing_ids = [item_id for item_id in item_ids if item_id not in found_ids]
            raise HTTPException(
                status_code=404,
                detail=f"Товары с ID {missing_ids} не найдены"
            )
        
        # Создаем словарь для быстрого доступа к товарам по id
        items_dict = {item.id: item for item in items}
        
        # Пытаемся определить organization_id из товаров (опционально)
        organization_ids = {item.organization_id for item in items if item.organization_id}
        if len(organization_ids) > 1:
            raise HTTPException(
                status_code=400,
                detail="Все товары должны принадлежать одной организации"
            )
        
        organization_id = organization_ids.pop() if organization_ids else None
        
        # Преобразуем упрощенный запрос в полный CreateWarehouseDocumentRequest
        invoice_items = [
            WarehouseDocumentItemRequest(
                item_id=item.id,
                item_iiko_id=items_dict[item.id].iiko_id,
                quantity=item.amount,
                price=item.price,
                amount=item.sum
            )
            for item in document_data.items
        ]
        
        # Определяем store_iiko_id в зависимости от TESTING_MODE
        if config.TESTING_MODE:
            store_iiko_id = DEFAULT_STORE_IIKO_ID
            conception_iiko_id = DEFAULT_CONCEPTION_IIKO_ID
        else:
            # В продакшен режиме используем переданные значения
            if document_data.storeId:
                store = db.query(Store).filter(Store.id == document_data.storeId).first()
                if not store:
                    raise HTTPException(status_code=404, detail=f"Склад с ID {document_data.storeId} не найден")
                if not store.iiko_id:
                    raise HTTPException(status_code=400, detail=f"У склада с ID {document_data.storeId} не указан iiko_id")
                store_iiko_id = store.iiko_id
            else:
                raise HTTPException(status_code=400, detail="Поле storeId обязательно в продакшен режиме (TESTING_MODE=false)")
            
            conception_iiko_id = None
            if document_data.conceptionId:
                conception = db.query(Conception).filter(Conception.id == document_data.conceptionId).first()
                if not conception:
                    raise HTTPException(status_code=404, detail=f"Концепция с ID {document_data.conceptionId} не найдена")
                conception_iiko_id = conception.iiko_id
        
        invoice_request = CreateWarehouseDocumentRequest(
            document_type="OUTGOING_INVOICE",
            date=document_data.dateIncoming,
            date_incoming=document_data.dateIncoming,
            organization_id=organization_id,
            store_iiko_id=store_iiko_id,
            conception_iiko_id=conception_iiko_id,
            account_to_code=document_data.accountToCode,
            supplier_iiko_id=document_data.supplier,
            comment=document_data.comment,
            items=invoice_items
        )
        
        # Создаем документ через существующий сервис
        result = await create_outgoing_invoice_in_iiko(
            db=db,
            document_data=invoice_request,
            user_id=user.id if hasattr(user, 'id') else None
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Ошибка создания расходной накладной")
            )
        
        return CreateWarehouseDocumentResponse(
            success=True,
            message=result.get("message", "Расходная накладная успешно создана"),
            iiko_id=result.get("iiko_id"),
            document_id=result.get("document_id")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating outgoing invoice: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/accounts", response_model=AccountsListResponse)
async def get_accounts_endpoint(
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Получить список всех счетов (accounts_list)
    
    **Response:**
    - Массив счетов с информацией: id, iiko_id, name, code, type, system
    """
    try:
        accounts = db.query(Account).filter(Account.deleted != True).all()
        
        account_responses = [
            AccountResponse(
                id=account.id,
                iiko_id=account.iiko_id,
                name=account.name,
                code=account.code,
                type=account.type,
                system=account.system
            )
            for account in accounts
        ]
        
        return AccountsListResponse(accounts=account_responses)
        
    except Exception as e:
        logger.error(f"Error getting accounts: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/inventory", response_model=CreateWarehouseDocumentResponse)
async def create_inventory_endpoint(
    document_data: SimpleInventoryRequest,
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Создать инвентаризацию
    
    **Request Body:**
    ```json
    {
      "storeId": 1,
      "dateIncoming": "28.12.2025",
      "comment": "Комментарий к инвентаризации",
      "accountSurplusCode": "5.10",
      "accountShortageCode": "5.09",
      "items": [
        {
          "id": 3181,
          "amount": 5.0,
          "price": 100.0,
          "sum": 500.0,
          "containerId": "optional-container-id",
          "comment": "Комментарий к позиции"
        }
      ]
    }
    ```
    
    **Поля:**
    - `storeId`: ID склада из таблицы stores (опционально, в TESTING_MODE используется фиксированный)
    - `dateIncoming`: Дата в формате dd.mm.YYYY
    - `comment`: Комментарий к документу (опционально)
    - `accountSurplusCode`: Код счета для излишков (по умолчанию "5.10")
    - `accountShortageCode`: Код счета для недостачи (по умолчанию "5.09")
    - `items`: Список позиций документа
      - `id`: ID товара из таблицы items (нашего)
      - `amount`: Количество товара (будет использовано как amountContainer)
      - `price`: Цена за единицу (опционально)
      - `sum`: Сумма позиции (опционально)
      - `containerId`: iiko_id фасовки (опционально)
      - `comment`: Комментарий к позиции (опционально)
    
    **Примечания:**
    - Все товары должны принадлежать одной организации
    - Статус документа всегда "NEW"
    """
    try:
        from services.warehouse.invoice_service import DEFAULT_STORE_IIKO_ID
        
        # Валидация товаров
        if not document_data.items:
            raise HTTPException(
                status_code=400,
                detail="Список позиций не может быть пустым"
            )
        
        # Получаем товары из БД
        item_ids = [item.id for item in document_data.items]
        items = db.query(Item).filter(Item.id.in_(item_ids)).all()
        
        if len(items) != len(item_ids):
            found_ids = {item.id for item in items}
            missing_ids = set(item_ids) - found_ids
            raise HTTPException(
                status_code=404,
                detail=f"Товары с ID {missing_ids} не найдены в БД"
            )
        
        # Проверяем, что все товары принадлежат одной организации
        organization_ids = {item.organization_id for item in items if item.organization_id}
        if len(organization_ids) != 1:
            raise HTTPException(
                status_code=400,
                detail="Все товары должны принадлежать одной организации"
            )
        
        organization_id = organization_ids.pop()
        
        # Проверяем наличие iiko_id у всех товаров
        items_without_iiko_id = [item for item in items if not item.iiko_id]
        if items_without_iiko_id:
            missing_ids = [item.id for item in items_without_iiko_id]
            raise HTTPException(
                status_code=400,
                detail=f"У товаров с ID {missing_ids} не указан iiko_id. Необходимо выполнить синхронизацию товаров."
            )
        
        # Создаем словарь для быстрого доступа к товарам
        items_dict = {item.id: item for item in items}
        
        # Определяем store_iiko_id в зависимости от TESTING_MODE
        store_iiko_id = None
        if config.TESTING_MODE:
            store_iiko_id = DEFAULT_STORE_IIKO_ID
        else:
            if document_data.storeId:
                store = db.query(Store).filter(Store.id == document_data.storeId).first()
                if not store:
                    raise HTTPException(status_code=404, detail=f"Склад с ID {document_data.storeId} не найден")
                if not store.iiko_id:
                    raise HTTPException(status_code=400, detail=f"У склада с ID {document_data.storeId} не указан iiko_id")
                store_iiko_id = store.iiko_id
            else:
                raise HTTPException(status_code=400, detail="Поле storeId обязательно в продакшен режиме (TESTING_MODE=false)")
        
        # Вызываем сервис для создания инвентаризации
        result = await create_inventory_in_iiko(
            db=db,
            document_data=document_data,
            organization_id=organization_id,
            user_id=user.id if user else None,
            store_iiko_id=store_iiko_id,
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Ошибка создания инвентаризации")
            )
        
        return CreateWarehouseDocumentResponse(
            success=True,
            message=result.get("message", "Инвентаризация успешно создана"),
            iiko_id=result.get("iiko_id"),
            document_id=result.get("document_id")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating inventory: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/pay-out-types/sync", response_model=SyncPayOutTypesResponse)
async def sync_pay_out_types_endpoint(
    include_deleted: bool = Query(default=False, description="Включать ли удаленные типы"),
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Синхронизировать типы изъятий/внесений из iiko API в локальную БД.
    
    **Описание:**
    - Получает данные из iiko API `/resto/api/v2/entities/payInOutTypes/list`
    - Сохраняет/обновляет записи в таблице `pay_out_types`
    - Связывает типы изъятий с таблицей `accounts_list` по полям `account` и `chiefAccount`
    
    **Параметры:**
    - `include_deleted`: Включать ли удаленные типы (по умолчанию false)
    
    **Ответ:**
    - `success`: Успешность операции
    - `message`: Сообщение о результате
    - `synced`: Количество синхронизированных типов
    """
    try:
        from services.cash.pay_out_service import sync_pay_out_types_from_iiko

        result = await sync_pay_out_types_from_iiko(db=db, include_deleted=include_deleted)
        return SyncPayOutTypesResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            synced=result.get("synced", 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing pay-out types: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/pay-out-types", response_model=List[PayOutTypeResponse])
async def get_pay_out_types_endpoint(
    include_deleted: bool = Query(default=False, description="Включать ли удаленные типы"),
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Получить список типов изъятий/внесений из локальной БД.
    
    **Важно:**
    - Типы должны быть предварительно синхронизированы из iiko API
      через эндпоинт `POST /documents/pay-out-types/sync`.
    - В ответе для фронтенда отдаем:
      - `id` — GUID типа из iiko,
      - `account_name` — название счета (account -> accounts_list.name),
      - `chief_account_name` — название главного счета (если есть),
      - `transactionType`, `counteragentType`, `comment`.
    """
    try:
        from services.cash.pay_out_service import get_local_pay_out_types

        return get_local_pay_out_types(db=db, include_deleted=include_deleted)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pay-out types: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/payrolls", response_model=List[PayrollResponse])
async def get_payrolls_endpoint(
    date_from: str = Query(..., description="Начало периода в формате yyyy-MM-dd, включительно"),
    date_to: str = Query(..., description="Окончание периода в формате yyyy-MM-dd, включительно"),
    department: Optional[str] = Query(default=None, description="UUID торгового предприятия"),
    include_deleted: bool = Query(default=False, description="Включать ли удаленные ведомости"),
    user = Depends(require_role("Менеджер")),
):
    """
    Получить список платежных ведомостей из iiko API
    
    **Параметры:**
    - `date_from`: Начало периода в формате yyyy-MM-dd, включительно (обязательное)
    - `date_to`: Окончание периода в формате yyyy-MM-dd, включительно (обязательное)
    - `department`: UUID торгового предприятия (опционально)
    - `include_deleted`: Включать ли удаленные ведомости (по умолчанию false)
    
    **Ответ:**
    Список платежных ведомостей с полями:
    - `id`: UUID ведомости
    - `dateFrom`: Дата начала действия
    - `dateTo`: Дата окончания действия
    - `department`: UUID торгового предприятия
    - `documentNumber`: Номер документа
    - `status`: Статус документа (NEW, PROCESSED, DELETED)
    - `comment`: Комментарий
    """
    try:
        # Валидация формата дат
        from datetime import datetime
        try:
            _df = datetime.strptime(date_from, "%Y-%m-%d")
            _dt = datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Даты должны быть в формате yyyy-MM-dd (например, 2025-01-15)"
            )

        # Защита от перегруза iiko: лимит памяти "открытого периода" — 65 дней.
        if (_dt - _df).days > 60:
            raise HTTPException(
                status_code=400,
                detail="Период между date_from и date_to не может превышать 60 дней (лимит iiko)."
            )

        iiko_service = IikoService()
        payrolls = await iiko_service.get_payrolls(
            date_from=date_from,
            date_to=date_to,
            department=department,
            include_deleted=include_deleted
        )
        
        if payrolls is None:
            raise HTTPException(
                status_code=500,
                detail="Не удалось получить список платежных ведомостей из iiko API"
            )
        
        return payrolls
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payrolls: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/pay-out", response_model=CreatePayOutResponse)
async def create_pay_out_endpoint(
    pay_out_data: CreatePayOutRequest,
    organization_id: Optional[int] = Query(default=None, description="ID организации (опционально)"),
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Создать изъятие из кассы в iiko API
    
    **Request Body:**
    ```json
    {
      "payOutTypeId": "7c4a6655-9543-42cd-bb6d-265813cdf65e",
      "payOutDate": "2025-01-15",
      "counteragent": "d244cb85-9115-4b4d-8e02-a4f7fdd8ec15",
      "departmentSumMap": {
        "06d7ec0c-8fee-f341-015f-b58127ff000d": 1500.0
      },
      "payrollId": "c1349656-8401-4476-9541-7f0325c65f98",
      "comment": "Комментарий к изъятию"
    }
    ```
    
    **Поля:**
    - `payOutTypeId`: UUID типа изъятия (обязательное)
    - `payOutDate`: Дата в формате yyyy-MM-dd (обязательное)
    - `counteragent`: UUID контрагента (опционально, зависит от типа изъятия)
    - `departmentSumMap`: Словарь UUID торгового предприятия -> сумма изъятия (обязательное)
    - `payrollId`: UUID платежной ведомости (опционально, для платежных ведомостей)
    - `comment`: Комментарий к изъятию (опционально)
    
    **Ответ:**
    ```json
    {
      "success": true,
      "message": "Изъятие успешно создано",
      "result": "SUCCESS",
      "errors": null,
      "payOutSettings": {...},
      "pay_out_id": 123
    }
    ```
    """
    try:
        # Создаем изъятие через сервис
        result = await create_pay_out_in_iiko(
            db=db,
            pay_out_data=pay_out_data,
            organization_id=organization_id,
            user_id=user.id if hasattr(user, 'id') else None
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Ошибка создания изъятия")
            )
        
        return CreatePayOutResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            result=result.get("result"),
            errors=result.get("errors"),
            payOutSettings=result.get("payOutSettings"),
            pay_out_id=result.get("pay_out_id")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating pay-out: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

