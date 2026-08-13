"""Server-owned storage abstraction; clients never receive NAS paths."""

from .service import LocalDevStorage, StorageService

__all__ = ["LocalDevStorage", "StorageService"]
