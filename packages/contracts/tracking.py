from datetime import date,datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel,Field
from packages.domain.tracking import ReportKind
class TrackingCreate(BaseModel):
    purchase_order_id:UUID;purchase_order_line_id:UUID;product_id:UUID;customer_id:UUID;quantity:Decimal=Field(gt=0);unit:str;delivery_date:date
class DateChange(BaseModel):delivery_date:date;reason:str|None=None
class NewOrder(BaseModel):po_number:str;delivery_date:date
class OperatorCreate(BaseModel):display_name:str
class PreferenceSet(BaseModel):machining_type_id:UUID
class AttemptExpand(BaseModel):machining_type_id:UUID;new_max:int=Field(ge=3,le=99);user_id:UUID|None=None
class ReportSubmit(BaseModel):
    request_id:UUID;tracking_item_id:UUID;machining_type_id:UUID;kind:ReportKind;attempt_number:int|None=None;quantity:Decimal=Field(gt=0);notes:str|None=None;actor_user_id:UUID;actor_display_name:str;client_timestamp:datetime|None=None;device_id:str|None=None
class ReportRevision(BaseModel):request_id:UUID;quantity:Decimal=Field(gt=0);actor_user_id:UUID;actor_display_name:str;reason:str
