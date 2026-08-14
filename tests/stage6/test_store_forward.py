from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from packages.domain.store_forward import ArchiveTransferState, StorageConfiguration
from packages.persistence.store_forward_repository import StoreForwardRepository
from packages.storage import FilesystemStorage, LocalCapacityError, StorageUnavailable
from packages.storage.managed_files import ManagedFileService
from packages.storage.store_forward import StoreForwardService


PNG = b"\x89PNG\r\n\x1a\n" + b"r009-safe-store-forward-image"
PDF = b"%PDF-1.7\nR009 attachment\n%%EOF"


def _upload(env, *, name="drawing.pdf", content=PDF):
    return env["managed"].upload_attachment(
        product_id=env["product_id"], original_filename=name,
        declared_mime="application/pdf", content=content,
        actor="r009-user", attachment_category="DRAWING",
    )


def _valid_copy_count(env, item) -> int:
    return sum((
        env["local"].verify(
            item.managed_file.storage_key,
            expected_sha256=item.managed_file.sha256,
            expected_size=item.managed_file.size_bytes,
        ).valid,
        env["archive"].verify(
            item.managed_file.storage_key,
            expected_sha256=item.managed_file.sha256,
            expected_size=item.managed_file.size_bytes,
        ).valid,
    ))


def test_upload_is_local_first_and_archive_offline_is_retryable_success(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    assert env["local"].exists(item.managed_file.storage_key)
    assert env["transfer"].status(item.managed_file.file_id).state is ArchiveTransferState.TRANSFER_QUEUED
    env["archive_root"].rmdir()
    result = env["transfer"].transfer_one(now=datetime.now(timezone.utc))
    assert result.state is ArchiveTransferState.TRANSFER_FAILED_RETRYABLE
    assert result.last_error_code == "ARCHIVE_UNAVAILABLE"
    assert env["managed"].read(item.managed_file.file_id) == PDF
    env["archive_root"].mkdir()
    assert env["local"].verify(
        item.managed_file.storage_key,
        expected_sha256=item.managed_file.sha256,
        expected_size=item.managed_file.size_bytes,
    ).valid


def test_copy_verify_remote_commit_grace_and_delete_local_last(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    start = datetime.now(timezone.utc)
    transferred = env["transfer"].transfer_one(now=start)
    assert transferred.state is ArchiveTransferState.LOCAL_GRACE_RETENTION
    assert transferred.remote_verified_at == start
    assert _valid_copy_count(env, item) == 2
    assert env["transfer"].purge_ready_local_copies(now=start + timedelta(hours=23)) == ()
    assert _valid_copy_count(env, item) == 2
    purged = env["transfer"].purge_ready_local_copies(now=start + timedelta(hours=25))
    assert purged[0].state is ArchiveTransferState.ARCHIVED_REMOTE_ONLY
    assert not env["local"].exists(item.managed_file.storage_key)
    assert _valid_copy_count(env, item) == 1
    assert env["managed"].read(item.managed_file.file_id) == PDF


def test_remote_final_already_valid_is_idempotent_and_not_duplicated(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    env["archive"].put(
        item.managed_file.storage_key, PDF,
        expected_sha256=item.managed_file.sha256,
        expected_size=item.managed_file.size_bytes,
    )
    result = env["transfer"].transfer_one()
    assert result.state is ArchiveTransferState.LOCAL_GRACE_RETENTION
    assert _valid_copy_count(env, item) == 2
    assert not tuple(env["archive_root"].rglob(".transfer-*.tmp"))


def test_partial_remote_temp_is_safely_restarted(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    job = env["transfer"].status(item.managed_file.file_id)
    temp = env["archive"].transfer_temp_path(item.managed_file.storage_key, str(job.job_id))
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_bytes(b"partial")
    result = env["transfer"].transfer_one()
    assert result.remote_verified_at is not None
    assert not temp.exists()
    assert _valid_copy_count(env, item) == 2


@pytest.mark.parametrize("remote_content", [b"bad", b"x" * len(PDF)])
def test_remote_final_mismatch_never_claims_success_or_deletes_local(store_forward_env, remote_content):
    env = store_forward_env
    item = _upload(env)
    target = env["archive_root"] / Path(*item.managed_file.storage_key.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(remote_content)
    result = env["transfer"].transfer_one()
    assert result.state is ArchiveTransferState.TRANSFER_FAILED_PERMANENT
    assert result.last_error_code in {"REMOTE_SIZE_MISMATCH", "REMOTE_HASH_MISMATCH"}
    assert env["local"].exists(item.managed_file.storage_key)
    assert _valid_copy_count(env, item) >= 1


def test_db_lease_prevents_duplicate_worker_and_expired_lease_recovers(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    now = datetime.now(timezone.utc)
    first = env["queue_repository"].claim_next(worker_id="worker-a", now=now, lease_seconds=5)
    assert first and first.state is ArchiveTransferState.TRANSFERRING
    assert env["queue_repository"].claim_next(worker_id="worker-b", now=now) is None
    assert env["queue_repository"].recover_expired_leases(at=now + timedelta(seconds=6)) == 1
    second = env["queue_repository"].claim_next(worker_id="worker-b", now=now + timedelta(seconds=6))
    assert second and second.job_id == first.job_id
    assert env["local"].exists(item.managed_file.storage_key)


def test_persistent_queue_survives_repository_restart(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    restarted = StoreForwardRepository(env["engine"])
    job = restarted.get_job(item.managed_file.file_id)
    assert job.state is ArchiveTransferState.TRANSFER_QUEUED
    assert job.configuration_id == env["configuration"].configuration_id


def test_remote_valid_with_stale_db_is_reconciled_without_local_copy(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    env["archive"].put(
        item.managed_file.storage_key, PDF,
        expected_sha256=item.managed_file.sha256,
        expected_size=item.managed_file.size_bytes,
    )
    env["local"].delete(item.managed_file.storage_key)
    result = env["transfer"].transfer_one()
    assert result.remote_verified_at is not None
    assert _valid_copy_count(env, item) == 1


def test_local_delete_failure_remains_purge_pending_and_does_not_retransfer(store_forward_env, monkeypatch):
    env = store_forward_env
    zero_grace = StorageConfiguration(
        configuration_id=uuid4(), local_ingest_root=str(env["local_root"]),
        archive_target_root=str(env["archive_root"]), grace_period_hours=0,
        retry_schedule_seconds=(60,), warning_free_bytes=300,
        critical_free_bytes=200, upload_refusal_free_bytes=100,
    )
    env["queue_repository"].create_configuration(zero_grace)
    item = _upload(env, name="delete-failure.pdf")
    now = datetime.now(timezone.utc)
    result = env["transfer"].transfer_one(now=now)
    assert result.state is ArchiveTransferState.LOCAL_PURGE_PENDING
    monkeypatch.setattr(env["local"], "delete", lambda _: (_ for _ in ()).throw(StorageUnavailable("locked")))
    purged = env["transfer"].purge_ready_local_copies(now=now)
    assert purged[0].state is ArchiveTransferState.LOCAL_PURGE_PENDING
    assert purged[0].last_error_code == "LOCAL_DELETE_FAILED"
    assert _valid_copy_count(env, item) == 2


def test_low_disk_refuses_before_any_metadata_or_bytes(store_forward_env):
    env = store_forward_env
    constrained = StoreForwardService(
        env["queue_repository"], env["managed_repository"], env["local"],
        archive_factory=lambda _: env["archive"],
        capacity_probe=lambda _: (1000, 880, 120),
    )
    service = ManagedFileService(
        env["managed_repository"], env["local"], archive_coordinator=constrained
    )
    with pytest.raises(LocalCapacityError):
        service.upload_attachment(
            product_id=env["product_id"], original_filename="large.pdf",
            declared_mime="application/pdf", content=PDF,
            actor="r009-user", attachment_category="DRAWING",
        )
    assert env["queue_repository"].list_jobs() == ()
    assert not tuple(env["local_root"].rglob("*.pdf"))


def test_configuration_validation_persistence_and_change_does_not_rewrite_queued_job(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    old_job = env["transfer"].status(item.managed_file.file_id)
    new_archive = env["root"] / "archive-new"
    new_archive.mkdir()
    new_config = StorageConfiguration(
        configuration_id=uuid4(), local_ingest_root=str(env["local_root"]),
        archive_target_root=str(new_archive), grace_period_hours=72,
        retry_schedule_seconds=(60, 300), warning_free_bytes=300,
        critical_free_bytes=200, upload_refusal_free_bytes=100,
    )
    env["queue_repository"].create_configuration(new_config)
    assert env["queue_repository"].get_active_configuration().configuration_id == new_config.configuration_id
    assert env["queue_repository"].get_job(item.managed_file.file_id).configuration_id == old_job.configuration_id
    with pytest.raises(ValueError):
        env["queue_repository"].create_configuration(
            StorageConfiguration(uuid4(), str(env["local_root"]), str(env["local_root"]))
        )


def test_retry_backoff_manual_retry_and_status_metrics(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    env["archive_root"].rmdir()
    now = datetime.now(timezone.utc)
    failed = env["transfer"].transfer_one(now=now)
    assert failed.next_retry_at == now + timedelta(seconds=60)
    queued = env["transfer"].retry_now(item.managed_file.file_id)
    assert queued.state is ArchiveTransferState.TRANSFER_QUEUED
    capacity = env["transfer"].capacity(at=now + timedelta(seconds=5))
    assert capacity.pending_transfer_count == 1
    assert capacity.pending_transfer_bytes == len(PDF)
    assert capacity.oldest_pending_transfer_age_seconds is not None


def test_reconciler_queues_ready_file_missing_job_without_deleting_data(store_forward_env):
    env = store_forward_env
    item = _upload(env)
    from packages.persistence.store_forward_models import ArchiveTransferJobORM
    with env["queue_repository"].Session.begin() as session:
        session.query(ArchiveTransferJobORM).delete()
    result = env["transfer"].reconcile()
    assert result["orphan_ready_files_queued"] == 1
    assert env["transfer"].status(item.managed_file.file_id).state is ArchiveTransferState.TRANSFER_QUEUED
    assert _valid_copy_count(env, item) >= 1


def test_crash_after_local_complete_before_queue_is_reconciled(store_forward_env):
    env = store_forward_env
    item = _upload(env, name="crash-b.pdf")
    from packages.persistence.store_forward_models import ArchiveTransferJobORM
    from packages.persistence.storage_models import ManagedFileORM
    with env["queue_repository"].Session.begin() as session:
        session.query(ArchiveTransferJobORM).delete()
        row = session.get(ManagedFileORM, str(item.managed_file.file_id))
        row.status = "PENDING"
    result = env["transfer"].reconcile()
    assert result["local_uploads_recovered"] == 1
    assert env["managed_repository"].get(item.managed_file.file_id).status.value == "READY"
    assert env["transfer"].status(item.managed_file.file_id).state is ArchiveTransferState.TRANSFER_QUEUED
    assert _valid_copy_count(env, item) >= 1


def test_crash_with_complete_local_upload_temp_is_published_and_queued(store_forward_env):
    env = store_forward_env
    item = _upload(env, name="crash-a.pdf")
    from packages.persistence.store_forward_models import ArchiveTransferJobORM
    from packages.persistence.storage_models import ManagedFileORM
    target = env["local_root"] / Path(*item.managed_file.storage_key.split("/"))
    interrupted = target.parent / f".{target.name}.crash.uploading"
    interrupted.write_bytes(target.read_bytes())
    target.unlink()
    with env["queue_repository"].Session.begin() as session:
        session.query(ArchiveTransferJobORM).delete()
        row = session.get(ManagedFileORM, str(item.managed_file.file_id))
        row.status = "PENDING"
    result = env["transfer"].reconcile()
    assert result["local_uploads_recovered"] == 1
    assert target.exists() and not interrupted.exists()
    assert _valid_copy_count(env, item) >= 1
