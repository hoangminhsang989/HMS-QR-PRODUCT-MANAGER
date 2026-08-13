"""Customer, purchase-order, delivery, and production-run domain contracts."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID, uuid4


class Stage2ValidationError(ValueError):
    def __init__(self, field: str, message: str):
        super().__init__(message); self.field = field; self.message = message


class POStatus(StrEnum):
    DRAFT="DRAFT"; CONFIRMED="CONFIRMED"; IN_PRODUCTION="IN_PRODUCTION"; PARTIALLY_COMPLETED="PARTIALLY_COMPLETED"; COMPLETED="COMPLETED"; CANCELLED="CANCELLED"; HOLD="HOLD"


class DeliveryStatus(StrEnum):
    PLANNED="PLANNED"; CONFIRMED="CONFIRMED"; PARTIAL="PARTIAL"; COMPLETED="COMPLETED"; CANCELLED="CANCELLED"


class RunStatus(StrEnum):
    PLANNED="PLANNED"; RELEASED="RELEASED"; IN_PROGRESS="IN_PROGRESS"; ON_HOLD="ON_HOLD"; WAITING_QC="WAITING_QC"; COMPLETED="COMPLETED"; CANCELLED="CANCELLED"


def now_utc() -> datetime: return datetime.now(timezone.utc)


def text(value: object | None, field: str, required: bool = False, limit: int = 255) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required: raise Stage2ValidationError(field, "Trường này là bắt buộc.")
        return None
    if not isinstance(value, str): raise Stage2ValidationError(field, "Giá trị phải là văn bản.")
    result=value.strip()
    if len(result)>limit: raise Stage2ValidationError(field, f"Tối đa {limit} ký tự.")
    return result


def quantity(value: object, field: str = "quantity", positive: bool = True) -> Decimal:
    try: q=Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc: raise Stage2ValidationError(field,"Số lượng phải là số.") from exc
    if not q.is_finite() or (q <= 0 if positive else q < 0): raise Stage2ValidationError(field,"Số lượng không hợp lệ.")
    return q


@dataclass(frozen=True, slots=True)
class Customer:
    internal_id: UUID; customer_code: str; name: str; short_name: str|None; address: str|None; tax_code: str|None; contact_name: str|None; phone: str|None; email: str|None; notes: str|None; active: bool; created_at: datetime; updated_at: datetime; created_by: str; updated_by: str
    @classmethod
    def create(cls, *, customer_code: str, name: str, actor: str, **data):
        t=now_utc(); return cls(uuid4(), text(customer_code,"customer_code",True,64).upper(), text(name,"name",True), text(data.get("short_name"),"short_name"), text(data.get("address"),"address",limit=1000), text(data.get("tax_code"),"tax_code"), text(data.get("contact_name"),"contact_name"), text(data.get("phone"),"phone"), text(data.get("email"),"email"), text(data.get("notes"),"notes",limit=2000), bool(data.get("active",True)), t,t,text(actor,"actor",True,128),text(actor,"actor",True,128))
    def update(self, *, actor: str, **changes):
        allowed={"name","short_name","address","tax_code","contact_name","phone","email","notes","active"}; unknown=set(changes)-allowed
        if unknown: raise Stage2ValidationError("payload","Trường không hỗ trợ: "+", ".join(sorted(unknown)))
        vals={k:(bool(v) if k=="active" else text(v,k,required=(k=="name"),limit=(1000 if k=="address" else 2000 if k=="notes" else 255))) for k,v in changes.items()}; vals.update(updated_by=text(actor,"actor",True,128),updated_at=now_utc()); return replace(self,**vals)


@dataclass(frozen=True, slots=True)
class PurchaseOrder:
    internal_id: UUID; po_number: str; customer_id: UUID; po_date: date; requested_delivery_date: date|None; status: POStatus; notes: str|None; created_at: datetime; updated_at: datetime; created_by: str; updated_by: str
    @classmethod
    def create(cls, *, po_number: str, customer_id: UUID, po_date: date, actor: str, requested_delivery_date: date|None=None, status: POStatus|str=POStatus.DRAFT, notes: str|None=None):
        if requested_delivery_date and requested_delivery_date < po_date: raise Stage2ValidationError("requested_delivery_date","Ngày giao không được trước ngày PO.")
        t=now_utc(); return cls(uuid4(),text(po_number,"po_number",True,128),customer_id,po_date,requested_delivery_date,POStatus(status),text(notes,"notes",limit=2000),t,t,text(actor,"actor",True,128),text(actor,"actor",True,128))
    def update(self, *, actor: str, **changes):
        allowed={"requested_delivery_date","status","notes"}; unknown=set(changes)-allowed
        if unknown: raise Stage2ValidationError("payload","Trường không hỗ trợ: "+", ".join(sorted(unknown)))
        requested=changes.get("requested_delivery_date",self.requested_delivery_date)
        if requested and requested<self.po_date: raise Stage2ValidationError("requested_delivery_date","Ngày giao không hợp lệ.")
        values={"requested_delivery_date":requested,"status":POStatus(changes.get("status",self.status)),"notes":text(changes.get("notes",self.notes),"notes",limit=2000),"updated_at":now_utc(),"updated_by":text(actor,"actor",True,128)}
        return replace(self,**values)


@dataclass(frozen=True, slots=True)
class PurchaseOrderLine:
    internal_id: UUID; po_id: UUID; product_id: UUID; line_number: int; ordered_quantity: Decimal; unit: str; unit_price: Decimal|None; currency: str|None; customer_part_reference: str|None; notes: str|None
    @classmethod
    def create(cls, *, po_id: UUID, product_id: UUID, line_number: int, ordered_quantity: object, unit: str, unit_price: object|None=None, currency: str|None=None, customer_part_reference: str|None=None, notes: str|None=None):
        if line_number<1: raise Stage2ValidationError("line_number","Dòng phải lớn hơn 0.")
        price=None if unit_price in (None,"") else quantity(unit_price,"unit_price",False)
        return cls(uuid4(),po_id,product_id,line_number,quantity(ordered_quantity,"ordered_quantity"),text(unit,"unit",True,32),price,text(currency,"currency",limit=8),text(customer_part_reference,"customer_part_reference"),text(notes,"notes",limit=2000))


@dataclass(frozen=True, slots=True)
class DeliveryScheduleEntry:
    internal_id: UUID; po_line_id: UUID; planned_date: date; planned_quantity: Decimal; status: DeliveryStatus; notes: str|None; created_at: datetime; updated_at: datetime
    @classmethod
    def create(cls, *, po_line_id: UUID, planned_date: date, planned_quantity: object, status: DeliveryStatus|str=DeliveryStatus.PLANNED, notes: str|None=None):
        t=now_utc(); return cls(uuid4(),po_line_id,planned_date,quantity(planned_quantity,"planned_quantity"),DeliveryStatus(status),text(notes,"notes",limit=2000),t,t)


@dataclass(frozen=True, slots=True)
class ProductionRun:
    internal_id: UUID; run_code: str; po_line_id: UUID; product_id: UUID; planned_quantity: Decimal; completed_quantity: Decimal; status: RunStatus; priority: int; planned_start: date|None; planned_finish: date|None; actual_start: date|None; actual_finish: date|None; notes: str|None; created_at: datetime; updated_at: datetime; created_by: str; updated_by: str
    @classmethod
    def create(cls, *, run_code: str, po_line_id: UUID, product_id: UUID, planned_quantity: object, actor: str, completed_quantity: object=0, status: RunStatus|str=RunStatus.PLANNED, priority: int=0, planned_start: date|None=None, planned_finish: date|None=None, actual_start: date|None=None, actual_finish: date|None=None, notes: str|None=None):
        planned=quantity(planned_quantity,"planned_quantity"); completed=quantity(completed_quantity,"completed_quantity",False)
        if completed>planned: raise Stage2ValidationError("completed_quantity","Không được vượt số lượng kế hoạch.")
        if planned_finish and planned_start and planned_finish<planned_start: raise Stage2ValidationError("planned_finish","Ngày kết thúc không hợp lệ.")
        t=now_utc(); actor=text(actor,"actor",True,128); return cls(uuid4(),text(run_code,"run_code",True,128),po_line_id,product_id,planned,completed,RunStatus(status),priority,planned_start,planned_finish,actual_start,actual_finish,text(notes,"notes",limit=2000),t,t,actor,actor)
    def update(self, *, actor: str, **changes):
        allowed={"planned_quantity","completed_quantity","status","priority","planned_start","planned_finish","actual_start","actual_finish","notes"}; unknown=set(changes)-allowed
        if unknown: raise Stage2ValidationError("payload","Trường không hỗ trợ: "+", ".join(sorted(unknown)))
        planned=quantity(changes.get("planned_quantity",self.planned_quantity),"planned_quantity")
        completed=quantity(changes.get("completed_quantity",self.completed_quantity),"completed_quantity",False)
        if completed>planned: raise Stage2ValidationError("completed_quantity","Không được vượt số lượng kế hoạch.")
        vals=dict(changes,planned_quantity=planned,completed_quantity=completed,updated_by=text(actor,"actor",True,128),updated_at=now_utc());
        if "status" in vals: vals["status"]=RunStatus(vals["status"])
        return replace(self,**vals)


class Stage2CodeService:
    def __init__(self): self._customer=0; self._run=0
    def customer_code(self, sequence: int) -> str: return f"CUS-{sequence:06d}"
    def run_code(self, sequence: int, year: int) -> str: return f"RUN-{year}-{sequence:06d}"
