from __future__ import annotations
from dataclasses import replace
from datetime import date
from uuid import UUID
from packages.domain.tracking import *
from packages.persistence.tracking_repository import TrackingRepository

class TrackingService:
    def __init__(self,repo):self.repo=repo;self.codes=TrackingCodeService()
    def create_item(self,*,purchase_order_id,purchase_order_line_id,product_id,customer_id,quantity,unit,delivery_date,actor):
        code=self.codes.tracking_code(self.repo.next_tracking_sequence(),date.today().year);return self.repo.add_item(OrderTrackingItem.create(tracking_code=code,purchase_order_id=purchase_order_id,purchase_order_line_id=purchase_order_line_id,product_id=product_id,customer_id=customer_id,quantity=quantity,unit=unit,delivery_date=delivery_date,actor=actor))
    def issue_qr(self,identifier,actor):
        item=self.repo.get_item(identifier); public=item.qr_public_id or self.codes.qr_public_id(); return self.repo.save_item(item.issue_qr(public),"QR_ISSUED",actor,new=public)
    def reissue_qr(self,identifier,actor):
        item=self.repo.get_item(identifier); old=item.qr_public_id; updated=item.issue_qr(self.codes.qr_public_id());return self.repo.save_item(updated,"QR_REISSUED",actor,old=old,new=updated.qr_public_id)
    def change_date(self,identifier,new_date,actor,reason=None):
        item=self.repo.get_item(identifier); updated=item.change_delivery_date(new_date,actor);return self.repo.save_item(updated,"DELIVERY_DATE_CHANGED",actor,item.delivery_date.isoformat(),new_date.isoformat(),reason)
    def scan(self,public_id):return self.repo.scan(public_id)
    def create_new_order_from_item(self,identifier,*,new_po_number,delivery_date,actor,inject_failure=False):
        source=self.repo.get_item(identifier);order_code=self.codes.internal_order_code(self.repo.next_tracking_sequence(),date.today().year);return self.repo.atomic_new_order(source,order_code,new_po_number,delivery_date,actor,self.codes.qr_public_id(),inject_failure)
    def submit_report(self,**data):return self.repo.submit_report(ProcessReportEvent.create(**data))
    def revise_report(self,event,*,request_id,quantity,actor_user_id,actor_display_name,reason):
        return self.submit_report(request_id=request_id,tracking_item_id=event.tracking_item_id,machining_type_id=event.machining_type_id,kind=event.kind,attempt_number=event.attempt_number,quantity=quantity,notes=reason,actor_user_id=actor_user_id,actor_display_name=actor_display_name,revision=event.revision+1,supersedes_id=event.internal_id)
