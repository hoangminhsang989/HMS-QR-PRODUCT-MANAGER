"""Stage 4 event-based QC, packing and delivery workflows."""

from alembic import op

from packages.persistence.tracking_models import TrackingWorkflowEventORM

revision = "0003_qc_packing_delivery"
down_revision = "0002_tracking_qr_reporting"
branch_labels = None
depends_on = None


def upgrade():
    TrackingWorkflowEventORM.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    TrackingWorkflowEventORM.__table__.drop(op.get_bind(), checkfirst=True)
