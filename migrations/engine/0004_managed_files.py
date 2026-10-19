"""Stage 6 managed-file metadata and product relations (engine format)."""

MANAGED_FILES = """
CREATE TABLE managed_files (
    internal_id TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    category TEXT NOT NULL,
    media_type TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at DATETIME NOT NULL,
    created_by TEXT NOT NULL,
    updated_at DATETIME NOT NULL,
    replaced_file_id TEXT,
    archived_at DATETIME,
    archived_by TEXT,
    failure_reason TEXT,
    FOREIGN KEY (replaced_file_id) REFERENCES managed_files(internal_id),
    UNIQUE (storage_key)
)
"""

PRODUCT_FILE_RELATIONS = """
CREATE TABLE product_file_relations (
    internal_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    managed_file_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    attachment_category TEXT,
    is_primary BOOLEAN NOT NULL,
    sort_order INTEGER NOT NULL,
    caption TEXT,
    created_at DATETIME NOT NULL,
    archived_at DATETIME,
    FOREIGN KEY (managed_file_id) REFERENCES managed_files(internal_id),
    FOREIGN KEY (product_id) REFERENCES products(internal_id),
    UNIQUE (managed_file_id)
)
"""


def upgrade(transaction):
    """Create only the managed-file schema owned by Stage 6."""

    transaction.execute(MANAGED_FILES)
    transaction.execute(PRODUCT_FILE_RELATIONS)
