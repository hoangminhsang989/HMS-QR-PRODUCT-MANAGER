import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QApplication
from apps.server.app import build_tracking_api
from apps.desktop.tracking_window import TrackingWindow
from alembic.config import Config
from alembic import command

def test_tracking_api_mobile_desktop_and_migration(tracking_env,tmp_path):
    service,item=tracking_env;client=TestClient(build_tracking_api(service));qr=client.post(f"/api/v1/tracking-items/{item.internal_id}/qr").json();scan=client.get(f"/api/v1/scan/{qr['qr_public_id']}");assert scan.status_code==200 and scan.json()["tracking_code"]==item.tracking_code
    mobile=client.get('/mobile');assert mobile.status_code==200 and "NGƯỜI DÙNG" in mobile.text and "+ THÊM LẦN" in mobile.text and "ĐÃ XONG" in mobile.text
    user=client.post('/api/v1/operators',json={"display_name":"Mobile User"});assert user.status_code==200
    process=client.post('/api/v1/machining-types?code=MILL&display_name=PHAY&display_order=1');assert process.status_code==200
    pref=client.put(f"/api/v1/operators/{user.json()['internal_id']}/preference",json={"machining_type_id":process.json()["internal_id"]});assert pref.status_code==200
    assert client.get(f"/api/v1/operators/{user.json()['internal_id']}/preference").json()["machining_type_id"]==process.json()["internal_id"]
    app=QApplication.instance() or QApplication([]);window=TrackingWindow();assert "Theo dõi" in window.windowTitle();window.close();app.processEvents()
    db=tmp_path/'migration.sqlite';cfg=Config('alembic.ini');cfg.set_main_option('sqlalchemy.url',f'sqlite:///{db.as_posix()}');command.upgrade(cfg,'head');assert db.exists()
