from datetime import date
from packages.qr.service import QRService

def test_change_date_preserves_tracking_and_qr_and_scan_is_live(tracking_env,tmp_path):
    service,item=tracking_env;issued=service.issue_qr(item.internal_id,"u");old_code=issued.tracking_code;old_qr=issued.qr_public_id
    changed=service.change_date(item.internal_id,date(2026,8,30),"u","khách đổi lịch")
    assert changed.tracking_code==old_code and changed.qr_public_id==old_qr
    resolved=service.scan(old_qr);assert resolved["delivery_date"]=="2026-08-30" and resolved["part_name"]=="Plate" and resolved["customer"]=="HMS"
    path,payload=QRService().render(old_qr,tmp_path/'qr.png');assert path.exists() and payload==f"HMSQR:v1:{old_qr}"

def test_new_order_creates_new_tracking_and_qr(tracking_env):
    service,item=tracking_env;old=service.issue_qr(item.internal_id,"u");new=service.create_new_order_from_item(item.internal_id,new_po_number="PO-NEW",delivery_date=date(2026,9,1),actor="u")
    assert new.product_id==old.product_id and new.tracking_code!=old.tracking_code and new.qr_public_id!=old.qr_public_id and new.purchase_order_id!=old.purchase_order_id
