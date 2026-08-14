"""Stage 6 R009 persistent store-and-forward configuration and queue."""

from alembic import op
import sqlalchemy as sa


revision = "0005_store_forward"
down_revision = "0004_managed_files"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "storage_configurations",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("local_ingest_root", sa.Text(), nullable=False),
        sa.Column("archive_target_root", sa.Text(), nullable=False),
        sa.Column("grace_period_hours", sa.Integer(), nullable=False),
        sa.Column("retry_schedule_seconds", sa.String(255), nullable=False),
        sa.Column("warning_free_bytes", sa.BigInteger(), nullable=False),
        sa.Column("critical_free_bytes", sa.BigInteger(), nullable=False),
        sa.Column("upload_refusal_free_bytes", sa.BigInteger(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_storage_configurations_active", "storage_configurations", ["active"])
    op.create_table(
        "archive_transfer_jobs",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("managed_file_id", sa.String(36), nullable=False),
        sa.Column("configuration_id", sa.String(36), nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("last_error_summary", sa.String(512), nullable=True),
        sa.Column("remote_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("local_purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_token", sa.String(64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["managed_file_id"], ["managed_files.internal_id"]),
        sa.ForeignKeyConstraint(["configuration_id"], ["storage_configurations.internal_id"]),
        sa.UniqueConstraint("managed_file_id"),
    )
    op.create_index("ix_archive_transfer_jobs_configuration_id", "archive_transfer_jobs", ["configuration_id"])
    op.create_index("ix_archive_transfer_jobs_state", "archive_transfer_jobs", ["state"])
    op.create_index("ix_archive_transfer_jobs_next_retry_at", "archive_transfer_jobs", ["next_retry_at"])
    op.create_index("ix_archive_transfer_jobs_grace_expires_at", "archive_transfer_jobs", ["grace_expires_at"])
    op.create_index("ix_archive_transfer_jobs_lease_token", "archive_transfer_jobs", ["lease_token"])
    op.create_index("ix_archive_transfer_jobs_lease_expires_at", "archive_transfer_jobs", ["lease_expires_at"])


def downgrade():
    op.drop_index("ix_archive_transfer_jobs_lease_expires_at", table_name="archive_transfer_jobs")
    op.drop_index("ix_archive_transfer_jobs_lease_token", table_name="archive_transfer_jobs")
    op.drop_index("ix_archive_transfer_jobs_grace_expires_at", table_name="archive_transfer_jobs")
    op.drop_index("ix_archive_transfer_jobs_next_retry_at", table_name="archive_transfer_jobs")
    op.drop_index("ix_archive_transfer_jobs_state", table_name="archive_transfer_jobs")
    op.drop_index("ix_archive_transfer_jobs_configuration_id", table_name="archive_transfer_jobs")
    op.drop_table("archive_transfer_jobs")
    op.drop_index("ix_storage_configurations_active", table_name="storage_configurations")
    op.drop_table("storage_configurations")
