"""R009A2A regressions for monotonic transfer and purge retry lifecycles."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from threading import Barrier
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QApplication
from sqlalchemy import select

from apps.desktop.file_panels import AdminStoragePanel, ProductFilesPanel
from apps.server.files import build_files_api
from config.environments import Environment, load_config
from packages.domain.store_forward import ArchiveTransferState, StorageConfiguration
from packages.persistence.store_forward_models import ArchiveTransferJobORM
from packages.storage.service import StorageUnavailable


PDF = b"%PDF-1.7\nR009A2A retry lifecycle\n%%EOF"


def _upload(env, name: str = "retry-lifecycle.pdf"):
    return env["managed"].upload_attachment(
        product_id=env["product_id"],
        original_filename=name,
        declared_mime="application/pdf",
        content=PDF,
        actor="r009a2a-test",
        attachment_category="DRAWING",
    )


def _set_state(
    env,
    item,
    state: ArchiveTransferState,
    *,
    remote_verified_at: datetime | None = None,
    grace_expires_at: datetime | None = None,
    lease_token: str | None = None,
    lease_expires_at: datetime | None = None,
    error_code: str | None = None,
) -> None:
    with env["queue_repository"].Session.begin() as session:
        row = session.scalar(select(ArchiveTransferJobORM).where(
            ArchiveTransferJobORM.managed_file_id == str(item.managed_file.file_id)
        ))
        assert row is not None
        row.state = state.value
        row.remote_verified_at = remote_verified_at
        row.grace_expires_at = grace_expires_at
        row.lease_token = lease_token
        row.lease_expires_at = lease_expires_at
        row.last_error_code = error_code
        row.last_error_summary = "preserve this error" if error_code else None


def _snapshot(job) -> tuple[object, ...]:
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


@pytest.mark.parametrize("state", [
    ArchiveTransferState.REMOTE_READY,
    ArchiveTransferState.LOCAL_GRACE_RETENTION,
    ArchiveTransferState.LOCAL_PURGE_PENDING,
    ArchiveTransferState.ARCHIVED_REMOTE_ONLY,
])
def test_remote_verified_states_are_byte_value_immutable_under_repeated_retry(
    store_forward_env, state
):
    env = store_forward_env
    item = _upload(env, f"{state.value.lower()}.pdf")
    verified = datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)
    grace = verified + timedelta(hours=24)
    _set_state(
        env, item, state,
        remote_verified_at=verified,
        grace_expires_at=grace,
    )
    before = env["transfer"].status(item.managed_file.file_id)
    metrics_before = env["queue_repository"].pending_summary(at=grace)

    for offset in range(10):
        result = env["queue_repository"].retry_now(
            item.managed_file.file_id,
            at=grace + timedelta(minutes=offset),
        )
        assert _snapshot(result) == _snapshot(before)

    after = env["transfer"].status(item.managed_file.file_id)
    assert _snapshot(after) == _snapshot(before)
    assert after.remote_verified_at == verified
    assert after.grace_expires_at == grace
    assert env["queue_repository"].pending_summary(at=grace) == metrics_before


def test_remote_verified_retry_does_not_enqueue_worker_or_copy_remote(store_forward_env, monkeypatch):
    env = store_forward_env
    item = _upload(env)
    verified = datetime.now(timezone.utc) + timedelta(minutes=1)
    completed = env["transfer"].transfer_one(now=verified)
    assert completed.state is ArchiveTransferState.LOCAL_GRACE_RETENTION
    copy_calls = 0

    def unexpected_copy(*args, **kwargs):
        nonlocal copy_calls
        copy_calls += 1
        raise AssertionError("remote copy must not run")

    monkeypatch.setattr(env["archive"], "publish_transfer", unexpected_copy)
    before_temps = tuple(env["archive_root"].rglob(".transfer-*.tmp"))
    env["transfer"].retry_now(item.managed_file.file_id)
    assert env["transfer"].transfer_one(now=verified + timedelta(hours=1)) is None
    assert copy_calls == 0
    assert tuple(env["archive_root"].rglob(".transfer-*.tmp")) == before_temps


def test_queued_manual_retry_is_an_exact_idempotent_noop(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    before = env["transfer"].status(item.managed_file.file_id)
    assert before.state is ArchiveTransferState.TRANSFER_QUEUED
    result = env["queue_repository"].retry_now(
        item.managed_file.file_id,
        at=before.updated_at + timedelta(days=1),
    )
    assert _snapshot(result) == _snapshot(before)
    assert len(env["queue_repository"].list_jobs()) == 1


def test_retryable_failure_requeues_same_job_and_permanent_failure_is_immutable(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    retry_at = datetime.now(timezone.utc) + timedelta(minutes=1)
    _set_state(
        env, item, ArchiveTransferState.TRANSFER_FAILED_RETRYABLE,
        error_code="ARCHIVE_UNAVAILABLE",
    )
    before = env["transfer"].status(item.managed_file.file_id)
    retried = env["queue_repository"].retry_now(item.managed_file.file_id, at=retry_at)
    assert retried.job_id == before.job_id
    assert retried.state is ArchiveTransferState.TRANSFER_QUEUED
    assert retried.next_retry_at == retry_at
    assert retried.last_error_code is None
    assert retried.attempt_count == before.attempt_count
    assert len(env["queue_repository"].list_jobs()) == 1

    _set_state(
        env, item, ArchiveTransferState.TRANSFER_FAILED_PERMANENT,
        error_code="REMOTE_HASH_MISMATCH",
    )
    permanent = env["transfer"].status(item.managed_file.file_id)
    result = env["queue_repository"].retry_now(
        item.managed_file.file_id, at=retry_at + timedelta(hours=1)
    )
    assert _snapshot(result) == _snapshot(permanent)


@pytest.mark.parametrize("state", [
    ArchiveTransferState.TRANSFERRING,
    ArchiveTransferState.REMOTE_VERIFYING,
])
def test_active_leased_transfer_retry_cannot_spawn_competing_worker(store_forward_env, state):
    env = store_forward_env
    item = _upload(env, f"active-{state.value.lower()}.pdf")
    now = datetime.now(timezone.utc) + timedelta(minutes=1)
    _set_state(
        env, item, state,
        lease_token="worker-owned",
        lease_expires_at=now + timedelta(minutes=5),
    )
    before = env["transfer"].status(item.managed_file.file_id)
    result = env["queue_repository"].retry_now(item.managed_file.file_id, at=now)
    assert _snapshot(result) == _snapshot(before)
    assert env["queue_repository"].claim_next(worker_id="competitor", now=now) is None


def test_retry_racing_remote_verification_never_regresses_verified_state(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    now = datetime.now(timezone.utc) + timedelta(minutes=1)
    claimed = env["queue_repository"].claim_next(worker_id="verifier", now=now)
    assert claimed and claimed.lease_token
    env["queue_repository"].mark_remote_verifying(
        claimed.job_id, lease_token=claimed.lease_token, at=now
    )
    gate = Barrier(2)

    def retry():
        gate.wait()
        return env["queue_repository"].retry_now(item.managed_file.file_id, at=now)

    def verify():
        gate.wait()
        return env["queue_repository"].mark_remote_ready(
            claimed.job_id,
            lease_token=claimed.lease_token,
            verified_at=now,
            grace_period_hours=24,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        retry_future = executor.submit(retry)
        verify_future = executor.submit(verify)
        retry_future.result()
        verify_future.result()

    final = env["transfer"].status(item.managed_file.file_id)
    assert final.state is ArchiveTransferState.LOCAL_GRACE_RETENTION
    assert final.remote_verified_at == now
    assert final.grace_expires_at == now + timedelta(hours=24)


def test_retry_racing_purge_never_requeues_or_resets_grace(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    verified = datetime.now(timezone.utc) + timedelta(minutes=1)
    env["transfer"].transfer_one(now=verified)
    purge_at = verified + timedelta(hours=25)
    assert env["queue_repository"].advance_expired_grace(at=purge_at) == 1
    before = env["transfer"].status(item.managed_file.file_id)
    gate = Barrier(2)

    def retry():
        gate.wait()
        return env["queue_repository"].retry_now(item.managed_file.file_id, at=purge_at)

    def purge():
        gate.wait()
        return env["transfer"].purge_ready_local_copies(now=purge_at)

    with ThreadPoolExecutor(max_workers=2) as executor:
        retry_future = executor.submit(retry)
        purge_future = executor.submit(purge)
        retry_future.result()
        purged = purge_future.result()

    assert purged[-1].state is ArchiveTransferState.ARCHIVED_REMOTE_ONLY
    final = env["transfer"].status(item.managed_file.file_id)
    assert final.state is ArchiveTransferState.ARCHIVED_REMOTE_ONLY
    assert final.remote_verified_at == before.remote_verified_at
    assert final.grace_expires_at == before.grace_expires_at


def test_purge_specific_retry_revalidates_and_never_restarts_grace(store_forward_env, monkeypatch):
    env = store_forward_env
    zero_grace = StorageConfiguration(
        configuration_id=uuid4(),
        local_ingest_root=str(env["local_root"]),
        archive_target_root=str(env["archive_root"]),
        grace_period_hours=0,
        retry_schedule_seconds=(60,),
        warning_free_bytes=300,
        critical_free_bytes=200,
        upload_refusal_free_bytes=100,
    )
    env["queue_repository"].create_configuration(zero_grace)
    item = _upload(env, "purge-retry.pdf")
    now = datetime.now(timezone.utc) + timedelta(minutes=1)
    transferred = env["transfer"].transfer_one(now=now)
    assert transferred.state is ArchiveTransferState.LOCAL_PURGE_PENDING
    original_delete = env["local"].delete

    def fail_delete(_key):
        raise StorageUnavailable("bounded delete failure")

    monkeypatch.setattr(env["local"], "delete", fail_delete)
    failed = env["transfer"].purge_ready_local_copies(now=now)[0]
    assert failed.state is ArchiveTransferState.LOCAL_PURGE_PENDING
    assert failed.last_error_code == "LOCAL_DELETE_FAILED"
    assert failed.grace_expires_at == transferred.grace_expires_at

    monkeypatch.setattr(env["local"], "delete", original_delete)
    completed = env["transfer"].purge_ready_local_copies(now=now + timedelta(minutes=1))[0]
    assert completed.state is ArchiveTransferState.ARCHIVED_REMOTE_ONLY
    assert completed.remote_verified_at == transferred.remote_verified_at
    assert completed.grace_expires_at == transferred.grace_expires_at
    assert not env["local"].exists(item.managed_file.storage_key)
    assert env["archive"].verify(
        item.managed_file.storage_key,
        expected_sha256=item.managed_file.sha256,
        expected_size=item.managed_file.size_bytes,
    ).valid


def test_api_noops_verified_retry_and_desktop_only_enables_canonical_retry(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    verified = datetime.now(timezone.utc) + timedelta(minutes=1)
    env["transfer"].transfer_one(now=verified)
    before = env["transfer"].status(item.managed_file.file_id)
    client = TestClient(build_files_api(
        env["managed"], env["transfer"], app_config=load_config(Environment.DEV)
    ))
    response = client.post(
        f"/api/v1/admin/transfers/{item.managed_file.file_id}/retry",
        headers={"x-storage-admin": "true"},
    )
    assert response.status_code == 200
    assert response.json()["archive_status"] == "LOCAL_GRACE_RETENTION"
    assert _snapshot(env["transfer"].status(item.managed_file.file_id)) == _snapshot(before)

    app = QApplication.instance() or QApplication([])
    files = ProductFilesPanel(env["managed"], env["transfer"])
    files.set_product(env["product_id"])
    files.attachments.selectRow(0)
    assert not files.retry_button.isEnabled()
    admin = AdminStoragePanel(env["transfer"])
    assert not admin.retry_failed_button.isEnabled()

    _set_state(
        env, item, ArchiveTransferState.TRANSFER_FAILED_RETRYABLE,
        error_code="ARCHIVE_UNAVAILABLE",
    )
    files.refresh()
    files.attachments.selectRow(0)
    admin.refresh()
    assert files.retry_button.isEnabled()
    assert admin.retry_failed_button.isEnabled()
    files.close()
    admin.close()
    app.processEvents()
