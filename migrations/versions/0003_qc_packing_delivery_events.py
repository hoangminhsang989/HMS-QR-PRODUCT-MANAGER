"""Stage 4 event-based QC, packing and delivery workflows."""

from alembic import op
import sqlalchemy as sa


revision = "0003_qc_packing_delivery"
down_revision = "0002_tracking_qr_reporting"
branch_labels = None
depends_on = None


_INDEXES = {
    ("tracking_item_id",): "ix_tracking_workflow_events_tracking_item_id",
    ("event_type",): "ix_tracking_workflow_events_event_type",
}


def _tracking_workflow_events_args():
    return (
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


def _fail(detail):
    raise RuntimeError(f"R010M1A1 legacy schema mismatch in 0003: {detail}")


def _type_signature(type_, dialect_name):
    if isinstance(type_, sa.Text):
        return ("text",)
    if isinstance(type_, sa.String):
        return ("string", type_.length)
    if isinstance(type_, sa.Numeric):
        return ("numeric", type_.precision, type_.scale)
    if isinstance(type_, sa.Boolean):
        return ("boolean",)
    if isinstance(type_, sa.DateTime):
        timezone = None if dialect_name == "sqlite" else bool(type_.timezone)
        return ("datetime", timezone)
    if isinstance(type_, sa.Date):
        return ("date",)
    if isinstance(type_, sa.Integer):
        return ("integer",)
    return (type(type_).__name__.lower(), str(type_).lower())


def _foreign_key_set(expected_table):
    result = set()
    for constraint in expected_table.foreign_key_constraints:
        elements = list(constraint.elements)
        result.add(
            (
                tuple(element.parent.name for element in elements),
                elements[0].target_fullname.rsplit(".", 1)[0],
                tuple(element.target_fullname.rsplit(".", 1)[1] for element in elements),
            )
        )
    return result


def _validate_existing_table():
    table_name = "tracking_workflow_events"
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    expected = sa.Table(table_name, sa.MetaData(), *_tracking_workflow_events_args())
    actual_columns = {column["name"]: column for column in inspector.get_columns(table_name)}
    expected_columns = {column.name: column for column in expected.columns}
    if set(actual_columns) != set(expected_columns):
        _fail(f"{table_name} column set")
    dialect_name = bind.dialect.name
    for name, expected_column in expected_columns.items():
        actual = actual_columns[name]
        if _type_signature(actual["type"], dialect_name) != _type_signature(
            expected_column.type, dialect_name
        ):
            _fail(f"{table_name}.{name} type")
        if bool(actual["nullable"]) != bool(expected_column.nullable):
            _fail(f"{table_name}.{name} nullability")
        if actual.get("default") is not None or expected_column.server_default is not None:
            _fail(f"{table_name}.{name} server default")
    actual_pk = tuple(inspector.get_pk_constraint(table_name).get("constrained_columns") or ())
    expected_pk = tuple(column.name for column in expected.primary_key.columns)
    if actual_pk != expected_pk:
        _fail(f"{table_name} primary key")
    actual_fks = {
        (
            tuple(fk["constrained_columns"]),
            fk["referred_table"],
            tuple(fk["referred_columns"]),
        )
        for fk in inspector.get_foreign_keys(table_name)
    }
    if actual_fks != _foreign_key_set(expected):
        _fail(f"{table_name} foreign keys")
    actual_uniques = {
        tuple(unique["column_names"])
        for unique in inspector.get_unique_constraints(table_name)
        if unique.get("column_names")
    }
    expected_uniques = {
        tuple(column.name for column in constraint.columns)
        for constraint in expected.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }
    if actual_uniques != expected_uniques:
        _fail(f"{table_name} unique constraints")
    actual_indexes = {
        tuple(index["column_names"])
        for index in inspector.get_indexes(table_name)
        if not index["unique"]
    }
    if actual_indexes != set(_INDEXES):
        _fail(f"{table_name} indexes")


def upgrade():
    """Create or validate only the workflow-event schema owned by Stage 4."""

    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("tracking_workflow_events"):
        _validate_existing_table()
        return

    op.create_table("tracking_workflow_events", *_tracking_workflow_events_args())
    for columns, name in _INDEXES.items():
        op.create_index(name, "tracking_workflow_events", list(columns))


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
