"""Stage 6 R009 persistent store-and-forward configuration and queue (engine format)."""

STORAGE_CONFIGURATIONS = """
CREATE TABLE storage_configurations (
    internal_id TEXT PRIMARY KEY,
    local_ingest_root TEXT NOT NULL,
    archive_target_root TEXT NOT NULL,
    grace_period_hours INTEGER NOT NULL,
    retry_schedule_seconds TEXT NOT NULL,
    warning_free_bytes INTEGER NOT NULL,
    critical_free_bytes INTEGER NOT NULL,
    upload_refusal_free_bytes INTEGER NOT NULL,
    active BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
)
"""

ARCHIVE_TRANSFER_JOBS = """
CREATE TABLE archive_transfer_jobs (
    internal_id TEXT PRIMARY KEY,
    managed_file_id TEXT NOT NULL,
    configuration_id TEXT NOT NULL,
    state TEXT NOT NULL,
    attempt_count INTEGER NOT NULL,
    next_retry_at DATETIME,
    last_attempt_at DATETIME,
    last_error_code TEXT,
    last_error_summary TEXT,
    remote_verified_at DATETIME,
    grace_expires_at DATETIME,
    local_purged_at DATETIME,
    lease_token TEXT,
    lease_expires_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (managed_file_id) REFERENCES managed_files(internal_id),
    FOREIGN KEY (configuration_id) REFERENCES storage_configurations(internal_id),
    UNIQUE (managed_file_id)
)
"""


def upgrade(transaction):
    """Create only the store-and-forward schema owned by Stage 6 R009."""

    transaction.execute(STORAGE_CONFIGURATIONS)
    transaction.execute(ARCHIVE_TRANSFER_JOBS)
