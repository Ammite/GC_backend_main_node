from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import logging

from database.database import get_db
from models.payment_type import PaymentType
from models.organization import Organization
from schemas.payment_types import PaymentTypesArrayResponse, PaymentTypeResponse
from utils.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["payment-types"])


@router.get("/payment-types", response_model=PaymentTypesArrayResponse)
def get_payment_types(
    organization_id: Optional[int] = Query(None, description="ID организации для фильтрации"),
    include_internal: bool = Query(False, description="Включать служебные виды (Перемещение, Бракераж и т.п.)"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Получить доступные виды оплат.

    - **organization_id**: фильтр по нашей организации. Возвращает только те
      виды оплат, которые привязаны к этой организации напрямую (Cloud) или
      через юр.лицо (Server-only с маркером "ИП Шаяхметов" и т.п.).
      Виды без явной привязки (`organization_iiko_ids IS NULL`) считаются
      доступными для всех организаций.
    - **include_internal**: по умолчанию false — служебные виды (Перемещение,
      Бракераж, Дегустация, Маркетинг и т.п.) скрыты. true — показываются.
    """
    try:
        query = db.query(PaymentType).filter(PaymentType.is_deleted == False)  # noqa: E712
        if not include_internal:
            query = query.filter(PaymentType.is_payable == True)  # noqa: E712

        if organization_id is not None:
            org = db.query(Organization).filter(Organization.id == organization_id).first()
            if not org or not org.iiko_id_cloud:
                return {
                    "success": True,
                    "message": "Организация не найдена или не имеет iiko_id_cloud",
                    "payment_types": [],
                }
            # Фильтр по организации:
            #   - organization_iiko_ids IS NULL → доступен для всех орг
            #   - org.iiko_id_cloud в списке → доступен этой орг
            payment_types = [
                pt for pt in query.all()
                if pt.organization_iiko_ids is None
                or org.iiko_id_cloud in pt.organization_iiko_ids
            ]
        else:
            payment_types = query.all()

        result = [
            PaymentTypeResponse(
                id=pt.id,
                iiko_id=pt.iiko_id,
                name=pt.name,
                code=pt.code,
                payment_type_kind=pt.payment_type_kind,
                comment=pt.comment,
                combinable=pt.combinable,
                print_cheque=pt.print_cheque,
                payment_processing_type=pt.payment_processing_type,
                is_payable=pt.is_payable,
                source=pt.source,
            )
            for pt in payment_types
        ]

        return {
            "success": True,
            "message": f"Найдено видов оплат: {len(result)}",
            "payment_types": result,
        }
    except Exception as e:
        logger.error(f"Ошибка при получении видов оплат: {e}")
        return {
            "success": False,
            "message": f"Ошибка: {str(e)}",
            "payment_types": [],
        }
