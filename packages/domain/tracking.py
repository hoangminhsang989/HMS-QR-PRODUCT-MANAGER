from __future__ import annotations
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID, uuid4
import secrets

class TrackingError(ValueError): pass
class TrackingStatus(StrEnum): NEW="NEW"; IN_PROCESS="IN_PROCESS"; COMPLETED="COMPLETED"; HOLD="HOLD"; CANCELLED="CANCELLED"
class QRStatus(StrEnum): ACTIVE="ACTIVE"; REVOKED="REVOKED"
class ReportKind(StrEnum): ATTEMPT="ATTEMPT"; PROCESS_COMPLETED="PROCESS_COMPLETED"
def utc_now(): return datetime.now(timezone.utc)
def qty(value):
    try:q=Decimal(str(value))
    except (InvalidOperation,TypeError,ValueError) as e: raise TrackingError("quantity must be numeric") from e
    if not q.is_finite() or q<=0: raise TrackingError("quantity must be greater than 0")
    return q

@dataclass(frozen=True,slots=True)
class OrderTrackingItem:
    internal_id: UUID; tracking_code: str; purchase_order_id: UUID; purchase_order_line_id: UUID; product_id: UUID; customer_id: UUID; quantity: Decimal; unit: str; delivery_date: date; status: TrackingStatus; qr_public_id: str|None; qr_status: QRStatus|None; created_at: datetime; updated_at: datetime; created_by: str; updated_by: str
    @classmethod
    def create(cls,*,tracking_code,purchase_order_id,purchase_order_line_id,product_id,customer_id,quantity,unit,delivery_date,actor):
        t=utc_now(); return cls(uuid4(),tracking_code,purchase_order_id,purchase_order_line_id,product_id,customer_id,qty(quantity),unit,delivery_date,TrackingStatus.NEW,None,None,t,t,actor,actor)
    def change_delivery_date(self,new_date,actor): return replace(self,delivery_date=new_date,updated_at=utc_now(),updated_by=actor)
    def issue_qr(self,public_id): return replace(self,qr_public_id=public_id,qr_status=QRStatus.ACTIVE,updated_at=utc_now())

class TrackingCodeService:
    def tracking_code(self,sequence:int,year:int): return f"ITEM-{year}-{sequence:06d}"
    def internal_order_code(self,sequence:int,year:int): return f"ORD-{year}-{sequence:06d}"
    def qr_public_id(self): return secrets.token_urlsafe(24)
    def payload(self,public_id): return f"HMSQR:v1:{public_id}"

@dataclass(frozen=True,slots=True)
class Operator:
    internal_id: UUID; display_name: str; active: bool; created_at: datetime; updated_at: datetime
    @classmethod
    def create(cls,name):
        if not str(name).strip(): raise TrackingError("display name required")
        t=utc_now(); return cls(uuid4(),str(name).strip(),True,t,t)

@dataclass(frozen=True,slots=True)
class MachiningType:
    internal_id: UUID; code: str; display_name: str; active: bool; display_order: int

@dataclass(frozen=True,slots=True)
class ProcessReportEvent:
    internal_id: UUID; request_id: UUID; tracking_item_id: UUID; machining_type_id: UUID; kind: ReportKind; attempt_number: int|None; quantity: Decimal; notes: str|None; actor_user_id: UUID; actor_display_name_snapshot: str; server_timestamp: datetime; client_timestamp: datetime|None; device_id: str|None; revision: int; supersedes_id: UUID|None; status: str
    @classmethod
    def create(cls,*,request_id,tracking_item_id,machining_type_id,kind,quantity,actor_user_id,actor_display_name,attempt_number=None,notes=None,client_timestamp=None,device_id=None,revision=1,supersedes_id=None):
        if kind==ReportKind.ATTEMPT and (attempt_number is None or attempt_number<1): raise TrackingError("attempt number required")
        if kind==ReportKind.PROCESS_COMPLETED: attempt_number=None
        return cls(uuid4(),request_id,tracking_item_id,machining_type_id,kind,attempt_number,qty(quantity),notes,actor_user_id,actor_display_name,utc_now(),client_timestamp,device_id,revision,supersedes_id,"ACTIVE")
