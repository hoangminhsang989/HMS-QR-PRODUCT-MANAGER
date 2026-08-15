"""R009A3A regressions for bounded managed-file download availability errors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import shutil
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.server.files import build_files_api
from config.environments import Environment, load_config
from packages.domain.store_forward import ArchiveTransferState
from packages.storage.service import StorageIntegrityError


PDF = b"%PDF-1.7\nR009A3A download contract\n%%EOF"
PNG = b"\x89PNG\r\n\x1a\n" + b"r009a3a-image"


def _client(env, *, raise_server_exceptions: bool = True) -> TestClient:
    return TestClient(
        build_files_api(
            env["managed"],
            env["transfer"],
            app_config=load_config(Environment.DEV),
        ),
        raise_server_exceptions=raise_server_exceptions,
    )


def _attachment(env, name: str = "download-contract.pdf"):
    return env["managed"].upload_attachment(
        product_id=env["product_id"],
        original_filename=name,
        declared_mime="application/pdf",
        content=PDF,
        actor="r009a3a-test",
        attachment_category="DRAWING",
    )


def _archive_only(env, item):
    verified = datetime.now(timezone.utc) + timedelta(minutes=1)
    transferred = env["transfer"].transfer_one(now=verified)
    assert transferred.state is ArchiveTransferState.LOCAL_GRACE_RETENTION
    purged = env["transfer"].purge_ready_local_copies(
        now=verified + timedelta(hours=25)
    )
    assert purged and purged[0].state is ArchiveTransferState.ARCHIVED_REMOTE_ONLY
    assert not env["local"].exists(item.managed_file.storage_key)
    return purged[0]


def _job_snapshot(job) -> tuple[object, ...]:
    return (
        job.state,
        job.attempt_count,
        job.next_retry_at,
        job.last_attempt_at,
        job.last_error_code,
        job.last_error_summary,
        job.remote_verified_at,
        job.grace_expires_at,
        job.local_purged_at,
        job.lease_token,
        job.lease_expires_at,
        job.created_at,
        job.updated_at,
    )


def test_local_download_uses_local_copy_with_archive_online_or_offline(store_forward_env):
    env = store_forward_env
    item = _attachment(env, "local-fallback.pdf")
    client = _client(env)
    route = f"/api/v1/files/{item.managed_file.file_id}"

    online = client.get(route)
    assert online.status_code == 200
    assert online.content == PDF

    shutil.rmtree(env["archive_root"])
    offline = client.get(route)
    assert offline.status_code == 200
    assert offline.content == PDF
    assert env["transfer"].status(item.managed_file.file_id).state is ArchiveTransferState.TRANSFER_QUEUED


def test_archive_only_download_online_then_offline_is_bounded_and_state_immutable(
    store_forward_env, monkeypatch
):
    env = store_forward_env
    item = _attachment(env, "archive-only.pdf")
    _archive_only(env, item)
    client = _client(env, raise_server_exceptions=False)
    route = f"/api/v1/files/{item.managed_file.file_id}"

    online = client.get(route)
    assert online.status_code == 200
    assert online.content == PDF

    worker_calls = 0

    def unexpected_worker(*args, **kwargs):
        nonlocal worker_calls
        worker_calls += 1
        raise AssertionError("download must not invoke transfer worker")

    monkeypatch.setattr(env["transfer"], "transfer_one", unexpected_worker)
    before = env["transfer"].status(item.managed_file.file_id)
    shutil.rmtree(env["archive_root"])
    offline = client.get(route)
    after = env["transfer"].status(item.managed_file.file_id)

    assert offline.status_code == 503
    assert offline.headers["content-type"].startswith("application/json")
    assert offline.json() == {
        "error": {
            "code": "STORAGE_UNAVAILABLE",
            "message": "Tệp hiện chưa thể truy cập do vị trí lưu trữ tạm thời không khả dụng.",
        }
    }
    assert _job_snapshot(after) == _job_snapshot(before)
    assert after.state is ArchiveTransferState.ARCHIVED_REMOTE_ONLY
    assert worker_calls == 0

    body = offline.text.casefold()
    assert str(env["local_root"]).casefold() not in body
    assert str(env["archive_root"]).casefold() not in body
    assert item.managed_file.storage_key.casefold() not in body
    assert "storageunavailable" not in body
    assert "traceback" not in body
    assert "password" not in body and "credential" not in body


@pytest.mark.parametrize("kind", ["image", "attachment"])
def test_image_and_attachment_archive_offline_share_bounded_download_contract(
    store_forward_env, kind
):
    env = store_forward_env
    if kind == "image":
        item = env["managed"].upload_product_image(
            product_id=env["product_id"],
            original_filename="archive-only.png",
            declared_mime="image/png",
            content=PNG,
            actor="r009a3a-test",
            make_primary=True,
        )
    else:
        item = _attachment(env, "archive-only-attachment.pdf")
    _archive_only(env, item)
    shutil.rmtree(env["archive_root"])

    response = _client(env, raise_server_exceptions=False).get(
        f"/api/v1/files/{item.managed_file.file_id}"
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STORAGE_UNAVAILABLE"


def test_unknown_file_preserves_existing_not_found_contract(store_forward_env):
    response = _client(store_forward_env, raise_server_exceptions=False).get(
        f"/api/v1/files/{uuid4()}"
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    "failure",
    [RuntimeError("unexpected bug"), StorageIntegrityError("corrupt bytes")],
    ids=["unexpected", "integrity"],
)
def test_non_availability_failures_are_not_silently_relabelled_503(
    store_forward_env, monkeypatch, failure
):
    env = store_forward_env
    item = _attachment(env, "unexpected-read.pdf")

    def fail_read(_file_id):
        raise failure

    monkeypatch.setattr(env["managed"], "read", fail_read)
    response = _client(env, raise_server_exceptions=False).get(
        f"/api/v1/files/{item.managed_file.file_id}"
    )
    assert response.status_code == 500
    assert "STORAGE_UNAVAILABLE" not in response.text
