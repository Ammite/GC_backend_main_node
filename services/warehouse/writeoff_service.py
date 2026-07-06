"""
Сервис для создания актов списания в iiko API
"""
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from models.organization import Organization
from models.account import Account
from models.store import Store
from models.item import Item
from models.warehouse import WarehouseDocument, WarehouseDocumentItem
from schemas.warehouse import CreateWriteoffDocumentRequest, CreateWriteoffItemRequest
from services.iiko.iiko_service import IikoService

logger = logging.getLogger(__name__)

iiko_service = IikoService()

# Константы для актов списания
DEFAULT_STORE_IIKO_ID = "5849a5b1-1a73-40c3-a2dd-fd32f35325a2"


def parse_date(date_str: str) -> datetime:
    """Парсинг даты из строки DD.MM.YYYY или ISO формата или YYYY-MM-DD или YYYY-MM-DDTHH:MM"""
    try:
        # Пробуем формат DD.MM.YYYY
        if "." in date_str and len(date_str.split(".")) == 3 and "T" not in date_str:
            return datetime.strptime(date_str, "%d.%m.%Y")
        # Пробуем формат YYYY-MM-DD
        if "-" in date_str and len(date_str.split("-")) == 3 and "T" not in date_str:
            return datetime.strptime(date_str, "%Y-%m-%d")
        # Пробуем формат YYYY-MM-DDTHH:MM
        if "T" in date_str:
            try:
                return datetime.strptime(date_str, "%Y-%m-%dT%H:%M")
            except:
                pass
        # Пробуем ISO формат
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception as e:
        logger.error(f"Ошибка парсинга даты {date_str}: {e}")
        raise ValueError(f"Неверный формат даты: {date_str}")


def format_date_for_iiko(dt: datetime) -> str:
    """Форматирование даты в формат YYYY-MM-DDTHH:MM для iiko API (акты списания требуют время)"""
    return dt.strftime("%Y-%m-%dT%H:%M")


async def create_writeoff_document_in_iiko(
    db: Session,
    document_data: CreateWriteoffDocumentRequest,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Создать акт списания в iiko API
    
    Args:
        db: сессия БД
        document_data: данные акта списания
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
        # Валидация организации
        organization = db.query(Organization).filter(
            Organization.id == document_data.organization_id
        ).first()
        
        if not organization:
            return {
                "success": False,
                "message": f"Организация с ID {document_data.organization_id} не найдена",
                "iiko_id": None,
                "document_id": None
            }
        
        # Валидация Store (склад)
        # Всегда используем фиксированный store
        if document_data.store_iiko_id:
            # Если указан store_iiko_id, используем его (но должен быть DEFAULT_STORE_IIKO_ID)
            store_iiko_id = document_data.store_iiko_id
        else:
            # Всегда используем фиксированный store
            store_iiko_id = DEFAULT_STORE_IIKO_ID
        
        # Валидация Account (счет)
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
            account_iiko_id = account.iiko_id
        elif document_data.account_iiko_id:
            # Обратная совместимость: прямое указание iiko_id
            account_iiko_id = document_data.account_iiko_id
        else:
            return {
                "success": False,
                "message": "Не указан account_id или account_iiko_id",
                "iiko_id": None,
                "document_id": None
            }
        
        # Валидация товаров
        invalid_items = []
        items_iiko_ids = {}
        for idx, item in enumerate(document_data.items, start=1):
            item_iiko_id = None
            item_id = None
            
            if item.item_id:
                # Если передан item_id (наш id), получаем iiko_id из БД
                item_obj = db.query(Item).filter(Item.id == item.item_id).first()
                if not item_obj:
                    invalid_items.append(f"Позиция {idx}: товар с ID {item.item_id} не найден")
                    continue
                item_iiko_id = item_obj.iiko_id
                item_id = item_obj.id
            elif item.product_id:
                # Обратная совместимость: прямое указание iiko_id
                item_obj = db.query(Item).filter(Item.iiko_id == item.product_id).first()
                if not item_obj:
                    invalid_items.append(f"Позиция {idx}: товар с iiko_id {item.product_id} не найден")
                    continue
                item_iiko_id = item.product_id
                item_id = item_obj.id
            else:
                invalid_items.append(f"Позиция {idx}: не указан ни item_id, ни product_id")
                continue
            
            items_iiko_ids[idx] = {
                "iiko_id": item_iiko_id,
                "item_id": item_id
            }
        
        if invalid_items:
            return {
                "success": False,
                "message": "Найдены несуществующие товары: " + "; ".join(invalid_items),
                "iiko_id": None,
                "document_id": None
            }
        
        # Парсим дату
        try:
            date_incoming = parse_date(document_data.date_incoming)
            # Если время не указано (00:00), используем текущее время
            if date_incoming.hour == 0 and date_incoming.minute == 0:
                now = datetime.now()
                date_incoming = date_incoming.replace(hour=now.hour, minute=now.minute)
        except ValueError as e:
            return {
                "success": False,
                "message": str(e),
                "iiko_id": None,
                "document_id": None
            }
        
        # Формируем запрос для iiko API
        # Обязательные поля: dateIncoming, status, storeId, accountId
        iiko_request = {
            "dateIncoming": format_date_for_iiko(date_incoming),
            "storeId": store_iiko_id,  # Используем iiko_id из БД
            "accountId": account_iiko_id,  # Используем iiko_id из БД
            "status": document_data.status or "NEW",  # По умолчанию "NEW"
            "items": []
        }
        
        # documentNumber не обязателен - если не задан, сгенерируется автоматически
        if document_data.document_number:
            iiko_request["documentNumber"] = document_data.document_number
        
        # comment опциональный
        if hasattr(document_data, 'comment') and document_data.comment:
            iiko_request["comment"] = document_data.comment
        
        # Формируем позиции
        # Обязательные поля для позиций: productId, amount
        for idx, item in enumerate(document_data.items):
            # Получаем iiko_id товара из нашего id или напрямую
            item_iiko_id = items_iiko_ids.get(idx + 1, {}).get("iiko_id")
            if not item_iiko_id:
                logger.warning(f"Позиция {idx + 1}: не найден iiko_id, пропускаем")
                continue
            
            # По формату iiko API для актов списания нужны только productId и amount
            item_data = {
                "productId": item_iiko_id,  # Используем iiko_id из БД
                "amount": float(item.amount)
            }
            
            iiko_request["items"].append(item_data)
        
        # Отправляем запрос в iiko API
        logger.info(f"Создание акта списания в iiko: {iiko_request}")
        iiko_response = await iiko_service.create_writeoff_document(iiko_request)
        
        if not iiko_response:
            return {
                "success": False,
                "message": "Не удалось создать акт списания в iiko API",
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
                f"iiko отклонил акт списания: {error_msg} | response={iiko_response}"
            )
            return {
                "success": False,
                "message": f"iiko отклонил акт списания: {error_msg}",
                "iiko_id": None,
                "document_id": None,
            }

        # Извлекаем ID созданного документа из ответа
        # Структура ответа может быть разной, проверяем несколько вариантов
        iiko_id = None
        if isinstance(iiko_response, dict):
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
                f"iiko не подтвердил создание акта списания (нет id и нет valid=true): {iiko_response}"
            )
            return {
                "success": False,
                "message": "iiko не подтвердил создание акта списания (нет id и нет valid=true)",
                "iiko_id": None,
                "document_id": None,
            }

        if not iiko_id:
            logger.info(f"iiko_id не пришёл, но valid=true — сохраняем без iiko_id. response={iiko_response}")
        
        # Сохраняем документ в локальную БД
        # Если iiko_id не получен, используем None (unique constraint позволяет NULL)
        document = WarehouseDocument(
            iiko_id=iiko_id if iiko_id else None,
            document_type="WRITEOFF",
            document_source="WRITEOFF",
            document_number=document_data.document_number,
            date=date_incoming,
            date_incoming=date_incoming,
            status=document_data.status,
            organization_id=document_data.organization_id,
            store_id=store_iiko_id,  # Пока сохраняем iiko_id как строку (для обратной совместимости)
            account_id=account_iiko_id,  # Пока сохраняем iiko_id как строку (для обратной совместимости)
            created_by=user_id,
        )
        
        db.add(document)
        db.flush()
        
        # Создаем позиции документа
        for idx, item in enumerate(document_data.items, start=1):
            item_info = items_iiko_ids.get(idx)
            if not item_info:
                continue
            
            doc_item = WarehouseDocumentItem(
                document_id=document.id,
                item_id=item_info.get("item_id"),  # Сохраняем наш внутренний ID
                item_iiko_id=item_info.get("iiko_id"),  # Сохраняем iiko_id
                product_id=item_info.get("iiko_id"),  # Для актов списания
                num=item.num or idx,
                product_size_id=item.product_size_id,
                amount_factor=item.amount_factor,
                amount=item.amount,
                quantity=item.amount,
                measure_unit_id=item.measure_unit_id,
                container_id=item.container_id,
                cost=item.cost,
                price=(item.cost / item.amount) if (item.cost is not None and item.amount and item.amount > 0) else 0,
                amount_total=item.cost,
            )
            db.add(doc_item)
        
        db.commit()
        db.refresh(document)
        
        logger.info(f"Акт списания создан: iiko_id={iiko_id}, document_id={document.id}")
        
        return {
            "success": True,
            "message": "Акт списания успешно создан",
            "iiko_id": iiko_id,
            "document_id": document.id
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка создания акта списания: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Ошибка создания акта списания: {str(e)}",
            "iiko_id": None,
            "document_id": None
        }

