"""Transaction-safe persistent archive queue and configuration repository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from packages.domain.store_forward import (
    ArchiveTransferJob,
    ArchiveTransferState,
    StorageConfiguration,
)
from packages.sqlengine.errors import IntegrityError
from .database import resolve_database


TRANSFER_PENDING_STATES = (
    ArchiveTransferState.LOCAL_READY,
    ArchiveTransferState.TRANSFER_QUEUED,
    ArchiveTransferState.TRANSFERRING,
    ArchiveTransferState.REMOTE_VERIFYING,
    ArchiveTransferState.TRANSFER_FAILED_RETRYABLE,
)

# Ordinary manual retry is deliberately narrower than worker recovery. Once
# remote verification succeeds, an ordinary retry must never move the job
# backwards into the transfer queue. Permanent failures require a separate
# force-retry action, which this product does not currently expose.
TRANSFER_RETRY_ELIGIBLE_STATES = frozenset({
    ArchiveTransferState.TRANSFER_FAILED_RETRYABLE,
})


def transfer_retry_eligible(state: ArchiveTransferState | str) -> bool:
    """Return the canonical eligibility decision for ordinary transfer retry."""

    return ArchiveTransferState(state) in TRANSFER_RETRY_ELIGIBLE_STATES


_JOB_COLUMNS = (
    "internal_id", "managed_file_id", "configuration_id", "state", "attempt_count",
    "next_retry_at", "last_attempt_at", "last_error_code", "last_error_summary",
    "remote_verified_at", "grace_expires_at", "local_purged_at", "lease_token",
    "lease_expires_at", "created_at", "updated_at",
)


def _job_values(job: ArchiveTransferJob) -> dict:
    return {
        "internal_id": str(job.job_id),
        "managed_file_id": str(job.managed_file_id),
        "configuration_id": str(job.configuration_id),
        "state": job.state.value,
        "attempt_count": job.attempt_count,
        "next_retry_at": job.next_retry_at,
        "last_attempt_at": job.last_attempt_at,
        "last_error_code": job.last_error_code,
        "last_error_summary": job.last_error_summary,
        "remote_verified_at": job.remote_verified_at,
        "grace_expires_at": job.grace_expires_at,
        "local_purged_at": job.local_purged_at,
        "lease_token": job.lease_token,
        "lease_expires_at": job.lease_expires_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


class StoreForwardRepository:
    """Archive queue persistence on the in-process HMS SQL engine."""

    def __init__(self, engine, session_factory=None) -> None:
        self.database = resolve_database(engine, session_factory)

    def create_configuration(self, configuration: StorageConfiguration) -> StorageConfiguration:
        configuration.validate()
        now = configuration.created_at or _now()
        with self.database.transaction() as transaction:
            if configuration.active:
                transaction.execute(
                    "UPDATE storage_configurations SET active = ?, updated_at = ?",
                    [False, now],
                )
            transaction.execute(
                "INSERT INTO storage_configurations (internal_id, local_ingest_root,"
                " archive_target_root, grace_period_hours, retry_schedule_seconds,"
                " warning_free_bytes, critical_free_bytes, upload_refusal_free_bytes,"
                " active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    str(configuration.configuration_id),
                    configuration.local_ingest_root.strip(),
                    configuration.archive_target_root.strip(),
                    configuration.grace_period_hours,
                    ",".join(str(value) for value in configuration.retry_schedule_seconds),
                    configuration.warning_free_bytes,
                    configuration.critical_free_bytes,
                    configuration.upload_refusal_free_bytes,
                    configuration.active,
                    now,
                    configuration.updated_at or now,
                ],
            )
        return self.get_configuration(configuration.configuration_id)

    def get_active_configuration(self) -> StorageConfiguration:
        rows = self.database.query(
            "SELECT * FROM storage_configurations WHERE active = ?"
            " ORDER BY updated_at DESC, internal_id DESC",
            [True],
        )
        if not rows:
            raise LookupError("Chưa cấu hình kho lưu trữ đang hoạt động.")
        return self._configuration(rows[0])

    def get_configuration(self, configuration_id: UUID) -> StorageConfiguration:
        rows = self.database.query(
            "SELECT * FROM storage_configurations WHERE internal_id = ?",
            [str(configuration_id)],
        )
        if not rows:
            raise LookupError("storage configuration not found")
        return self._configuration(rows[0])

    def ensure_job(
        self,
        managed_file_id: UUID,
        configuration_id: UUID,
        *,
        at: datetime | None = None,
    ) -> ArchiveTransferJob:
        timestamp = at or _now()
        try:
            with self.database.transaction() as transaction:
                existing = transaction.execute(
                    "SELECT internal_id FROM archive_transfer_jobs WHERE managed_file_id = ?",
                    [str(managed_file_id)],
                )
                if not existing:
                    configured = transaction.execute(
                        "SELECT internal_id FROM storage_configurations WHERE internal_id = ?",
                        [str(configuration_id)],
                    )
                    if not configured:
                        raise LookupError("storage configuration not found")
                    job_id = str(uuid4())
                    transaction.execute(
                        "INSERT INTO archive_transfer_jobs (internal_id, managed_file_id,"
                        " configuration_id, state, attempt_count, next_retry_at,"
                        " last_attempt_at, last_error_code, last_error_summary,"
                        " remote_verified_at, grace_expires_at, local_purged_at,"
                        " lease_token, lease_expires_at, created_at, updated_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [
                            job_id, str(managed_file_id), str(configuration_id),
                            ArchiveTransferState.TRANSFER_QUEUED.value, 0, timestamp,
                            None, None, None, None, None, None, None, None,
                            timestamp, timestamp,
                        ],
                    )
                else:
                    job_id = existing[0]["internal_id"]
        except IntegrityError:
            # A concurrent ensure may win the unique(managed_file_id) race.
            return self.get_job(managed_file_id)
        return self.get_job_by_id(UUID(job_id))

    def get_job(self, managed_file_id: UUID) -> ArchiveTransferJob:
        rows = self.database.query(
            "SELECT * FROM archive_transfer_jobs WHERE managed_file_id = ?",
            [str(managed_file_id)],
        )
        if not rows:
            raise LookupError("archive transfer job not found")
        return self._job(rows[0])

    def get_job_by_id(self, job_id: UUID) -> ArchiveTransferJob:
        rows = self.database.query(
            "SELECT * FROM archive_transfer_jobs WHERE internal_id = ?", [str(job_id)]
        )
        if not rows:
            raise LookupError("archive transfer job not found")
        return self._job(rows[0])

    def list_jobs(self) -> tuple[ArchiveTransferJob, ...]:
        rows = self.database.query(
            "SELECT * FROM archive_transfer_jobs ORDER BY created_at ASC, internal_id ASC"
        )
        return tuple(self._job(row) for row in rows)

    def claim_next(
        self,
        *,
        worker_id: str,
        now: datetime | None = None,
        lease_seconds: int = 300,
    ) -> ArchiveTransferJob | None:
        timestamp = now or _now()
        token = f"{worker_id.strip()}:{uuid4().hex}"
        eligible = tuple(state.value for state in (
            ArchiveTransferState.LOCAL_READY,
            ArchiveTransferState.TRANSFER_QUEUED,
            ArchiveTransferState.TRANSFER_FAILED_RETRYABLE,
        ))
        placeholders = ", ".join("?" for _ in eligible)
        candidates = self.database.query(
            f"SELECT internal_id FROM archive_transfer_jobs WHERE state IN ({placeholders})"
            " AND (next_retry_at IS NULL OR next_retry_at <= ?)"
            " AND (lease_expires_at IS NULL OR lease_expires_at <= ?)"
            " ORDER BY next_retry_at ASC, created_at ASC LIMIT 8",
            [*eligible, timestamp, timestamp],
        )
        for candidate in candidates:
            with self.database.transaction() as transaction:
                current = transaction.execute(
                    "SELECT attempt_count FROM archive_transfer_jobs WHERE internal_id = ?",
                    [candidate["internal_id"]],
                )
                if not current:
                    continue
                result = transaction.execute(
                    f"UPDATE archive_transfer_jobs SET state = ?, attempt_count = ?,"
                    " last_attempt_at = ?, lease_token = ?,"
                    " lease_expires_at = ?, updated_at = ? WHERE internal_id = ?"
                    f" AND state IN ({placeholders})"
                    " AND (lease_expires_at IS NULL OR lease_expires_at <= ?)",
                    [
                        ArchiveTransferState.TRANSFERRING.value,
                        int(current[0]["attempt_count"]) + 1, timestamp, token,
                        timestamp + timedelta(seconds=lease_seconds), timestamp,
                        candidate["internal_id"], *eligible, timestamp,
                    ],
                )
                if result["updated"] == 1:
                    return self.get_job_by_id(UUID(candidate["internal_id"]))
        return None

    def mark_remote_verifying(self, job_id: UUID, *, lease_token: str, at: datetime) -> ArchiveTransferJob:
        self._leased_update(job_id, lease_token, at, state=ArchiveTransferState.REMOTE_VERIFYING.value)
        return self.get_job_by_id(job_id)

    def mark_remote_ready(
        self,
        job_id: UUID,
        *,
        lease_token: str,
        verified_at: datetime,
        grace_period_hours: int,
    ) -> ArchiveTransferJob:
        grace_expires = verified_at + timedelta(hours=grace_period_hours)
        state = (
            ArchiveTransferState.LOCAL_GRACE_RETENTION
            if grace_period_hours > 0 else ArchiveTransferState.LOCAL_PURGE_PENDING
        )
        self._leased_update(
            job_id, lease_token, verified_at,
            state=state.value,
            remote_verified_at=verified_at,
            grace_expires_at=grace_expires,
            last_error_code=None,
            last_error_summary=None,
            next_retry_at=None,
            lease_token=None,
            lease_expires_at=None,
        )
        return self.get_job_by_id(job_id)

    def mark_failure(
        self,
        job_id: UUID,
        *,
        lease_token: str,
        code: str,
        summary: str,
        retry_at: datetime | None,
        permanent: bool,
        at: datetime,
    ) -> ArchiveTransferJob:
        state = (
            ArchiveTransferState.TRANSFER_FAILED_PERMANENT
            if permanent else ArchiveTransferState.TRANSFER_FAILED_RETRYABLE
        )
        self._leased_update(
            job_id, lease_token, at,
            state=state.value,
            last_error_code=code[:64],
            last_error_summary=_bounded(summary),
            next_retry_at=retry_at,
            lease_token=None,
            lease_expires_at=None,
        )
        return self.get_job_by_id(job_id)

    def retry_now(self, managed_file_id: UUID, *, at: datetime | None = None) -> ArchiveTransferJob:
        timestamp = at or _now()
        eligible = tuple(state.value for state in TRANSFER_RETRY_ELIGIBLE_STATES)
        placeholders = ", ".join("?" for _ in eligible)
        with self.database.transaction() as transaction:
            # Put eligibility in the mutation predicate. A concurrent worker
            # can change the row, but retry can only update a still-retryable
            # failure and can never demote an active or verified state.
            result = transaction.execute(
                f"UPDATE archive_transfer_jobs SET state = ?, next_retry_at = ?,"
                " last_error_code = ?, last_error_summary = ?, lease_token = ?,"
                " lease_expires_at = ?, updated_at = ?"
                f" WHERE managed_file_id = ? AND state IN ({placeholders})",
                [
                    ArchiveTransferState.TRANSFER_QUEUED.value, timestamp, None, None,
                    None, None, timestamp, str(managed_file_id), *eligible,
                ],
            )
            rows = transaction.execute(
                "SELECT * FROM archive_transfer_jobs WHERE managed_file_id = ?",
                [str(managed_file_id)],
            )
            if not rows:
                raise LookupError("archive transfer job not found")
            row = rows[0]
            if result["updated"] != 1:
                return self._job(row)
            if row["state"] in {
                ArchiveTransferState.TRANSFERRING.value,
                ArchiveTransferState.REMOTE_VERIFYING.value,
            } and row["lease_expires_at"] and _utc(row["lease_expires_at"]) > timestamp:
                raise ValueError("Tệp đang được một worker khác xử lý.")
            if row["state"] == ArchiveTransferState.ARCHIVED_REMOTE_ONLY.value:
                return self._job(row)
            transaction.execute(
                "UPDATE archive_transfer_jobs SET state = ?, next_retry_at = ?,"
                " last_error_code = ?, last_error_summary = ?, lease_token = ?,"
                " lease_expires_at = ?, updated_at = ? WHERE internal_id = ?",
                [
                    ArchiveTransferState.TRANSFER_QUEUED.value, timestamp, None, None,
                    None, None, timestamp, row["internal_id"],
                ],
            )
            job_id = row["internal_id"]
        return self.get_job_by_id(UUID(job_id))

    def recover_expired_leases(self, *, at: datetime | None = None) -> int:
        timestamp = at or _now()
        with self.database.transaction() as transaction:
            result = transaction.execute(
                "UPDATE archive_transfer_jobs SET state = ?, next_retry_at = ?,"
                " lease_token = ?, lease_expires_at = ?, updated_at = ?"
                " WHERE state IN (?, ?) AND lease_expires_at <= ?",
                [
                    ArchiveTransferState.TRANSFER_QUEUED.value, timestamp, None, None,
                    timestamp,
                    ArchiveTransferState.TRANSFERRING.value,
                    ArchiveTransferState.REMOTE_VERIFYING.value, timestamp,
                ],
            )
        return int(result["updated"] or 0)

    def advance_expired_grace(self, *, at: datetime | None = None) -> int:
        timestamp = at or _now()
        with self.database.transaction() as transaction:
            result = transaction.execute(
                "UPDATE archive_transfer_jobs SET state = ?, updated_at = ?"
                " WHERE state = ? AND grace_expires_at <= ?",
                [
                    ArchiveTransferState.LOCAL_PURGE_PENDING.value, timestamp,
                    ArchiveTransferState.LOCAL_GRACE_RETENTION.value, timestamp,
                ],
            )
        return int(result["updated"] or 0)

    def purge_candidates(self, *, at: datetime | None = None) -> tuple[ArchiveTransferJob, ...]:
        timestamp = at or _now()
        rows = self.database.query(
            "SELECT * FROM archive_transfer_jobs WHERE state = ?"
            " AND remote_verified_at IS NOT NULL AND grace_expires_at <= ?"
            " AND lease_token IS NULL ORDER BY grace_expires_at ASC, internal_id ASC",
            [
                ArchiveTransferState.LOCAL_PURGE_PENDING.value, timestamp,
            ],
        )
        return tuple(self._job(row) for row in rows)

    def mark_local_purged(self, job_id: UUID, *, at: datetime | None = None) -> ArchiveTransferJob:
        timestamp = at or _now()
        with self.database.transaction() as transaction:
            rows = transaction.execute(
                "SELECT state FROM archive_transfer_jobs WHERE internal_id = ?", [str(job_id)]
            )
            if not rows:
                raise LookupError("archive transfer job not found")
            if rows[0]["state"] != ArchiveTransferState.LOCAL_PURGE_PENDING.value:
                raise ValueError("Job is not eligible for local purge.")
            transaction.execute(
                "UPDATE archive_transfer_jobs SET state = ?, local_purged_at = ?,"
                " last_error_code = ?, last_error_summary = ?, updated_at = ?"
                " WHERE internal_id = ?",
                [
                    ArchiveTransferState.ARCHIVED_REMOTE_ONLY.value, timestamp, None,
                    None, timestamp, str(job_id),
                ],
            )
        return self.get_job_by_id(job_id)

    def mark_local_delete_failed(self, job_id: UUID, *, summary: str, at: datetime | None = None) -> None:
        timestamp = at or _now()
        with self.database.transaction() as transaction:
            rows = transaction.execute(
                "SELECT internal_id FROM archive_transfer_jobs WHERE internal_id = ?",
                [str(job_id)],
            )
            if not rows:
                raise LookupError("archive transfer job not found")
            transaction.execute(
                "UPDATE archive_transfer_jobs SET state = ?, last_error_code = ?,"
                " last_error_summary = ?, updated_at = ? WHERE internal_id = ?",
                [
                    ArchiveTransferState.LOCAL_PURGE_PENDING.value, "LOCAL_DELETE_FAILED",
                    _bounded(summary), timestamp, str(job_id),
                ],
            )

    def pending_summary(self, *, at: datetime | None = None) -> tuple[int, int, int | None]:
        timestamp = at or _now()
        pending = tuple(state.value for state in TRANSFER_PENDING_STATES)
        placeholders = ", ".join("?" for _ in pending)
        rows = self.database.query(
            "SELECT archive_transfer_jobs.created_at AS job_created_at,"
            " managed_files.size_bytes AS file_size_bytes"
            " FROM archive_transfer_jobs JOIN managed_files"
            " ON managed_files.internal_id = archive_transfer_jobs.managed_file_id"
            f" WHERE archive_transfer_jobs.state IN ({placeholders})",
            list(pending),
        )
        count = len(rows)
        total = sum(int(row["file_size_bytes"] or 0) for row in rows)
        oldest = min((row["job_created_at"] for row in rows), default=None)
        age = max(0, int((timestamp - _utc(oldest)).total_seconds())) if oldest else None
        return count, total, age

    def last_successful_transfer_at(self) -> datetime | None:
        rows = self.database.query(
            "SELECT remote_verified_at FROM archive_transfer_jobs"
            " WHERE remote_verified_at IS NOT NULL"
        )
        values = [_utc(row["remote_verified_at"]) for row in rows]
        return max(values) if values else None

    def _leased_update(self, job_id: UUID, owned_lease_token: str, at: datetime, **values: object) -> None:
        assignments = ", ".join(f"{name} = ?" for name in values)
        with self.database.transaction() as transaction:
            result = transaction.execute(
                f"UPDATE archive_transfer_jobs SET {assignments}, updated_at = ?"
                " WHERE internal_id = ? AND lease_token = ?",
                [*values.values(), at, str(job_id), owned_lease_token],
            )
            if result["updated"] != 1:
                raise ValueError("Archive job lease is no longer owned by this worker.")

    @staticmethod
    def _configuration(row) -> StorageConfiguration:
        return StorageConfiguration(
            configuration_id=UUID(row["internal_id"]),
            local_ingest_root=row["local_ingest_root"],
            archive_target_root=row["archive_target_root"],
            grace_period_hours=row["grace_period_hours"],
            retry_schedule_seconds=tuple(int(value) for value in row["retry_schedule_seconds"].split(",")),
            warning_free_bytes=row["warning_free_bytes"],
            critical_free_bytes=row["critical_free_bytes"],
            upload_refusal_free_bytes=row["upload_refusal_free_bytes"],
            active=row["active"],
            created_at=_utc(row["created_at"]),
            updated_at=_utc(row["updated_at"]),
        )

    @staticmethod
    def _job(row) -> ArchiveTransferJob:
        return ArchiveTransferJob(
            job_id=UUID(row["internal_id"]),
            managed_file_id=UUID(row["managed_file_id"]),
            configuration_id=UUID(row["configuration_id"]),
            state=ArchiveTransferState(row["state"]),
            attempt_count=row["attempt_count"],
            next_retry_at=_utc(row["next_retry_at"]) if row["next_retry_at"] else None,
            last_attempt_at=_utc(row["last_attempt_at"]) if row["last_attempt_at"] else None,
            last_error_code=row["last_error_code"],
            last_error_summary=row["last_error_summary"],
            remote_verified_at=_utc(row["remote_verified_at"]) if row["remote_verified_at"] else None,
            grace_expires_at=_utc(row["grace_expires_at"]) if row["grace_expires_at"] else None,
            local_purged_at=_utc(row["local_purged_at"]) if row["local_purged_at"] else None,
            lease_token=row["lease_token"],
            lease_expires_at=_utc(row["lease_expires_at"]) if row["lease_expires_at"] else None,
            created_at=_utc(row["created_at"]),
            updated_at=_utc(row["updated_at"]),
        )


def _bounded(value: str) -> str:
    return " ".join(str(value).split())[:512] or "Unspecified storage failure"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


__all__ = [
    "StoreForwardRepository",
    "TRANSFER_PENDING_STATES",
    "TRANSFER_RETRY_ELIGIBLE_STATES",
    "transfer_retry_eligible",
]
