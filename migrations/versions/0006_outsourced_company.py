"""Store the name of the outsourced company for each product."""

from alembic import op
import sqlalchemy as sa


revision = "0006_outsourced_company"
down_revision = "0005_store_forward"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("outsourced_company", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("products", "outsourced_company")
