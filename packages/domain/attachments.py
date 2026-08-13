"""Extension-point metadata; binary content belongs behind StorageService."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StorageReference:
    backend: str
    object_key: str


@dataclass(frozen=True, slots=True)
class ProductAttachment:
    attachment_id: UUID
    product_id: UUID
    file_name: str
    media_type: str
    storage: StorageReference


@dataclass(frozen=True, slots=True)
class ProductImage(ProductAttachment):
    alt_text: str | None = None
