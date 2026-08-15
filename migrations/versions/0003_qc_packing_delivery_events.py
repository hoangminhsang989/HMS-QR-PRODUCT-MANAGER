"""Stage 4 event-based QC, packing and delivery workflows."""

from alembic import op
import sqlalchemy as sa


revision = "0003_qc_packing_delivery"
down_revision = "0002_tracking_qr_reporting"
branch_labels = None
depends_on = None


def upgrade():
    """Create only the workflow-event schema owned by Stage 4."""

    op.create_table(
        "tracking_workflow_events",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("tracking_item_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("machining_type_id", sa.String(36), nullable=True),
        sa.Column("process_report_id", sa.String(36), nullable=True),
        sa.Column("actor_user_id", sa.String(36), nullable=False),
        sa.Column("actor_display_name_snapshot", sa.String(255), nullable=False),
        sa.Column("server_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_id", sa.String(255), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("supersedes_event_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["tracking_item_id"], ["order_tracking_items.internal_id"]
        ),
        sa.ForeignKeyConstraint(["machining_type_id"], ["machining_types.internal_id"]),
        sa.ForeignKeyConstraint(
            ["process_report_id"], ["process_report_events.internal_id"]
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["operators.internal_id"]),
        sa.ForeignKeyConstraint(
            ["supersedes_event_id"], ["tracking_workflow_events.internal_id"]
        ),
        sa.UniqueConstraint("request_id"),
        sa.UniqueConstraint(
            "tracking_item_id",
            "sequence_number",
            "revision",
            name="uq_workflow_sequence_revision",
        ),
    )
    op.create_index(
        "ix_tracking_workflow_events_tracking_item_id",
        "tracking_workflow_events",
        ["tracking_item_id"],
    )
    op.create_index(
        "ix_tracking_workflow_events_event_type",
        "tracking_workflow_events",
        ["event_type"],
    )


def downgrade():
    """Remove only the workflow-event delta owned by Stage 4."""

    op.drop_index(
        "ix_tracking_workflow_events_event_type",
        table_name="tracking_workflow_events",
    )
    op.drop_index(
        "ix_tracking_workflow_events_tracking_item_id",
        table_name="tracking_workflow_events",
    )
    op.drop_table("tracking_workflow_events")
