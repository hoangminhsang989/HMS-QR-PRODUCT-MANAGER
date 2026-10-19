"""Add server accounts and website settings (engine format)."""

USER_ACCOUNTS = """
CREATE TABLE user_accounts (
    internal_id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    active BOOLEAN NOT NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE (username)
)
"""

SERVER_SETTINGS = """
CREATE TABLE server_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_at DATETIME NOT NULL
)
"""


def upgrade(transaction):
    """Create the server-account and website-settings schema."""

    transaction.execute(USER_ACCOUNTS)
    transaction.execute(SERVER_SETTINGS)
