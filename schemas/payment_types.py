from pydantic import BaseModel
from typing import List, Optional


class PaymentTypeResponse(BaseModel):
    id: int
    iiko_id: str
    name: Optional[str] = None
    code: Optional[str] = None
    payment_type_kind: Optional[str] = None
    comment: Optional[str] = None
    combinable: Optional[bool] = None
    print_cheque: Optional[bool] = None
    payment_processing_type: Optional[str] = None
    is_payable: Optional[bool] = None
    source: Optional[str] = None


class PaymentTypesArrayResponse(BaseModel):
    success: bool
    message: str
    payment_types: List[PaymentTypeResponse]
