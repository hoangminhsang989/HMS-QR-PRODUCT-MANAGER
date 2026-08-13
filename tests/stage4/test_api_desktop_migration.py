import os
from datetime import date
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QApplication
from sqlalchemy import inspect
from sqlalchemy import text

from apps.desktop.tracking_window import TrackingWindow,WorkflowActionDialog
from apps.server.app import build_tracking_api
from packages.domain.workflow import WorkflowEventType


def payload(env,event_type,quantity=None,notes=None,request_id=None):
    return {"request_id":str(request_id or uuid4()),"event_type":event_type,"quantity":quantity,"notes":notes,"actor_user_id":str(env["operator"].internal_id),"actor_display_name":"QC User"}


def test_stage4_api_surface_status_filter_and_qr_unchanged(workflow_env):
    env=workflow_env;tracking=env["tracking"];item=env["item"];client=TestClient(build_tracking_api(tracking))
    tracking.issue_qr(item.internal_id,"u");qr_before=tracking.qr_payload(item.internal_id)
    qc=client.post(f"/api/v1/tracking-items/{item.internal_id}/qc-events",json=payload(env,"QC_CHECKED",100));assert qc.status_code==200
    packed=client.post(f"/api/v1/tracking-items/{item.internal_id}/packing-events",json=payload(env,"PACKED",100));assert packed.status_code==200
    delivered=client.post(f"/api/v1/tracking-items/{item.internal_id}/delivery-events",json=payload(env,"DELIVERED",40));assert delivered.status_code==200
    general=client.post(f"/api/v1/tracking-items/{item.internal_id}/reports",json=payload(env,"GENERAL_REPORT",None,"Đang xử lý lại bề mặt"));assert general.status_code==200
    summary=client.get(f"/api/v1/tracking-items/{item.internal_id}/workflow-summary").json();assert summary["current_status"]=="PARTIALLY_DELIVERED"
    filtered=client.get("/api/v1/tracking-items",params={"status":"PARTIALLY_DELIVERED"}).json()["items"];assert filtered[0]["tracking_code"]==item.tracking_code
    history=client.get(f"/api/v1/tracking-items/{item.internal_id}/history").json()["items"];assert [x["event_type"] for x in history]==["QC_CHECKED","PACKED","DELIVERED","GENERAL_REPORT"]
    revision=client.post(f"/api/v1/workflow-events/{delivered.json()['internal_id']}/revisions",json={"request_id":str(uuid4()),"quantity":30,"notes":"Sửa số lượng","actor_user_id":str(env["operator"].internal_id),"actor_display_name":"QC User","reason":"Nhập nhầm"});assert revision.status_code==200 and revision.json()["revision"]==2
    current=tracking.repo.get_item(item.internal_id)
    assert current.delivery_date==date(2026,8,30) and tracking.qr_payload(item.internal_id)==qr_before and set(__import__('json').loads(qr_before))=={"product_name","customer_name","product_code","tracking_code"}
    mobile=client.get("/mobile");assert mobile.status_code==200 and "prompt(" not in mobile.text and "XÁC NHẬN USER" in mobile.text and "QC / GIAO HÀNG" in mobile.text


def test_stage4_desktop_controls_and_summary():
    app=QApplication.instance() or QApplication([]);window=TrackingWindow()
    assert window.table.columnCount()==12 and {"QC_CHECKED","SHORTAGE_REPORTED","QC_NG_RETURNED_TO_MACHINING","PACKED","DELIVERED","GENERAL_REPORT"} <= set(window.workflow_buttons)
    window.show_summaries([{"tracking_code":"ITEM-1","current_status":"QC_NG","checked_quantity":"10","ng_quantity":"2","packed_quantity":"0","delivered_quantity":"0"}]);assert window.table.item(0,10).text()=="QC_NG"
    window.close();app.processEvents()


def test_desktop_action_uses_application_service(workflow_env,monkeypatch):
    from PySide6.QtWidgets import QDialog
    env=workflow_env;app=QApplication.instance() or QApplication([])
    def accept_dialog(dialog):dialog.quantity.setText("10");dialog.notes.setText("Desktop QC");return QDialog.DialogCode.Accepted
    monkeypatch.setattr(WorkflowActionDialog,"exec",accept_dialog)
    window=TrackingWindow(workflow_context={"tracking_item_id":env["item"].internal_id,"actor_user_id":env["operator"].internal_id,"actor_display_name":"QC User","qc_service":env["qc"],"packing_service":env["packing"],"delivery_service":env["delivery"],"general_service":env["general"],"history_service":env["history"]})
    window.workflow_buttons["QC_CHECKED"].click();app.processEvents();assert env["history"].summary(env["item"].internal_id)["checked_quantity"]=="10.0000"
    window.close();app.processEvents()


def test_stage4_fresh_and_upgrade_path_migrations(tmp_path):
    for name,preupgrade in (("fresh.sqlite",False),("upgrade.sqlite",True)):
        db=tmp_path/name;cfg=Config("alembic.ini");cfg.set_main_option("sqlalchemy.url",f"sqlite:///{db.as_posix()}")
        if preupgrade:
            command.upgrade(cfg,"0002_tracking_qr_reporting")
            from sqlalchemy import create_engine
            engine=create_engine(f"sqlite:///{db.as_posix()}")
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO products (internal_id,product_code,company,part_name,quantity,unit,outsourced,status) VALUES ('00000000-0000-0000-0000-000000000399','KEEP-ME','HMS','Preserved',1,'pcs',0,'NEW')"))
        command.upgrade(cfg,"head")
        from sqlalchemy import create_engine
        engine=create_engine(f"sqlite:///{db.as_posix()}");tables=set(inspect(engine).get_table_names())
        assert {"products","customers","purchase_orders","order_tracking_items","process_report_events","tracking_workflow_events"} <= tables
        if preupgrade:
            with engine.connect() as connection:assert connection.scalar(text("SELECT product_code FROM products WHERE product_code='KEEP-ME'"))=="KEEP-ME"
