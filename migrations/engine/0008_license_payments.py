MIGRATION_ID = "0008_license_payments"

LICENSE_KEYS = """
CREATE TABLE license_keys (
    key_id TEXT PRIMARY KEY,
    license_key TEXT NOT NULL,
    product_tier TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    activated_at DATETIME,
    expires_at DATETIME,
    customer_email TEXT,
    payment_id TEXT,
    hwid TEXT,
    UNIQUE (license_key)
)
"""

PAYMENTS = """
CREATE TABLE payments (
    payment_id TEXT PRIMARY KEY,
    amount INTEGER NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    vietqr_reference TEXT,
    qr_payload TEXT,
    created_at DATETIME NOT NULL,
    confirmed_at DATETIME,
    webhook_payload TEXT,
    customer_email TEXT
)
"""


def upgrade(transaction):
    transaction.execute(LICENSE_KEYS)
    transaction.execute(PAYMENTS)
