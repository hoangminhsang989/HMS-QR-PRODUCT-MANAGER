"""Tracking, QR, operator preference and process reporting."""

from alembic import op
import sqlalchemy as sa


revision = "0002_tracking_qr_reporting"
down_revision = "0001_stage2_baseline"
branch_labels = None
depends_on = None


_INTERNAL_ORDER_CODE_UNIQUE = "uq_purchase_orders_internal_order_code"


def _operators_args():
    return (
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def _machining_types_args():
    return (
        sa.Column("internal_id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("code"),
    )


def _order_tracking_items_args():
    return (
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


def _user_preferences_args():
    return (
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column("machining_type_id", sa.String(36), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["operators.internal_id"]),
        sa.ForeignKeyConstraint(["machining_type_id"], ["machining_types.internal_id"]),
    )


def _attempt_display_state_args():
    return (
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


def _process_report_events_args():
    return (
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
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["process_report_events.internal_id"]
        ),
        sa.UniqueConstraint("request_id"),
    )


def _tracking_audit_events_args():
    return (
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


_TABLE_SPECS = (
    ("operators", _operators_args),
    ("machining_types", _machining_types_args),
    ("order_tracking_items", _order_tracking_items_args),
    ("user_preferences", _user_preferences_args),
    ("attempt_display_state", _attempt_display_state_args),
    ("process_report_events", _process_report_events_args),
    ("tracking_audit_events", _tracking_audit_events_args),
)


def _fail(detail):
    raise RuntimeError(f"R010M1A1 legacy schema mismatch in 0002: {detail}")


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


def _validate_existing_table(table_name, args_factory, expected_indexes=()):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    expected = sa.Table(table_name, sa.MetaData(), *args_factory())
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
    if actual_indexes != set(expected_indexes):
        _fail(f"{table_name} indexes")


def _validate_internal_order_code(actual):
    bind = op.get_bind()
    expected = sa.Column("internal_order_code", sa.String(64), nullable=True)
    if _type_signature(actual["type"], bind.dialect.name) != _type_signature(
        expected.type, bind.dialect.name
    ):
        _fail("purchase_orders.internal_order_code type")
    if bool(actual["nullable"]) is not True:
        _fail("purchase_orders.internal_order_code nullability")
    if actual.get("default") is not None:
        _fail("purchase_orders.internal_order_code server default")


def _internal_order_code_unique_present(inspector):
    target = ("internal_order_code",)
    unique_sets = {
        tuple(unique["column_names"])
        for unique in inspector.get_unique_constraints("purchase_orders")
        if unique.get("column_names")
    }
    unique_sets.update(
        tuple(index["column_names"])
        for index in inspector.get_indexes("purchase_orders")
        if index["unique"] and index.get("column_names")
    )
    conflicting = {columns for columns in unique_sets if "internal_order_code" in columns}
    if conflicting and conflicting != {target}:
        _fail("purchase_orders.internal_order_code unique semantics")
    return target in unique_sets


def _validate_no_internal_order_code_duplicates():
    column = sa.column("internal_order_code")
    table = sa.table("purchase_orders", column)
    duplicate = op.get_bind().execute(
        sa.select(column)
        .select_from(table)
        .where(column.is_not(None))
        .group_by(column)
        .having(sa.func.count() > 1)
        .limit(1)
    ).first()
    if duplicate is not None:
        _fail("purchase_orders.internal_order_code duplicate values")


def upgrade():
    """Create or validate only the tracking/reporting schema owned by Stage 3."""

    inspector = sa.inspect(op.get_bind())
    purchase_order_columns = {
        column["name"]: column for column in inspector.get_columns("purchase_orders")
    }
    column_exists = "internal_order_code" in purchase_order_columns
    if column_exists:
        _validate_internal_order_code(purchase_order_columns["internal_order_code"])
    unique_exists = _internal_order_code_unique_present(inspector) if column_exists else False
    if column_exists and not unique_exists:
        _validate_no_internal_order_code_duplicates()

    existing_tables = set(inspector.get_table_names())
    for table_name, args_factory in _TABLE_SPECS:
        if table_name in existing_tables:
            _validate_existing_table(table_name, args_factory)

    if not column_exists or not unique_exists:
        with op.batch_alter_table("purchase_orders") as batch:
            if not column_exists:
                batch.add_column(
                    sa.Column("internal_order_code", sa.String(64), nullable=True)
                )
            if not unique_exists:
                batch.create_unique_constraint(
                    _INTERNAL_ORDER_CODE_UNIQUE, ["internal_order_code"]
                )

    for table_name, args_factory in _TABLE_SPECS:
        if table_name not in existing_tables:
            op.create_table(table_name, *args_factory())


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
        batch.drop_constraint(_INTERNAL_ORDER_CODE_UNIQUE, type_="unique")
        batch.drop_column("internal_order_code")
