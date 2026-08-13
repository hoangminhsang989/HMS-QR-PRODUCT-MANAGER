"""Portable SQLite adapter for isolated DEV and automated tests."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import sqlite3
from uuid import UUID

from packages.domain.product import Product, ProductStatus
from packages.domain.repository import DuplicateProductCode, ProductNotFound, ProductPage, ProductQuery, ProductRepository


_COLUMNS = """internal_id, product_code, company, part_name, quantity, unit, material,
requester, surface_treatment, outsourced, size, notes, delivery_schedule, status,
created_at, updated_at, created_by, updated_by"""


class SQLiteProductRepository(ProductRepository):
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS product_code_sequence (
                    singleton INTEGER PRIMARY KEY CHECK(singleton = 1), value INTEGER NOT NULL
                );
                INSERT OR IGNORE INTO product_code_sequence(singleton, value) VALUES (1, 0);
                CREATE TABLE IF NOT EXISTS products (
                    internal_id TEXT PRIMARY KEY,
                    product_code TEXT NOT NULL UNIQUE,
                    company TEXT NOT NULL,
                    part_name TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    material TEXT, requester TEXT, surface_treatment TEXT,
                    outsourced INTEGER NOT NULL CHECK(outsourced IN (0,1)),
                    size TEXT, notes TEXT, delivery_schedule TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    created_by TEXT NOT NULL, updated_by TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_products_status ON products(status);
                CREATE INDEX IF NOT EXISTS ix_products_search ON products(product_code, part_name, company, material);
            """)

    def next_sequence(self) -> int:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE product_code_sequence SET value = value + 1 WHERE singleton = 1")
            return int(db.execute("SELECT value FROM product_code_sequence WHERE singleton = 1").fetchone()[0])

    def create(self, product: Product) -> Product:
        values = self._values(product)
        placeholders = ",".join("?" for _ in values)
        try:
            with self._connect() as db:
                db.execute(f"INSERT INTO products ({_COLUMNS}) VALUES ({placeholders})", values)
        except sqlite3.IntegrityError as exc:
            raise DuplicateProductCode(product.product_code) from exc
        return product

    def get_by_id(self, internal_id: UUID) -> Product:
        return self._one("internal_id = ?", (str(internal_id),))

    def get_by_code(self, product_code: str) -> Product:
        return self._one("product_code = ?", (product_code,))

    def _one(self, where: str, values: tuple[object, ...]) -> Product:
        with self._connect() as db:
            row = db.execute(f"SELECT {_COLUMNS} FROM products WHERE {where}", values).fetchone()
        if row is None:
            raise ProductNotFound(str(values[0]))
        return self._product(row)

    def update(self, product: Product) -> Product:
        assignments = ",".join(f"{column.strip()} = ?" for column in _COLUMNS.split(",") if column.strip() != "internal_id")
        values = self._values(product)
        try:
            with self._connect() as db:
                cursor = db.execute(f"UPDATE products SET {assignments} WHERE internal_id = ?", values[1:] + (values[0],))
                if cursor.rowcount != 1:
                    raise ProductNotFound(str(product.internal_id))
        except sqlite3.IntegrityError as exc:
            raise DuplicateProductCode(product.product_code) from exc
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
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        direction = "DESC" if query.descending else "ASC"
        offset = (query.page - 1) * query.page_size
        with self._connect() as db:
            total = int(db.execute(f"SELECT COUNT(*) FROM products{where}", params).fetchone()[0])
            rows = db.execute(
                f"SELECT {_COLUMNS} FROM products{where} ORDER BY {query.sort_by} {direction}, internal_id ASC LIMIT ? OFFSET ?",
                params + [query.page_size, offset],
            ).fetchall()
        return ProductPage(tuple(self._product(row) for row in rows), total, query.page, query.page_size)

    @staticmethod
    def _values(product: Product) -> tuple[object, ...]:
        return (str(product.internal_id), product.product_code, product.company, product.part_name,
                str(product.quantity), product.unit, product.material, product.requester,
                product.surface_treatment, int(product.outsourced), product.size, product.notes,
                product.delivery_schedule.isoformat() if product.delivery_schedule else None,
                product.status.value, product.created_at.isoformat(), product.updated_at.isoformat(),
                product.created_by, product.updated_by)

    @staticmethod
    def _product(row: sqlite3.Row) -> Product:
        return Product(UUID(row["internal_id"]), row["product_code"], row["company"], row["part_name"],
                       Decimal(row["quantity"]), row["unit"], row["material"], row["requester"],
                       row["surface_treatment"], bool(row["outsourced"]), row["size"], row["notes"],
                       date.fromisoformat(row["delivery_schedule"]) if row["delivery_schedule"] else None,
                       ProductStatus(row["status"]), datetime.fromisoformat(row["created_at"]),
                       datetime.fromisoformat(row["updated_at"]), row["created_by"], row["updated_by"])
