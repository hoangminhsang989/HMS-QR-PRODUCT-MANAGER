import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from pathlib import Path
import subprocess
import sys
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QApplication
from apps.server.app import build_tracking_api
from apps.desktop.tracking_window import TrackingWindow


def _run_clean_alembic(database: Path, revision: str) -> None:
    code = (
        "import sys; from alembic.config import Config; from alembic import command; "
        "cfg=Config('alembic.ini'); "
        "cfg.set_main_option('sqlalchemy.url', 'sqlite:///' + sys.argv[1]); "
        "command.upgrade(cfg, sys.argv[2])"
    )
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [sys.executable, "-B", "-c", code, database.as_posix(), revision],
        cwd=Path.cwd(), env=environment, check=True,
    )

def test_tracking_api_mobile_desktop_and_migration(tracking_env,tmp_path):
    service,item=tracking_env;client=TestClient(build_tracking_api(service));qr=client.post(f"/api/v1/tracking-items/{item.internal_id}/qr").json();scan=client.get("/api/v1/scan",params={"payload":qr["payload"]});assert scan.status_code==200 and scan.json()["tracking_code"]==item.tracking_code
    mobile=client.get('/mobile');assert mobile.status_code==200 and "NGƯỜI DÙNG" in mobile.text and "+ THÊM LẦN" in mobile.text and "ĐÃ XONG" in mobile.text
    user=client.post('/api/v1/operators',json={"display_name":"Mobile User"});assert user.status_code==200
    process=client.post('/api/v1/machining-types?code=MILL&display_name=PHAY&display_order=1');assert process.status_code==200
    pref=client.put(f"/api/v1/operators/{user.json()['internal_id']}/preference",json={"machining_type_id":process.json()["internal_id"]});assert pref.status_code==200
    assert client.get(f"/api/v1/operators/{user.json()['internal_id']}/preference").json()["machining_type_id"]==process.json()["internal_id"]
    catalog=client.get('/api/v1/machining-types').json()['items'];assert {'TẠO PHÔI','TIỆN','PHAY','CẮT DÂY'} <= {x['display_name'] for x in catalog}
    app=QApplication.instance() or QApplication([]);window=TrackingWindow();assert "Theo dõi" in window.windowTitle();window.close();app.processEvents()
    db=tmp_path/'migration.sqlite';_run_clean_alembic(db,'head');assert db.exists()
