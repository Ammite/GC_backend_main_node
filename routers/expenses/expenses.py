from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user
from database.database import get_db
from services.analytics.analytics_service import get_expenses_analytics
from schemas.analytics import ExpensesAnalyticsResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/expenses", response_model=ExpensesAnalyticsResponse)
def get_expenses_endpoint(
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
        expenses = get_expenses_analytics(
            db=db,
            date=date,
            period=period,
            organization_id=organization_id
        )
        return expenses
    except Exception as e:
        logger.error(f"Error getting expenses analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

