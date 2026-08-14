import hashlib
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from config.paths import TEST_ROOT
from packages.storage import LocalDevStorage, StorageConflict, StorageUnavailable
from packages.storage.keys import (
    generate_storage_key,
    normalized_extension,
    validate_original_filename,
    validate_storage_key,
)
from packages.storage.validation import UploadKind, UploadLimits, validate_upload


def test_storage_key_and_filename_reject_traversal_absolute_unc_and_reserved_names():
    for unsafe in (
        "../secret.pdf", "/absolute/file.pdf", r"C:\secret.pdf", r"\\server\share\x",
        "safe/./file.pdf", "safe//file.pdf",
    ):
        with pytest.raises(ValueError):
            validate_storage_key(unsafe)
    for unsafe_name in ("../secret.pdf", r"C:\secret.pdf", "CON.txt", "bad?.pdf", "trail. "):
        with pytest.raises(ValueError):
            validate_original_filename(unsafe_name)
    assert normalized_extension("Bản-vẽ.PDF") == ".pdf"


def test_generated_key_uses_only_server_owned_identity():
    product_id = uuid4()
    file_id = uuid4()
    key, stored = generate_storage_key(
        product_id=product_id,
        file_id=file_id,
        version=2,
        category="images",
        extension=".png",
    )
    assert key == f"products/{product_id}/images/{file_id}/v0002/{file_id.hex}.png"
    assert stored == f"{file_id.hex}.png"
    assert "customer-name" not in key


def test_mime_extension_signature_and_central_size_limit():
    png = b"\x89PNG\r\n\x1a\n" + b"safe-image"
    validated = validate_upload(
        filename="photo.png", declared_mime="image/png", content=png,
        expected_kind=UploadKind.IMAGE,
    )
    assert validated.size_bytes == len(png)
    with pytest.raises(ValueError, match="MIME"):
        validate_upload(filename="photo.jpg", declared_mime="image/png", content=png)
    with pytest.raises(ValueError, match="chữ ký|MIME"):
        validate_upload(filename="photo.png", declared_mime="image/png", content=b"%PDF-1.7")
    with pytest.raises(ValueError, match="giới hạn"):
        validate_upload(
            filename="photo.png", declared_mime="image/png", content=png,
            limits=UploadLimits(image_bytes=4),
        )


def test_atomic_publication_checksum_conflict_missing_and_tamper(tmp_path: Path, monkeypatch):
    assert TEST_ROOT.resolve() in tmp_path.resolve().parents
    storage = LocalDevStorage(tmp_path / "storage")
    key = "products/00000000-0000-0000-0000-000000000001/images/00000000-0000-0000-0000-000000000002/v0001/a.png"
    content = b"managed-content"
    digest = hashlib.sha256(content).hexdigest()
    stored = storage.put(key, content, expected_sha256=digest, expected_size=len(content))
    assert stored.sha256 == digest and not stored.already_present
    assert not tuple((tmp_path / "storage").rglob("*.uploading"))
    duplicate = storage.put(key, content, expected_sha256=digest, expected_size=len(content))
    assert duplicate.already_present
    with pytest.raises(StorageConflict):
        storage.put(key, b"different")
    target = tmp_path / "storage" / Path(*key.split("/"))
    target.write_bytes(b"tampered")
    result = storage.verify(key, expected_sha256=digest, expected_size=len(content))
    assert result.exists and not result.valid and result.reason == "SIZE_OR_SHA256_MISMATCH"
    target.unlink()
    missing = storage.verify(key, expected_sha256=digest, expected_size=len(content))
    assert not missing.exists and not missing.valid and missing.reason == "MISSING"

    failed_key = key.replace("a.png", "b.png")
    original_replace = __import__("os").replace
    monkeypatch.setattr("packages.storage.service.os.replace", lambda *_: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(StorageUnavailable):
        storage.put(failed_key, content)
    monkeypatch.setattr("packages.storage.service.os.replace", original_replace)
    assert not storage.exists(failed_key)
    assert not tuple((tmp_path / "storage").rglob("*.uploading"))


def test_missing_storage_fails_closed_without_random_fallback(tmp_path: Path):
    root = tmp_path / "unavailable"
    storage = LocalDevStorage(root)
    root.rmdir()
    with pytest.raises(StorageUnavailable):
        storage.put("safe/file.bin", b"bytes")
    assert storage.health().writable is False
