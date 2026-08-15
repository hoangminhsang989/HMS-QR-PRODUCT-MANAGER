"""SQLAlchemy Product Master adapter for server-owned PostgreSQL persistence."""

from __future__ import annotations

from datetime import timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from packages.domain.product import Product, ProductStatus
from packages.domain.repository import (
    DuplicateProductCode,
    ProductNotFound,
    ProductPage,
    ProductQuery,
    ProductRepository,
)
from .sqlalchemy_models import ProductORM
from .database import resolve_database


class SqlAlchemyProductRepository(ProductRepository):
    def __init__(self, engine, session_factory=None) -> None:
        self.engine, self.Session = resolve_database(engine, session_factory)

    def next_sequence(self) -> int:
        with self.Session() as session:
            return int(session.scalar(select(func.count()).select_from(ProductORM)) or 0) + 1

    def create(self, product: Product) -> Product:
        try:
            with self.Session.begin() as session:
                session.add(ProductORM(**self._values(product)))
        except IntegrityError as exc:
            raise DuplicateProductCode(product.product_code) from exc
        return product

    def get_by_id(self, internal_id: UUID) -> Product:
        with self.Session() as session:
            row = session.get(ProductORM, str(internal_id))
            if row is None:
                raise ProductNotFound(str(internal_id))
            return self._product(row)

    def get_by_code(self, product_code: str) -> Product:
        with self.Session() as session:
            row = session.scalar(
                select(ProductORM).where(ProductORM.product_code == product_code)
            )
            if row is None:
                raise ProductNotFound(product_code)
            return self._product(row)

    def update(self, product: Product) -> Product:
        try:
            with self.Session.begin() as session:
                if session.get(ProductORM, str(product.internal_id)) is None:
                    raise ProductNotFound(str(product.internal_id))
                session.merge(ProductORM(**self._values(product)))
        except IntegrityError as exc:
            raise DuplicateProductCode(product.product_code) from exc
        return product

    def list(self, query: ProductQuery) -> ProductPage:
        if query.page < 1 or not 1 <= query.page_size <= 200:
            raise ValueError("Pagination is invalid.")
        columns = {
            "product_code": ProductORM.product_code,
            "company": ProductORM.company,
            "part_name": ProductORM.part_name,
            "quantity": ProductORM.quantity,
            "delivery_schedule": ProductORM.delivery_schedule,
            "status": ProductORM.status,
            "updated_at": ProductORM.updated_at,
        }
        if query.sort_by not in columns:
            raise ValueError("Sort field is invalid.")
        statement = select(ProductORM)
        if query.search:
            term = f"%{query.search.strip()}%"
            statement = statement.where(or_(
                ProductORM.product_code.ilike(term),
                ProductORM.part_name.ilike(term),
                ProductORM.company.ilike(term),
                ProductORM.material.ilike(term),
            ))
        if query.status:
            statement = statement.where(ProductORM.status == query.status.value)
        with self.Session() as session:
            total = int(session.scalar(
                select(func.count()).select_from(statement.subquery())
            ) or 0)
            ordering = columns[query.sort_by].desc() if query.descending else columns[query.sort_by].asc()
            rows = session.scalars(
                statement.order_by(ordering, ProductORM.internal_id.asc())
                .offset((query.page - 1) * query.page_size)
                .limit(query.page_size)
            ).all()
            return ProductPage(
                tuple(self._product(row) for row in rows),
                total,
                query.page,
                query.page_size,
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
    def _product(row: ProductORM) -> Product:
        created_at = row.created_at
        updated_at = row.updated_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        return Product(
            UUID(row.internal_id), row.product_code, row.company, row.part_name,
            row.quantity, row.unit, row.material, row.requester,
            row.surface_treatment, row.outsourced, row.size, row.notes,
            row.delivery_schedule, ProductStatus(row.status), created_at, updated_at,
            row.created_by, row.updated_by,
        )


__all__ = ["SqlAlchemyProductRepository"]
