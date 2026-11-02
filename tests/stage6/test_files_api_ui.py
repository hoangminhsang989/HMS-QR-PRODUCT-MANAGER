import json
import os
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from fastapi.testclient import TestClient
from PySide6.QtWidgets import QApplication, QMessageBox

from apps.desktop.file_panels import AdminStoragePanel, ProductFilesPanel
from apps.mobile.web import MOBILE_PAGE_PATH
from apps.server.files import build_files_api
from config.environments import Environment, load_config
from packages.domain.store_forward import StorageConfiguration
from packages.persistence.managed_file_repository import ManagedFileRepository
from packages.persistence.store_forward_repository import StoreForwardRepository
from packages.storage import FilesystemStorage, LocalDevStorage
from packages.storage.store_forward import StoreForwardService
from tests.stage6.conftest import _engine_database, _seed_product


PNG = b"\x89PNG\r\n\x1a\n" + b"r009-api-image"
PDF = b"%PDF-1.7\nR009 api attachment\n%%EOF"


def test_product_image_attachment_api_local_first_list_download_update_archive_and_no_paths(store_forward_env):
    env = store_forward_env
    client = TestClient(build_files_api(
        env["managed"], env["transfer"], app_config=load_config(Environment.DEV)
    ))
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
    client = TestClient(build_files_api(
        env["managed"], env["transfer"], app_config=load_config(Environment.DEV)
    ))
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


def test_file_readiness_reports_ready_degraded_and_missing_configuration(store_forward_env):
    env = store_forward_env
    client = TestClient(build_files_api(
        env["managed"], env["transfer"], app_config=load_config(Environment.DEV)
    ))
    ready = client.get("/health/readiness/files")
    assert ready.status_code == 200
    assert ready.json()["state"] == "READY"

    env["archive_root"].rmdir()
    degraded = client.get("/health/readiness/files")
    assert degraded.status_code == 200
    assert degraded.json()["state"] == "DEGRADED"

    class MissingConfigurationTransfer:
        def health(self):
            raise LookupError("Chưa cấu hình kho lưu trữ đang hoạt động.")

    missing = TestClient(build_files_api(
        object(), MissingConfigurationTransfer(), app_config=load_config(Environment.DEV)
    )).get("/health/readiness/files")
    assert missing.status_code == 503
    assert missing.json()["error"]["code"] == "FILE_TRANSFER_UNAVAILABLE"


def test_file_readiness_answers_503_not_500_when_the_ingest_root_is_missing(tmp_path):
    """A missing local ingest root must answer 503, not 500.

    ``file_readiness`` wraps ``transfer_service.health()`` in

        except (LookupError, StorageUnavailable):

    ``StoreForwardService.health()`` calls ``capacity()``, which calls
    ``self.capacity_probe(Path(root))``. The production probe is ``_disk_usage``,
    which is ``shutil.disk_usage(path)`` - and that raises ``OSError``
    (``FileNotFoundError``) when the path does not exist.

    The two storages' own ``health()`` methods do not raise for a missing root:
    ``FilesystemStorage.health()`` returns UNAVAILABLE. So the failure arrives
    from the capacity probe, one call further in, and ``OSError`` is not in the
    tuple - it escapes the endpoint as a 500 where the endpoint exists precisely
    to answer 503 FILE_TRANSFER_UNAVAILABLE.

    The misconfiguration is ordinary: an unplugged drive, a removed NAS mount,
    or a typo in the configured root.

    Note the fixture above stubs ``capacity_probe`` with a lambda that never
    touches the filesystem, which is why no existing test could catch this. This
    one uses the real probe.
    """

    database = _engine_database(tmp_path, "readiness-oserror")
    _seed_product(database, "00000000-0000-0000-0000-000000000610", "SP-R009-002", "R009 Readiness")
    missing_root = tmp_path / "local-ingest-that-is-not-there"
    archive_root = tmp_path / "archive-target"
    archive_root.mkdir()
    local = LocalDevStorage(tmp_path / "local-ingest")
    archive = FilesystemStorage(archive_root, create_root=False)
    queue_repository = StoreForwardRepository(database)
    queue_repository.create_configuration(StorageConfiguration(
        configuration_id=uuid4(), local_ingest_root=str(missing_root),
        archive_target_root=str(archive_root), grace_period_hours=24,
        retry_schedule_seconds=(60, 300, 900, 1800, 3600),
        warning_free_bytes=300, critical_free_bytes=200, upload_refusal_free_bytes=100,
    ))
    transfer = StoreForwardService(
        queue_repository, ManagedFileRepository(database), local,
        archive_factory=lambda _: archive,
    )
    client = TestClient(build_files_api(
        object(), transfer, app_config=load_config(Environment.DEV)
    ))
    response = client.get("/health/readiness/files")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "FILE_TRANSFER_UNAVAILABLE"


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


def test_desktop_file_operation_reports_safe_success_and_hides_unexpected_error(store_forward_env, monkeypatch):
    env = store_forward_env
    app = QApplication.instance() or QApplication([])
    files = ProductFilesPanel(env["managed"], env["transfer"])
    files.set_product(env["product_id"])
    files._run(lambda: None, "Đang kiểm tra tệp...")
    assert "Hoàn tất" in files.state_label.text()
    warning = __import__("unittest.mock", fromlist=["Mock"]).Mock()
    monkeypatch.setattr(QMessageBox, "warning", warning)

    files._run(lambda: (_ for _ in ()).throw(RuntimeError(r"D:\secret\storage")), "Đang kiểm tra tệp...")

    assert "D:\\secret" not in warning.call_args.args[2]
    assert "Kiểm tra kết nối Server" in files.state_label.text()
    files.close(); app.processEvents()


def test_mobile_file_access_is_server_mediated_touch_safe_and_has_no_raw_path():
    page = MOBILE_PAGE_PATH.read_text(encoding="utf-8")
    assert "filesApi + '/api/v1/products/'" in page
    assert "${filesApi}/api/v1/files/" in page
    assert "min-height:44px" in page
    assert "archive_target_root" not in page
    assert "\\\\192.168.1.58" not in page
