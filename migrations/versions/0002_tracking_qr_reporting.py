"""Tracking, QR, operator preference and process reporting."""

from alembic import op
import sqlalchemy as sa


revision = "0002_tracking_qr_reporting"
down_revision = "0001_stage2_baseline"
branch_labels = None
depends_on = None


def upgrade():
    """Create only the tracking/reporting schema owned by Stage 3."""

    with op.batch_alter_table("purchase_orders") as batch:
        batch.add_column(sa.Column("internal_order_code", sa.String(64), nullable=True))
        batch.create_unique_constraint(
            "uq_purchase_orders_internal_order_code", ["internal_order_code"]
        )

    op.create_table(
        "operators",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "machining_types",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "order_tracking_items",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("tracking_code", sa.String(64), nullable=False),
        sa.Column("purchase_order_id", sa.String(36), nullable=False),
        sa.Column("purchase_order_line_id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("qr_public_id", sa.String(64), nullable=True),
        sa.Column("qr_status", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.internal_id"]),
        sa.ForeignKeyConstraint(
            ["purchase_order_line_id"], ["purchase_order_lines.internal_id"]
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.internal_id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.internal_id"]),
        sa.UniqueConstraint("tracking_code"),
        sa.UniqueConstraint("qr_public_id"),
    )
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column("machining_type_id", sa.String(36), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["operators.internal_id"]),
        sa.ForeignKeyConstraint(["machining_type_id"], ["machining_types.internal_id"]),
    )
    op.create_table(
        "attempt_display_state",
        sa.Column("tracking_item_id", sa.String(36), primary_key=True),
        sa.Column("machining_type_id", sa.String(36), primary_key=True),
        sa.Column("max_visible_attempt", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(
            ["tracking_item_id"], ["order_tracking_items.internal_id"]
        ),
        sa.ForeignKeyConstraint(["machining_type_id"], ["machining_types.internal_id"]),
    )
    op.create_table(
        "process_report_events",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("tracking_item_id", sa.String(36), nullable=False),
        sa.Column("machining_type_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.String(36), nullable=False),
        sa.Column("actor_display_name_snapshot", sa.String(255), nullable=False),
        sa.Column("server_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_id", sa.String(255), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["tracking_item_id"], ["order_tracking_items.internal_id"]
        ),
        sa.ForeignKeyConstraint(["machining_type_id"], ["machining_types.internal_id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["operators.internal_id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["process_report_events.internal_id"]),
        sa.UniqueConstraint("request_id"),
    )
    op.create_table(
        "tracking_audit_events",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("tracking_item_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("server_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tracking_item_id"], ["order_tracking_items.internal_id"]
        ),
    )


def downgrade():
    """Remove only the tracking/reporting delta owned by Stage 3."""

    op.drop_table("tracking_audit_events")
    op.drop_table("process_report_events")
    op.drop_table("attempt_display_state")
    op.drop_table("user_preferences")
    op.drop_table("order_tracking_items")
    op.drop_table("machining_types")
    op.drop_table("operators")
    with op.batch_alter_table("purchase_orders") as batch:
        batch.drop_constraint(
            "uq_purchase_orders_internal_order_code", type_="unique"
        )
        batch.drop_column("internal_order_code")
