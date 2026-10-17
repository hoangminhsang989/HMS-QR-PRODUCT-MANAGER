"""Add server accounts and website settings."""

from alembic import op
import sqlalchemy as sa


revision = "0007_server_accounts"
down_revision = "0006_outsourced_company"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_accounts",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "server_settings",
        sa.Column("setting_key", sa.String(64), primary_key=True),
        sa.Column("setting_value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_products_delivery_product_code", "products", ["delivery_schedule", "product_code"])


def downgrade():
    op.drop_index("ix_products_delivery_product_code", "products")
    op.drop_table("server_settings")
    op.drop_table("user_accounts")
