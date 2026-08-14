from pathlib import Path

import pytest

from packages.domain.attachments import ManagedFileStatus
from packages.storage import LocalDevStorage, StorageUnavailable
from packages.storage.managed_files import ManagedFileService


PNG = b"\x89PNG\r\n\x1a\n" + b"r008-image-content"
PDF = b"%PDF-1.7\nR008 attachment\n%%EOF"


def test_multiple_product_images_primary_order_and_duplicate_content_are_distinct(managed_file_env):
    env = managed_file_env
    service = env["service"]
    first = service.upload_product_image(
        product_id=env["product_id"], original_filename="front.png",
        declared_mime="image/png", content=PNG, actor="stage6-user",
        caption="Mặt trước", sort_order=10, make_primary=True,
    )
    second = service.upload_product_image(
        product_id=env["product_id"], original_filename="duplicate-content.png",
        declared_mime="image/png", content=PNG, actor="stage6-user",
        caption="Góc khác", sort_order=20,
    )
    assert first.managed_file.sha256 == second.managed_file.sha256
    assert first.managed_file.file_id != second.managed_file.file_id
    assert first.managed_file.storage_key != second.managed_file.storage_key
    assert env["storage"].exists(first.managed_file.storage_key)
    assert env["storage"].exists(second.managed_file.storage_key)
    images = env["repository"].list_images(env["product_id"])
    assert [image.relation.sort_order for image in images] == [10, 20]
    assert [image.relation.is_primary for image in images] == [True, False]
    service.set_primary_image(product_id=env["product_id"], file_id=second.managed_file.file_id)
    assert [image.relation.is_primary for image in env["repository"].list_images(env["product_id"])] == [False, True]


def test_attachment_relation_replacement_preserves_history_and_old_bytes(managed_file_env):
    env = managed_file_env
    first = env["service"].upload_attachment(
        product_id=env["product_id"], original_filename="drawing.pdf",
        declared_mime="application/pdf", content=PDF, actor="stage6-user",
        attachment_category="DRAWING", caption="Rev A", sort_order=5,
    )
    replacement = env["service"].upload_attachment(
        product_id=env["product_id"], original_filename="drawing-rev-b.pdf",
        declared_mime="application/pdf", content=PDF + b"\nrev-b", actor="stage6-user",
        attachment_category="DRAWING", caption="Rev B", sort_order=6,
        replaces_file_id=first.managed_file.file_id,
    )
    assert replacement.managed_file.version == 2
    assert replacement.managed_file.replaced_file_id == first.managed_file.file_id
    assert env["repository"].get(first.managed_file.file_id).status is ManagedFileStatus.ARCHIVED
    assert env["storage"].exists(first.managed_file.storage_key)
    active = env["repository"].list_attachments(env["product_id"])
    history = env["repository"].list_attachments(env["product_id"], include_archived=True)
    assert len(active) == 1 and active[0].relation.caption == "Rev B"
    assert len(history) == 2


def test_failed_publication_latches_failed_metadata(managed_file_env):
    env = managed_file_env
    unavailable_root = env["root"] / "gone-storage"
    storage = LocalDevStorage(unavailable_root)
    unavailable_root.rmdir()
    service = ManagedFileService(env["repository"], storage)
    with pytest.raises(StorageUnavailable):
        service.upload_attachment(
            product_id=env["product_id"], original_filename="inspection.pdf",
            declared_mime="application/pdf", content=PDF, actor="stage6-user",
            attachment_category="INSPECTION",
        )
    failed = env["repository"].failed_files()
    assert len(failed) == 1
    assert failed[0].status is ManagedFileStatus.FAILED
    assert failed[0].failure_reason == "StorageUnavailable"


def test_managed_download_identity_never_accepts_a_client_path(managed_file_env):
    env = managed_file_env
    attachment = env["service"].upload_attachment(
        product_id=env["product_id"], original_filename="order.pdf",
        declared_mime="application/pdf", content=PDF, actor="stage6-user",
        attachment_category="PURCHASE_ORDER",
    )
    assert env["service"].verify(attachment.managed_file.file_id).valid
    with pytest.raises(ValueError):
        env["storage"].read(r"C:\Windows\system.ini")
