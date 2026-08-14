"""Application service coordinating metadata and durable managed-file bytes."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from uuid import UUID, uuid4
from typing import Protocol

from packages.domain.attachments import (
    ManagedFile,
    ManagedFileSource,
    ManagedFileStatus,
    ProductAttachment,
    ProductFileKind,
    ProductFileRelation,
    ProductImage,
)
from packages.persistence.managed_file_repository import ManagedFileRepository
from .keys import generate_storage_key
from .service import IntegrityResult, StorageService
from .validation import UploadKind, UploadLimits, validate_upload


_ATTACHMENT_CATEGORY = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class ArchiveCoordinator(Protocol):
    @property
    def active_configuration_id(self) -> UUID: ...

    @property
    def ingest_storage(self) -> StorageService: ...

    def preflight_upload(self, size_bytes: int): ...

    def read_available(self, managed: ManagedFile) -> bytes: ...


class ManagedFileService:
    def __init__(
        self,
        repository: ManagedFileRepository,
        storage: StorageService,
        *,
        limits: UploadLimits = UploadLimits(),
        archive_coordinator: ArchiveCoordinator | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.limits = limits
        self.archive_coordinator = archive_coordinator

    def upload_product_image(
        self,
        *,
        product_id: UUID,
        original_filename: str,
        declared_mime: str,
        content: bytes,
        actor: str,
        caption: str | None = None,
        sort_order: int = 0,
        make_primary: bool = False,
        replaces_file_id: UUID | None = None,
    ) -> ProductImage:
        file, relation = self._publish(
            product_id=product_id,
            original_filename=original_filename,
            declared_mime=declared_mime,
            content=content,
            actor=actor,
            kind=ProductFileKind.IMAGE,
            attachment_category=None,
            caption=caption,
            sort_order=sort_order,
            make_primary=make_primary,
            replaces_file_id=replaces_file_id,
        )
        return ProductImage(relation, file)

    def upload_attachment(
        self,
        *,
        product_id: UUID,
        original_filename: str,
        declared_mime: str,
        content: bytes,
        actor: str,
        attachment_category: str,
        caption: str | None = None,
        sort_order: int = 0,
        replaces_file_id: UUID | None = None,
    ) -> ProductAttachment:
        category = attachment_category.strip().upper()
        if not _ATTACHMENT_CATEGORY.fullmatch(category):
            raise ValueError("Attachment category must be an extensible safe code.")
        file, relation = self._publish(
            product_id=product_id,
            original_filename=original_filename,
            declared_mime=declared_mime,
            content=content,
            actor=actor,
            kind=ProductFileKind.ATTACHMENT,
            attachment_category=category,
            caption=caption,
            sort_order=sort_order,
            make_primary=False,
            replaces_file_id=replaces_file_id,
        )
        return ProductAttachment(relation, file)

    def set_primary_image(self, *, product_id: UUID, file_id: UUID) -> None:
        self.repository.set_primary_image(product_id=product_id, file_id=file_id)

    def update_relation(
        self,
        *,
        product_id: UUID,
        file_id: UUID,
        sort_order: int | None = None,
        caption: str | None = None,
    ) -> ProductFileRelation:
        return self.repository.update_relation(
            product_id=product_id,
            file_id=file_id,
            sort_order=sort_order,
            caption=caption,
        )

    def archive(self, *, file_id: UUID, actor: str) -> ManagedFile:
        return self.repository.archive(file_id, actor=actor, at=_now())

    def verify(self, file_id: UUID) -> IntegrityResult:
        managed = self.repository.get(file_id)
        return self.storage.verify(
            managed.storage_key,
            expected_sha256=managed.sha256,
            expected_size=managed.size_bytes,
        )

    def read(self, file_id: UUID) -> bytes:
        managed = self.repository.get(file_id)
        if self.archive_coordinator is not None:
            return self.archive_coordinator.read_available(managed)
        result = self.verify(file_id)
        if not result.valid:
            raise FileNotFoundError("Managed file has no valid available copy.")
        return self.storage.read(managed.storage_key)

    def _publish(
        self,
        *,
        product_id: UUID,
        original_filename: str,
        declared_mime: str,
        content: bytes,
        actor: str,
        kind: ProductFileKind,
        attachment_category: str | None,
        caption: str | None,
        sort_order: int,
        make_primary: bool,
        replaces_file_id: UUID | None,
    ) -> tuple[ManagedFile, ProductFileRelation]:
        if not actor.strip():
            raise ValueError("actor is required")
        if sort_order < 0:
            raise ValueError("sort_order cannot be negative")
        validated = validate_upload(
            filename=original_filename,
            declared_mime=declared_mime,
            content=content,
            expected_kind=UploadKind.IMAGE if kind is ProductFileKind.IMAGE else None,
            limits=self.limits,
        )
        if kind is ProductFileKind.ATTACHMENT and validated.kind is UploadKind.IMAGE:
            raise ValueError("Product images must use the image operation.")
        if self.archive_coordinator is not None:
            self.archive_coordinator.preflight_upload(validated.size_bytes)

        old = self.repository.get(replaces_file_id) if replaces_file_id else None
        if old:
            old_relation = self.repository.get_relation(old.file_id)
            if old_relation.product_id != product_id:
                raise ValueError("Replacement must belong to the same product.")
            if old_relation.kind is not kind:
                raise ValueError("Replacement must preserve the relation kind.")
            if old.status is not ManagedFileStatus.READY:
                raise ValueError("Only a READY managed file can be replaced.")
        version = old.version + 1 if old else 1
        file_id = uuid4()
        storage_key, stored_filename = generate_storage_key(
            product_id=product_id,
            file_id=file_id,
            version=version,
            category="images" if kind is ProductFileKind.IMAGE else "attachments",
            extension=validated.extension,
        )
        timestamp = _now()
        digest = hashlib.sha256(content).hexdigest()
        managed = ManagedFile(
            file_id=file_id,
            original_filename=validated.original_filename,
            stored_filename=stored_filename,
            storage_key=storage_key,
            category="PRODUCT_IMAGE" if kind is ProductFileKind.IMAGE else attachment_category or "OTHER",
            media_type=validated.media_type,
            extension=validated.extension,
            size_bytes=validated.size_bytes,
            sha256=digest,
            status=ManagedFileStatus.PENDING,
            source=ManagedFileSource.UPLOAD,
            version=version,
            created_at=timestamp,
            created_by=actor.strip(),
            updated_at=timestamp,
            replaced_file_id=old.file_id if old else None,
        )
        relation = ProductFileRelation(
            relation_id=uuid4(),
            product_id=product_id,
            managed_file_id=file_id,
            kind=kind,
            attachment_category=attachment_category,
            is_primary=False,
            sort_order=sort_order,
            caption=caption.strip() if caption and caption.strip() else None,
            created_at=timestamp,
        )
        self.repository.create_pending(managed, relation)
        try:
            storage = (
                self.archive_coordinator.ingest_storage
                if self.archive_coordinator is not None else self.storage
            )
            storage.put(
                storage_key,
                content,
                expected_sha256=digest,
                expected_size=validated.size_bytes,
            )
            verification = storage.verify(
                storage_key,
                expected_sha256=digest,
                expected_size=validated.size_bytes,
            )
            if not verification.valid:
                raise RuntimeError(f"publication verification failed: {verification.reason}")
            managed = self.repository.finalize_ready(
                file_id,
                at=_now(),
                replaces_file_id=old.file_id if old else None,
                actor=actor.strip(),
                make_primary=make_primary,
                transfer_configuration_id=(
                    self.archive_coordinator.active_configuration_id
                    if self.archive_coordinator is not None else None
                ),
            )
        except Exception as exc:
            try:
                self.repository.mark_failed(file_id, reason=type(exc).__name__, at=_now())
            except Exception:
                pass
            raise
        return managed, self.repository.get_relation(file_id)


def _now() -> datetime:
    return datetime.now(timezone.utc)
