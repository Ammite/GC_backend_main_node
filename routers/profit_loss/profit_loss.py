from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user
from database.database import get_db
from services.profit_loss import get_profit_loss_report
from schemas.profit_loss import ProfitLossResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/profit-loss", response_model=ProfitLossResponse)
def get_profit_loss_endpoint(
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY"),
    period: Optional[str] = Query(default="day", description="Период: day, week, month"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    """
    Получить отчет о прибылях и убытках (Profit & Loss Report)
    
    **Query Parameters:**
    - `date` (optional): Дата в формате "DD.MM.YYYY" - дата для отчета
    - `period` (optional): Период отчета ("day" | "week" | "month")
    - `organization_id` (optional): ID организации для фильтрации
    
    **Response:**
    - `total_revenue`: Общий доход (из Sales.dish_discount_sum_int)
    - `revenue_by_category`: Доходы по категориям (Кухня, Бар, Прочее)
    - `total_expenses`: Общие расходы (из Transactions: EXPENSES, EQUITY, EMPLOYEES_LIABILITY, DEBTS_OF_EMPLOYEES)
    - `expenses_by_type`: Расходы по типам счетов
    - `bank_commission`: Комиссия банка (из d_order.bank_commission)
    - `gross_profit`: Валовая прибыль (Доход - Расходы - Комиссия)
    - `profit_margin`: Маржа прибыли в процентах
    
    **Расчет прибыли:**
    ```
    Прибыль = Доход - Расходы - Комиссия банков
    Маржа = (Прибыль / Доход) * 100%
    ```
    """
    try:
        report = get_profit_loss_report(
            db=db,
            date=date,
            period=period,
            organization_id=organization_id
        )
        return report
    except Exception as e:
        logger.error(f"Error generating profit & loss report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

