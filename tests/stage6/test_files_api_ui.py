import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fastapi.testclient import TestClient
from PySide6.QtWidgets import QApplication

from apps.desktop.file_panels import AdminStoragePanel, ProductFilesPanel
from apps.mobile.web import MOBILE_HTML
from apps.server.files import build_files_api


PNG = b"\x89PNG\r\n\x1a\n" + b"r009-api-image"
PDF = b"%PDF-1.7\nR009 api attachment\n%%EOF"


def test_product_image_attachment_api_local_first_list_download_update_archive_and_no_paths(store_forward_env):
    env = store_forward_env
    client = TestClient(build_files_api(env["managed"], env["transfer"]))
    product_id = str(env["product_id"])
    image = client.post(
        f"/api/v1/products/{product_id}/images",
        params={"filename": "front.png", "declared_mime": "image/png", "make_primary": "true"},
        content=PNG, headers={"content-type": "application/octet-stream", "x-actor": "api-user"},
    )
    assert image.status_code == 201
    image_data = image.json()
    assert image_data["availability"] == "READY"
    assert image_data["archive_status"] == "TRANSFER_QUEUED"
    assert image_data["is_primary"] is True
    encoded = json.dumps(image_data).lower()
    assert "storage_key" not in encoded and "archive_target_root" not in encoded
    attachment = client.post(
        f"/api/v1/products/{product_id}/attachments",
        params={"filename": "drawing.pdf", "declared_mime": "application/pdf", "category": "DRAWING"},
        content=PDF, headers={"content-type": "application/octet-stream", "x-actor": "api-user"},
    )
    assert attachment.status_code == 201
    file_id = attachment.json()["file_id"]
    assert client.get(f"/api/v1/products/{product_id}/images").json()["items"][0]["file_id"] == image_data["file_id"]
    assert client.get(f"/api/v1/products/{product_id}/attachments").json()["items"][0]["file_id"] == file_id
    downloaded = client.get(f"/api/v1/files/{file_id}")
    assert downloaded.status_code == 200 and downloaded.content == PDF
    patched = client.patch(
        f"/api/v1/products/{product_id}/files/{file_id}",
        json={"sort_order": 7, "caption": "Rev A"},
    )
    assert patched.json() == {"file_id": file_id, "sort_order": 7, "caption": "Rev A"}
    archived = client.delete(f"/api/v1/files/{file_id}", headers={"x-actor": "api-user"})
    assert archived.json()["availability"] == "ARCHIVED"


def test_admin_api_is_guarded_and_status_is_path_free(store_forward_env):
    env = store_forward_env
    item = env["managed"].upload_attachment(
        product_id=env["product_id"], original_filename="status.pdf",
        declared_mime="application/pdf", content=PDF,
        actor="api-user", attachment_category="OTHER",
    )
    client = TestClient(build_files_api(env["managed"], env["transfer"]))
    assert client.get("/api/v1/admin/storage/health").status_code == 403
    health = client.get("/api/v1/admin/storage/health", headers={"x-storage-admin": "true"})
    assert health.status_code == 200
    status = client.get(f"/api/v1/files/{item.managed_file.file_id}/status")
    body = json.dumps(status.json()).lower()
    assert status.status_code == 200
    assert "local_ingest_root" not in body and "archive_target_root" not in body and "storage_key" not in body
    retry = client.post(
        f"/api/v1/admin/transfers/{item.managed_file.file_id}/retry",
        headers={"x-storage-admin": "true"},
    )
    assert retry.json()["archive_status"] == "TRANSFER_QUEUED"


def test_desktop_light_industrial_file_and_admin_panels_smoke(store_forward_env):
    env = store_forward_env
    app = QApplication.instance() or QApplication([])
    files = ProductFilesPanel(env["managed"], env["transfer"])
    files.set_product(env["product_id"])
    admin = AdminStoragePanel(env["transfer"])
    assert files.add_image_button.text() == "THÊM ẢNH"
    assert files.attachments.columnCount() == 5
    assert admin.grace_hours.maximum() == 168
    assert admin.isEnabled()
    files.close(); admin.close(); app.processEvents()


def test_mobile_file_access_is_server_mediated_touch_safe_and_has_no_raw_path():
    assert "/files/api/v1/products/" in MOBILE_HTML
    assert "/files/api/v1/files/" in MOBILE_HTML
    assert "min-height:44px" in MOBILE_HTML
    assert "archive_target_root" not in MOBILE_HTML
    assert "\\\\192.168.1.58" not in MOBILE_HTML
