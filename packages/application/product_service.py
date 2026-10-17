"""Product Master use cases; no UI, HTTP, or SQL concerns."""

from __future__ import annotations

from uuid import UUID
from datetime import date, datetime, timezone

from packages.domain.product import Product, ProductStatus
from packages.domain.repository import ProductConflict
from packages.domain.product_code import ProductCodeService
from packages.domain.repository import ProductPage, ProductQuery, ProductRepository


class ProductService:
    def __init__(self, repository: ProductRepository, code_service: ProductCodeService | None = None) -> None:
        self.repository = repository
        self.code_service = code_service or ProductCodeService()

    def create_product(self, *, actor: str, product_code: str | None = None, **data: object) -> Product:
        code = self.code_service.normalize(product_code) if product_code else self.code_service.generate(self.repository.next_sequence())
        product = Product.create(product_code=code, actor=actor, **data)
        return self.repository.create(product)

    def get_product(self, identifier: UUID | str) -> Product:
        if isinstance(identifier, UUID):
            return self.repository.get_by_id(identifier)
        text = str(identifier).strip()
        try:
            return self.repository.get_by_id(UUID(text))
        except ValueError:
            return self.repository.get_by_code(self.code_service.normalize(text))

    def update_product(self, identifier: UUID | str, *, actor: str, expected_updated_at: datetime | str | None = None, **changes: object) -> Product:
        if "product_code" in changes:
            changes["product_code"] = self.code_service.normalize(str(changes["product_code"]))
        current = self.get_product(identifier)
        if expected_updated_at is not None:
            expected = datetime.fromisoformat(str(expected_updated_at).replace("Z", "+00:00"))
            if expected.tzinfo is None:
                expected = expected.replace(tzinfo=timezone.utc)
            if current.updated_at.astimezone(timezone.utc) != expected.astimezone(timezone.utc):
                raise ProductConflict("Sản phẩm đã được người dùng khác cập nhật. Hãy làm mới trước khi lưu lại.")
        return self.repository.update(current.update(actor=actor, **changes))

    def list_products(self, *, page: int = 1, page_size: int = 50, search: str | None = None,
                      status: ProductStatus | str | None = None, sort_by: str = "updated_at",
                      descending: bool = True, delivery_start: date | None = None,
                      delivery_end: date | None = None) -> ProductPage:
        parsed_status = ProductStatus(status) if status else None
        return self.repository.list(ProductQuery(
            page, page_size, search, parsed_status, sort_by, descending, delivery_start, delivery_end,
        ))
