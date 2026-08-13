from datetime import date
import json
from hashlib import sha256
from html import unescape
import re

from packages.labels.service import LabelExportService, LabelTemplateRenderer
from packages.qr.payload import QR_PAYLOAD_FIELDS
from packages.qr.service import QRService

def test_change_date_preserves_tracking_and_qr_and_scan_is_live(tracking_env,tmp_path):
    service,item=tracking_env;issued=service.issue_qr(item.internal_id,"u");old_code=issued.tracking_code;old_qr=issued.qr_public_id;old_payload=service.qr_payload(item.internal_id)
    decoded=json.loads(old_payload)
    assert tuple(decoded)==QR_PAYLOAD_FIELDS
    assert decoded=={"product_name":"Plate","customer_name":"HMS","product_code":"SP-T","tracking_code":old_code}
    forbidden=("delivery_date","quantity","material","size","surface_treatment","po","status","internal_id","qr_public_id")
    assert all(field not in decoded for field in forbidden)
    path,payload=QRService().render(service.qr_payload_data(item.internal_id),tmp_path/'qr-before.png');before_pattern=sha256(path.read_bytes()).hexdigest()
    changed=service.change_date(item.internal_id,date(2026,8,30),"u","khách đổi lịch")
    assert changed.tracking_code==old_code and changed.qr_public_id==old_qr
    new_payload=service.qr_payload(item.internal_id);assert new_payload.encode("utf-8")==old_payload.encode("utf-8")
    resolved=service.scan(old_payload);assert resolved["delivery_date"]=="2026-08-30" and resolved["part_name"]=="Plate" and resolved["customer"]=="HMS" and resolved["qr_identity_consistent"] is True
    changed_path,new_rendered=QRService().render(service.qr_payload_data(item.internal_id),tmp_path/'qr-after.png')
    assert path.exists() and payload==old_payload==new_rendered and sha256(changed_path.read_bytes()).hexdigest()==before_pattern

def test_new_order_creates_new_tracking_and_qr(tracking_env):
    service,item=tracking_env;old=service.issue_qr(item.internal_id,"u");old_payload=service.qr_payload(old.internal_id);new=service.create_new_order_from_item(item.internal_id,new_po_number="PO-NEW",delivery_date=date(2026,9,1),actor="u");new_payload=service.qr_payload(new.internal_id)
    assert new.product_id==old.product_id and new.tracking_code!=old.tracking_code and new.qr_public_id!=old.qr_public_id and new.purchase_order_id!=old.purchase_order_id and new_payload!=old_payload

def test_reissue_changes_internal_audit_id_not_payload(tracking_env):
    service,item=tracking_env;issued=service.issue_qr(item.internal_id,"u");payload=service.qr_payload(item.internal_id);reissued=service.reissue_qr(item.internal_id,"u")
    assert reissued.qr_public_id!=issued.qr_public_id and service.qr_payload(item.internal_id)==payload

def test_label_visible_data_is_separate_and_reprint_keeps_qr(tracking_env,tmp_path):
    service,item=tracking_env;service.issue_qr(item.internal_id,"u");payload=service.qr_payload_data(item.internal_id);before=service.qr_payload(item.internal_id)
    first=service.labels.load(item.internal_id)
    assert (first.material,first.quantity,first.size,first.surface_treatment,first.delivery_date,first.customer_po_number)==("SUS304","100.0000","10x20x30","Anodized","2026-08-20","PO-T")
    qr_image,qr_encoded=QRService().data_uri(payload);assert qr_encoded==before
    service.change_date(item.internal_id,date(2026,8,30),"u");second=service.labels.load(item.internal_id);rendered=LabelTemplateRenderer().render(second,payload,qr_image)
    assert second.delivery_date=="2026-08-30" and service.qr_payload(item.internal_id)==before and "2026-08-30" in rendered
    assert "<img class='qr'" in rendered and qr_image in rendered
    embedded=unescape(re.search(r"data-qr-payload='([^']+)'",rendered).group(1));assert json.loads(embedded)==json.loads(before) and tuple(json.loads(embedded))==QR_PAYLOAD_FIELDS
    target=LabelExportService().export_html(rendered,tmp_path/'label.html');assert target.exists()

def test_generated_assets_reject_production_tree(tracking_env):
    service,item=tracking_env;service.issue_qr(item.internal_id,"u")
    try:QRService().render(service.qr_payload_data(item.internal_id),"qr-production.png")
    except ValueError:pass
    else:raise AssertionError("QR generation must reject production-tree output")
