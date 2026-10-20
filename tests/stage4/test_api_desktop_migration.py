import os
from datetime import date
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

from fastapi.testclient import TestClient
from PySide6.QtWidgets import QApplication

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
    history=client.get(f"/api/v1/tracking-items/{item.internal_id}/history").json()["items"];assert [x["event_type"] for x in history]==["QR_ISSUED","QC_CHECKED","PACKED","DELIVERED","GENERAL_REPORT"]
    issued=[x for x in history if x["event_type"]=="QR_ISSUED"]
    assert issued[0]["source"]=="AUDIT" and issued[0]["actor_display_name_snapshot"]=="u"
    revision=client.post(f"/api/v1/workflow-events/{delivered.json()['internal_id']}/revisions",json={"request_id":str(uuid4()),"quantity":30,"notes":"Sửa số lượng","actor_user_id":str(env["operator"].internal_id),"actor_display_name":"QC User","reason":"Nhập nhầm"});assert revision.status_code==200 and revision.json()["revision"]==2
    current=tracking.repo.get_item(item.internal_id)
    assert current.delivery_date==date(2026,8,30) and tracking.qr_payload(item.internal_id)==qr_before and set(__import__('json').loads(qr_before))=={"product_name","customer_name","product_code","tracking_code"}
    mobile=client.get("/mobile");assert mobile.status_code==200 and "prompt(" not in mobile.text and "XÁC NHẬN USER" in mobile.text and "QC / GIAO HÀNG" in mobile.text


def test_stage4_desktop_controls_and_summary():
    app=QApplication.instance() or QApplication([]);window=TrackingWindow()
    assert window.table.columnCount()==12 and {"QC_CHECKED","SHORTAGE_REPORTED","QC_NG_RETURNED_TO_MACHINING","PACKED","DELIVERED","GENERAL_REPORT"} <= set(window.workflow_buttons)
    window.selected_delivery_date=date(2026,9,26)
    window._update_delivery_date_labels()
    window.show_summaries([
        {"tracking_code":"ITEM-1","delivery_date":"2026-09-26","current_status":"QC_NG","checked_quantity":"10","ng_quantity":"2","packed_quantity":"0","delivered_quantity":"0"},
        {"tracking_code":"ITEM-2","delivery_date":"2026-09-27","current_status":"DELIVERED"},
    ])
    assert window.table.rowCount()==1 and window.table.item(0,10).text()=="QC_NG"
    assert [window.delivery_date_labels[key].text() for key in ("year","month","day")]==["2026","THÁNG 9","26"]
    window.change_delivery_date("day",1)
    assert window.table.rowCount()==1 and window.table.item(0,0).text()=="ITEM-2"
    window.change_delivery_date("month",-1)
    assert window.selected_delivery_date==date(2026,8,27) and window.table.rowCount()==0
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
    from config.paths import SOURCE_ROOT
    from packages.sqlengine import Database
    from packages.sqlengine.migrations import load_migration_modules, run_migrations

    migrations = load_migration_modules(SOURCE_ROOT / "migrations" / "engine")
    required = {
        "products", "customers", "purchase_orders",
        "order_tracking_items", "process_report_events", "tracking_workflow_events",
    }
    for name, preupgrade in (("fresh", False), ("upgrade", True)):
        database = Database(tmp_path / f"{name}-engine")
        try:
            if preupgrade:
                prefix = [item for item in migrations if item[0] <= 2]
                run_migrations(database, prefix, now=lambda: "2026-01-01T00:00:00+00:00")
                database.execute(
                    "INSERT INTO products (internal_id, product_code, company, part_name, "
                    "quantity, unit, outsourced, status) "
                    "VALUES ('00000000-0000-0000-0000-000000000399','KEEP-ME','HMS','Preserved',1,'pcs',0,'NEW')"
                )
            run_migrations(database, migrations, now=lambda: "2026-01-01T00:00:00+00:00")
            assert required <= set(database.schema.tables)
            if preupgrade:
                rows = database.query(
                    "SELECT product_code FROM products WHERE product_code = 'KEEP-ME'"
                )
                assert rows[0]["product_code"] == "KEEP-ME"
        finally:
            database.close()
