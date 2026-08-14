"""SQLAlchemy persistence for versioned storage configuration and archive jobs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .sqlalchemy_models import Base


class StorageConfigurationORM(Base):
    __tablename__ = "storage_configurations"

    internal_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    local_ingest_root: Mapped[str] = mapped_column(Text, nullable=False)
    archive_target_root: Mapped[str] = mapped_column(Text, nullable=False)
    grace_period_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_schedule_seconds: Mapped[str] = mapped_column(String(255), nullable=False)
    warning_free_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    critical_free_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    upload_refusal_free_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ArchiveTransferJobORM(Base):
    __tablename__ = "archive_transfer_jobs"

    internal_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    managed_file_id: Mapped[str] = mapped_column(
        ForeignKey("managed_files.internal_id"), nullable=False, unique=True
    )
    configuration_id: Mapped[str] = mapped_column(
        ForeignKey("storage_configurations.internal_id"), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    last_error_summary: Mapped[str | None] = mapped_column(String(512))
    remote_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grace_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    local_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(64), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
