"""Product Master use cases; no UI, HTTP, or SQL concerns."""

from __future__ import annotations

from uuid import UUID

from packages.domain.product import Product, ProductStatus
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

    def update_product(self, identifier: UUID | str, *, actor: str, **changes: object) -> Product:
        return self.repository.update(self.get_product(identifier).update(actor=actor, **changes))

    def list_products(self, *, page: int = 1, page_size: int = 50, search: str | None = None,
                      status: ProductStatus | str | None = None, sort_by: str = "updated_at",
                      descending: bool = True) -> ProductPage:
        parsed_status = ProductStatus(status) if status else None
        return self.repository.list(ProductQuery(page, page_size, search, parsed_status, sort_by, descending))
