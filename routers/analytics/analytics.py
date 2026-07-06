from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from utils.security import get_current_user, require_role
from database.database import get_db
from services.analytics.analytics_service import get_analytics
from schemas.analytics import AnalyticsResponse
from services.transactions_and_statistics.daily_aggregates_service import recalculate_daily_employee_metrics_for_date
import logging


logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["reports"])


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics_endpoint(
    date: Optional[str] = Query(default=None, description="Дата в формате DD.MM.YYYY"),
    period: Optional[str] = Query(default="day", description="Период: day, week, month"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации"),
    date_from: Optional[str] = Query(default=None, description="Начало периода DD.MM.YYYY (приоритет над date+period)"),
    date_to: Optional[str] = Query(default=None, description="Конец периода DD.MM.YYYY (приоритет над date+period)"),
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
):
    """
    Получить аналитику (для CEO)

    **Query Parameters:**
    - `date` (optional): Дата в формате "DD.MM.YYYY" - дата для аналитики
    - `period` (optional): Период аналитики ("day" | "week" | "month")
    - `date_from` (optional): Начало периода DD.MM.YYYY (приоритет над date+period)
    - `date_to` (optional): Конец периода DD.MM.YYYY (приоритет над date+period)
    - `organization_id` (optional): ID организации для фильтрации
    """
    try:
        analytics = await get_analytics(
            db=db,
            date=date,
            period=period,
            organization_id=organization_id,
            date_from=date_from,
            date_to=date_to,
        )
        return analytics
    except Exception as e:
        logger.error(f"Error getting analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/recalculate-employee-metrics")
async def recalculate_employee_metrics(
    from_date: Optional[str] = Query(default=None, description="Начальная дата в формате DD.MM.YYYY или YYYY-MM-DD (если не указана, используется to_date)"),
    to_date: Optional[str] = Query(default=None, description="Конечная дата в формате DD.MM.YYYY или YYYY-MM-DD (если не указана, используется сегодня)"),
    organization_id: Optional[int] = Query(default=None, description="ID организации для фильтрации (если не указан, пересчитываются для всех)"),
    db: Session = Depends(get_db),
    user = Depends(require_role("Менеджер")),
) -> Dict[str, Any]:
    """
    Пересчитать метрики по сотрудникам (таблица daily_employee_analytics) за указанный период.
    
    **Query Parameters:**
    - `from_date` (optional): Начальная дата в формате "YYYY-MM-DD". Если не указана, используется `to_date` или сегодня.
    - `to_date` (optional): Конечная дата в формате "YYYY-MM-DD". Если не указана, используется сегодня.
    - `organization_id` (optional): ID организации для фильтрации. Если не указан, пересчитываются метрики для всех организаций.
    
    **Примеры использования:**
    - Пересчитать за сегодня: `/recalculate-employee-metrics`
    - Пересчитать за конкретную дату: `/recalculate-employee-metrics?to_date=2024-01-15`
    - Пересчитать за период: `/recalculate-employee-metrics?from_date=2024-01-01&to_date=2024-01-31`
    - Пересчитать для организации: `/recalculate-employee-metrics?organization_id=1&to_date=2024-01-15`
    
    **Возвращает:**
    - `success`: Успешность операции
    - `message`: Сообщение о результате
    - `data`: Словарь с результатами пересчета:
        - `dates_processed`: Список обработанных дат
        - `total_dates`: Общее количество дат
        - `total_employees_processed`: Общее количество обработанных сотрудников
        - `errors`: Список ошибок (если есть)
    """
    try:
        def _parse_flex_date(value: str) -> 'date':
            """Парсит дату в формате DD.MM.YYYY или YYYY-MM-DD"""
            for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            raise HTTPException(
                status_code=400,
                detail=f"Неверный формат даты: {value}. Используйте DD.MM.YYYY или YYYY-MM-DD"
            )

        # Определяем даты
        if to_date:
            end_date = _parse_flex_date(to_date)
        else:
            end_date = datetime.now().date()

        if from_date:
            start_date = _parse_flex_date(from_date)
        else:
            start_date = end_date  # Если from_date не указан, используем to_date
        
        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="from_date не может быть больше to_date"
            )
        
        logger.info(f"Запуск пересчета метрик по сотрудникам с {start_date} по {end_date}" + (f" для организации {organization_id}" if organization_id else " для всех организаций"))
        
        # Пересчитываем метрики для каждой даты в диапазоне
        dates_processed = []
        errors = []
        total_employees_processed = 0
        current_date = start_date
        
        while current_date <= end_date:
            try:
                result = recalculate_daily_employee_metrics_for_date(db, current_date, organization_id)
                employees_count = result.get("processed_employees", 0)
                total_employees_processed += employees_count
                dates_processed.append({
                    "date": current_date.strftime('%Y-%m-%d'),
                    "success": True,
                    "employees_processed": employees_count
                })
                logger.debug(f"Пересчитаны метрики по сотрудникам за {current_date}: обработано {employees_count} сотрудников")
            except Exception as e:
                error_msg = f"Ошибка пересчета метрик по сотрудникам за {current_date}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append({
                    "date": current_date.strftime('%Y-%m-%d'),
                    "error": str(e)
                })
                dates_processed.append({
                    "date": current_date.strftime('%Y-%m-%d'),
                    "success": False,
                    "error": str(e)
                })
            
            current_date += timedelta(days=1)
        
        logger.info(f"Пересчет метрик по сотрудникам завершен. Обработано {len(dates_processed)} дат, {total_employees_processed} сотрудников, ошибок: {len(errors)}")
        
        return {
            "success": True,
            "message": f"Пересчет метрик по сотрудникам завершен. Обработано {len(dates_processed)} дат, {total_employees_processed} сотрудников, ошибок: {len(errors)}",
            "data": {
                "dates_processed": dates_processed,
                "total_dates": len(dates_processed),
                "total_employees_processed": total_employees_processed,
                "errors": errors if errors else None,
                "from_date": start_date.strftime('%Y-%m-%d'),
                "to_date": end_date.strftime('%Y-%m-%d'),
                "organization_id": organization_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка пересчета метрик по сотрудникам: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка пересчета метрик по сотрудникам: {str(e)}"
        )

