"""HMS SQL engine Product Master adapter."""

from __future__ import annotations

from datetime import timezone
from uuid import UUID

from packages.domain.product import Product, ProductStatus
from packages.domain.repository import (
    DuplicateProductCode,
    ProductNotFound,
    ProductPage,
    ProductQuery,
    ProductRepository,
)
from packages.sqlengine.errors import IntegrityError
from .database import resolve_database

_SORT_COLUMNS = (
    "product_code",
    "company",
    "part_name",
    "quantity",
    "delivery_schedule",
    "status",
    "updated_at",
)
_SEARCH_COLUMNS = ("product_code", "part_name", "company", "material")


class SqlAlchemyProductRepository(ProductRepository):
    """Product Master persistence on the in-process HMS SQL engine."""

    def __init__(self, database, session_factory=None) -> None:
        self.database = resolve_database(database, session_factory)

    def next_sequence(self) -> int:
        return int(self.database.scalar("SELECT COUNT(*) FROM products") or 0) + 1

    def create(self, product: Product) -> Product:
        values = self._values(product)
        try:
            with self.database.transaction() as transaction:
                transaction.execute(self._insert_sql(), list(values.values()))
        except IntegrityError as exc:
            raise DuplicateProductCode(product.product_code) from exc
        return product

    def get_by_id(self, internal_id: UUID) -> Product:
        rows = self.database.query(
            "SELECT * FROM products WHERE internal_id = ?", [str(internal_id)]
        )
        if not rows:
            raise ProductNotFound(str(internal_id))
        return self._product(rows[0])

    def get_by_code(self, product_code: str) -> Product:
        rows = self.database.query(
            "SELECT * FROM products WHERE product_code = ?", [product_code]
        )
        if not rows:
            raise ProductNotFound(product_code)
        return self._product(rows[0])

    def update(self, product: Product) -> Product:
        values = self._values(product)
        assignments = ", ".join(f"{name} = ?" for name in values)
        try:
            with self.database.transaction() as transaction:
                result = transaction.execute(
                    f"UPDATE products SET {assignments} WHERE internal_id = ?",
                    [*values.values(), str(product.internal_id)],
                )
                if not result["updated"]:
                    raise ProductNotFound(str(product.internal_id))
        except IntegrityError as exc:
            raise DuplicateProductCode(product.product_code) from exc
        return product

    def list(self, query: ProductQuery) -> ProductPage:
        if query.page < 1 or not 1 <= query.page_size <= 200:
            raise ValueError("Pagination is invalid.")
        if query.sort_by not in _SORT_COLUMNS:
            raise ValueError("Sort field is invalid.")

        clauses: list[str] = []
        parameters: list[object] = []
        if query.search:
            term = f"%{query.search.strip()}%"
            clauses.append(
                "(" + " OR ".join(f"{name} LIKE ?" for name in _SEARCH_COLUMNS) + ")"
            )
            parameters.extend([term] * len(_SEARCH_COLUMNS))
        if query.status:
            clauses.append("status = ?")
            parameters.append(query.status.value)
        if query.delivery_start:
            clauses.append("delivery_schedule >= ?")
            parameters.append(query.delivery_start)
        if query.delivery_end:
            clauses.append("delivery_schedule < ?")
            parameters.append(query.delivery_end)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        direction = "DESC" if query.descending else "ASC"

        total = int(
            self.database.scalar(
                f"SELECT COUNT(*) FROM products{where}", parameters
            )
            or 0
        )
        rows = self.database.query(
            f"SELECT * FROM products{where} ORDER BY {query.sort_by} {direction},"
            " internal_id ASC LIMIT ? OFFSET ?",
            [*parameters, query.page_size, (query.page - 1) * query.page_size],
        )
        return ProductPage(
            tuple(self._product(row) for row in rows),
            total,
            query.page,
            query.page_size,
        )

    @staticmethod
    def _insert_sql() -> str:
        columns = (
            "internal_id",
            "product_code",
            "company",
            "part_name",
            "quantity",
            "unit",
            "material",
            "requester",
            "surface_treatment",
            "outsourced",
            "outsourced_company",
            "size",
            "notes",
            "delivery_schedule",
            "status",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        )
        placeholders = ", ".join("?" for _ in columns)
        return (
            f"INSERT INTO products ({', '.join(columns)}) VALUES ({placeholders})"
        )

    @staticmethod
    def _values(product: Product) -> dict[str, object]:
        return {
            "internal_id": str(product.internal_id),
            "product_code": product.product_code,
            "company": product.company,
            "part_name": product.part_name,
            "quantity": product.quantity,
            "unit": product.unit,
            "material": product.material,
            "requester": product.requester,
            "surface_treatment": product.surface_treatment,
            "outsourced": product.outsourced,
            "outsourced_company": product.outsourced_company,
            "size": product.size,
            "notes": product.notes,
            "delivery_schedule": product.delivery_schedule,
            "status": product.status.value,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
            "created_by": product.created_by,
            "updated_by": product.updated_by,
        }

    @staticmethod
    def _product(row: dict) -> Product:
        created_at = row["created_at"]
        updated_at = row["updated_at"]
        if created_at is not None and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if updated_at is not None and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        return Product(
            UUID(row["internal_id"]),
            row["product_code"],
            row["company"],
            row["part_name"],
            row["quantity"],
            row["unit"],
            row["material"],
            row["requester"],
            row["surface_treatment"],
            row["outsourced"],
            row["size"],
            row["notes"],
            row["delivery_schedule"],
            ProductStatus(row["status"]),
            created_at,
            updated_at,
            row["created_by"],
            row["updated_by"],
            row["outsourced_company"],
        )


__all__ = ["SqlAlchemyProductRepository"]
