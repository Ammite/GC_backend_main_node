from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from utils.security import get_current_user
from database.database import get_db
from services.profit_loss import get_profit_loss_report, get_profit_loss_detail
from schemas.profit_loss import ProfitLossResponse, ProfitLossDetailResponse
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/profit-loss", response_model=ProfitLossResponse)
async def get_profit_loss_endpoint(
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY"),
    period: Optional[str] = Query(default="day", description="Период: day, week, month"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    date_from: Optional[str] = Query(default=None, description="Начало периода DD.MM.YYYY (приоритет над date+period)"),
    date_to: Optional[str] = Query(default=None, description="Конец периода DD.MM.YYYY (приоритет над date+period)"),
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
        report = await get_profit_loss_report(
            db=db,
            date=date,
            period=period,
            organization_id=organization_id,
            date_from=date_from,
            date_to=date_to,
        )
        return report
    except Exception as e:
        logger.error(f"Error generating profit & loss report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/profit-loss/detail", response_model=ProfitLossDetailResponse)
def get_profit_loss_detail_endpoint(
    item_id: str = Query(description="ID статьи из profit-loss (например 'revenue_kitchen', 'expense_account:Аренда')"),
    item_type: str = Query(description="Тип: 'revenue' или 'expense'"),
    date_from: str = Query(description="Начало периода DD.MM.YYYY"),
    date_to: str = Query(description="Конец периода DD.MM.YYYY"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Детализация статьи P&L по организациям (точкам).

    Принимает ID статьи из ответа /reports/profit-loss и возвращает
    разбивку суммы по каждой организации за указанный период.
    """
    if item_type not in ("revenue", "expense"):
        raise HTTPException(status_code=400, detail="item_type должен быть 'revenue' или 'expense'")
    try:
        return get_profit_loss_detail(
            db=db,
            item_id=item_id,
            item_type=item_type,
            date_from=date_from,
            date_to=date_to,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating P&L detail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

