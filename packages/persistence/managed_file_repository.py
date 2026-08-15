"""Transactional metadata repository for managed files."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from packages.domain.attachments import (
    ManagedFile,
    ManagedFileSource,
    ManagedFileStatus,
    ProductAttachment,
    ProductFileKind,
    ProductFileRelation,
    ProductImage,
)
from .sqlalchemy_models import ProductORM
from .storage_models import ManagedFileORM, ProductFileRelationORM
from .store_forward_models import ArchiveTransferJobORM, StorageConfigurationORM
from packages.domain.store_forward import ArchiveTransferState
from .database import resolve_database, transaction_lock


class ManagedFileRepository:
    def __init__(self, engine, session_factory=None) -> None:
        self.engine, self.Session = resolve_database(engine, session_factory)

    def create_pending(self, managed_file: ManagedFile, relation: ProductFileRelation) -> None:
        if managed_file.status is not ManagedFileStatus.PENDING:
            raise ValueError("New managed file metadata must be PENDING.")
        with self.Session.begin() as session:
            if session.get(ProductORM, str(relation.product_id)) is None:
                raise LookupError("product not found")
            session.add(ManagedFileORM(
                internal_id=str(managed_file.file_id),
                original_filename=managed_file.original_filename,
                stored_filename=managed_file.stored_filename,
                storage_key=managed_file.storage_key,
                category=managed_file.category,
                media_type=managed_file.media_type,
                extension=managed_file.extension,
                size_bytes=managed_file.size_bytes,
                sha256=managed_file.sha256,
                status=managed_file.status.value,
                source=managed_file.source.value,
                version=managed_file.version,
                created_at=managed_file.created_at,
                created_by=managed_file.created_by,
                updated_at=managed_file.updated_at,
                replaced_file_id=str(managed_file.replaced_file_id) if managed_file.replaced_file_id else None,
                archived_at=managed_file.archived_at,
                archived_by=managed_file.archived_by,
                failure_reason=managed_file.failure_reason,
            ))
            session.add(ProductFileRelationORM(
                internal_id=str(relation.relation_id),
                product_id=str(relation.product_id),
                managed_file_id=str(relation.managed_file_id),
                kind=relation.kind.value,
                attachment_category=relation.attachment_category,
                is_primary=relation.is_primary,
                sort_order=relation.sort_order,
                caption=relation.caption,
                created_at=relation.created_at,
                archived_at=relation.archived_at,
            ))

    def mark_ready(self, file_id: UUID, *, at: datetime) -> ManagedFile:
        return self.finalize_ready(file_id, at=at)

    def finalize_ready(
        self,
        file_id: UUID,
        *,
        at: datetime,
        replaces_file_id: UUID | None = None,
        actor: str | None = None,
        make_primary: bool = False,
        transfer_configuration_id: UUID | None = None,
    ) -> ManagedFile:
        with self.Session.begin() as session:
            row = self._required_file(session, file_id)
            if row.status != ManagedFileStatus.PENDING.value:
                raise ValueError("Only PENDING metadata can become READY.")
            row.status = ManagedFileStatus.READY.value
            row.updated_at = at
            relation = session.scalar(select(ProductFileRelationORM).where(
                ProductFileRelationORM.managed_file_id == str(file_id)
            ))
            if relation is None:
                raise LookupError("managed-file relation not found")
            if replaces_file_id is not None:
                previous = self._required_file(session, replaces_file_id)
                previous_relation = session.scalar(select(ProductFileRelationORM).where(
                    ProductFileRelationORM.managed_file_id == str(replaces_file_id)
                ))
                if previous_relation is None:
                    raise LookupError("replacement relation not found")
                previous.status = ManagedFileStatus.ARCHIVED.value
                previous.archived_at = at
                previous.archived_by = actor
                previous.updated_at = at
                previous_relation.archived_at = at
                previous_relation.is_primary = False
            if make_primary:
                if relation.kind != ProductFileKind.IMAGE.value:
                    raise ValueError("Only a product image can be primary.")
                transaction_lock(session, "product-primary-image", relation.product_id)
                active_images = session.scalars(select(ProductFileRelationORM).where(
                    ProductFileRelationORM.product_id == relation.product_id,
                    ProductFileRelationORM.kind == ProductFileKind.IMAGE.value,
                    ProductFileRelationORM.archived_at.is_(None),
                )).all()
                for image in active_images:
                    image.is_primary = image.internal_id == relation.internal_id
            if transfer_configuration_id is not None:
                if session.get(StorageConfigurationORM, str(transfer_configuration_id)) is None:
                    raise LookupError("storage configuration not found")
                existing_job = session.scalar(select(ArchiveTransferJobORM).where(
                    ArchiveTransferJobORM.managed_file_id == str(file_id)
                ))
                if existing_job is None:
                    session.add(ArchiveTransferJobORM(
                        internal_id=str(__import__("uuid").uuid4()),
                        managed_file_id=str(file_id),
                        configuration_id=str(transfer_configuration_id),
                        state=ArchiveTransferState.TRANSFER_QUEUED.value,
                        attempt_count=0,
                        next_retry_at=at,
                        last_attempt_at=None,
                        last_error_code=None,
                        last_error_summary=None,
                        remote_verified_at=None,
                        grace_expires_at=None,
                        local_purged_at=None,
                        lease_token=None,
                        lease_expires_at=None,
                        created_at=at,
                        updated_at=at,
                    ))
        return self.get(file_id)

    def mark_failed(self, file_id: UUID, *, reason: str, at: datetime) -> ManagedFile:
        with self.Session.begin() as session:
            row = self._required_file(session, file_id)
            if row.status == ManagedFileStatus.READY.value:
                raise ValueError("READY metadata cannot be relabelled FAILED.")
            row.status = ManagedFileStatus.FAILED.value
            row.failure_reason = reason[:2000]
            row.updated_at = at
        return self.get(file_id)

    def archive(self, file_id: UUID, *, actor: str, at: datetime) -> ManagedFile:
        with self.Session.begin() as session:
            row = self._required_file(session, file_id)
            if row.status != ManagedFileStatus.READY.value:
                raise ValueError("Only a READY managed file can be archived.")
            relation = session.scalar(
                select(ProductFileRelationORM).where(
                    ProductFileRelationORM.managed_file_id == str(file_id)
                )
            )
            row.status = ManagedFileStatus.ARCHIVED.value
            row.archived_at = at
            row.archived_by = actor
            row.updated_at = at
            if relation is not None:
                relation.archived_at = at
                relation.is_primary = False
        return self.get(file_id)

    def set_primary_image(self, *, product_id: UUID, file_id: UUID) -> None:
        with self.Session.begin() as session:
            transaction_lock(session, "product-primary-image", str(product_id))
            target = session.scalar(select(ProductFileRelationORM).where(
                ProductFileRelationORM.product_id == str(product_id),
                ProductFileRelationORM.managed_file_id == str(file_id),
                ProductFileRelationORM.kind == ProductFileKind.IMAGE.value,
                ProductFileRelationORM.archived_at.is_(None),
            ))
            if target is None:
                raise LookupError("active product image not found")
            managed = self._required_file(session, file_id)
            if managed.status != ManagedFileStatus.READY.value:
                raise ValueError("Only a READY image can be primary.")
            rows = session.scalars(select(ProductFileRelationORM).where(
                ProductFileRelationORM.product_id == str(product_id),
                ProductFileRelationORM.kind == ProductFileKind.IMAGE.value,
                ProductFileRelationORM.archived_at.is_(None),
            )).all()
            for row in rows:
                row.is_primary = row.internal_id == target.internal_id

    def update_relation(
        self,
        *,
        product_id: UUID,
        file_id: UUID,
        sort_order: int | None = None,
        caption: str | None = None,
    ) -> ProductFileRelation:
        if sort_order is not None and sort_order < 0:
            raise ValueError("sort_order cannot be negative")
        with self.Session.begin() as session:
            row = session.scalar(select(ProductFileRelationORM).where(
                ProductFileRelationORM.product_id == str(product_id),
                ProductFileRelationORM.managed_file_id == str(file_id),
                ProductFileRelationORM.archived_at.is_(None),
            ))
            if row is None:
                raise LookupError("active product file relation not found")
            if sort_order is not None:
                row.sort_order = sort_order
            if caption is not None:
                row.caption = caption.strip()[:512] or None
        return self.get_relation(file_id)

    def get(self, file_id: UUID) -> ManagedFile:
        with self.Session() as session:
            return self._file(self._required_file(session, file_id))

    def get_relation(self, file_id: UUID) -> ProductFileRelation:
        with self.Session() as session:
            row = session.scalar(select(ProductFileRelationORM).where(
                ProductFileRelationORM.managed_file_id == str(file_id)
            ))
            if row is None:
                raise LookupError("managed-file relation not found")
            return self._relation(row)

    def list_images(self, product_id: UUID, *, include_archived: bool = False) -> tuple[ProductImage, ...]:
        return tuple(ProductImage(relation, managed) for relation, managed in self._list(
            product_id, ProductFileKind.IMAGE, include_archived=include_archived
        ))

    def list_attachments(
        self, product_id: UUID, *, include_archived: bool = False
    ) -> tuple[ProductAttachment, ...]:
        return tuple(ProductAttachment(relation, managed) for relation, managed in self._list(
            product_id, ProductFileKind.ATTACHMENT, include_archived=include_archived
        ))

    def ready_files(self) -> tuple[ManagedFile, ...]:
        with self.Session() as session:
            rows = session.scalars(select(ManagedFileORM).where(
                ManagedFileORM.status == ManagedFileStatus.READY.value
            ).order_by(ManagedFileORM.storage_key)).all()
            return tuple(self._file(row) for row in rows)

    def failed_files(self) -> tuple[ManagedFile, ...]:
        with self.Session() as session:
            rows = session.scalars(select(ManagedFileORM).where(
                ManagedFileORM.status == ManagedFileStatus.FAILED.value
            ).order_by(ManagedFileORM.created_at)).all()
            return tuple(self._file(row) for row in rows)

    def local_recovery_candidates(self) -> tuple[ManagedFile, ...]:
        with self.Session() as session:
            rows = session.scalars(select(ManagedFileORM).where(
                ManagedFileORM.status.in_((
                    ManagedFileStatus.PENDING.value,
                    ManagedFileStatus.FAILED.value,
                ))
            ).order_by(ManagedFileORM.created_at)).all()
            return tuple(self._file(row) for row in rows)

    def recover_local_ready_and_queue(
        self,
        file_id: UUID,
        *,
        transfer_configuration_id: UUID,
        at: datetime,
    ) -> ManagedFile:
        """Reconcile a verified local object after a crash before queue commit."""

        with self.Session.begin() as session:
            row = self._required_file(session, file_id)
            if row.status not in {
                ManagedFileStatus.PENDING.value,
                ManagedFileStatus.FAILED.value,
                ManagedFileStatus.READY.value,
            }:
                raise ValueError("Managed file is not eligible for local recovery.")
            relation = session.scalar(select(ProductFileRelationORM).where(
                ProductFileRelationORM.managed_file_id == str(file_id)
            ))
            if relation is None:
                raise LookupError("managed-file relation not found")
            row.status = ManagedFileStatus.READY.value
            row.failure_reason = None
            row.updated_at = at
            if row.replaced_file_id:
                previous = self._required_file(session, UUID(row.replaced_file_id))
                previous_relation = session.scalar(select(ProductFileRelationORM).where(
                    ProductFileRelationORM.managed_file_id == row.replaced_file_id
                ))
                previous.status = ManagedFileStatus.ARCHIVED.value
                previous.archived_at = at
                previous.archived_by = "store-forward-recovery"
                previous.updated_at = at
                if previous_relation:
                    previous_relation.archived_at = at
                    previous_relation.is_primary = False
            if relation.kind == ProductFileKind.IMAGE.value:
                other_primary = session.scalar(select(ProductFileRelationORM).where(
                    ProductFileRelationORM.product_id == relation.product_id,
                    ProductFileRelationORM.kind == ProductFileKind.IMAGE.value,
                    ProductFileRelationORM.archived_at.is_(None),
                    ProductFileRelationORM.is_primary.is_(True),
                    ProductFileRelationORM.internal_id != relation.internal_id,
                ))
                if other_primary is None:
                    relation.is_primary = True
            if session.get(StorageConfigurationORM, str(transfer_configuration_id)) is None:
                raise LookupError("storage configuration not found")
            existing_job = session.scalar(select(ArchiveTransferJobORM).where(
                ArchiveTransferJobORM.managed_file_id == str(file_id)
            ))
            if existing_job is None:
                session.add(ArchiveTransferJobORM(
                    internal_id=str(__import__("uuid").uuid4()),
                    managed_file_id=str(file_id),
                    configuration_id=str(transfer_configuration_id),
                    state=ArchiveTransferState.TRANSFER_QUEUED.value,
                    attempt_count=0, next_retry_at=at, last_attempt_at=None,
                    last_error_code=None, last_error_summary=None,
                    remote_verified_at=None, grace_expires_at=None, local_purged_at=None,
                    lease_token=None, lease_expires_at=None, created_at=at, updated_at=at,
                ))
        return self.get(file_id)

    def _list(
        self, product_id: UUID, kind: ProductFileKind, *, include_archived: bool
    ) -> tuple[tuple[ProductFileRelation, ManagedFile], ...]:
        with self.Session() as session:
            query = select(ProductFileRelationORM, ManagedFileORM).join(
                ManagedFileORM,
                ManagedFileORM.internal_id == ProductFileRelationORM.managed_file_id,
            ).where(
                ProductFileRelationORM.product_id == str(product_id),
                ProductFileRelationORM.kind == kind.value,
            )
            if not include_archived:
                query = query.where(
                    ProductFileRelationORM.archived_at.is_(None),
                    ManagedFileORM.status == ManagedFileStatus.READY.value,
                )
            rows = session.execute(query.order_by(
                ProductFileRelationORM.sort_order,
                ProductFileRelationORM.created_at,
            )).all()
            return tuple((self._relation(relation), self._file(managed)) for relation, managed in rows)

    @staticmethod
    def _required_file(session, file_id: UUID) -> ManagedFileORM:
        row = session.get(ManagedFileORM, str(file_id))
        if row is None:
            raise LookupError("managed file not found")
        return row

    @staticmethod
    def _file(row: ManagedFileORM) -> ManagedFile:
        return ManagedFile(
            file_id=UUID(row.internal_id),
            original_filename=row.original_filename,
            stored_filename=row.stored_filename,
            storage_key=row.storage_key,
            category=row.category,
            media_type=row.media_type,
            extension=row.extension,
            size_bytes=row.size_bytes,
            sha256=row.sha256,
            status=ManagedFileStatus(row.status),
            source=ManagedFileSource(row.source),
            version=row.version,
            created_at=_utc(row.created_at),
            created_by=row.created_by,
            updated_at=_utc(row.updated_at),
            replaced_file_id=UUID(row.replaced_file_id) if row.replaced_file_id else None,
            archived_at=_utc(row.archived_at) if row.archived_at else None,
            archived_by=row.archived_by,
            failure_reason=row.failure_reason,
        )

    @staticmethod
    def _relation(row: ProductFileRelationORM) -> ProductFileRelation:
        return ProductFileRelation(
            relation_id=UUID(row.internal_id),
            product_id=UUID(row.product_id),
            managed_file_id=UUID(row.managed_file_id),
            kind=ProductFileKind(row.kind),
            attachment_category=row.attachment_category,
            is_primary=row.is_primary,
            sort_order=row.sort_order,
            caption=row.caption,
            created_at=_utc(row.created_at),
            archived_at=_utc(row.archived_at) if row.archived_at else None,
        )


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
