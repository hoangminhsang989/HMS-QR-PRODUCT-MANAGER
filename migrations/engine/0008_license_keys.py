MIGRATION_ID = "0008_license_keys"

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


def upgrade(transaction):
    transaction.execute(LICENSE_KEYS)
