from fastapi import APIRouter, Depends, Query, HTTPException, Path, Body
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user
from database.database import get_db
from services.analytics.analytics_service import get_expenses_analytics
from schemas.analytics import ExpensesAnalyticsResponse
from services.expenses.expenses_management_service import (
    create_expense,
    get_expenses,
    get_expense_by_id,
    update_expense,
    delete_expense,
)
from schemas.expenses_management import (
    CreateExpenseRequest,
    CreateExpenseResponse,
    ExpensesListResponse,
    ExpenseDetailResponse,
    UpdateExpenseRequest,
    UpdateExpenseResponse,
    DeleteExpenseResponse,
)
from schemas.pay_out import CreatePayOutRequest
from services.cash.pay_out_service import create_pay_out_in_iiko
from models.organization import Organization
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])
router_management = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("/expenses", response_model=ExpensesAnalyticsResponse)
async def get_expenses_endpoint(
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY"),
    period: Optional[str] = Query(default="day", description="Период: day, week, month"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить аналитику расходов
    
    **Query Parameters:**
    - `date` (optional): Дата в формате "DD.MM.YYYY" - дата для аналитики
    - `period` (optional): Период аналитики ("day" | "week" | "month")
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - `expenses_amount`: Общая сумма расходов
    - `data`: Массив групп расходов по типам счетов
        - `transaction_type`: Тип счета (EXPENSES, EQUITY, EMPLOYEES_LIABILITY, DEBTS_OF_EMPLOYEES)
        - `transaction_name`: Название счета
        - `transaction_amount`: Сумма всех транзакций по этому счету
        - `transactions`: Массив отдельных транзакций с деталями
    
    **Типы расходов:**
    - EXPENSES - Расходы
    - EQUITY - Капитал
    - EMPLOYEES_LIABILITY - Обязательства перед сотрудниками
    - DEBTS_OF_EMPLOYEES - Долги сотрудников
    """
    try:
        expenses = await get_expenses_analytics(
            db=db,
            date=date,
            period=period,
            organization_id=organization_id
        )
        return expenses
    except Exception as e:
        logger.error(f"Error getting expenses analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ==================== УПРАВЛЕНИЕ РАСХОДАМИ ====================

@router_management.post("", response_model=CreateExpenseResponse)
async def create_expense_endpoint(
    expense_data: CreateExpenseRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Создать новый расход и отправить изъятие в iiko.

    **Request Body:**
    - `organization_id` (int) — ID организации
    - `expense_type` (str) — UUID типа изъятия из iiko (из `GET /pay-out-types`)
    - `amount` (float) — сумма расхода
    - `date` (str) — дата в формате "DD.MM.YYYY" или ISO
    - `comment` (str, optional) — комментарий
    - `account_id` (str, optional) — iiko_id счёта из таблицы Account
    - `counteragent_id` (int, optional) — ID контрагента из нашей БД.
      Обязателен, если у типа изъятия `counteragentType != NONE`:
      - `EMPLOYEE` — ID сотрудника из `/employees`
      - `SUPPLIER` — ID поставщика

    **Пример:**
    ```json
    {
      "organization_id": 13,
      "expense_type": "de9eac0d-a85a-47ee-935c-5cb7b9c4e041",
      "amount": 50000.00,
      "date": "01.04.2026",
      "comment": "Аванс сотруднику",
      "counteragent_id": 42
    }
    ```
    """
    try:
        expense = create_expense(db, expense_data, user_id=user.id if hasattr(user, 'id') else None)

        iiko_message = ""
        # expense_type — UUID типа изъятия, department берём через organization.department_id
        if expense_data.organization_id:
            org = db.query(Organization).filter(Organization.id == expense_data.organization_id).first()
            dept = None
            if org and org.department_id:
                from models.department import Department
                dept = db.query(Department).filter(Department.id == org.department_id).first()
            logger.info(f"Expense iiko send: org_id={expense_data.organization_id}, org.department_id={org.department_id if org else None}, dept.iiko_id={dept.iiko_id if dept else None}")
            if dept and dept.iiko_id:
                try:
                    from datetime import datetime as _dt
                    raw_date = expense_data.date
                    try:
                        parsed = _dt.strptime(raw_date, "%d.%m.%Y")
                    except ValueError:
                        parsed = _dt.fromisoformat(raw_date.replace("Z", "+00:00"))
                    pay_out_date = parsed.strftime("%Y-%m-%d")

                    pay_out_request = CreatePayOutRequest(
                        payOutTypeId=expense_data.expense_type,
                        payOutDate=pay_out_date,
                        departmentSumMap={dept.iiko_id: expense_data.amount},
                        comment=expense_data.comment,
                        counteragent_id=expense_data.counteragent_id,
                    )
                    pay_out_result = await create_pay_out_in_iiko(
                        db=db,
                        pay_out_data=pay_out_request,
                        organization_id=expense_data.organization_id,
                        user_id=user.id if hasattr(user, 'id') else None,
                    )
                    if pay_out_result.get("success"):
                        iiko_message = " и отправлен в iiko"
                    else:
                        iiko_message = f" (ошибка отправки в iiko: {pay_out_result.get('message', '')})"
                        logger.warning(f"Расход {expense.id} создан локально, но не отправлен в iiko: {pay_out_result}")
                except Exception as iiko_err:
                    iiko_message = " (ошибка отправки в iiko)"
                    logger.error(f"Ошибка отправки расхода {expense.id} в iiko: {iiko_err}", exc_info=True)
            else:
                iiko_message = " (для этой организации не задан департамент — в iiko не отправлено)"

        return CreateExpenseResponse(
            success=True,
            message=f"Расход успешно создан{iiko_message}",
            expense_id=expense.id
        )
    except Exception as e:
        logger.error(f"Error creating expense: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router_management.get("", response_model=ExpensesListResponse)
async def get_expenses_list_endpoint(
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    expense_type: Optional[str] = Query(default=None, description="Тип расхода для фильтрации"),
    from_date: Optional[str] = Query(default=None, description="Дата начала периода в формате DD.MM.YYYY"),
    to_date: Optional[str] = Query(default=None, description="Дата конца периода в формате DD.MM.YYYY"),
    limit: int = Query(default=100, description="Лимит записей"),
    offset: int = Query(default=0, description="Смещение для пагинации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить список расходов с фильтрацией
    """
    try:
        result = get_expenses(
            db=db,
            organization_id=organization_id,
            expense_type=expense_type,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
        return result
    except Exception as e:
        logger.error(f"Error getting expenses list: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router_management.get("/{expense_id}", response_model=ExpenseDetailResponse)
async def get_expense_detail_endpoint(
    expense_id: int = Path(..., description="ID расхода"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить детали расхода по ID
    """
    try:
        result = get_expense_by_id(db, expense_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Расход с ID={expense_id} не найден")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting expense detail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router_management.put("/{expense_id}", response_model=UpdateExpenseResponse)
async def update_expense_endpoint(
    expense_id: int = Path(..., description="ID расхода"),
    expense_data: UpdateExpenseRequest = Body(...),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Обновить расход (только локально, в iiko не перезаправляется).

    Все поля опциональны — передайте только те, что нужно изменить.
    """
    try:
        expense = update_expense(db, expense_id, expense_data)
        return UpdateExpenseResponse(
            success=True,
            message="Расход успешно обновлен",
            expense_id=expense.id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating expense: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router_management.delete("/{expense_id}", response_model=DeleteExpenseResponse)
async def delete_expense_endpoint(
    expense_id: int = Path(..., description="ID расхода"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Удалить расход
    """
    try:
        delete_expense(db, expense_id)
        return DeleteExpenseResponse(
            success=True,
            message="Расход успешно удален"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting expense: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

