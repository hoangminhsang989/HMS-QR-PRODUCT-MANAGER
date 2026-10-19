"""Transactional metadata repository for managed files."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from packages.domain.attachments import (
    ManagedFile,
    ManagedFileSource,
    ManagedFileStatus,
    ProductAttachment,
    ProductFileKind,
    ProductFileRelation,
    ProductImage,
)
from packages.domain.store_forward import ArchiveTransferState
from .database import resolve_database


class ManagedFileRepository:
    """Managed-file metadata persistence on the in-process HMS SQL engine."""

    def __init__(self, engine, session_factory=None) -> None:
        self.database = resolve_database(engine, session_factory)

    def create_pending(self, managed_file: ManagedFile, relation: ProductFileRelation) -> None:
        if managed_file.status is not ManagedFileStatus.PENDING:
            raise ValueError("New managed file metadata must be PENDING.")
        with self.database.transaction() as transaction:
            if not transaction.execute(
                "SELECT internal_id FROM products WHERE internal_id = ?",
                [str(relation.product_id)],
            ):
                raise LookupError("product not found")
            transaction.execute(
                "INSERT INTO managed_files (internal_id, original_filename, stored_filename,"
                " storage_key, category, media_type, extension, size_bytes, sha256, status,"
                " source, version, created_at, created_by, updated_at, replaced_file_id,"
                " archived_at, archived_by, failure_reason)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    str(managed_file.file_id), managed_file.original_filename,
                    managed_file.stored_filename, managed_file.storage_key,
                    managed_file.category, managed_file.media_type, managed_file.extension,
                    managed_file.size_bytes, managed_file.sha256,
                    managed_file.status.value, managed_file.source.value,
                    managed_file.version, managed_file.created_at, managed_file.created_by,
                    managed_file.updated_at,
                    str(managed_file.replaced_file_id) if managed_file.replaced_file_id else None,
                    managed_file.archived_at, managed_file.archived_by,
                    managed_file.failure_reason,
                ],
            )
            transaction.execute(
                "INSERT INTO product_file_relations (internal_id, product_id,"
                " managed_file_id, kind, attachment_category, is_primary, sort_order,"
                " caption, created_at, archived_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    str(relation.relation_id), str(relation.product_id),
                    str(relation.managed_file_id), relation.kind.value,
                    relation.attachment_category, relation.is_primary, relation.sort_order,
                    relation.caption, relation.created_at, relation.archived_at,
                ],
            )

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
        with self.database.transaction() as transaction:
            row = self._required_file(transaction, file_id)
            if row["status"] != ManagedFileStatus.PENDING.value:
                raise ValueError("Only PENDING metadata can become READY.")
            transaction.execute(
                "UPDATE managed_files SET status = ?, updated_at = ? WHERE internal_id = ?",
                [ManagedFileStatus.READY.value, at, str(file_id)],
            )
            relations = transaction.execute(
                "SELECT * FROM product_file_relations WHERE managed_file_id = ?", [str(file_id)]
            )
            if not relations:
                raise LookupError("managed-file relation not found")
            relation = relations[0]
            if replaces_file_id is not None:
                previous = self._required_file(transaction, replaces_file_id)
                previous_relations = transaction.execute(
                    "SELECT * FROM product_file_relations WHERE managed_file_id = ?",
                    [str(replaces_file_id)],
                )
                if not previous_relations:
                    raise LookupError("replacement relation not found")
                transaction.execute(
                    "UPDATE managed_files SET status = ?, archived_at = ?, archived_by = ?,"
                    " updated_at = ? WHERE internal_id = ?",
                    [
                        ManagedFileStatus.ARCHIVED.value, at, actor, at,
                        str(replaces_file_id),
                    ],
                )
                transaction.execute(
                    "UPDATE product_file_relations SET archived_at = ?, is_primary = ?"
                    " WHERE internal_id = ?",
                    [at, False, previous_relations[0]["internal_id"]],
                )
            if make_primary:
                if relation["kind"] != ProductFileKind.IMAGE.value:
                    raise ValueError("Only a product image can be primary.")
                active_images = transaction.execute(
                    "SELECT internal_id FROM product_file_relations WHERE product_id = ?"
                    " AND kind = ? AND archived_at IS NULL",
                    [relation["product_id"], ProductFileKind.IMAGE.value],
                )
                for image in active_images:
                    transaction.execute(
                        "UPDATE product_file_relations SET is_primary = ? WHERE internal_id = ?",
                        [image["internal_id"] == relation["internal_id"], image["internal_id"]],
                    )
            if transfer_configuration_id is not None:
                if not transaction.execute(
                    "SELECT internal_id FROM storage_configurations WHERE internal_id = ?",
                    [str(transfer_configuration_id)],
                ):
                    raise LookupError("storage configuration not found")
                existing_job = transaction.execute(
                    "SELECT internal_id FROM archive_transfer_jobs WHERE managed_file_id = ?",
                    [str(file_id)],
                )
                if not existing_job:
                    transaction.execute(
                        "INSERT INTO archive_transfer_jobs (internal_id, managed_file_id,"
                        " configuration_id, state, attempt_count, next_retry_at,"
                        " last_attempt_at, last_error_code, last_error_summary,"
                        " remote_verified_at, grace_expires_at, local_purged_at,"
                        " lease_token, lease_expires_at, created_at, updated_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        [
                            str(uuid4()), str(file_id), str(transfer_configuration_id),
                            ArchiveTransferState.TRANSFER_QUEUED.value, 0, at, None, None,
                            None, None, None, None, None, None, at, at,
                        ],
                    )
        return self.get(file_id)

    def mark_failed(self, file_id: UUID, *, reason: str, at: datetime) -> ManagedFile:
        with self.database.transaction() as transaction:
            row = self._required_file(transaction, file_id)
            if row["status"] == ManagedFileStatus.READY.value:
                raise ValueError("READY metadata cannot be relabelled FAILED.")
            transaction.execute(
                "UPDATE managed_files SET status = ?, failure_reason = ?, updated_at = ?"
                " WHERE internal_id = ?",
                [ManagedFileStatus.FAILED.value, reason[:2000], at, str(file_id)],
            )
        return self.get(file_id)

    def archive(self, file_id: UUID, *, actor: str, at: datetime) -> ManagedFile:
        with self.database.transaction() as transaction:
            row = self._required_file(transaction, file_id)
            if row["status"] != ManagedFileStatus.READY.value:
                raise ValueError("Only a READY managed file can be archived.")
            transaction.execute(
                "UPDATE managed_files SET status = ?, archived_at = ?, archived_by = ?,"
                " updated_at = ? WHERE internal_id = ?",
                [ManagedFileStatus.ARCHIVED.value, at, actor, at, str(file_id)],
            )
            transaction.execute(
                "UPDATE product_file_relations SET archived_at = ?, is_primary = ?"
                " WHERE managed_file_id = ?",
                [at, False, str(file_id)],
            )
        return self.get(file_id)

    def set_primary_image(self, *, product_id: UUID, file_id: UUID) -> None:
        with self.database.transaction() as transaction:
            targets = transaction.execute(
                "SELECT * FROM product_file_relations WHERE product_id = ?"
                " AND managed_file_id = ? AND kind = ? AND archived_at IS NULL",
                [str(product_id), str(file_id), ProductFileKind.IMAGE.value],
            )
            if not targets:
                raise LookupError("active product image not found")
            target = targets[0]
            managed = self._required_file(transaction, file_id)
            if managed["status"] != ManagedFileStatus.READY.value:
                raise ValueError("Only a READY image can be primary.")
            rows = transaction.execute(
                "SELECT internal_id FROM product_file_relations WHERE product_id = ?"
                " AND kind = ? AND archived_at IS NULL",
                [str(product_id), ProductFileKind.IMAGE.value],
            )
            for row in rows:
                transaction.execute(
                    "UPDATE product_file_relations SET is_primary = ? WHERE internal_id = ?",
                    [row["internal_id"] == target["internal_id"], row["internal_id"]],
                )

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
        with self.database.transaction() as transaction:
            rows = transaction.execute(
                "SELECT * FROM product_file_relations WHERE product_id = ?"
                " AND managed_file_id = ? AND archived_at IS NULL",
                [str(product_id), str(file_id)],
            )
            if not rows:
                raise LookupError("active product file relation not found")
            if sort_order is not None:
                transaction.execute(
                    "UPDATE product_file_relations SET sort_order = ? WHERE internal_id = ?",
                    [sort_order, rows[0]["internal_id"]],
                )
            if caption is not None:
                transaction.execute(
                    "UPDATE product_file_relations SET caption = ? WHERE internal_id = ?",
                    [caption.strip()[:512] or None, rows[0]["internal_id"]],
                )
        return self.get_relation(file_id)

    def get(self, file_id: UUID) -> ManagedFile:
        with self.database.transaction() as transaction:
            return self._file(self._required_file(transaction, file_id))

    def get_relation(self, file_id: UUID) -> ProductFileRelation:
        rows = self.database.query(
            "SELECT * FROM product_file_relations WHERE managed_file_id = ?", [str(file_id)]
        )
        if not rows:
            raise LookupError("managed-file relation not found")
        return self._relation(rows[0])

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
        rows = self.database.query(
            "SELECT * FROM managed_files WHERE status = ? ORDER BY storage_key ASC,"
            " internal_id ASC",
            [ManagedFileStatus.READY.value],
        )
        return tuple(self._file(row) for row in rows)

    def failed_files(self) -> tuple[ManagedFile, ...]:
        rows = self.database.query(
            "SELECT * FROM managed_files WHERE status = ? ORDER BY created_at ASC,"
            " internal_id ASC",
            [ManagedFileStatus.FAILED.value],
        )
        return tuple(self._file(row) for row in rows)

    def local_recovery_candidates(self) -> tuple[ManagedFile, ...]:
        rows = self.database.query(
            "SELECT * FROM managed_files WHERE status IN (?, ?) ORDER BY created_at ASC,"
            " internal_id ASC",
            [ManagedFileStatus.PENDING.value, ManagedFileStatus.FAILED.value],
        )
        return tuple(self._file(row) for row in rows)

    def recover_local_ready_and_queue(
        self,
        file_id: UUID,
        *,
        transfer_configuration_id: UUID,
        at: datetime,
    ) -> ManagedFile:
        """Reconcile a verified local object after a crash before queue commit."""

        with self.database.transaction() as transaction:
            row = self._required_file(transaction, file_id)
            if row["status"] not in {
                ManagedFileStatus.PENDING.value,
                ManagedFileStatus.FAILED.value,
                ManagedFileStatus.READY.value,
            }:
                raise ValueError("Managed file is not eligible for local recovery.")
            relations = transaction.execute(
                "SELECT * FROM product_file_relations WHERE managed_file_id = ?", [str(file_id)]
            )
            if not relations:
                raise LookupError("managed-file relation not found")
            relation = relations[0]
            transaction.execute(
                "UPDATE managed_files SET status = ?, failure_reason = ?, updated_at = ?"
                " WHERE internal_id = ?",
                [ManagedFileStatus.READY.value, None, at, str(file_id)],
            )
            if row["replaced_file_id"]:
                previous = self._required_file(transaction, UUID(row["replaced_file_id"]))
                previous_relations = transaction.execute(
                    "SELECT internal_id FROM product_file_relations WHERE managed_file_id = ?",
                    [row["replaced_file_id"]],
                )
                transaction.execute(
                    "UPDATE managed_files SET status = ?, archived_at = ?, archived_by = ?,"
                    " updated_at = ? WHERE internal_id = ?",
                    [
                        ManagedFileStatus.ARCHIVED.value, at, "store-forward-recovery", at,
                        row["replaced_file_id"],
                    ],
                )
                if previous_relations:
                    transaction.execute(
                        "UPDATE product_file_relations SET archived_at = ?, is_primary = ?"
                        " WHERE internal_id = ?",
                        [at, False, previous_relations[0]["internal_id"]],
                    )
            if relation["kind"] == ProductFileKind.IMAGE.value:
                other_primary = transaction.execute(
                    "SELECT internal_id FROM product_file_relations WHERE product_id = ?"
                    " AND kind = ? AND archived_at IS NULL AND is_primary = ?"
                    " AND internal_id != ?",
                    [
                        relation["product_id"], ProductFileKind.IMAGE.value, True,
                        relation["internal_id"],
                    ],
                )
                if not other_primary:
                    transaction.execute(
                        "UPDATE product_file_relations SET is_primary = ? WHERE internal_id = ?",
                        [True, relation["internal_id"]],
                    )
            if not transaction.execute(
                "SELECT internal_id FROM storage_configurations WHERE internal_id = ?",
                [str(transfer_configuration_id)],
            ):
                raise LookupError("storage configuration not found")
            existing_job = transaction.execute(
                "SELECT internal_id FROM archive_transfer_jobs WHERE managed_file_id = ?",
                [str(file_id)],
            )
            if not existing_job:
                transaction.execute(
                    "INSERT INTO archive_transfer_jobs (internal_id, managed_file_id,"
                    " configuration_id, state, attempt_count, next_retry_at,"
                    " last_attempt_at, last_error_code, last_error_summary,"
                    " remote_verified_at, grace_expires_at, local_purged_at,"
                    " lease_token, lease_expires_at, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        str(uuid4()), str(file_id), str(transfer_configuration_id),
                        ArchiveTransferState.TRANSFER_QUEUED.value, 0, at, None, None,
                        None, None, None, None, None, None, at, at,
                    ],
                )
        return self.get(file_id)

    def _list(
        self, product_id: UUID, kind: ProductFileKind, *, include_archived: bool
    ) -> tuple[tuple[ProductFileRelation, ManagedFile], ...]:
        if include_archived:
            rows = self.database.query(
                "SELECT product_file_relations.internal_id AS relation_id,"
                " product_file_relations.product_id AS product_id,"
                " product_file_relations.managed_file_id AS managed_file_id,"
                " product_file_relations.kind AS kind,"
                " product_file_relations.attachment_category AS attachment_category,"
                " product_file_relations.is_primary AS is_primary,"
                " product_file_relations.sort_order AS sort_order,"
                " product_file_relations.caption AS caption,"
                " product_file_relations.created_at AS relation_created_at,"
                " product_file_relations.archived_at AS relation_archived_at,"
                " managed_files.internal_id AS file_internal_id,"
                " managed_files.original_filename AS original_filename,"
                " managed_files.stored_filename AS stored_filename,"
                " managed_files.storage_key AS storage_key,"
                " managed_files.category AS category,"
                " managed_files.media_type AS media_type,"
                " managed_files.extension AS extension,"
                " managed_files.size_bytes AS size_bytes,"
                " managed_files.sha256 AS sha256,"
                " managed_files.status AS status,"
                " managed_files.source AS source,"
                " managed_files.version AS version,"
                " managed_files.created_at AS created_at,"
                " managed_files.created_by AS created_by,"
                " managed_files.updated_at AS updated_at,"
                " managed_files.replaced_file_id AS replaced_file_id,"
                " managed_files.archived_at AS archived_at,"
                " managed_files.archived_by AS archived_by,"
                " managed_files.failure_reason AS failure_reason"
                " FROM product_file_relations JOIN managed_files"
                " ON managed_files.internal_id = product_file_relations.managed_file_id"
                " WHERE product_file_relations.product_id = ?"
                " AND product_file_relations.kind = ?"
                " ORDER BY product_file_relations.sort_order ASC,"
                " product_file_relations.created_at ASC",
                [str(product_id), kind.value],
            )
        else:
            rows = self.database.query(
                "SELECT product_file_relations.internal_id AS relation_id,"
                " product_file_relations.product_id AS product_id,"
                " product_file_relations.managed_file_id AS managed_file_id,"
                " product_file_relations.kind AS kind,"
                " product_file_relations.attachment_category AS attachment_category,"
                " product_file_relations.is_primary AS is_primary,"
                " product_file_relations.sort_order AS sort_order,"
                " product_file_relations.caption AS caption,"
                " product_file_relations.created_at AS relation_created_at,"
                " product_file_relations.archived_at AS relation_archived_at,"
                " managed_files.internal_id AS file_internal_id,"
                " managed_files.original_filename AS original_filename,"
                " managed_files.stored_filename AS stored_filename,"
                " managed_files.storage_key AS storage_key,"
                " managed_files.category AS category,"
                " managed_files.media_type AS media_type,"
                " managed_files.extension AS extension,"
                " managed_files.size_bytes AS size_bytes,"
                " managed_files.sha256 AS sha256,"
                " managed_files.status AS status,"
                " managed_files.source AS source,"
                " managed_files.version AS version,"
                " managed_files.created_at AS created_at,"
                " managed_files.created_by AS created_by,"
                " managed_files.updated_at AS updated_at,"
                " managed_files.replaced_file_id AS replaced_file_id,"
                " managed_files.archived_at AS archived_at,"
                " managed_files.archived_by AS archived_by,"
                " managed_files.failure_reason AS failure_reason"
                " FROM product_file_relations JOIN managed_files"
                " ON managed_files.internal_id = product_file_relations.managed_file_id"
                " WHERE product_file_relations.product_id = ?"
                " AND product_file_relations.kind = ?"
                " AND product_file_relations.archived_at IS NULL"
                " AND managed_files.status = ?"
                " ORDER BY product_file_relations.sort_order ASC,"
                " product_file_relations.created_at ASC",
                [str(product_id), kind.value, ManagedFileStatus.READY.value],
            )
        return tuple((self._relation(row), self._file(row)) for row in rows)

    @staticmethod
    def _required_file(session, file_id: UUID) -> dict:
        rows = session.execute(
            "SELECT * FROM managed_files WHERE internal_id = ?", [str(file_id)]
        )
        if not rows:
            raise LookupError("managed file not found")
        return rows[0]

    @staticmethod
    def _file(row) -> ManagedFile:
        return ManagedFile(
            file_id=UUID(row["internal_id"] if "internal_id" in row else row["file_internal_id"]),
            original_filename=row["original_filename"],
            stored_filename=row["stored_filename"],
            storage_key=row["storage_key"],
            category=row["category"],
            media_type=row["media_type"],
            extension=row["extension"],
            size_bytes=row["size_bytes"],
            sha256=row["sha256"],
            status=ManagedFileStatus(row["status"]),
            source=ManagedFileSource(row["source"]),
            version=row["version"],
            created_at=_utc(row["created_at"]),
            created_by=row["created_by"],
            updated_at=_utc(row["updated_at"]),
            replaced_file_id=UUID(row["replaced_file_id"]) if row["replaced_file_id"] else None,
            archived_at=_utc(row["archived_at"]) if row["archived_at"] else None,
            archived_by=row["archived_by"],
            failure_reason=row["failure_reason"],
        )

    @staticmethod
    def _relation(row) -> ProductFileRelation:
        return ProductFileRelation(
            relation_id=UUID(row["relation_id"] if "relation_id" in row else row["internal_id"]),
            product_id=UUID(row["product_id"]),
            managed_file_id=UUID(row["managed_file_id"]),
            kind=ProductFileKind(row["kind"]),
            attachment_category=row["attachment_category"],
            is_primary=row["is_primary"],
            sort_order=row["sort_order"],
            caption=row["caption"],
            created_at=_utc(row["relation_created_at"] if "relation_created_at" in row else row["created_at"]),
            archived_at=_utc(row["relation_archived_at"]) if row.get("relation_archived_at", row.get("archived_at")) else None,
        )


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


__all__ = ["ManagedFileRepository"]
