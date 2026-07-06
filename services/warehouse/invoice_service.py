"""
Сервис для создания накладных (приходных и расходных) в iiko API
"""
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from models.organization import Organization
from models.item import Item
from models.store import Store
from models.conception import Conception
from models.supplier import Supplier
from models.account import Account
from models.warehouse import WarehouseDocument, WarehouseDocumentItem
from models.income import Income
from models.expense import Expense
from schemas.warehouse import CreateWarehouseDocumentRequest, SimpleInventoryRequest
from services.iiko.iiko_service import IikoService

logger = logging.getLogger(__name__)

iiko_service = IikoService()

# Константы для накладных
DEFAULT_STORE_IIKO_ID = "5849a5b1-1a73-40c3-a2dd-fd32f35325a2"
DEFAULT_CONCEPTION_NAME = "ГК 9 Премьера"
DEFAULT_CONCEPTION_CODE = "13"
DEFAULT_CONCEPTION_IIKO_ID = "7e97ff39-9c68-40d7-9993-0a5dc53016e8"
DEFAULT_SUPPLIER_IIKO_ID = "707a8ef8-60c0-f07e-018a-f452cbcd454b"


def parse_date(date_str: str) -> datetime:
    """Парсинг даты из строки DD.MM.YYYY или ISO формата или YYYY-MM-DD"""
    try:
        # Пробуем формат DD.MM.YYYY
        if "." in date_str and len(date_str.split(".")) == 3:
            return datetime.strptime(date_str, "%d.%m.%Y")
        # Пробуем формат YYYY-MM-DD
        if "-" in date_str and len(date_str.split("-")) == 3:
            return datetime.strptime(date_str, "%Y-%m-%d")
        # Пробуем ISO формат
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception as e:
        logger.error(f"Ошибка парсинга даты {date_str}: {e}")
        raise ValueError(f"Неверный формат даты: {date_str}")


def format_date_for_iiko(dt: datetime) -> str:
    """Форматирование даты в формат YYYY-MM-DDTHH:MM для iiko API (для расходных накладных и актов списания)"""
    return dt.strftime("%Y-%m-%dT%H:%M")

def format_date_dd_mm_yyyy(dt: datetime) -> str:
    """Форматирование даты в формат dd.mm.YYYY для iiko API (для приходных накладных: dateIncoming, dueDate)"""
    return dt.strftime("%d.%m.%Y")

def format_date_yyyy_mm_dd(dt: datetime) -> str:
    """Форматирование даты в формат YYYY-mm-dd для iiko API (для приходных накладных: incomingDate)"""
    return dt.strftime("%Y-%m-%d")


async def create_incoming_invoice_in_iiko(
    db: Session,
    document_data: CreateWarehouseDocumentRequest,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Создать приходную накладную в iiko API
    
    Args:
        db: сессия БД
        document_data: данные приходной накладной
        user_id: ID пользователя, создающего документ
    
    Returns:
        Словарь с результатом создания:
        {
            "success": bool,
            "message": str,
            "iiko_id": Optional[str],
            "document_id": Optional[int]
        }
    """
    try:
        # Валидация организации (опционально)
        # organization_id не обязателен, так как все параметры (store, conception, supplier) статические
        organization = None
        if document_data.organization_id:
            organization = db.query(Organization).filter(
                Organization.id == document_data.organization_id
            ).first()
            
            if not organization:
                logger.warning(f"Организация с ID {document_data.organization_id} не найдена, продолжаем без organization_id")
        
        # Валидация товаров
        invalid_items = []
        for idx, item_data in enumerate(document_data.items, start=1):
            if item_data.item_id:
                # Проверяем по нашему id
                item_obj = db.query(Item).filter(Item.id == item_data.item_id).first()
                if not item_obj:
                    invalid_items.append(f"Позиция {idx}: товар с ID {item_data.item_id} не найден")
            elif item_data.item_iiko_id:
                # Обратная совместимость: проверяем по iiko_id
                item_obj = db.query(Item).filter(Item.iiko_id == item_data.item_iiko_id).first()
                if not item_obj:
                    invalid_items.append(f"Позиция {idx}: товар с iiko_id {item_data.item_iiko_id} не найден")
            else:
                invalid_items.append(f"Позиция {idx}: не указан ни item_id, ни item_iiko_id")
        
        if invalid_items:
            return {
                "success": False,
                "message": "Найдены ошибки в позициях: " + "; ".join(invalid_items),
                "iiko_id": None,
                "document_id": None
            }
        
        # Парсим дату
        try:
            date_incoming = parse_date(document_data.date_incoming or document_data.date)
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "iiko_id": None,
                "document_id": None
            }
        
        # Формируем запрос для iiko API (XML формат)
        # Форматы дат для приходных накладных:
        # - dateIncoming: dd.mm.YYYY
        # - dueDate: dd.mm.YYYY
        # - incomingDate: YYYY-mm-dd
        iiko_request = {
            "dateIncoming": format_date_dd_mm_yyyy(date_incoming),
            "status": document_data.status or "NEW",  # По умолчанию "NEW"
        }
        
        # documentNumber не обязателен
        if document_data.document_number:
            iiko_request["documentNumber"] = document_data.document_number
        
        # Обработка Store (склад)
        # Всегда используем фиксированный store
        iiko_request["defaultStore"] = DEFAULT_STORE_IIKO_ID
        logger.info(f"Используется склад: {DEFAULT_STORE_IIKO_ID}")
        
        # Обработка Conception (концепция)
        # Всегда используем фиксированную концепцию по iiko_id
        iiko_request["conception"] = DEFAULT_CONCEPTION_IIKO_ID
        iiko_request["conceptionCode"] = DEFAULT_CONCEPTION_CODE
        logger.info(f"Используется концепция: iiko_id={DEFAULT_CONCEPTION_IIKO_ID}, код={DEFAULT_CONCEPTION_CODE}")
        
        # Обработка Supplier (поставщик)
        # Всегда используем фиксированного поставщика
        iiko_request["supplier"] = DEFAULT_SUPPLIER_IIKO_ID
        logger.info(f"Используется поставщик: iiko_id={DEFAULT_SUPPLIER_IIKO_ID}")
        if document_data.invoice:
            iiko_request["invoice"] = document_data.invoice
        if document_data.comment:
            iiko_request["comment"] = document_data.comment
        if document_data.use_default_document_time is not None:
            iiko_request["useDefaultDocumentTime"] = document_data.use_default_document_time
        if document_data.due_date:
            try:
                due_date = parse_date(document_data.due_date)
                iiko_request["dueDate"] = format_date_dd_mm_yyyy(due_date)
            except:
                pass
        if document_data.incoming_date:
            try:
                incoming_date = parse_date(document_data.incoming_date)
                iiko_request["incomingDate"] = format_date_yyyy_mm_dd(incoming_date)
            except:
                pass
        if document_data.incoming_document_number:
            iiko_request["incomingDocumentNumber"] = document_data.incoming_document_number
        if document_data.employee_pass_to_account:
            iiko_request["employeePassToAccount"] = document_data.employee_pass_to_account
        if document_data.transport_invoice_number:
            iiko_request["transportInvoiceNumber"] = document_data.transport_invoice_number
        if document_data.distribution_algorithm:
            iiko_request["distributionAlgorithm"] = document_data.distribution_algorithm
        
        # Формируем позиции
        # Для приходных накладных обязательные поля позиции: num, sum
        # product или productArticle должны быть указаны
        iiko_request["items"] = []
        for idx, item_data in enumerate(document_data.items, start=1):
            # Получаем iiko_id товара из нашего id или напрямую
            item_iiko_id = None
            if item_data.item_id:
                # Если передан item_id (наш id), получаем iiko_id из БД
                item = db.query(Item).filter(Item.id == item_data.item_id).first()
                if not item:
                    logger.warning(f"Позиция {idx}: товар с ID {item_data.item_id} не найден, пропускаем")
                    continue
                item_iiko_id = item.iiko_id
            elif item_data.item_iiko_id:
                # Обратная совместимость: прямое указание iiko_id
                item_iiko_id = item_data.item_iiko_id
            else:
                logger.warning(f"Позиция {idx}: не указан ни item_id, ни item_iiko_id, пропускаем")
                continue
            
            # Обязательные поля для приходных накладных: num, sum, product (или productArticle)
            item_dict = {
                "num": idx,
                "product": item_iiko_id,  # Для приходных накладных используется "product" (guid) - обязательное
            }
            
            # amount опциональный, но обычно указывается
            if item_data.quantity is not None:
                item_dict["amount"] = float(item_data.quantity)
            
            # sum - обязательное поле (minOccurs="1")
            if item_data.amount is not None:
                item_dict["sum"] = float(item_data.amount)
            elif item_data.price is not None and item_data.quantity is not None:
                # Рассчитываем сумму, если не указана
                item_dict["sum"] = float(item_data.price) * float(item_data.quantity)
            else:
                # Если нет суммы - пропускаем позицию
                logger.warning(f"Позиция {idx}: не указана сумма, пропускаем")
                continue
            
            # price опциональный
            if item_data.price is not None:
                item_dict["price"] = float(item_data.price)
            
            # Остальные опциональные поля
            if item_data.batch_number:
                item_dict["code"] = item_data.batch_number
            
            # Всегда используем фиксированный склад для позиций
            item_dict["store"] = DEFAULT_STORE_IIKO_ID
            
            iiko_request["items"].append(item_dict)
        
        # Отправляем запрос в iiko API
        logger.info(f"Создание приходной накладной в iiko: {iiko_request}")
        iiko_response = await iiko_service.create_incoming_invoice(iiko_request)
        
        if not iiko_response:
            return {
                "success": False,
                "message": "Не удалось создать приходную накладную в iiko API",
                "iiko_id": None,
                "document_id": None
            }
        
        # Извлекаем информацию из ответа валидации
        # Для приходных накладных ответ - это documentValidationResult
        iiko_id = None
        validation_result = None
        
        if isinstance(iiko_response, dict):
            validation_result = iiko_response
            # Проверяем валидность документа
            if not iiko_response.get("valid", False):
                error_msg = iiko_response.get("errorMessage", "Документ не прошел валидацию")
                additional_info = iiko_response.get("additionalInfo", "")
                if additional_info:
                    error_msg += f"\nДополнительная информация: {additional_info}"
                return {
                    "success": False,
                    "message": error_msg,
                    "iiko_id": None,
                    "document_id": None
                }
            
            # Если валидация прошла успешно, используем documentNumber из ответа
            document_number = iiko_response.get("documentNumber") or iiko_response.get("otherSuggestedNumber")
            if document_number:
                # Обновляем номер документа в запросе для сохранения в БД
                document_data.document_number = document_number
        
        if not validation_result or not validation_result.get("valid", False):
            logger.warning(f"Документ не прошел валидацию: {iiko_response}")
        
        # Всегда используем фиксированные значения для сохранения в БД
        store_iiko_id_for_db = DEFAULT_STORE_IIKO_ID
        conception_iiko_id_for_db = DEFAULT_CONCEPTION_IIKO_ID
        conception_code_for_db = DEFAULT_CONCEPTION_CODE
        supplier_iiko_id_for_db = DEFAULT_SUPPLIER_IIKO_ID
        
        # Сохраняем документ в локальную БД
        document = WarehouseDocument(
            iiko_id=iiko_id if iiko_id else None,
            document_type="RECEIPT",
            document_source="INCOMING_INVOICE",
            document_number=document_data.document_number,
            date=date_incoming,
            date_incoming=date_incoming,
            status=document_data.status,
            organization_id=document_data.organization_id,
            store_id=store_iiko_id_for_db,  # Пока сохраняем iiko_id как строку (для обратной совместимости)
            default_store=store_iiko_id_for_db,  # Пока сохраняем iiko_id как строку
            conception=conception_iiko_id_for_db,  # Пока сохраняем iiko_id как строку
            conception_code=conception_code_for_db,
            invoice=document_data.invoice,
            supplier=supplier_iiko_id_for_db,  # Пока сохраняем iiko_id как строку
            due_date=parse_date(document_data.due_date) if document_data.due_date else None,
            incoming_date=parse_date(document_data.incoming_date) if document_data.incoming_date else None,
            use_default_document_time=document_data.use_default_document_time,
            incoming_document_number=document_data.incoming_document_number,
            employee_pass_to_account=document_data.employee_pass_to_account,
            transport_invoice_number=document_data.transport_invoice_number,
            distribution_algorithm=document_data.distribution_algorithm,
            comment=document_data.comment,
            created_by=user_id,
        )
        
        db.add(document)
        db.flush()
        
        # Создаем позиции документа
        total_sum = 0.0
        for idx, item_data in enumerate(document_data.items, start=1):
            # Получаем item_id и item_iiko_id
            item_id = None
            item_iiko_id = None
            item_name = item_data.item_name
            
            if item_data.item_id:
                item = db.query(Item).filter(Item.id == item_data.item_id).first()
                if item:
                    item_id = item.id
                    item_iiko_id = item.iiko_id
                    if not item_name:
                        item_name = item.name
            elif item_data.item_iiko_id:
                item = db.query(Item).filter(Item.iiko_id == item_data.item_iiko_id).first()
                if item:
                    item_id = item.id
                    item_iiko_id = item.iiko_id
                    if not item_name:
                        item_name = item.name
                else:
                    item_iiko_id = item_data.item_iiko_id
            
            amount = item_data.amount
            if amount is None:
                if item_data.price is not None:
                    amount = float(item_data.price) * float(item_data.quantity)
                else:
                    amount = 0.0
            
            doc_item = WarehouseDocumentItem(
                document_id=document.id,
                item_id=item_id,
                item_iiko_id=item_iiko_id,
                item_name=item_name,
                quantity=item_data.quantity,
                price=item_data.price,
                amount=amount,
                batch_number=item_data.batch_number,
                expiry_date=parse_date(item_data.expiry_date) if item_data.expiry_date else None,
            )
            db.add(doc_item)
            total_sum += float(amount)
        
        # Создаем Income для приходной накладной
        if total_sum > 0:
            new_income = Income(
                income_type="INCOMING_INVOICE",
                amount=total_sum,
                date=date_incoming,
                warehouse_document_id=document.id,
                organization_id=document_data.organization_id,
                comment=f"Приходная накладная {document_data.document_number or ''}",
            )
            db.add(new_income)
        
        db.commit()
        db.refresh(document)
        
        logger.info(f"Приходная накладная создана: iiko_id={iiko_id}, document_id={document.id}")
        
        return {
            "success": True,
            "message": "Приходная накладная успешно создана",
            "iiko_id": iiko_id,
            "document_id": document.id
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка создания приходной накладной: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Ошибка создания приходной накладной: {str(e)}",
            "iiko_id": None,
            "document_id": None
        }


async def create_outgoing_invoice_in_iiko(
    db: Session,
    document_data: CreateWarehouseDocumentRequest,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Создать расходную накладную в iiko API
    
    Args:
        db: сессия БД
        document_data: данные расходной накладной
        user_id: ID пользователя, создающего документ
    
    Returns:
        Словарь с результатом создания:
        {
            "success": bool,
            "message": str,
            "iiko_id": Optional[str],
            "document_id": Optional[int]
        }
    """
    try:
        # Валидация организации (опционально)
        # organization_id не обязателен, так как все параметры (store, conception) статические
        organization = None
        if document_data.organization_id:
            organization = db.query(Organization).filter(
                Organization.id == document_data.organization_id
            ).first()
            
            if not organization:
                logger.warning(f"Организация с ID {document_data.organization_id} не найдена, продолжаем без organization_id")
        
        # Валидация товаров
        invalid_items = []
        for idx, item_data in enumerate(document_data.items, start=1):
            if item_data.item_id:
                # Проверяем по нашему id
                item_obj = db.query(Item).filter(Item.id == item_data.item_id).first()
                if not item_obj:
                    invalid_items.append(f"Позиция {idx}: товар с ID {item_data.item_id} не найден")
            elif item_data.item_iiko_id:
                # Обратная совместимость: проверяем по iiko_id
                item_obj = db.query(Item).filter(Item.iiko_id == item_data.item_iiko_id).first()
                if not item_obj:
                    invalid_items.append(f"Позиция {idx}: товар с iiko_id {item_data.item_iiko_id} не найден")
            else:
                invalid_items.append(f"Позиция {idx}: не указан ни item_id, ни item_iiko_id")
        
        if invalid_items:
            return {
                "success": False,
                "message": "Найдены ошибки в позициях: " + "; ".join(invalid_items),
                "iiko_id": None,
                "document_id": None
            }
        
        # Парсим дату
        try:
            date_incoming = parse_date(document_data.date_incoming or document_data.date)
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "iiko_id": None,
                "document_id": None
            }
        
        # Формируем запрос для iiko API
        # Для расходной накладной используется XML формат, как и для приходной
        iiko_request = {
            "dateIncoming": format_date_dd_mm_yyyy(date_incoming),  # Формат dd.mm.YYYY для XML
            "status": document_data.status or "NEW",  # По умолчанию "NEW"
        }
        
        # Добавляем documentNumber если указан
        if document_data.document_number:
            iiko_request["documentNumber"] = document_data.document_number
        
        # Обработка Store (склад) для расходных накладных
        # Всегда используем фиксированный store
        iiko_request["defaultStoreId"] = DEFAULT_STORE_IIKO_ID
        logger.info(f"Используется склад для расходной накладной: {DEFAULT_STORE_IIKO_ID}")
        
        # Обработка Account (счет)
        if document_data.account_id:
            # Если передан account_id (наш id), получаем iiko_id из БД
            account = db.query(Account).filter(Account.id == document_data.account_id).first()
            if not account:
                return {
                    "success": False,
                    "message": f"Счет с ID {document_data.account_id} не найден",
                    "iiko_id": None,
                    "document_id": None
                }
            # Для расходных накладных используется код счета
            if account.code:
                iiko_request["accountToCode"] = account.code
        elif document_data.account_to_code:
            iiko_request["accountToCode"] = document_data.account_to_code
        
        if document_data.revenue_account_code:
            iiko_request["revenueAccountCode"] = document_data.revenue_account_code
        
        # Обработка Counteragent (контрагент)
        # Пока нет модели Counteragent, используем прямое указание iiko_id
        if document_data.counteragent_id:
            # TODO: Когда будет создана модель Counteragent, добавить преобразование
            # Пока оставляем как есть, но логируем предупреждение
            logger.warning("counteragent_id передан как int, но модель Counteragent еще не создана. Используется как iiko_id")
            # Временно не обрабатываем, так как нет модели
        elif document_data.counteragent_iiko_id:
            iiko_request["counteragentId"] = document_data.counteragent_iiko_id
        
        if document_data.counteragent_code:
            iiko_request["counteragentCode"] = document_data.counteragent_code
        
        # Обработка Conception (концепция) для расходных накладных
        # Всегда используем фиксированную концепцию по iiko_id
        iiko_request["conceptionId"] = DEFAULT_CONCEPTION_IIKO_ID
        iiko_request["conceptionCode"] = DEFAULT_CONCEPTION_CODE
        logger.info(f"Используется концепция для расходной накладной: iiko_id={DEFAULT_CONCEPTION_IIKO_ID}, код={DEFAULT_CONCEPTION_CODE}")
        if document_data.comment:
            iiko_request["comment"] = document_data.comment
        if document_data.use_default_document_time is not None:
            iiko_request["useDefaultDocumentTime"] = document_data.use_default_document_time
        
        # Формируем позиции
        iiko_request["items"] = []
        for idx, item_data in enumerate(document_data.items, start=1):
            # Получаем iiko_id товара из нашего id или напрямую
            item_iiko_id = None
            if item_data.item_id:
                # Если передан item_id (наш id), получаем iiko_id из БД
                item = db.query(Item).filter(Item.id == item_data.item_id).first()
                if not item:
                    logger.warning(f"Позиция {idx}: товар с ID {item_data.item_id} не найден, пропускаем")
                    continue
                item_iiko_id = item.iiko_id
            elif item_data.item_iiko_id:
                # Обратная совместимость: прямое указание iiko_id
                item_iiko_id = item_data.item_iiko_id
            else:
                logger.warning(f"Позиция {idx}: не указан ни item_id, ни item_iiko_id, пропускаем")
                continue
                
            item_dict = {
                "num": idx,
                "productId": item_iiko_id,  # Для расходных накладных используется "productId"
                "amount": float(item_data.quantity),
            }
            
            # Обязательно указываем цену и сумму
            if item_data.price is not None:
                item_dict["price"] = float(item_data.price)
            
            if item_data.amount is not None:
                item_dict["sum"] = float(item_data.amount)
            elif item_data.price is not None:
                # Рассчитываем сумму, если не указана
                item_dict["sum"] = float(item_data.price) * float(item_data.quantity)
            else:
                # Если нет ни цены, ни суммы - пропускаем позицию
                logger.warning(f"Позиция {idx}: не указаны цена и сумма, пропускаем")
                continue
            
            iiko_request["items"].append(item_dict)
        
        # Отправляем запрос в iiko API
        logger.info(f"Создание расходной накладной в iiko: {iiko_request}")
        iiko_response = await iiko_service.create_outgoing_invoice(iiko_request)
        
        if not iiko_response:
            return {
                "success": False,
                "message": "Не удалось создать расходную накладную в iiko API",
                "iiko_id": None,
                "document_id": None
            }

        # Явная проверка iiko-валидации: если iiko вернул valid=false — НЕ коммитим в БД.
        # Без этой проверки ошибка iiko молча проглатывалась, документ в нашу БД попадал, в iiko — нет.
        if isinstance(iiko_response, dict) and iiko_response.get("valid") is False:
            error_msg = (
                iiko_response.get("errorMessage")
                or iiko_response.get("error")
                or iiko_response.get("message")
                or "iiko вернул valid=false"
            )
            logger.warning(
                f"iiko отклонил расходную накладную: {error_msg} | response={iiko_response}"
            )
            return {
                "success": False,
                "message": f"iiko отклонил расходную накладную: {error_msg}",
                "iiko_id": None,
                "document_id": None,
            }

        # Извлекаем ID созданного документа из ответа
        iiko_id = None
        if isinstance(iiko_response, dict):
            if iiko_response.get("valid", False):
                # Если документ валиден, но id нет в ответе, используем documentNumber как идентификатор
                document_number = iiko_response.get("documentNumber")
                if document_number:
                    logger.info(f"Документ прошел валидацию, номер: {document_number}")
            iiko_id = iiko_response.get("id") or iiko_response.get("documentId") or iiko_response.get("iiko_id")
            if not iiko_id and "response" in iiko_response:
                response_data = iiko_response.get("response")
                if isinstance(response_data, dict):
                    iiko_id = response_data.get("id") or response_data.get("documentId")
                elif isinstance(response_data, list) and response_data:
                    iiko_id = response_data[0].get("id") or response_data[0].get("documentId")

        # Если iiko НЕ подтвердил создание (нет ни iiko_id, ни явного valid=true) — не сохраняем локально.
        if not iiko_id and not (isinstance(iiko_response, dict) and iiko_response.get("valid") is True):
            logger.warning(
                f"iiko не подтвердил создание расходной накладной (нет id и нет valid=true): {iiko_response}"
            )
            return {
                "success": False,
                "message": "iiko не подтвердил создание расходной накладной (нет id и нет valid=true)",
                "iiko_id": None,
                "document_id": None,
            }

        if not iiko_id:
            logger.info(f"iiko_id не пришёл, но valid=true — сохраняем по documentNumber. response={iiko_response}")
        
        # Всегда используем фиксированные значения для сохранения в БД
        store_iiko_id_for_db = DEFAULT_STORE_IIKO_ID
        store_code_for_db = None
        # Пытаемся получить код склада из БД (опционально)
        store = db.query(Store).filter(Store.iiko_id == DEFAULT_STORE_IIKO_ID).first()
        if store:
            store_code_for_db = store.code
        
        account_code_for_db = None
        if document_data.account_id:
            account = db.query(Account).filter(Account.id == document_data.account_id).first()
            if account and account.code:
                account_code_for_db = account.code
        
        # Всегда используем фиксированную концепцию для сохранения в БД
        conception_iiko_id_for_db = DEFAULT_CONCEPTION_IIKO_ID
        conception_code_for_db = DEFAULT_CONCEPTION_CODE
        
        # Сохраняем документ в локальную БД
        document = WarehouseDocument(
            iiko_id=iiko_id if iiko_id else None,
            document_type="WRITEOFF",
            document_source="OUTGOING_INVOICE",
            document_number=document_data.document_number,
            date=date_incoming,
            date_incoming=date_incoming,
            status=document_data.status,
            organization_id=document_data.organization_id,
            use_default_document_time=document_data.use_default_document_time,
            account_to_code=account_code_for_db or document_data.account_to_code,
            revenue_account_code=document_data.revenue_account_code,
            default_store_id=store_iiko_id_for_db,  # Пока сохраняем iiko_id как строку
            default_store_code=store_code_for_db or document_data.default_store_code,
            counteragent_id=document_data.counteragent_iiko_id,  # Пока нет модели Counteragent
            counteragent_code=document_data.counteragent_code,
            conception_id=conception_iiko_id_for_db,  # Пока сохраняем iiko_id как строку
            conception_code=conception_code_for_db,
            comment=document_data.comment,
            created_by=user_id,
        )
        
        db.add(document)
        db.flush()
        
        # Создаем позиции документа
        total_sum = 0.0
        for idx, item_data in enumerate(document_data.items, start=1):
            # Получаем item_id и item_iiko_id
            item_id = None
            item_iiko_id = None
            item_name = item_data.item_name
            
            if item_data.item_id:
                item = db.query(Item).filter(Item.id == item_data.item_id).first()
                if item:
                    item_id = item.id
                    item_iiko_id = item.iiko_id
                    if not item_name:
                        item_name = item.name
            elif item_data.item_iiko_id:
                item = db.query(Item).filter(Item.iiko_id == item_data.item_iiko_id).first()
                if item:
                    item_id = item.id
                    item_iiko_id = item.iiko_id
                    if not item_name:
                        item_name = item.name
                else:
                    item_iiko_id = item_data.item_iiko_id
            
            amount = item_data.amount
            if amount is None:
                if item_data.price is not None:
                    amount = float(item_data.price) * float(item_data.quantity)
                else:
                    amount = 0.0
            
            doc_item = WarehouseDocumentItem(
                document_id=document.id,
                item_id=item_id,
                item_iiko_id=item_iiko_id,
                item_name=item_name,
                quantity=item_data.quantity,
                price=item_data.price,
                amount=amount,
                batch_number=item_data.batch_number,
                expiry_date=parse_date(item_data.expiry_date) if item_data.expiry_date else None,
            )
            db.add(doc_item)
            total_sum += float(amount)
        
        # Создаем Expense для расходной накладной
        if total_sum > 0:
            new_expense = Expense(
                expense_type="OUTGOING_INVOICE",
                amount=total_sum,
                date=date_incoming,
                account_id=document_data.account_to_code,
                warehouse_document_id=document.id,
                organization_id=document_data.organization_id,
                comment=f"Расходная накладная {document_data.document_number or ''}",
            )
            db.add(new_expense)
        
        db.commit()
        db.refresh(document)
        
        logger.info(f"Расходная накладная создана: iiko_id={iiko_id}, document_id={document.id}")
        
        return {
            "success": True,
            "message": "Расходная накладная успешно создана",
            "iiko_id": iiko_id,
            "document_id": document.id
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка создания расходной накладной: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Ошибка создания расходной накладной: {str(e)}",
            "iiko_id": None,
            "document_id": None
        }


async def create_inventory_in_iiko(
    db: Session,
    document_data: SimpleInventoryRequest,
    organization_id: int,
    user_id: Optional[int] = None,
    store_iiko_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Создать инвентаризацию в iiko API
    
    Args:
        db: сессия БД
        document_data: данные инвентаризации
        organization_id: ID организации
        user_id: ID пользователя, создающего документ
        store_iiko_id: iiko_id склада (опционально, по умолчанию используется DEFAULT_STORE_IIKO_ID)
    
    Returns:
        Словарь с результатом создания:
        {
            "success": bool,
            "message": str,
            "iiko_id": Optional[str],
            "document_id": Optional[int]
        }
    """
    try:
        # Валидация организации
        organization = db.query(Organization).filter(Organization.id == organization_id).first()
        if not organization:
            return {
                "success": False,
                "message": f"Организация с ID {organization_id} не найдена",
                "iiko_id": None,
                "document_id": None
            }
        
        # Получаем товары из БД и проверяем их наличие
        item_ids = [item.id for item in document_data.items]
        items_dict = {}
        items_iiko_ids = {}
        
        for item_data in document_data.items:
            item = db.query(Item).filter(Item.id == item_data.id).first()
            if not item:
                return {
                    "success": False,
                    "message": f"Товар с ID {item_data.id} не найден в БД",
                    "iiko_id": None,
                    "document_id": None
                }
            
            if not item.iiko_id:
                return {
                    "success": False,
                    "message": f"У товара с ID {item_data.id} не указан iiko_id",
                    "iiko_id": None,
                    "document_id": None
                }
            
            items_dict[item_data.id] = item
            items_iiko_ids[item_data.id] = {
                "iiko_id": item.iiko_id,
                "name": item.name
            }
        
        # Парсим дату
        try:
            # Формат dd.mm.YYYY
            date_obj = datetime.strptime(document_data.dateIncoming, "%d.%m.%Y")
            # Форматируем для iiko API: yyyy-MM-ddTHH:mm:ss
            date_incoming_str = date_obj.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return {
                "success": False,
                "message": f"Неверный формат даты: {document_data.dateIncoming}. Ожидается формат dd.mm.YYYY",
                "iiko_id": None,
                "document_id": None
            }
        
        # Используем переданный store_iiko_id или фиксированный
        effective_store_iiko_id = store_iiko_id or DEFAULT_STORE_IIKO_ID
        
        # Формируем запрос для iiko API
        iiko_request = {
            "dateIncoming": date_incoming_str,
            "status": "NEW",
            "storeId": effective_store_iiko_id,
            "conceptionId": DEFAULT_CONCEPTION_IIKO_ID,
            "conceptionCode": DEFAULT_CONCEPTION_CODE,
            "comment": document_data.comment,
            "accountSurplusCode": document_data.accountSurplusCode or "5.10",
            "accountShortageCode": document_data.accountShortageCode or "5.09",
            "items": []
        }
        
        logger.info(f"Используется склад: {effective_store_iiko_id}")
        logger.info(f"Используется концепция: iiko_id={DEFAULT_CONCEPTION_IIKO_ID}, код={DEFAULT_CONCEPTION_CODE}")
        
        # Формируем позиции документа
        for item_data in document_data.items:
            item_iiko_id = items_iiko_ids[item_data.id]["iiko_id"]
            
            item_request = {
                "status": "NEW",
                "productId": item_iiko_id,
                "amountContainer": float(item_data.amount)
            }
            
            if item_data.containerId:
                item_request["containerId"] = item_data.containerId
            if item_data.comment:
                item_request["comment"] = item_data.comment
            
            iiko_request["items"].append(item_request)
        
        # Отправляем запрос в iiko API
        logger.info(f"Отправка запроса на создание инвентаризации в iiko API для организации {organization_id}")
        iiko_result = await iiko_service.create_inventory(iiko_request)
        
        if not iiko_result:
            return {
                "success": False,
                "message": "Не удалось создать инвентаризацию в iiko API",
                "iiko_id": None,
                "document_id": None
            }
        
        # Проверяем результат валидации
        if not iiko_result.get("valid", False):
            error_msg = iiko_result.get("errorMessage", "Неизвестная ошибка валидации")
            return {
                "success": False,
                "message": f"Ошибка валидации в iiko API: {error_msg}",
                "iiko_id": None,
                "document_id": None,
                "iiko_validation_result": iiko_result
            }
        
        # Получаем номер документа из ответа iiko
        document_number = iiko_result.get("documentNumber")
        iiko_document_id = None  # iiko не возвращает id документа в ответе на инвентаризацию
        
        # Сохраняем документ в БД
        from services.warehouse.warehouse_service import generate_document_number
        db_document_number = document_number or generate_document_number(db, "INVENTORY")
        
        # Создаем документ в БД
        from models.warehouse import WarehouseDocument, WarehouseDocumentItem
        
        db_document = WarehouseDocument(
            document_type="INVENTORY",
            document_number=db_document_number,
            date=date_obj,
            date_incoming=date_obj,
            status="NEW",
            organization_id=organization_id,
            store_id=DEFAULT_STORE_IIKO_ID,
            conception=DEFAULT_CONCEPTION_IIKO_ID,
            conception_code=DEFAULT_CONCEPTION_CODE,
            comment=document_data.comment,
            created_by=user_id,
            iiko_id=iiko_document_id
        )
        
        db.add(db_document)
        db.flush()
        
        # Сохраняем позиции документа
        for idx, item_data in enumerate(document_data.items):
            item = items_dict[item_data.id]
            db_item = WarehouseDocumentItem(
                document_id=db_document.id,
                item_id=item.id,
                quantity=item_data.amount,
                price=item_data.price or 0.0,
                amount=item_data.sum or (item_data.amount * (item_data.price or 0.0))
            )
            db.add(db_item)
        
        db.commit()
        
        logger.info(f"Инвентаризация создана: ID={db_document.id}, номер={db_document_number}, organization_id={organization_id}")
        
        return {
            "success": True,
            "message": f"Инвентаризация успешно создана (номер: {db_document_number})",
            "iiko_id": iiko_document_id,
            "document_id": db_document.id,
            "document_number": db_document_number,
            "iiko_validation_result": iiko_result
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка создания инвентаризации: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Ошибка создания инвентаризации: {str(e)}",
            "iiko_id": None,
            "document_id": None
        }

