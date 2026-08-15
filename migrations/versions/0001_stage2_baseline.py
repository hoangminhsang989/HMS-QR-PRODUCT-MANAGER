"""Stage 2 normalized baseline."""

from alembic import op
import sqlalchemy as sa


revision = "0001_stage2_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create only the schema owned by the Stage 2 baseline."""

    op.create_table(
        "products",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("product_code", sa.String(64), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("part_name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("material", sa.String(255), nullable=True),
        sa.Column("requester", sa.String(255), nullable=True),
        sa.Column("surface_treatment", sa.String(255), nullable=True),
        sa.Column("outsourced", sa.Boolean(), nullable=False),
        sa.Column("size", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("delivery_schedule", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.UniqueConstraint("product_code"),
    )
    op.create_table(
        "customers",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("customer_code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("short_name", sa.String(255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("tax_code", sa.String(64), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.UniqueConstraint("customer_code"),
    )
    op.create_table(
        "purchase_orders",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("po_number", sa.String(128), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("po_date", sa.Date(), nullable=False),
        sa.Column("requested_delivery_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.internal_id"]),
        sa.UniqueConstraint("po_number"),
    )
    op.create_table(
        "purchase_order_lines",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("po_id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("ordered_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(8), nullable=True),
        sa.Column("customer_part_reference", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.internal_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.internal_id"]),
        sa.UniqueConstraint("po_id", "line_number", name="uq_po_line_number"),
    )
    op.create_table(
        "delivery_schedule_entries",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("po_line_id", sa.String(36), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("planned_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["po_line_id"], ["purchase_order_lines.internal_id"]),
    )
    op.create_table(
        "production_runs",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("run_code", sa.String(128), nullable=False),
        sa.Column("po_line_id", sa.String(36), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("planned_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("completed_quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("planned_start", sa.Date(), nullable=True),
        sa.Column("planned_finish", sa.Date(), nullable=True),
        sa.Column("actual_start", sa.Date(), nullable=True),
        sa.Column("actual_finish", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(["po_line_id"], ["purchase_order_lines.internal_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.internal_id"]),
        sa.UniqueConstraint("run_code"),
    )


def downgrade():
    """Remove only the schema owned by the Stage 2 baseline."""

    op.drop_table("production_runs")
    op.drop_table("delivery_schedule_entries")
    op.drop_table("purchase_order_lines")
    op.drop_table("purchase_orders")
    op.drop_table("customers")
    op.drop_table("products")
