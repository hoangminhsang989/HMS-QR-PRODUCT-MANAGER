"""Stage 2 normalized baseline (engine format)."""

PRODUCTS = """
CREATE TABLE products (
    internal_id TEXT PRIMARY KEY,
    product_code TEXT NOT NULL,
    company TEXT NOT NULL,
    part_name TEXT NOT NULL,
    quantity NUMERIC(18,4) NOT NULL,
    unit TEXT NOT NULL,
    material TEXT,
    requester TEXT,
    surface_treatment TEXT,
    outsourced BOOLEAN NOT NULL,
    size TEXT,
    notes TEXT,
    delivery_schedule DATE,
    status TEXT NOT NULL,
    created_at DATETIME,
    updated_at DATETIME,
    created_by TEXT,
    updated_by TEXT,
    UNIQUE (product_code)
)
"""

CUSTOMERS = """
CREATE TABLE customers (
    internal_id TEXT PRIMARY KEY,
    customer_code TEXT NOT NULL,
    name TEXT NOT NULL,
    short_name TEXT,
    address TEXT,
    tax_code TEXT,
    contact_name TEXT,
    phone TEXT,
    email TEXT,
    notes TEXT,
    active BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    UNIQUE (customer_code)
)
"""

PURCHASE_ORDERS = """
CREATE TABLE purchase_orders (
    internal_id TEXT PRIMARY KEY,
    po_number TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    po_date DATE NOT NULL,
    requested_delivery_date DATE,
    status TEXT NOT NULL,
    notes TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(internal_id),
    UNIQUE (po_number)
)
"""

PURCHASE_ORDER_LINES = """
CREATE TABLE purchase_order_lines (
    internal_id TEXT PRIMARY KEY,
    po_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    ordered_quantity NUMERIC(18,4) NOT NULL,
    unit TEXT NOT NULL,
    unit_price NUMERIC(18,4),
    currency TEXT,
    customer_part_reference TEXT,
    notes TEXT,
    FOREIGN KEY (po_id) REFERENCES purchase_orders(internal_id),
    FOREIGN KEY (product_id) REFERENCES products(internal_id),
    UNIQUE (po_id, line_number)
)
"""

DELIVERY_SCHEDULE_ENTRIES = """
CREATE TABLE delivery_schedule_entries (
    internal_id TEXT PRIMARY KEY,
    po_line_id TEXT NOT NULL,
    planned_date DATE NOT NULL,
    planned_quantity NUMERIC(18,4) NOT NULL,
    status TEXT NOT NULL,
    notes TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY (po_line_id) REFERENCES purchase_order_lines(internal_id)
)
"""

PRODUCTION_RUNS = """
CREATE TABLE production_runs (
    internal_id TEXT PRIMARY KEY,
    run_code TEXT NOT NULL,
    po_line_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    planned_quantity NUMERIC(18,4) NOT NULL,
    completed_quantity NUMERIC(18,4) NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL,
    planned_start DATE,
    planned_finish DATE,
    actual_start DATE,
    actual_finish DATE,
    notes TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    FOREIGN KEY (po_line_id) REFERENCES purchase_order_lines(internal_id),
    FOREIGN KEY (product_id) REFERENCES products(internal_id),
    UNIQUE (run_code)
)
"""


def upgrade(transaction):
    """Create only the schema owned by the Stage 2 baseline."""

    for statement in (
        PRODUCTS,
        CUSTOMERS,
        PURCHASE_ORDERS,
        PURCHASE_ORDER_LINES,
        DELIVERY_SCHEDULE_ENTRIES,
        PRODUCTION_RUNS,
    ):
        transaction.execute(statement)
