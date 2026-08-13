"""Repository contract shared by SQLite now and PostgreSQL adapters later."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from uuid import UUID

from .product import Product, ProductStatus


class ProductNotFound(LookupError):
    pass


class DuplicateProductCode(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProductQuery:
    page: int = 1
    page_size: int = 50
    search: str | None = None
    status: ProductStatus | None = None
    sort_by: str = "updated_at"
    descending: bool = True


@dataclass(frozen=True, slots=True)
class ProductPage:
    items: tuple[Product, ...]
    total: int
    page: int
    page_size: int


class ProductRepository(ABC):
    @abstractmethod
    def next_sequence(self) -> int: ...

    @abstractmethod
    def create(self, product: Product) -> Product: ...

    @abstractmethod
    def get_by_id(self, internal_id: UUID) -> Product: ...

    @abstractmethod
    def get_by_code(self, product_code: str) -> Product: ...

    @abstractmethod
    def update(self, product: Product) -> Product: ...

    @abstractmethod
    def list(self, query: ProductQuery) -> ProductPage: ...


__all__ = ["DuplicateProductCode", "ProductNotFound", "ProductPage", "ProductQuery", "ProductRepository"]
