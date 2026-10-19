"""Tracking, QR, operator preference and process reporting (engine format)."""

OPERATORS = """
CREATE TABLE operators (
    internal_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    active BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
)
"""

MACHINING_TYPES = """
CREATE TABLE machining_types (
    internal_id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    display_name TEXT NOT NULL,
    active BOOLEAN NOT NULL,
    display_order INTEGER NOT NULL,
    UNIQUE (code)
)
"""

ORDER_TRACKING_ITEMS = """
CREATE TABLE order_tracking_items (
    internal_id TEXT PRIMARY KEY,
    tracking_code TEXT NOT NULL,
    purchase_order_id TEXT NOT NULL,
    purchase_order_line_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    quantity NUMERIC(18,4) NOT NULL,
    unit TEXT NOT NULL,
    delivery_date DATE NOT NULL,
    status TEXT NOT NULL,
    qr_public_id TEXT,
    qr_status TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders(internal_id),
    FOREIGN KEY (purchase_order_line_id) REFERENCES purchase_order_lines(internal_id),
    FOREIGN KEY (product_id) REFERENCES products(internal_id),
    FOREIGN KEY (customer_id) REFERENCES customers(internal_id),
    UNIQUE (tracking_code),
    UNIQUE (qr_public_id)
)
"""

USER_PREFERENCES = """
CREATE TABLE user_preferences (
    user_id TEXT PRIMARY KEY,
    machining_type_id TEXT NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES operators(internal_id),
    FOREIGN KEY (machining_type_id) REFERENCES machining_types(internal_id)
)
"""

ATTEMPT_DISPLAY_STATE = """
CREATE TABLE attempt_display_state (
    tracking_item_id TEXT,
    machining_type_id TEXT,
    max_visible_attempt INTEGER NOT NULL,
    updated_at DATETIME NOT NULL,
    updated_by TEXT,
    PRIMARY KEY (tracking_item_id, machining_type_id),
    FOREIGN KEY (tracking_item_id) REFERENCES order_tracking_items(internal_id),
    FOREIGN KEY (machining_type_id) REFERENCES machining_types(internal_id)
)
"""

PROCESS_REPORT_EVENTS = """
CREATE TABLE process_report_events (
    internal_id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    tracking_item_id TEXT NOT NULL,
    machining_type_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    attempt_number INTEGER,
    quantity NUMERIC(18,4) NOT NULL,
    notes TEXT,
    actor_user_id TEXT NOT NULL,
    actor_display_name_snapshot TEXT NOT NULL,
    server_timestamp DATETIME NOT NULL,
    client_timestamp DATETIME,
    device_id TEXT,
    revision INTEGER NOT NULL,
    supersedes_id TEXT,
    status TEXT NOT NULL,
    FOREIGN KEY (tracking_item_id) REFERENCES order_tracking_items(internal_id),
    FOREIGN KEY (machining_type_id) REFERENCES machining_types(internal_id),
    FOREIGN KEY (actor_user_id) REFERENCES operators(internal_id),
    FOREIGN KEY (supersedes_id) REFERENCES process_report_events(internal_id),
    UNIQUE (request_id)
)
"""

TRACKING_AUDIT_EVENTS = """
CREATE TABLE tracking_audit_events (
    internal_id TEXT PRIMARY KEY,
    tracking_item_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    actor TEXT NOT NULL,
    reason TEXT,
    server_timestamp DATETIME NOT NULL,
    FOREIGN KEY (tracking_item_id) REFERENCES order_tracking_items(internal_id)
)
"""

INTERNAL_ORDER_CODE_COLUMN = (
    "ALTER TABLE purchase_orders ADD COLUMN internal_order_code TEXT"
)
INTERNAL_ORDER_CODE_UNIQUE = (
    "ALTER TABLE purchase_orders ADD CONSTRAINT "
    "uq_purchase_orders_internal_order_code UNIQUE (internal_order_code)"
)

_TABLES = (
    OPERATORS,
    MACHINING_TYPES,
    ORDER_TRACKING_ITEMS,
    USER_PREFERENCES,
    ATTEMPT_DISPLAY_STATE,
    PROCESS_REPORT_EVENTS,
    TRACKING_AUDIT_EVENTS,
)


def upgrade(transaction):
    """Create only the tracking/reporting schema owned by Stage 3."""

    for statement in _TABLES:
        transaction.execute(statement)
    transaction.execute(INTERNAL_ORDER_CODE_COLUMN)
    transaction.execute(INTERNAL_ORDER_CODE_UNIQUE)
