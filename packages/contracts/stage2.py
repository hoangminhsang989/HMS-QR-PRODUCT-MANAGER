from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from packages.domain.stage2 import DeliveryStatus, POStatus, RunStatus

class CustomerPayload(BaseModel):
    customer_code: str|None=None; name: str=Field(min_length=1); short_name: str|None=None; address: str|None=None; tax_code: str|None=None; contact_name: str|None=None; phone: str|None=None; email: str|None=None; notes: str|None=None; active: bool=True
class CustomerPatch(BaseModel):
    name: str|None=None; short_name: str|None=None; address: str|None=None; tax_code: str|None=None; contact_name: str|None=None; phone: str|None=None; email: str|None=None; notes: str|None=None; active: bool|None=None
class CustomerResponse(CustomerPayload):
    model_config=ConfigDict(from_attributes=True); internal_id: UUID; customer_code: str; created_at: object; updated_at: object; created_by: str; updated_by: str
class POData(BaseModel):
    po_number: str; customer_id: UUID; po_date: date; requested_delivery_date: date|None=None; status: POStatus=POStatus.DRAFT; notes: str|None=None
class POLineData(BaseModel):
    product_id: UUID; line_number: int=Field(ge=1); ordered_quantity: Decimal=Field(gt=0); unit: str; unit_price: Decimal|None=None; currency: str|None=None; customer_part_reference: str|None=None; notes: str|None=None
class DeliveryData(BaseModel):
    planned_date: date; planned_quantity: Decimal=Field(gt=0); status: DeliveryStatus=DeliveryStatus.PLANNED; notes: str|None=None
class RunData(BaseModel):
    po_line_id: UUID; product_id: UUID; ordered_quantity: Decimal=Field(gt=0); run_code: str|None=None; planned_quantity: Decimal=Field(gt=0); completed_quantity: Decimal=Field(ge=0,default=Decimal("0")); status: RunStatus=RunStatus.PLANNED; priority: int=0; planned_start: date|None=None; planned_finish: date|None=None; notes: str|None=None
def dump(obj):
    from dataclasses import asdict
    data=asdict(obj)
    for k,v in list(data.items()):
        if isinstance(v,(UUID,date)): data[k]=str(v)
        elif hasattr(v,"value"): data[k]=v.value
        elif isinstance(v,Decimal): data[k]=str(v)
    return data
