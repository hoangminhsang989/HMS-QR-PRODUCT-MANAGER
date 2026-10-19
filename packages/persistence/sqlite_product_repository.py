"""Portable engine adapter for isolated DEV and automated tests.

The repository used to open the ``.sqlite`` file directly with ``sqlite3`` and
express its schema bootstrap as one ``executescript`` of ``CREATE TABLE IF NOT
EXISTS`` / ``INSERT OR IGNORE`` / ``PRAGMA table_info`` statements. The engine
supports none of those, so the bootstrap now asks the schema whether each table
and column already exists before creating it, and the sequence row is seeded with
a read-then-insert instead of ``INSERT OR IGNORE``.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from packages.domain.product import Product, ProductStatus
from packages.domain.repository import DuplicateProductCode, ProductNotFound, ProductPage, ProductQuery, ProductRepository
from packages.sqlengine import connect
from packages.sqlengine.errors import IntegrityError


_COLUMNS = """internal_id, product_code, company, part_name, quantity, unit, material,
requester, surface_treatment, outsourced, size, notes, delivery_schedule, status,
created_at, updated_at, created_by, updated_by, outsourced_company"""

_TABLES = (
    """
    CREATE TABLE product_code_sequence (
        singleton INTEGER PRIMARY KEY, value INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE products (
        internal_id TEXT PRIMARY KEY,
        product_code TEXT NOT NULL UNIQUE,
        company TEXT NOT NULL,
        part_name TEXT NOT NULL,
        quantity TEXT NOT NULL,
        unit TEXT NOT NULL,
        material TEXT, requester TEXT, surface_treatment TEXT,
        outsourced INTEGER NOT NULL,
        size TEXT, notes TEXT, delivery_schedule TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        created_by TEXT NOT NULL, updated_by TEXT NOT NULL
    )
    """,
)

_INDEXES = ()


class SQLiteProductRepository(ProductRepository):
    """Product persistence on the in-process HMS SQL engine.

    ``database_path`` is the configured SQLite address; the engine keeps its data
    in the sibling ``<name>-engine`` directory, exactly as it does in production.
    """

    def __init__(self, database_path: str | Path) -> None:
        from packages.persistence.database import engine_path

        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._database = connect(engine_path(f"sqlite:///{self.database_path.as_posix()}"))
        self._initialize()

    def _connect(self):
        return self._database

    def _initialize(self) -> None:
        schema = self._database.schema
        for statement in _TABLES:
            table = statement.split("(", 1)[0].split()[-1].strip()
            if not schema.has_table(table):
                self._database.execute(statement)
        products = schema.table("products")
        if not products.has_column("outsourced_company"):
            self._database.execute("ALTER TABLE products ADD COLUMN outsourced_company TEXT")
        if not self._database.query("SELECT value FROM product_code_sequence WHERE singleton = 1"):
            self._database.execute("INSERT INTO product_code_sequence (singleton, value) VALUES (1, 0)")
        for statement in _INDEXES:
            self._database.execute(statement)

    def next_sequence(self) -> int:
        # The engine's UPDATE takes literals only, so the counter is read,
        # incremented and written back inside one transaction; the engine
        # serialises writes on a single lock, so the pair stays atomic.
        with self._database.transaction() as transaction:
            rows = transaction.execute("SELECT value FROM product_code_sequence WHERE singleton = 1")
            current = int(rows[0]["value"]) if rows else 0
            nxt = current + 1
            if rows:
                transaction.execute(
                    "UPDATE product_code_sequence SET value = ? WHERE singleton = 1", [nxt]
                )
            else:
                transaction.execute(
                    "INSERT INTO product_code_sequence (singleton, value) VALUES (1, ?)", [nxt]
                )
        return nxt

    def create(self, product: Product) -> Product:
        values = self._values(product)
        placeholders = ",".join("?" for _ in values)
        try:
            self._database.execute(f"INSERT INTO products ({_COLUMNS}) VALUES ({placeholders})", list(values))
        except IntegrityError as exc:
            raise DuplicateProductCode(product.product_code) from exc
        return product

    def get_by_id(self, internal_id: UUID) -> Product:
        return self._one("internal_id = ?", (str(internal_id),))

    def get_by_code(self, product_code: str) -> Product:
        return self._one("product_code = ?", (product_code,))

    def _one(self, where: str, values: tuple[object, ...]) -> Product:
        rows = self._database.query(f"SELECT {_COLUMNS} FROM products WHERE {where}", list(values))
        if not rows:
            raise ProductNotFound(str(values[0]))
        return self._product(rows[0])

    def update(self, product: Product) -> Product:
        assignments = ",".join(f"{column.strip()} = ?" for column in _COLUMNS.split(",") if column.strip() != "internal_id")
        values = self._values(product)
        try:
            cursor = self._database.execute(
                f"UPDATE products SET {assignments} WHERE internal_id = ?",
                list(values[1:]) + [values[0]],
            )
        except IntegrityError as exc:
            raise DuplicateProductCode(product.product_code) from exc
        if not cursor.get("updated"):
            raise ProductNotFound(str(product.internal_id))
        return product

    def list(self, query: ProductQuery) -> ProductPage:
        if query.page < 1 or not 1 <= query.page_size <= 200:
            raise ValueError("Pagination không hợp lệ.")
        allowed_sort = {"product_code", "company", "part_name", "quantity", "delivery_schedule", "status", "updated_at"}
        if query.sort_by not in allowed_sort:
            raise ValueError("Trường sắp xếp không hợp lệ.")
        conditions: list[str] = []
        params: list[object] = []
        if query.search:
            conditions.append("(product_code LIKE ? OR part_name LIKE ? OR company LIKE ? OR material LIKE ?)")
            term = f"%{query.search.strip()}%"
            params.extend([term] * 4)
        if query.status:
            conditions.append("status = ?")
            params.append(query.status.value)
        if query.delivery_start:
            conditions.append("delivery_schedule >= ?")
            params.append(query.delivery_start.isoformat())
        if query.delivery_end:
            conditions.append("delivery_schedule < ?")
            params.append(query.delivery_end.isoformat())
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        direction = "DESC" if query.descending else "ASC"
        offset = (query.page - 1) * query.page_size
        total = int(self._database.scalar(f"SELECT COUNT(*) FROM products{where}", params) or 0)
        rows = self._database.query(
            f"SELECT {_COLUMNS} FROM products{where} ORDER BY {query.sort_by} {direction}, internal_id ASC LIMIT ? OFFSET ?",
            params + [query.page_size, offset],
        )
        return ProductPage(tuple(self._product(row) for row in rows), total, query.page, query.page_size)

    @staticmethod
    def _values(product: Product) -> tuple[object, ...]:
        return (str(product.internal_id), product.product_code, product.company, product.part_name,
                str(product.quantity), product.unit, product.material, product.requester,
                 product.surface_treatment, int(product.outsourced), product.size, product.notes,
                 product.delivery_schedule.isoformat() if product.delivery_schedule else None,
                 product.status.value, product.created_at.isoformat(), product.updated_at.isoformat(),
                 product.created_by, product.updated_by, product.outsourced_company)

    @staticmethod
    def _product(row: dict) -> Product:
        return Product(UUID(row["internal_id"]), row["product_code"], row["company"], row["part_name"],
                       Decimal(row["quantity"]), row["unit"], row["material"], row["requester"],
                        row["surface_treatment"], bool(row["outsourced"]), row["size"], row["notes"],
                        date.fromisoformat(row["delivery_schedule"]) if row["delivery_schedule"] else None,
                        ProductStatus(row["status"]), datetime.fromisoformat(row["created_at"]),
                        datetime.fromisoformat(row["updated_at"]), row["created_by"], row["updated_by"],
                        row["outsourced_company"])
