from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from uuid import UUID,uuid4
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from packages.domain.tracking import *
from .sqlalchemy_models import CustomerORM,ProductORM,PurchaseOrderLineORM,PurchaseOrderORM
from .tracking_models import *

def vals(obj): return {k:(str(v) if isinstance(v,UUID) else v.value if hasattr(v,"value") else v) for k,v in asdict(obj).items()}
class TrackingRepository:
    def __init__(self,engine): self.engine=engine
    def next_tracking_sequence(self):
        with Session(self.engine) as s:return (s.scalar(select(func.count()).select_from(TrackingItemORM)) or 0)+1
    def add_item(self,item):
        with Session(self.engine) as s:
            line=s.get(PurchaseOrderLineORM,str(item.purchase_order_line_id)); po=s.get(PurchaseOrderORM,str(item.purchase_order_id))
            if not line or str(line.po_id)!=str(item.purchase_order_id) or str(line.product_id)!=str(item.product_id): raise TrackingError("tracking item relation mismatch")
            if not po or str(po.customer_id)!=str(item.customer_id): raise TrackingError("tracking item customer mismatch")
            s.add(TrackingItemORM(**vals(item)));s.commit()
        return item
    def save_item(self,item,event_type,actor,old=None,new=None,reason=None):
        with Session(self.engine) as s:
            s.merge(TrackingItemORM(**vals(item)));s.add(TrackingAuditORM(internal_id=str(uuid4()),tracking_item_id=str(item.internal_id),event_type=event_type,old_value=old,new_value=new,actor=actor,reason=reason,server_timestamp=utc_now()));s.commit()
        return item
    def get_item(self,identifier):
        with Session(self.engine) as s:
            x=s.get(TrackingItemORM,str(identifier)) or s.scalar(select(TrackingItemORM).where(TrackingItemORM.tracking_code==str(identifier)))
            if not x:raise LookupError("tracking item not found")
            return self._item(x)
    def list_items(self,search=None):
        with Session(self.engine) as s:
            q=select(TrackingItemORM)
            if search:q=q.where(TrackingItemORM.tracking_code.contains(search))
            return tuple(self._item(x) for x in s.scalars(q.order_by(TrackingItemORM.updated_at.desc())).all())
    def qr_identity(self,identifier):
        with Session(self.engine) as s:
            item=s.get(TrackingItemORM,str(identifier)) or s.scalar(select(TrackingItemORM).where(TrackingItemORM.tracking_code==str(identifier)))
            if not item:raise LookupError("tracking item not found")
            product=s.get(ProductORM,item.product_id);customer=s.get(CustomerORM,item.customer_id)
            return {"product_name":product.part_name,"customer_name":customer.name,"product_code":product.product_code,"tracking_code":item.tracking_code}
    def scan_by_tracking_code(self,tracking_code):
        with Session(self.engine) as s:
            item=s.scalar(select(TrackingItemORM).where(TrackingItemORM.tracking_code==tracking_code,TrackingItemORM.qr_status==QRStatus.ACTIVE.value))
            if not item:raise LookupError("QR not found or revoked")
            product=s.get(ProductORM,item.product_id); customer=s.get(CustomerORM,item.customer_id); po=s.get(PurchaseOrderORM,item.purchase_order_id)
            return {"internal_id":item.internal_id,"tracking_code":item.tracking_code,"product_code":product.product_code,"part_name":product.part_name,"customer":customer.name,"order_code":po.internal_order_code or po.po_number,"customer_po_number":po.po_number,"delivery_date":item.delivery_date.isoformat(),"quantity":str(item.quantity),"unit":item.unit,"status":item.status,"qr_status":item.qr_status}
    def label_data(self,identifier):
        with Session(self.engine) as s:
            item=s.get(TrackingItemORM,str(identifier)) or s.scalar(select(TrackingItemORM).where(TrackingItemORM.tracking_code==str(identifier)))
            if not item:raise LookupError("tracking item not found")
            product=s.get(ProductORM,item.product_id);customer=s.get(CustomerORM,item.customer_id);po=s.get(PurchaseOrderORM,item.purchase_order_id)
            return {"product_name":product.part_name,"customer_name":customer.name,"product_code":product.product_code,"tracking_code":item.tracking_code,"material":product.material,"quantity":str(item.quantity),"unit":item.unit,"size":product.size,"surface_treatment":product.surface_treatment,"delivery_date":item.delivery_date.isoformat(),"order_code":po.internal_order_code or po.po_number,"customer_po_number":po.po_number,"notes":product.notes}
    def add_operator(self,obj):
        with Session(self.engine) as s:s.add(OperatorORM(**vals(obj)));s.commit()
        return obj
    def list_operators(self):
        with Session(self.engine) as s:return tuple(s.scalars(select(OperatorORM).where(OperatorORM.active==True).order_by(OperatorORM.display_name)).all())
    def add_machining_type(self,obj):
        with Session(self.engine) as s:
            existing=s.scalar(select(MachiningTypeORM).where(MachiningTypeORM.code==obj.code))
            if existing:return MachiningType(UUID(existing.internal_id),existing.code,existing.display_name,existing.active,existing.display_order)
            s.add(MachiningTypeORM(**vals(obj)));s.commit();return obj
    def list_machining_types(self):
        with Session(self.engine) as s:return tuple(s.scalars(select(MachiningTypeORM).where(MachiningTypeORM.active==True).order_by(MachiningTypeORM.display_order)).all())
    def atomic_new_order(self,source,order_code,po_number,delivery_date,actor,qr_public_id,fail=False):
        with Session(self.engine) as s:
            po_id=str(uuid4());line_id=str(uuid4());now=utc_now()
            s.add(PurchaseOrderORM(internal_id=po_id,po_number=po_number,internal_order_code=order_code,customer_id=str(source.customer_id),po_date=delivery_date,requested_delivery_date=delivery_date,status="DRAFT",notes=None,created_at=now,updated_at=now,created_by=actor,updated_by=actor))
            s.add(PurchaseOrderLineORM(internal_id=line_id,po_id=po_id,product_id=str(source.product_id),line_number=1,ordered_quantity=source.quantity,unit=source.unit,unit_price=None,currency=None,customer_part_reference=None,notes=None))
            item=OrderTrackingItem.create(tracking_code=f"ITEM-{delivery_date.year}-{self.next_tracking_sequence():06d}",purchase_order_id=UUID(po_id),purchase_order_line_id=UUID(line_id),product_id=source.product_id,customer_id=source.customer_id,quantity=source.quantity,unit=source.unit,delivery_date=delivery_date,actor=actor).issue_qr(qr_public_id)
            if fail: raise RuntimeError("injected transaction failure")
            s.add(TrackingItemORM(**vals(item)));s.commit();return item
    def set_preference(self,user_id,type_id):
        with Session(self.engine) as s:s.merge(UserPreferenceORM(user_id=str(user_id),machining_type_id=str(type_id),updated_at=utc_now()));s.commit()
    def get_preference(self,user_id):
        with Session(self.engine) as s:
            x=s.get(UserPreferenceORM,str(user_id));return UUID(x.machining_type_id) if x else None
    def get_attempt_max(self,item_id,type_id):
        with Session(self.engine) as s:
            x=s.get(AttemptDisplayORM,(str(item_id),str(type_id)));return x.max_visible_attempt if x else 3
    def expand_attempt(self,item_id,type_id,new_max,user_id=None):
        current=self.get_attempt_max(item_id,type_id)
        if new_max<current or new_max>99:raise TrackingError("attempt expansion must be monotonic and <= 99")
        with Session(self.engine) as s:s.merge(AttemptDisplayORM(tracking_item_id=str(item_id),machining_type_id=str(type_id),max_visible_attempt=new_max,updated_at=utc_now(),updated_by=str(user_id) if user_id else None));s.commit()
        return new_max
    def submit_report(self,event):
        with Session(self.engine) as s:
            item=s.get(TrackingItemORM,str(event.tracking_item_id))
            if not item:raise LookupError("tracking item not found")
            if event.quantity>item.quantity:raise TrackingError("report quantity exceeds tracking quantity")
            old=s.scalar(select(ProcessReportORM).where(ProcessReportORM.request_id==str(event.request_id)))
            if old:return self._report(old)
            s.add(ProcessReportORM(**vals(event)))
            if event.revision==1:
                if event.kind==ReportKind.PROCESS_COMPLETED:item.status=TrackingStatus.WAITING_QC.value
                elif item.status in {TrackingStatus.QC_NG.value,TrackingStatus.REWORK.value}:item.status=TrackingStatus.REWORK.value
                else:item.status=TrackingStatus.IN_PROCESS.value
                item.updated_at=utc_now();item.updated_by=str(event.actor_user_id)
            s.commit();return event
    def history(self,item_id):
        with Session(self.engine) as s:return tuple(self._report(x) for x in s.scalars(select(ProcessReportORM).where(ProcessReportORM.tracking_item_id==str(item_id)).order_by(ProcessReportORM.server_timestamp)).all())
    def get_report(self,event_id):
        with Session(self.engine) as s:
            x=s.get(ProcessReportORM,str(event_id))
            if not x:raise LookupError("report not found")
            return self._report(x)
    @staticmethod
    def _item(x):return OrderTrackingItem(UUID(x.internal_id),x.tracking_code,UUID(x.purchase_order_id),UUID(x.purchase_order_line_id),UUID(x.product_id),UUID(x.customer_id),x.quantity,x.unit,x.delivery_date,TrackingStatus(x.status),x.qr_public_id,QRStatus(x.qr_status) if x.qr_status else None,x.created_at,x.updated_at,x.created_by,x.updated_by)
    @staticmethod
    def _report(x):return ProcessReportEvent(UUID(x.internal_id),UUID(x.request_id),UUID(x.tracking_item_id),UUID(x.machining_type_id),ReportKind(x.kind),x.attempt_number,x.quantity,x.notes,UUID(x.actor_user_id),x.actor_display_name_snapshot,x.server_timestamp,x.client_timestamp,x.device_id,x.revision,UUID(x.supersedes_id) if x.supersedes_id else None,x.status)
