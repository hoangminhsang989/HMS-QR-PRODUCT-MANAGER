"""Persistence adapters."""

from .sqlite_product_repository import SQLiteProductRepository
from .sqlalchemy_product_repository import SqlAlchemyProductRepository

__all__ = ["SQLiteProductRepository", "SqlAlchemyProductRepository"]
