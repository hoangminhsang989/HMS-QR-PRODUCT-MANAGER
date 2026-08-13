"""Tracking, QR, operator preference and process reporting."""
from alembic import op
import sqlalchemy as sa
from packages.persistence.tracking_models import TrackingItemORM,OperatorORM,MachiningTypeORM,UserPreferenceORM,AttemptDisplayORM,ProcessReportORM,TrackingAuditORM
revision="0002_tracking_qr_reporting";down_revision="0001_stage2_baseline";branch_labels=None;depends_on=None
def upgrade():
    bind=op.get_bind()
    columns={x["name"] for x in sa.inspect(bind).get_columns("purchase_orders")}
    if "internal_order_code" not in columns:
        op.add_column("purchase_orders",sa.Column("internal_order_code",sa.String(64),nullable=True))
        op.create_unique_constraint("uq_purchase_orders_internal_order_code","purchase_orders",["internal_order_code"])
    for table in (TrackingItemORM.__table__,OperatorORM.__table__,MachiningTypeORM.__table__,UserPreferenceORM.__table__,AttemptDisplayORM.__table__,ProcessReportORM.__table__,TrackingAuditORM.__table__):table.create(bind,checkfirst=True)
def downgrade():
    bind=op.get_bind()
    for table in reversed((TrackingItemORM.__table__,OperatorORM.__table__,MachiningTypeORM.__table__,UserPreferenceORM.__table__,AttemptDisplayORM.__table__,ProcessReportORM.__table__,TrackingAuditORM.__table__)):table.drop(bind,checkfirst=True)
