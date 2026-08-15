"""Transaction-safe persistent archive queue and configuration repository."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from packages.domain.store_forward import (
    ArchiveTransferJob,
    ArchiveTransferState,
    StorageConfiguration,
)
from .storage_models import ManagedFileORM
from .store_forward_models import ArchiveTransferJobORM, StorageConfigurationORM
from .database import resolve_database, transaction_lock


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


class StoreForwardRepository:
    def __init__(self, engine, session_factory=None) -> None:
        self.engine, self.Session = resolve_database(engine, session_factory)

    def create_configuration(self, configuration: StorageConfiguration) -> StorageConfiguration:
        configuration.validate()
        now = configuration.created_at or _now()
        with self.Session.begin() as session:
            if configuration.active:
                transaction_lock(session, "active-storage-configuration")
                session.execute(update(StorageConfigurationORM).values(active=False, updated_at=now))
            session.add(StorageConfigurationORM(
                internal_id=str(configuration.configuration_id),
                local_ingest_root=configuration.local_ingest_root.strip(),
                archive_target_root=configuration.archive_target_root.strip(),
                grace_period_hours=configuration.grace_period_hours,
                retry_schedule_seconds=",".join(str(value) for value in configuration.retry_schedule_seconds),
                warning_free_bytes=configuration.warning_free_bytes,
                critical_free_bytes=configuration.critical_free_bytes,
                upload_refusal_free_bytes=configuration.upload_refusal_free_bytes,
                active=configuration.active,
                created_at=now,
                updated_at=configuration.updated_at or now,
            ))
        return self.get_configuration(configuration.configuration_id)

    def get_active_configuration(self) -> StorageConfiguration:
        with self.Session() as session:
            row = session.scalar(select(StorageConfigurationORM).where(
                StorageConfigurationORM.active.is_(True)
            ).order_by(StorageConfigurationORM.updated_at.desc()))
            if row is None:
                raise LookupError("Chưa cấu hình kho lưu trữ đang hoạt động.")
            return self._configuration(row)

    def get_configuration(self, configuration_id: UUID) -> StorageConfiguration:
        with self.Session() as session:
            row = session.get(StorageConfigurationORM, str(configuration_id))
            if row is None:
                raise LookupError("storage configuration not found")
            return self._configuration(row)

    def ensure_job(
        self,
        managed_file_id: UUID,
        configuration_id: UUID,
        *,
        at: datetime | None = None,
    ) -> ArchiveTransferJob:
        timestamp = at or _now()
        try:
            with self.Session.begin() as session:
                existing = session.scalar(select(ArchiveTransferJobORM).where(
                    ArchiveTransferJobORM.managed_file_id == str(managed_file_id)
                ))
                if existing is None:
                    if session.get(StorageConfigurationORM, str(configuration_id)) is None:
                        raise LookupError("storage configuration not found")
                    existing = ArchiveTransferJobORM(
                        internal_id=str(uuid4()), managed_file_id=str(managed_file_id),
                        configuration_id=str(configuration_id),
                        state=ArchiveTransferState.TRANSFER_QUEUED.value,
                        attempt_count=0, next_retry_at=timestamp, last_attempt_at=None,
                        last_error_code=None, last_error_summary=None,
                        remote_verified_at=None, grace_expires_at=None, local_purged_at=None,
                        lease_token=None, lease_expires_at=None,
                        created_at=timestamp, updated_at=timestamp,
                    )
                    session.add(existing)
                    session.flush()
                job_id = existing.internal_id
        except IntegrityError:
            # A concurrent ensure may win the unique(managed_file_id) race.
            return self.get_job(managed_file_id)
        return self.get_job_by_id(UUID(job_id))

    def get_job(self, managed_file_id: UUID) -> ArchiveTransferJob:
        with self.Session() as session:
            row = session.scalar(select(ArchiveTransferJobORM).where(
                ArchiveTransferJobORM.managed_file_id == str(managed_file_id)
            ))
            if row is None:
                raise LookupError("archive transfer job not found")
            return self._job(row)

    def get_job_by_id(self, job_id: UUID) -> ArchiveTransferJob:
        with self.Session() as session:
            row = session.get(ArchiveTransferJobORM, str(job_id))
            if row is None:
                raise LookupError("archive transfer job not found")
            return self._job(row)

    def list_jobs(self) -> tuple[ArchiveTransferJob, ...]:
        with self.Session() as session:
            rows = session.scalars(select(ArchiveTransferJobORM).order_by(
                ArchiveTransferJobORM.created_at, ArchiveTransferJobORM.internal_id
            )).all()
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
        with self.Session.begin() as session:
            candidates = session.scalars(select(ArchiveTransferJobORM.internal_id).where(
                ArchiveTransferJobORM.state.in_(eligible),
                or_(ArchiveTransferJobORM.next_retry_at.is_(None), ArchiveTransferJobORM.next_retry_at <= timestamp),
                or_(ArchiveTransferJobORM.lease_expires_at.is_(None), ArchiveTransferJobORM.lease_expires_at <= timestamp),
            ).order_by(
                ArchiveTransferJobORM.next_retry_at,
                ArchiveTransferJobORM.created_at,
            ).limit(8)).all()
            claimed_id = None
            for candidate_id in candidates:
                result = session.execute(update(ArchiveTransferJobORM).where(
                    ArchiveTransferJobORM.internal_id == candidate_id,
                    ArchiveTransferJobORM.state.in_(eligible),
                    or_(ArchiveTransferJobORM.lease_expires_at.is_(None), ArchiveTransferJobORM.lease_expires_at <= timestamp),
                ).values(
                    state=ArchiveTransferState.TRANSFERRING.value,
                    attempt_count=ArchiveTransferJobORM.attempt_count + 1,
                    last_attempt_at=timestamp,
                    lease_token=token,
                    lease_expires_at=timestamp + timedelta(seconds=lease_seconds),
                    updated_at=timestamp,
                ))
                if result.rowcount == 1:
                    claimed_id = candidate_id
                    break
        return self.get_job_by_id(UUID(claimed_id)) if claimed_id else None

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
        with self.Session.begin() as session:
            # Put eligibility in the mutation predicate. A concurrent worker
            # can change the row, but retry can only update a still-retryable
            # failure and can never demote an active or verified state.
            result = session.execute(update(ArchiveTransferJobORM).where(
                ArchiveTransferJobORM.managed_file_id == str(managed_file_id),
                ArchiveTransferJobORM.state.in_(tuple(
                    state.value for state in TRANSFER_RETRY_ELIGIBLE_STATES
                )),
            ).values(
                state=ArchiveTransferState.TRANSFER_QUEUED.value,
                next_retry_at=timestamp,
                last_error_code=None,
                last_error_summary=None,
                lease_token=None,
                lease_expires_at=None,
                updated_at=timestamp,
            ))
            row = session.scalar(select(ArchiveTransferJobORM).where(
                ArchiveTransferJobORM.managed_file_id == str(managed_file_id)
            ))
            if row is None:
                raise LookupError("archive transfer job not found")
            if result.rowcount != 1:
                return self._job(row)
            if row.state in {
                ArchiveTransferState.TRANSFERRING.value,
                ArchiveTransferState.REMOTE_VERIFYING.value,
            } and row.lease_expires_at and _utc(row.lease_expires_at) > timestamp:
                raise ValueError("Tệp đang được một worker khác xử lý.")
            if row.state == ArchiveTransferState.ARCHIVED_REMOTE_ONLY.value:
                return self._job(row)
            row.state = ArchiveTransferState.TRANSFER_QUEUED.value
            row.next_retry_at = timestamp
            row.last_error_code = None
            row.last_error_summary = None
            row.lease_token = None
            row.lease_expires_at = None
            row.updated_at = timestamp
            job_id = row.internal_id
        return self.get_job_by_id(UUID(job_id))

    def recover_expired_leases(self, *, at: datetime | None = None) -> int:
        timestamp = at or _now()
        with self.Session.begin() as session:
            result = session.execute(update(ArchiveTransferJobORM).where(
                ArchiveTransferJobORM.state.in_((
                    ArchiveTransferState.TRANSFERRING.value,
                    ArchiveTransferState.REMOTE_VERIFYING.value,
                )),
                ArchiveTransferJobORM.lease_expires_at <= timestamp,
            ).values(
                state=ArchiveTransferState.TRANSFER_QUEUED.value,
                next_retry_at=timestamp,
                lease_token=None,
                lease_expires_at=None,
                updated_at=timestamp,
            ))
            return int(result.rowcount or 0)

    def advance_expired_grace(self, *, at: datetime | None = None) -> int:
        timestamp = at or _now()
        with self.Session.begin() as session:
            result = session.execute(update(ArchiveTransferJobORM).where(
                ArchiveTransferJobORM.state == ArchiveTransferState.LOCAL_GRACE_RETENTION.value,
                ArchiveTransferJobORM.grace_expires_at <= timestamp,
            ).values(state=ArchiveTransferState.LOCAL_PURGE_PENDING.value, updated_at=timestamp))
            return int(result.rowcount or 0)

    def purge_candidates(self, *, at: datetime | None = None) -> tuple[ArchiveTransferJob, ...]:
        timestamp = at or _now()
        with self.Session() as session:
            rows = session.scalars(select(ArchiveTransferJobORM).where(
                ArchiveTransferJobORM.state == ArchiveTransferState.LOCAL_PURGE_PENDING.value,
                ArchiveTransferJobORM.remote_verified_at.is_not(None),
                ArchiveTransferJobORM.grace_expires_at <= timestamp,
                ArchiveTransferJobORM.lease_token.is_(None),
            ).order_by(ArchiveTransferJobORM.grace_expires_at)).all()
            return tuple(self._job(row) for row in rows)

    def mark_local_purged(self, job_id: UUID, *, at: datetime | None = None) -> ArchiveTransferJob:
        timestamp = at or _now()
        with self.Session.begin() as session:
            row = session.get(ArchiveTransferJobORM, str(job_id))
            if row is None:
                raise LookupError("archive transfer job not found")
            if row.state != ArchiveTransferState.LOCAL_PURGE_PENDING.value:
                raise ValueError("Job is not eligible for local purge.")
            row.state = ArchiveTransferState.ARCHIVED_REMOTE_ONLY.value
            row.local_purged_at = timestamp
            row.last_error_code = None
            row.last_error_summary = None
            row.updated_at = timestamp
        return self.get_job_by_id(job_id)

    def mark_local_delete_failed(self, job_id: UUID, *, summary: str, at: datetime | None = None) -> None:
        timestamp = at or _now()
        with self.Session.begin() as session:
            row = session.get(ArchiveTransferJobORM, str(job_id))
            if row is None:
                raise LookupError("archive transfer job not found")
            row.state = ArchiveTransferState.LOCAL_PURGE_PENDING.value
            row.last_error_code = "LOCAL_DELETE_FAILED"
            row.last_error_summary = _bounded(summary)
            row.updated_at = timestamp

    def pending_summary(self, *, at: datetime | None = None) -> tuple[int, int, int | None]:
        timestamp = at or _now()
        pending = tuple(state.value for state in TRANSFER_PENDING_STATES)
        with self.Session() as session:
            count, total, oldest = session.execute(select(
                func.count(ArchiveTransferJobORM.internal_id),
                func.coalesce(func.sum(ManagedFileORM.size_bytes), 0),
                func.min(ArchiveTransferJobORM.created_at),
            ).join(
                ManagedFileORM, ManagedFileORM.internal_id == ArchiveTransferJobORM.managed_file_id
            ).where(ArchiveTransferJobORM.state.in_(pending))).one()
        age = max(0, int((timestamp - _utc(oldest)).total_seconds())) if oldest else None
        return int(count), int(total), age

    def last_successful_transfer_at(self) -> datetime | None:
        with self.Session() as session:
            value = session.scalar(select(func.max(ArchiveTransferJobORM.remote_verified_at)))
            return _utc(value) if value else None

    def _leased_update(self, job_id: UUID, owned_lease_token: str, at: datetime, **values: object) -> None:
        with self.Session.begin() as session:
            result = session.execute(update(ArchiveTransferJobORM).where(
                ArchiveTransferJobORM.internal_id == str(job_id),
                ArchiveTransferJobORM.lease_token == owned_lease_token,
            ).values(updated_at=at, **values))
            if result.rowcount != 1:
                raise ValueError("Archive job lease is no longer owned by this worker.")

    @staticmethod
    def _configuration(row: StorageConfigurationORM) -> StorageConfiguration:
        return StorageConfiguration(
            configuration_id=UUID(row.internal_id),
            local_ingest_root=row.local_ingest_root,
            archive_target_root=row.archive_target_root,
            grace_period_hours=row.grace_period_hours,
            retry_schedule_seconds=tuple(int(value) for value in row.retry_schedule_seconds.split(",")),
            warning_free_bytes=row.warning_free_bytes,
            critical_free_bytes=row.critical_free_bytes,
            upload_refusal_free_bytes=row.upload_refusal_free_bytes,
            active=row.active,
            created_at=_utc(row.created_at),
            updated_at=_utc(row.updated_at),
        )

    @staticmethod
    def _job(row: ArchiveTransferJobORM) -> ArchiveTransferJob:
        return ArchiveTransferJob(
            job_id=UUID(row.internal_id), managed_file_id=UUID(row.managed_file_id),
            configuration_id=UUID(row.configuration_id), state=ArchiveTransferState(row.state),
            attempt_count=row.attempt_count,
            next_retry_at=_utc(row.next_retry_at) if row.next_retry_at else None,
            last_attempt_at=_utc(row.last_attempt_at) if row.last_attempt_at else None,
            last_error_code=row.last_error_code, last_error_summary=row.last_error_summary,
            remote_verified_at=_utc(row.remote_verified_at) if row.remote_verified_at else None,
            grace_expires_at=_utc(row.grace_expires_at) if row.grace_expires_at else None,
            local_purged_at=_utc(row.local_purged_at) if row.local_purged_at else None,
            lease_token=row.lease_token,
            lease_expires_at=_utc(row.lease_expires_at) if row.lease_expires_at else None,
            created_at=_utc(row.created_at), updated_at=_utc(row.updated_at),
        )


def _bounded(value: str) -> str:
    return " ".join(str(value).split())[:512] or "Unspecified storage failure"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
