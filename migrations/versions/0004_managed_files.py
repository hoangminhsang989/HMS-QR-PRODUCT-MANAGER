"""Stage 6 managed-file metadata and product relations."""

from alembic import op
import sqlalchemy as sa


revision = "0004_managed_files"
down_revision = "0003_qc_packing_delivery"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "managed_files",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("stored_filename", sa.String(128), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("media_type", sa.String(255), nullable=False),
        sa.Column("extension", sa.String(16), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("replaced_file_id", sa.String(36), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", sa.String(128), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["replaced_file_id"], ["managed_files.internal_id"]),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_managed_files_sha256", "managed_files", ["sha256"])
    op.create_index("ix_managed_files_status", "managed_files", ["status"])

    op.create_table(
        "product_file_relations",
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("managed_file_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("attachment_category", sa.String(64), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("caption", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["managed_file_id"], ["managed_files.internal_id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.internal_id"]),
        sa.UniqueConstraint("managed_file_id"),
    )
    op.create_index(
        "ix_product_file_relations_product_id",
        "product_file_relations",
        ["product_id"],
    )


def downgrade():
    op.drop_index("ix_product_file_relations_product_id", table_name="product_file_relations")
    op.drop_table("product_file_relations")
    op.drop_index("ix_managed_files_status", table_name="managed_files")
    op.drop_index("ix_managed_files_sha256", table_name="managed_files")
    op.drop_table("managed_files")
