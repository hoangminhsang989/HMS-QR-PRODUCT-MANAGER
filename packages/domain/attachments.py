"""Managed-file metadata and product-file relation contracts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ManagedFileStatus(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class ManagedFileSource(StrEnum):
    UPLOAD = "UPLOAD"
    IMPORT = "IMPORT"
    GENERATED = "GENERATED"


class ProductFileKind(StrEnum):
    IMAGE = "IMAGE"
    ATTACHMENT = "ATTACHMENT"


@dataclass(frozen=True, slots=True)
class StorageReference:
    backend: str
    storage_key: str


@dataclass(frozen=True, slots=True)
class ManagedFile:
    file_id: UUID
    original_filename: str
    stored_filename: str
    storage_key: str
    category: str
    media_type: str
    extension: str
    size_bytes: int
    sha256: str
    status: ManagedFileStatus
    source: ManagedFileSource
    version: int
    created_at: datetime
    created_by: str
    updated_at: datetime
    replaced_file_id: UUID | None = None
    archived_at: datetime | None = None
    archived_by: str | None = None
    failure_reason: str | None = None

    def with_status(self, status: ManagedFileStatus, *, at: datetime, **changes: object) -> "ManagedFile":
        return replace(self, status=status, updated_at=at, **changes)


@dataclass(frozen=True, slots=True)
class ProductFileRelation:
    relation_id: UUID
    product_id: UUID
    managed_file_id: UUID
    kind: ProductFileKind
    attachment_category: str | None
    is_primary: bool
    sort_order: int
    caption: str | None
    created_at: datetime
    archived_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ProductAttachment:
    relation: ProductFileRelation
    managed_file: ManagedFile


@dataclass(frozen=True, slots=True)
class ProductImage(ProductAttachment):
    pass
