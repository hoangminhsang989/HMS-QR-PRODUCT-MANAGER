"""Local-first archive transfer, recovery, capacity, and delete-last workflow."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
from typing import Callable
from uuid import UUID, uuid4

from packages.domain.attachments import ManagedFile, ManagedFileStatus
from packages.domain.store_forward import (
    ArchiveTransferJob,
    ArchiveTransferState,
    StorageCapacity,
    StorageConfiguration,
    TransferErrorCode,
)
from packages.persistence.managed_file_repository import ManagedFileRepository
from packages.persistence.store_forward_repository import StoreForwardRepository
from .service import (
    FilesystemStorage,
    StorageConflict,
    StorageIntegrityError,
    StorageService,
    StorageUnavailable,
)


class LocalCapacityError(RuntimeError):
    """The local ingest tier cannot safely accept another upload."""


class StoreForwardService:
    def __init__(
        self,
        repository: StoreForwardRepository,
        managed_repository: ManagedFileRepository,
        local_storage: StorageService,
        *,
        archive_factory: Callable[[StorageConfiguration], StorageService] | None = None,
        local_factory: Callable[[StorageConfiguration], StorageService] | None = None,
        capacity_probe: Callable[[Path], tuple[int, int, int]] | None = None,
    ) -> None:
        self.repository = repository
        self.managed_repository = managed_repository
        self.local_storage = local_storage
        self.archive_factory = archive_factory or (
            lambda cfg: FilesystemStorage(cfg.archive_target_root, create_root=False)
        )
        initial_root = str(getattr(local_storage, "root", "")).rstrip("\\/").casefold()
        self.local_factory = local_factory or (
            lambda cfg: local_storage
            if cfg.local_ingest_root.rstrip("\\/").casefold() == initial_root
            else FilesystemStorage(cfg.local_ingest_root, create_root=False)
        )
        self.capacity_probe = capacity_probe or _disk_usage

    @property
    def active_configuration_id(self) -> UUID:
        return self.repository.get_active_configuration().configuration_id

    @property
    def ingest_storage(self) -> StorageService:
        return self.local_factory(self.repository.get_active_configuration())

    def configure(
        self,
        configuration: StorageConfiguration,
        *,
        validate_write: bool = False,
    ) -> StorageConfiguration:
        configuration.validate()
        local_health = self.local_factory(configuration).health()
        if not local_health.writable:
            raise StorageUnavailable("Vị trí lưu trữ trên Server không ghi được.")
        archive = self.archive_factory(configuration)
        if validate_write:
            health = archive.health()
            if not health.writable:
                raise StorageUnavailable("Vị trí lưu trữ dài hạn hiện không ghi được.")
            probe_key = f"admin-validation/{uuid4().hex}.probe"
            probe = b"HMS-QR-STORAGE-VALIDATION"
            stored = archive.put(probe_key, probe)
            if stored.size_bytes != len(probe):
                raise StorageIntegrityError("Storage validation object size mismatch.")
            archive.delete(probe_key)
        return self.repository.create_configuration(configuration)

    def preflight_upload(self, size_bytes: int) -> StorageCapacity:
        if size_bytes < 0:
            raise ValueError("size_bytes cannot be negative")
        config = self.repository.get_active_configuration()
        local_storage = self.local_factory(config)
        health = local_storage.health()
        if not health.writable:
            raise LocalCapacityError("Bộ nhớ máy chủ không thể lưu an toàn tệp mới.")
        capacity = self.capacity()
        if capacity.local_free_bytes - size_bytes < config.upload_refusal_free_bytes:
            raise LocalCapacityError("Bộ nhớ máy chủ không đủ để lưu an toàn tệp mới.")
        return capacity

    def capacity(self, *, at: datetime | None = None) -> StorageCapacity:
        config = self.repository.get_active_configuration()
        local_storage = self.local_factory(config)
        root = getattr(local_storage, "root", Path(config.local_ingest_root))
        total, used, free = self.capacity_probe(Path(root))
        count, pending_bytes, oldest_age = self.repository.pending_summary(at=at)
        level = "HEALTHY"
        if free <= config.upload_refusal_free_bytes:
            level = "UPLOAD_REFUSAL"
        elif free <= config.critical_free_bytes:
            level = "CRITICAL"
        elif free <= config.warning_free_bytes:
            level = "WARNING"
        return StorageCapacity(total, free, used, pending_bytes, count, oldest_age, level)

    def transfer_one(
        self,
        *,
        worker_id: str = "archive-worker",
        now: datetime | None = None,
    ) -> ArchiveTransferJob | None:
        timestamp = now or _now()
        job = self.repository.claim_next(worker_id=worker_id, now=timestamp)
        if job is None:
            return None
        assert job.lease_token
        try:
            managed = self.managed_repository.get(job.managed_file_id)
            configuration = self.repository.get_configuration(job.configuration_id)
            local_storage = self.local_factory(configuration)
            archive = self.archive_factory(configuration)
            remote = archive.verify(
                managed.storage_key,
                expected_sha256=managed.sha256,
                expected_size=managed.size_bytes,
            )
            if remote.exists and not remote.valid:
                code = (
                    TransferErrorCode.REMOTE_SIZE_MISMATCH
                    if remote.actual_size != managed.size_bytes
                    else TransferErrorCode.REMOTE_HASH_MISMATCH
                )
                raise _PermanentTransferError(code, "Remote final object has mismatched identity.")
            if not remote.valid:
                local = local_storage.verify(
                    managed.storage_key,
                    expected_sha256=managed.sha256,
                    expected_size=managed.size_bytes,
                )
                if not local.valid:
                    raise _PermanentTransferError(
                        TransferErrorCode.LOCAL_FILE_MISSING,
                        f"Local authoritative copy unavailable: {local.reason}",
                    )
                content = local_storage.read(managed.storage_key)
                archive.publish_transfer(
                    managed.storage_key,
                    content,
                    transfer_id=str(job.job_id),
                    expected_sha256=managed.sha256,
                    expected_size=managed.size_bytes,
                )
            self.repository.mark_remote_verifying(
                job.job_id, lease_token=job.lease_token, at=timestamp
            )
            verified = archive.verify(
                managed.storage_key,
                expected_sha256=managed.sha256,
                expected_size=managed.size_bytes,
            )
            if not (verified.exists and verified.valid):
                raise StorageIntegrityError("Remote final verification did not pass.")
            return self.repository.mark_remote_ready(
                job.job_id,
                lease_token=job.lease_token,
                verified_at=timestamp,
                grace_period_hours=configuration.grace_period_hours,
            )
        except Exception as exc:
            code, permanent = _classify(exc)
            configuration = self.repository.get_configuration(job.configuration_id)
            retry_at = None
            if not permanent:
                schedule = configuration.retry_schedule_seconds
                delay = schedule[min(max(job.attempt_count, 1) - 1, len(schedule) - 1)]
                retry_at = timestamp + timedelta(seconds=delay)
            return self.repository.mark_failure(
                job.job_id,
                lease_token=job.lease_token,
                code=code.value,
                summary=str(exc),
                retry_at=retry_at,
                permanent=permanent,
                at=timestamp,
            )

    def retry_now(self, managed_file_id: UUID) -> ArchiveTransferJob:
        return self.repository.retry_now(managed_file_id)

    def purge_ready_local_copies(self, *, now: datetime | None = None) -> tuple[ArchiveTransferJob, ...]:
        timestamp = now or _now()
        self.repository.advance_expired_grace(at=timestamp)
        results: list[ArchiveTransferJob] = []
        for job in self.repository.purge_candidates(at=timestamp):
            try:
                managed = self.managed_repository.get(job.managed_file_id)
                configuration = self.repository.get_configuration(job.configuration_id)
                local_storage = self.local_factory(configuration)
                archive = self.archive_factory(configuration)
                remote = archive.verify(
                    managed.storage_key,
                    expected_sha256=managed.sha256,
                    expected_size=managed.size_bytes,
                )
                if not (remote.exists and remote.valid and job.remote_verified_at):
                    raise StorageIntegrityError("Remote copy is no longer verified.")
                local = local_storage.verify(
                    managed.storage_key,
                    expected_sha256=managed.sha256,
                    expected_size=managed.size_bytes,
                )
                if local.exists and not local.valid:
                    raise StorageIntegrityError("Local object identity changed; deletion refused.")
                if local.valid:
                    local_storage.delete(managed.storage_key)
                if local_storage.exists(managed.storage_key):
                    raise StorageUnavailable("Local delete did not remove the expected object.")
                results.append(self.repository.mark_local_purged(job.job_id, at=timestamp))
            except Exception as exc:
                self.repository.mark_local_delete_failed(job.job_id, summary=str(exc), at=timestamp)
                results.append(self.repository.get_job_by_id(job.job_id))
        return tuple(results)

    def read_available(self, managed: ManagedFile) -> bytes:
        job = self.repository.get_job(managed.file_id)
        configuration = self.repository.get_configuration(job.configuration_id)
        local_storage = self.local_factory(configuration)
        local = local_storage.verify(
            managed.storage_key,
            expected_sha256=managed.sha256,
            expected_size=managed.size_bytes,
        )
        if local.valid:
            return local_storage.read(managed.storage_key)
        if job.remote_verified_at is None:
            raise FileNotFoundError("Không còn bản sao hợp lệ có thể phục vụ.")
        archive = self.archive_factory(configuration)
        remote = archive.verify(
            managed.storage_key,
            expected_sha256=managed.sha256,
            expected_size=managed.size_bytes,
        )
        if not remote.valid:
            raise FileNotFoundError("Không còn bản sao hợp lệ có thể phục vụ.")
        return archive.read(managed.storage_key)

    def status(self, managed_file_id: UUID) -> ArchiveTransferJob:
        return self.repository.get_job(managed_file_id)

    def reconcile(self, *, now: datetime | None = None) -> dict[str, int]:
        """Bounded restart recovery without deleting ambiguous data."""

        timestamp = now or _now()
        recovered = self.repository.recover_expired_leases(at=timestamp)
        queued = 0
        active = self.repository.get_active_configuration()
        local_storage = self.local_factory(active)
        local_recovered = 0
        for managed in self.managed_repository.local_recovery_candidates():
            local = local_storage.verify(
                managed.storage_key,
                expected_sha256=managed.sha256,
                expected_size=managed.size_bytes,
            )
            if not local.valid and isinstance(local_storage, FilesystemStorage):
                local_storage.recover_upload_temp(
                    managed.storage_key,
                    expected_sha256=managed.sha256,
                    expected_size=managed.size_bytes,
                )
                local = local_storage.verify(
                    managed.storage_key,
                    expected_sha256=managed.sha256,
                    expected_size=managed.size_bytes,
                )
            if local.valid:
                self.managed_repository.recover_local_ready_and_queue(
                    managed.file_id,
                    transfer_configuration_id=active.configuration_id,
                    at=timestamp,
                )
                local_recovered += 1
        for managed in self.managed_repository.ready_files():
            try:
                self.repository.get_job(managed.file_id)
            except LookupError:
                local = local_storage.verify(
                    managed.storage_key,
                    expected_sha256=managed.sha256,
                    expected_size=managed.size_bytes,
                )
                if local.valid:
                    self.repository.ensure_job(
                        managed.file_id, active.configuration_id, at=timestamp
                    )
                    queued += 1
        grace = self.repository.advance_expired_grace(at=timestamp)
        return {
            "expired_leases_requeued": recovered,
            "local_uploads_recovered": local_recovered,
            "orphan_ready_files_queued": queued,
            "grace_advanced": grace,
        }

    def health(self) -> dict[str, object]:
        config = self.repository.get_active_configuration()
        local = self.local_factory(config).health()
        archive = self.archive_factory(config).health()
        capacity = self.capacity()
        return {
            "local": {"state": local.state.value, "writable": local.writable},
            "archive": {"state": archive.state.value, "writable": archive.writable},
            "capacity": capacity,
            "last_successful_transfer": self.repository.last_successful_transfer_at(),
        }


class _PermanentTransferError(RuntimeError):
    def __init__(self, code: TransferErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def _classify(exc: Exception) -> tuple[TransferErrorCode, bool]:
    if isinstance(exc, _PermanentTransferError):
        return exc.code, True
    if isinstance(exc, StorageConflict):
        return TransferErrorCode.REMOTE_HASH_MISMATCH, True
    if isinstance(exc, StorageIntegrityError):
        return TransferErrorCode.REMOTE_HASH_MISMATCH, False
    if isinstance(exc, PermissionError):
        return TransferErrorCode.PERMISSION_DENIED, False
    if isinstance(exc, StorageUnavailable):
        return TransferErrorCode.ARCHIVE_UNAVAILABLE, False
    if isinstance(exc, (ValueError, LookupError)):
        return TransferErrorCode.PERMANENT_CONFIGURATION_ERROR, True
    if isinstance(exc, OSError) and getattr(exc, "errno", None) == 28:
        return TransferErrorCode.DISK_FULL, False
    if isinstance(exc, OSError):
        return TransferErrorCode.TEMPORARY_IO_FAILURE, False
    return TransferErrorCode.UNKNOWN_FAILURE, False


def _disk_usage(path: Path) -> tuple[int, int, int]:
    usage = shutil.disk_usage(path)
    return usage.total, usage.used, usage.free


def _now() -> datetime:
    return datetime.now(timezone.utc)
