"""Safe store-and-forward domain contracts.

Managed-file availability remains independent from archive-transfer progress.
Physical roots are operational configuration and are never business identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PureWindowsPath
from uuid import UUID


class ArchiveTransferState(StrEnum):
    LOCAL_READY = "LOCAL_READY"
    TRANSFER_QUEUED = "TRANSFER_QUEUED"
    TRANSFERRING = "TRANSFERRING"
    REMOTE_VERIFYING = "REMOTE_VERIFYING"
    REMOTE_READY = "REMOTE_READY"
    LOCAL_GRACE_RETENTION = "LOCAL_GRACE_RETENTION"
    LOCAL_PURGE_PENDING = "LOCAL_PURGE_PENDING"
    ARCHIVED_REMOTE_ONLY = "ARCHIVED_REMOTE_ONLY"
    TRANSFER_FAILED_RETRYABLE = "TRANSFER_FAILED_RETRYABLE"
    TRANSFER_FAILED_PERMANENT = "TRANSFER_FAILED_PERMANENT"


class TransferErrorCode(StrEnum):
    ARCHIVE_UNAVAILABLE = "ARCHIVE_UNAVAILABLE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    DISK_FULL = "DISK_FULL"
    REMOTE_HASH_MISMATCH = "REMOTE_HASH_MISMATCH"
    REMOTE_SIZE_MISMATCH = "REMOTE_SIZE_MISMATCH"
    LOCAL_FILE_MISSING = "LOCAL_FILE_MISSING"
    REMOTE_PATH_INVALID = "REMOTE_PATH_INVALID"
    TEMPORARY_IO_FAILURE = "TEMPORARY_IO_FAILURE"
    PERMANENT_CONFIGURATION_ERROR = "PERMANENT_CONFIGURATION_ERROR"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"
    LOCAL_DELETE_FAILED = "LOCAL_DELETE_FAILED"


@dataclass(frozen=True, slots=True)
class StorageConfiguration:
    configuration_id: UUID
    local_ingest_root: str
    archive_target_root: str
    grace_period_hours: int = 24
    retry_schedule_seconds: tuple[int, ...] = (60, 300, 900, 1800, 3600)
    warning_free_bytes: int = 10 * 1024**3
    critical_free_bytes: int = 5 * 1024**3
    upload_refusal_free_bytes: int = 2 * 1024**3
    active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def validate(self) -> "StorageConfiguration":
        local = self.local_ingest_root.strip()
        archive = self.archive_target_root.strip()
        if not local or not archive:
            raise ValueError("Vị trí lưu trữ không được để trống.")
        if not _is_absolute_server_path(local) or not _is_absolute_server_path(archive):
            raise ValueError("Vị trí lưu trữ phải là đường dẫn tuyệt đối phía server.")
        if local.rstrip("\\/").casefold() == archive.rstrip("\\/").casefold():
            raise ValueError("Kho nhận cục bộ và kho lưu trữ dài hạn phải tách biệt.")
        if not 0 <= self.grace_period_hours <= 168:
            raise ValueError("Thời gian giữ bản sao server phải trong khoảng 0-168 giờ.")
        if not self.retry_schedule_seconds or len(self.retry_schedule_seconds) > 16:
            raise ValueError("Lịch thử lại phải có từ 1 đến 16 mốc.")
        if any(value < 1 or value > 86400 for value in self.retry_schedule_seconds):
            raise ValueError("Mỗi khoảng thử lại phải trong khoảng 1-86400 giây.")
        if not (
            self.warning_free_bytes >= self.critical_free_bytes
            >= self.upload_refusal_free_bytes >= 0
        ):
            raise ValueError("Ngưỡng dung lượng phải theo thứ tự WARNING >= CRITICAL >= UPLOAD_REFUSAL.")
        return self


@dataclass(frozen=True, slots=True)
class ArchiveTransferJob:
    job_id: UUID
    managed_file_id: UUID
    configuration_id: UUID
    state: ArchiveTransferState
    attempt_count: int
    next_retry_at: datetime | None
    last_attempt_at: datetime | None
    last_error_code: str | None
    last_error_summary: str | None
    remote_verified_at: datetime | None
    grace_expires_at: datetime | None
    local_purged_at: datetime | None
    lease_token: str | None
    lease_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class StorageCapacity:
    local_total_bytes: int
    local_free_bytes: int
    local_used_bytes: int
    pending_transfer_bytes: int
    pending_transfer_count: int
    oldest_pending_transfer_age_seconds: int | None
    level: str


def _is_absolute_server_path(value: str) -> bool:
    # PureWindowsPath also recognizes UNC and drive paths without touching them.
    return PureWindowsPath(value).is_absolute()
