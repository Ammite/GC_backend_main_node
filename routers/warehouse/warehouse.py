from fastapi import APIRouter, Depends, Query, HTTPException, Path, Body
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user
from database.database import get_db
from services.warehouse.warehouse_service import (
    create_warehouse_document,
    get_warehouse_documents,
    get_warehouse_document_by_id,
    update_warehouse_document,
    delete_warehouse_document,
)
from schemas.warehouse import (
    CreateWarehouseDocumentRequest,
    CreateWarehouseDocumentResponse,
    WarehouseDocumentsListResponse,
    WarehouseDocumentDetailResponse,
    UpdateWarehouseDocumentRequest,
    UpdateWarehouseDocumentResponse,
    DeleteWarehouseDocumentResponse,
    SyncWarehouseDocumentsRequest,
    SyncWarehouseDocumentsResponse,
    CreateWriteoffDocumentRequest,
    CreateWriteoffDocumentResponse,
    BalanceStoresResponse,
    StoreResponse,
    StoresListResponse,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/warehouse", tags=["warehouse"])


@router.post("/documents", response_model=CreateWarehouseDocumentResponse, include_in_schema=False)
async def create_warehouse_document_endpoint(
    document_data: CreateWarehouseDocumentRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Создать новый складской документ (поступление, списание, приходная или расходная накладная)
    
    **Типы документов:**
    - `RECEIPT` - поступление (создается только в локальной БД)
    - `WRITEOFF` - акт списания (создается через iiko API)
    - `INCOMING_INVOICE` - приходная накладная (создается через iiko API)
    - `OUTGOING_INVOICE` - расходная накладная (создается через iiko API)
    
    **Request Body:**
    ```json
    {
      "document_type": "INCOMING_INVOICE",
      "document_number": "INV-20250115-0001",
      "date": "15.01.2025",
      "date_incoming": "15.01.2025",
      "organization_id": 1,
      "store_id": "store-123",
      "default_store": "store-guid-123",
      "comment": "Приходная накладная",
      "items": [
        {
          "item_id": 1,
          "item_iiko_id": "item-123",
          "item_name": "Товар 1",
          "quantity": 10.0,
          "price": 1000.00,
          "amount": 10000.00
        }
      ]
    }
    ```
    """
    try:
        user_id = user.id if hasattr(user, 'id') else None
        
        # Определяем, нужно ли создавать через iiko API
        if document_data.document_type == "WRITEOFF":
            # Акты списания создаются через отдельный эндпоинт /writeoff-documents
            raise HTTPException(
                status_code=400,
                detail="Для создания акта списания используйте эндпоинт /writeoff-documents"
            )
        elif document_data.document_type == "INCOMING_INVOICE":
            # Приходная накладная - создаем через iiko API
            from services.warehouse.invoice_service import create_incoming_invoice_in_iiko
            
            result = await create_incoming_invoice_in_iiko(
                db=db,
                document_data=document_data,
                user_id=user_id
            )
            
            if not result.get("success"):
                raise HTTPException(
                    status_code=400,
                    detail=result.get("message", "Ошибка создания приходной накладной")
                )
            
            return CreateWarehouseDocumentResponse(
                success=True,
                message=result.get("message", "Приходная накладная успешно создана"),
                document_id=result.get("document_id"),
                iiko_id=result.get("iiko_id")
            )
        elif document_data.document_type == "OUTGOING_INVOICE":
            # Расходная накладная - создаем через iiko API
            from services.warehouse.invoice_service import create_outgoing_invoice_in_iiko
            
            result = await create_outgoing_invoice_in_iiko(
                db=db,
                document_data=document_data,
                user_id=user_id
            )
            
            if not result.get("success"):
                raise HTTPException(
                    status_code=400,
                    detail=result.get("message", "Ошибка создания расходной накладной")
                )
            
            return CreateWarehouseDocumentResponse(
                success=True,
                message=result.get("message", "Расходная накладная успешно создана"),
                document_id=result.get("document_id"),
                iiko_id=result.get("iiko_id")
            )
        else:
            # RECEIPT или другие типы - создаем только в локальной БД
            document = create_warehouse_document(
                db, 
                document_data, 
                user_id=user_id
            )
            return CreateWarehouseDocumentResponse(
                success=True,
                message="Складской документ успешно создан",
                document_id=document.id
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating warehouse document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/documents", response_model=WarehouseDocumentsListResponse, include_in_schema=False)
async def get_warehouse_documents_endpoint(
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    document_type: Optional[str] = Query(default=None, description="Тип документа: RECEIPT, WRITEOFF, INCOMING_INVOICE, OUTGOING_INVOICE, INVENTORY"),
    from_date: Optional[str] = Query(default=None, description="Дата начала периода в формате DD.MM.YYYY"),
    to_date: Optional[str] = Query(default=None, description="Дата конца периода в формате DD.MM.YYYY"),
    limit: int = Query(default=100, description="Лимит записей"),
    offset: int = Query(default=0, description="Смещение для пагинации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить список складских документов с фильтрацией
    """
    try:
        result = get_warehouse_documents(
            db=db,
            organization_id=organization_id,
            document_type=document_type,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
        return result
    except Exception as e:
        logger.error(f"Error getting warehouse documents list: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/documents/{document_id}", response_model=WarehouseDocumentDetailResponse, include_in_schema=False)
async def get_warehouse_document_detail_endpoint(
    document_id: int = Path(..., description="ID складского документа"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить детали складского документа по ID
    """
    try:
        result = get_warehouse_document_by_id(db, document_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Складской документ с ID={document_id} не найден")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting warehouse document detail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/documents/{document_id}", response_model=UpdateWarehouseDocumentResponse, include_in_schema=False)
async def update_warehouse_document_endpoint(
    document_id: int = Path(..., description="ID складского документа"),
    document_data: UpdateWarehouseDocumentRequest = Body(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Обновить складской документ
    
    **Request Body:**
    ```json
    {
      "document_type": "WRITEOFF",
      "document_number": "WRITEOFF-20250115-0001",
      "date": "15.01.2025",
      "store_id": "store-123",
      "comment": "Списание товара",
      "items": [...]
    }
    ```
    """
    try:
        document = update_warehouse_document(db, document_id, document_data)
        return UpdateWarehouseDocumentResponse(
            success=True,
            message="Складской документ успешно обновлен",
            document_id=document.id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating warehouse document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/documents/{document_id}", response_model=DeleteWarehouseDocumentResponse, include_in_schema=False)
async def delete_warehouse_document_endpoint(
    document_id: int = Path(..., description="ID складского документа"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Удалить складской документ
    """
    try:
        delete_warehouse_document(db, document_id)
        return DeleteWarehouseDocumentResponse(
            success=True,
            message="Складской документ успешно удален"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting warehouse document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/sync", response_model=SyncWarehouseDocumentsResponse)
async def sync_warehouse_documents_endpoint(
    sync_data: SyncWarehouseDocumentsRequest = Body(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Синхронизировать складские документы из iiko
    
    **Request Body:**
    ```json
    {
      "from_date": "01.01.2025",
      "to_date": "31.01.2025",
      "organization_id": 1
    }
    ```
    
    **Примечание:** Синхронизация выполняется через транзакции iiko (фильтрация по полю Document)
    """
    try:
        # Импортируем здесь, чтобы избежать циклических зависимостей
        from services.iiko.iiko_sync import iiko_sync
        
        from_date = None
        to_date = None
        
        if sync_data.from_date:
            from datetime import datetime
            from_date = datetime.strptime(sync_data.from_date, "%d.%m.%Y") if "." in sync_data.from_date else datetime.fromisoformat(sync_data.from_date.replace("Z", "+00:00"))
        
        if sync_data.to_date:
            from datetime import datetime
            to_date = datetime.strptime(sync_data.to_date, "%d.%m.%Y") if "." in sync_data.to_date else datetime.fromisoformat(sync_data.to_date.replace("Z", "+00:00"))
        
        result = await iiko_sync.sync_warehouse_documents_from_transactions(
            db=db,
            from_date=from_date,
            to_date=to_date,
        )
        
        return SyncWarehouseDocumentsResponse(
            success=True,
            message="Синхронизация складских документов завершена",
            created=result.get("created", 0),
            updated=result.get("updated", 0),
            errors=result.get("errors", 0),
        )
    except Exception as e:
        logger.error(f"Error syncing warehouse documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/writeoff-documents", response_model=CreateWriteoffDocumentResponse, include_in_schema=False)
async def create_writeoff_document_endpoint(
    document_data: CreateWriteoffDocumentRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Создать акт списания в iiko API
    
    **Request Body:**
    ```json
    {
      "document_number": "WRITEOFF-20250115-0001",
      "date_incoming": "2025-01-15",
      "organization_id": 1,
      "store_id": "store-guid-123",
      "account_id": "account-guid-456",
      "status": "NEW",
      "items": [
        {
          "product_id": "product-guid-789",
          "product_size_id": "size-guid-101",
          "amount_factor": 1.0,
          "amount": 10.0,
          "measure_unit_id": "unit-guid-202",
          "container_id": "container-guid-303",
          "cost": 1000.00,
          "num": 1
        }
      ]
    }
    ```
    
    **Поля:**
    - `document_number` (optional): Номер документа. Если не указан, будет сгенерирован автоматически
    - `date_incoming`: Дата в формате "YYYY-MM-DD" или "DD.MM.YYYY"
    - `organization_id`: ID организации в нашей БД
    - `store_id`: ID склада в нашей БД (Store.id) - обязательное
    - `account_id`: ID счета в нашей БД (Account.id) - обязательное
    - `status` (optional): Статус документа
    - `items`: Список позиций акта списания
    
    **Поля позиции:**
    - `item_id`: ID товара в нашей БД (Item.id) - обязательное, если не указан product_id
    - `product_id`: ID товара в iiko (Item.iiko_id, GUID) - обязательное, если не указан item_id
    - `amount`: Количество - обязательное
    - `cost`: Стоимость - опциональное
    - `product_size_id` (optional): ID размера товара
    - `amount_factor` (optional): Коэффициент количества
    - `measure_unit_id` (optional): ID единицы измерения
    - `container_id` (optional): ID фасовки
    - `num` (optional): Номер позиции (если не указан, присваивается автоматически)
    """
    try:
        from services.warehouse.writeoff_service import create_writeoff_document_in_iiko
        
        result = await create_writeoff_document_in_iiko(
            db=db,
            document_data=document_data,
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


@router.get("/balance", response_model=BalanceStoresResponse)
async def get_balance_stores_endpoint(
    timestamp: Optional[str] = Query(
        default=None,
        description="Дата и время в формате ISO (например, 2025-12-27T12:20:00). Если не указано, используется текущее время"
    ),
    organization_id: Optional[int] = Query(
        default=None,
        description="ID организации для фильтрации"
    ),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить остатки товаров по складам
    
    **Параметры:**
    - `timestamp`: Дата и время в формате ISO (например, "2025-12-27T12:20:00")
    - `organization_id`: ID организации для фильтрации (опционально)
    
    **Ответ:**
    ```json
    {
      "success": true,
      "message": "Остатки успешно получены",
      "data": [
        {
          "store": "Название склада",
          "sum": 2400.0,
          "products": [
            {
              "item": "Название товара",
              "amount": 2.0,
              "sum": 2400.0
            }
          ]
        }
      ]
    }
    ```
    """
    try:
        from services.warehouse.balance_service import get_balance_stores
        
        balance_data = await get_balance_stores(
            db=db,
            timestamp=timestamp,
            organization_id=organization_id
        )
        
        return BalanceStoresResponse(
            success=True,
            message=f"Получено остатков по {len(balance_data)} складам",
            data=balance_data
        )
    except Exception as e:
        logger.error(f"Error getting balance stores: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/stores", response_model=StoresListResponse)
async def get_stores_endpoint(
    user = Depends(get_current_user),
):
    """
    Получить список всех складов из iiko Server API
    
    **Описание:**
    Получает список всех складов через iiko Server API по эндпоинту `/resto/api/corporation/stores/`
    
    **Ответ:**
    ```json
    {
      "success": true,
      "message": "Получено складов: 5",
      "data": [
        {
          "id": "5849a5b1-1a73-40c3-a2dd-fd32f35325a2",
          "name": "Основной склад",
          "code": "001"
        }
      ]
    }
    ```
    """
    try:
        from services.iiko.iiko_service import IikoService
        
        iiko_service = IikoService()
        stores_data = await iiko_service.get_server_stores()
        
        if stores_data is None:
            raise HTTPException(
                status_code=500,
                detail="Не удалось получить список складов из iiko API"
            )
        
        # Преобразуем данные в формат ответа
        stores = [
            StoreResponse(
                id=store.get("id", ""),
                name=store.get("name"),
                code=store.get("code")
            )
            for store in stores_data
            if store.get("id")  # Пропускаем склады без id
        ]
        
        return StoresListResponse(
            success=True,
            message=f"Получено складов: {len(stores)}",
            data=stores
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stores: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

