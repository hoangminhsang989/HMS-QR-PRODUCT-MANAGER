"""Store the name of the outsourced company for each product (engine format)."""

OUTSOURCED_COMPANY_COLUMN = (
    "ALTER TABLE products ADD COLUMN outsourced_company TEXT"
)


def upgrade(transaction):
    """Add the outsourced-company column to products."""

    transaction.execute(OUTSOURCED_COMPANY_COLUMN)
