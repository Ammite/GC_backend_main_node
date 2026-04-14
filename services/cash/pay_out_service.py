"""
Сервис для создания изъятий из кассы в iiko API
"""
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging

from models.organization import Organization
from models.pay_out import PayOut, PayOutType
from models.account import Account
from models.employees import Employees
from models.supplier import Supplier
from schemas.pay_out import CreatePayOutRequest, PayOutTypeApiResponse, PayOutTypeResponse
from services.iiko.iiko_service import IikoService

logger = logging.getLogger(__name__)

iiko_service = IikoService()


async def sync_pay_out_types_from_iiko(db: Session, include_deleted: bool = False) -> Dict[str, Any]:
    """
    Синхронизировать типы изъятий/внесений из iiko API в локальную таблицу pay_out_types.

    - Берем данные с /resto/api/v2/entities/payInOutTypes/list.
    - Маппим chiefAccount/account на Account через Account.iiko_id.
    """
    try:
        raw_types = await iiko_service.get_pay_in_out_types(include_deleted=include_deleted)
        if raw_types is None:
            return {
                "success": False,
                "message": "Не удалось получить типы изъятий из iiko API",
                "synced": 0,
            }

        synced = 0

        # Подготовим карту iiko_id -> Account заранее
        accounts_by_iiko: Dict[str, Account] = {
            acc.iiko_id: acc for acc in db.query(Account).all() if acc.iiko_id
        }

        for item in raw_types:
            try:
                pay_out_type_api = PayOutTypeApiResponse.model_validate(item)
            except Exception as e:
                logger.warning(f"Пропуск типа изъятия из-за ошибки валидации: {e} | raw={item}")
                continue

            chief_acc_iiko = pay_out_type_api.chiefAccount
            acc_iiko = pay_out_type_api.account

            chief_account = accounts_by_iiko.get(chief_acc_iiko) if chief_acc_iiko else None
            account = accounts_by_iiko.get(acc_iiko) if acc_iiko else None

            existing = db.query(PayOutType).filter(PayOutType.id == pay_out_type_api.id).first()

            if existing:
                existing.chief_account_iiko_id = chief_acc_iiko
                existing.account_iiko_id = acc_iiko
                existing.chief_account_id = chief_account.id if chief_account else None
                existing.account_id = account.id if account else None
                existing.counteragent_type = pay_out_type_api.counteragentType
                existing.transaction_type = pay_out_type_api.transactionType
                if pay_out_type_api.cashFlowCategory:
                    existing.cash_flow_category_id = pay_out_type_api.cashFlowCategory.id
                    existing.cash_flow_category_code = pay_out_type_api.cashFlowCategory.code
                    existing.cash_flow_category_type = pay_out_type_api.cashFlowCategory.type
                existing.conception_iiko_id = (
                    pay_out_type_api.conception.id if pay_out_type_api.conception else None
                )
                existing.limit = pay_out_type_api.limit
                existing.comment = pay_out_type_api.comment
                existing.mandatory_front_comment = pay_out_type_api.mandatoryFrontComment
                existing.is_deleted = pay_out_type_api.isDeleted
            else:
                new_type = PayOutType(
                    id=pay_out_type_api.id,
                    chief_account_iiko_id=chief_acc_iiko,
                    account_iiko_id=acc_iiko,
                    chief_account_id=chief_account.id if chief_account else None,
                    account_id=account.id if account else None,
                    counteragent_type=pay_out_type_api.counteragentType,
                    transaction_type=pay_out_type_api.transactionType,
                    cash_flow_category_id=pay_out_type_api.cashFlowCategory.id
                    if pay_out_type_api.cashFlowCategory
                    else None,
                    cash_flow_category_code=pay_out_type_api.cashFlowCategory.code
                    if pay_out_type_api.cashFlowCategory
                    else None,
                    cash_flow_category_type=pay_out_type_api.cashFlowCategory.type
                    if pay_out_type_api.cashFlowCategory
                    else None,
                    conception_iiko_id=pay_out_type_api.conception.id
                    if pay_out_type_api.conception
                    else None,
                    limit=pay_out_type_api.limit,
                    comment=pay_out_type_api.comment,
                    mandatory_front_comment=pay_out_type_api.mandatoryFrontComment,
                    is_deleted=pay_out_type_api.isDeleted,
                )
                db.add(new_type)

            synced += 1

        db.commit()

        return {
            "success": True,
            "message": f"Синхронизировано типов изъятий: {synced}",
            "synced": synced,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка синхронизации типов изъятий: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Ошибка синхронизации типов изъятий: {str(e)}",
            "synced": 0,
        }


def get_local_pay_out_types(db: Session, include_deleted: bool = False) -> List[PayOutTypeResponse]:
    """
    Получить список типов изъятий из локальной таблицы pay_out_types
    с маппингом на названия счетов из accounts_list.
    """
    query = db.query(PayOutType, Account, Account).outerjoin(
        Account, PayOutType.account_id == Account.id
    )

    # Нам также понадобится chiefAccount, поэтому второй join (aliased через повторный Account)
    from sqlalchemy.orm import aliased

    ChiefAccount = aliased(Account)
    query = query.outerjoin(ChiefAccount, PayOutType.chief_account_id == ChiefAccount.id)

    if not include_deleted:
        query = query.filter((PayOutType.is_deleted.is_(False)) | (PayOutType.is_deleted.is_(None)))

    query = query.filter(PayOutType.chief_account_iiko_id.isnot(None))

    rows = query.all()

    result: List[PayOutTypeResponse] = []
    for pay_out_type, account, chief_account in rows:
        result.append(
            PayOutTypeResponse(
                id=pay_out_type.id,
                account_name=account.name if account else None,
                chief_account_name=chief_account.name if chief_account else None,
                transactionType=pay_out_type.transaction_type,
                counteragentType=pay_out_type.counteragent_type,
                comment=pay_out_type.comment,
            )
        )

    return result


async def create_pay_out_in_iiko(
    db: Session,
    pay_out_data: CreatePayOutRequest,
    organization_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Создать изъятие из кассы в iiko API
    
    Args:
        db: сессия БД
        pay_out_data: данные изъятия
        organization_id: ID организации (опционально)
        user_id: ID пользователя, создающего изъятие
    
    Returns:
        Словарь с результатом создания:
        {
            "success": bool,
            "message": str,
            "result": str,  # SUCCESS или ERROR
            "errors": Optional[List[Dict]],
            "payOutSettings": Optional[Dict],
            "pay_out_id": Optional[int]
        }
    """
    try:
        # Валидация организации (опционально)
        organization = None
        if organization_id:
            organization = db.query(Organization).filter(
                Organization.id == organization_id
            ).first()
            
            if not organization:
                logger.warning(f"Организация с ID {organization_id} не найдена, продолжаем без organization_id")
        
        # Проверка типа изъятия на основе локальной таблицы
        local_type = db.query(PayOutType).filter(PayOutType.id == pay_out_data.payOutTypeId).first()
        if not local_type:
            logger.warning(f"Тип изъятия {pay_out_data.payOutTypeId} не найден в локальной таблице pay_out_types")
        
        # Проверка торговых предприятий (departments)
        departments = await iiko_service.get_departments()
        if departments:
            department_ids = {dept.get("id") for dept in departments if dept.get("id")}
            missing_departments = [
                dept_id for dept_id in pay_out_data.departmentSumMap.keys()
                if dept_id not in department_ids
            ]
            if missing_departments:
                logger.warning(f"Торговые предприятия {missing_departments} не найдены в списке departments")
        
        # Проверка платежной ведомости (если указана)
        if pay_out_data.payrollId:
            # Получаем ведомости за период (берем дату изъятия ±30 дней)
            try:
                pay_out_date = datetime.strptime(pay_out_data.payOutDate, "%Y-%m-%d")
                date_from = (pay_out_date - timedelta(days=30)).strftime("%Y-%m-%d")
                date_to = (pay_out_date + timedelta(days=30)).strftime("%Y-%m-%d")
                
                payrolls = await iiko_service.get_payrolls(
                    date_from=date_from,
                    date_to=date_to,
                    include_deleted=False
                )
                if payrolls:
                    payroll_found = any(
                        payroll.get("id") == pay_out_data.payrollId
                        for payroll in payrolls
                    )
                    if not payroll_found:
                        logger.warning(f"Платежная ведомость {pay_out_data.payrollId} не найдена")
            except Exception as e:
                logger.warning(f"Ошибка при проверке платежной ведомости: {e}")
        
        # Резолвим counteragent: из нашего ID в iiko_id
        counteragent_iiko_id = None
        if local_type and local_type.counteragent_type and local_type.counteragent_type != "NONE":
            if not pay_out_data.counteragent_id:
                return {
                    "success": False,
                    "message": f"Для типа изъятия с counteragentType={local_type.counteragent_type} необходимо указать counteragent_id",
                    "result": "ERROR",
                    "errors": None,
                    "payOutSettings": None,
                    "pay_out_id": None,
                }

            if local_type.counteragent_type == "EMPLOYEE":
                employee = db.query(Employees).filter(Employees.id == pay_out_data.counteragent_id).first()
                if not employee:
                    return {
                        "success": False,
                        "message": f"Сотрудник с id {pay_out_data.counteragent_id} не найден",
                        "result": "ERROR", "errors": None, "payOutSettings": None, "pay_out_id": None,
                    }
                counteragent_iiko_id = employee.iiko_id

            elif local_type.counteragent_type == "SUPPLIER":
                supplier = db.query(Supplier).filter(Supplier.id == pay_out_data.counteragent_id).first()
                if not supplier:
                    return {
                        "success": False,
                        "message": f"Поставщик с id {pay_out_data.counteragent_id} не найден",
                        "result": "ERROR", "errors": None, "payOutSettings": None, "pay_out_id": None,
                    }
                counteragent_iiko_id = supplier.iiko_id

        # Формируем запрос для iiko API
        iiko_request = {
            "payOutTypeId": pay_out_data.payOutTypeId,
            "payOutDate": pay_out_data.payOutDate,
            "departmentSumMap": pay_out_data.departmentSumMap
        }

        if counteragent_iiko_id:
            iiko_request["counteragent"] = counteragent_iiko_id

        if pay_out_data.payrollId:
            iiko_request["payrollId"] = pay_out_data.payrollId

        if pay_out_data.comment:
            iiko_request["comment"] = pay_out_data.comment
        
        # Отправляем запрос в iiko API
        logger.info(f"Создание изъятия в iiko: {iiko_request}")
        iiko_response = await iiko_service.create_pay_out(iiko_request)
        
        if not iiko_response:
            return {
                "success": False,
                "message": "Не удалось создать изъятие в iiko API",
                "result": "ERROR",
                "errors": None,
                "payOutSettings": None,
                "pay_out_id": None
            }
        
        # Обрабатываем ответ
        result = iiko_response.get("result", "ERROR")
        errors = iiko_response.get("errors")
        pay_out_settings = iiko_response.get("payOutSettings") or iiko_response.get("payOutSettingsDto")
        
        # Определяем успешность операции
        success = result == "SUCCESS"
        
        # Сохраняем изъятие в локальную БД
        # Для departmentSumMap берем первое торговое предприятие (или можно создать несколько записей)
        # Создаем запись для каждого торгового предприятия
        pay_out_ids = []
        
        for department_id, amount in pay_out_data.departmentSumMap.items():
            pay_out = PayOut(
                pay_out_type_id=pay_out_data.payOutTypeId,
                pay_out_date=datetime.strptime(pay_out_data.payOutDate, "%Y-%m-%d"),
                counteragent_id=counteragent_iiko_id,
                department_id=department_id,
                amount=amount,
                payroll_id=pay_out_data.payrollId,
                comment=pay_out_data.comment,
                result=result,
                errors=errors if errors else None,
                organization_id=organization_id,
                created_by=user_id
            )
            
            db.add(pay_out)
            db.flush()
            pay_out_ids.append(pay_out.id)
        
        db.commit()
        
        message = "Изъятие успешно создано" if success else "Ошибка при создании изъятия"
        if errors:
            error_messages = [f"{err.get('code', 'UNKNOWN')}: {err.get('value', '')}" for err in errors]
            message += f". Ошибки: {', '.join(error_messages)}"
        
        return {
            "success": success,
            "message": message,
            "result": result,
            "errors": errors,
            "payOutSettings": pay_out_settings,
            "pay_out_id": pay_out_ids[0] if pay_out_ids else None  # Возвращаем первый ID
        }
        
    except Exception as e:
        logger.error(f"Ошибка создания изъятия: {e}", exc_info=True)
        db.rollback()
        return {
            "success": False,
            "message": f"Внутренняя ошибка при создании изъятия: {str(e)}",
            "result": "ERROR",
            "errors": None,
            "payOutSettings": None,
            "pay_out_id": None
        }
