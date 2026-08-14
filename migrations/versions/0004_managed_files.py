"""Stage 6 managed-file metadata and product relations."""

from alembic import op

from packages.persistence.storage_models import ManagedFileORM, ProductFileRelationORM


revision = "0004_managed_files"
down_revision = "0003_qc_packing_delivery"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    ManagedFileORM.__table__.create(bind, checkfirst=True)
    ProductFileRelationORM.__table__.create(bind, checkfirst=True)


def downgrade():
    bind = op.get_bind()
    ProductFileRelationORM.__table__.drop(bind, checkfirst=True)
    ManagedFileORM.__table__.drop(bind, checkfirst=True)
