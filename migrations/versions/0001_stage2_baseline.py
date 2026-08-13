"""Stage 2 normalized baseline."""
from alembic import op
from packages.persistence.sqlalchemy_models import Base

revision="0001_stage2_baseline"; down_revision=None; branch_labels=None; depends_on=None

def upgrade():
    bind=op.get_bind(); Base.metadata.create_all(bind)

def downgrade():
    Base.metadata.drop_all(op.get_bind())
