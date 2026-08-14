"""Server-owned managed-storage backends.

Only logical storage keys cross this boundary.  Physical roots (including a
future NAS UNC root) remain server configuration and are never returned to a
client.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
import hashlib
import os
from pathlib import Path
from uuid import uuid4

from .keys import validate_storage_key


class StorageError(RuntimeError):
    """Base class for controlled storage failures."""


class StorageUnavailable(StorageError):
    """The configured storage root is not available."""


class StorageConflict(StorageError):
    """An immutable storage key already contains different bytes."""


class StorageIntegrityError(StorageError):
    """Published bytes do not match their expected identity."""


class HealthState(StrEnum):
    HEALTHY = "HEALTHY"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class StorageHealth:
    state: HealthState
    writable: bool
    message: str


@dataclass(frozen=True, slots=True)
class StoredObject:
    storage_key: str
    size_bytes: int
    sha256: str
    already_present: bool = False


@dataclass(frozen=True, slots=True)
class IntegrityResult:
    storage_key: str
    exists: bool
    valid: bool
    actual_size: int | None = None
    actual_sha256: str | None = None
    reason: str | None = None


class StorageService(ABC):
    @abstractmethod
    def put(
        self,
        storage_key: str,
        content: bytes,
        *,
        expected_sha256: str | None = None,
        expected_size: int | None = None,
    ) -> StoredObject: ...

    @abstractmethod
    def read(self, storage_key: str) -> bytes: ...

    @abstractmethod
    def exists(self, storage_key: str) -> bool: ...

    @abstractmethod
    def archive(self, storage_key: str, archive_key: str) -> str: ...

    @abstractmethod
    def delete(self, storage_key: str) -> None: ...

    @abstractmethod
    def verify(
        self,
        storage_key: str,
        *,
        expected_sha256: str,
        expected_size: int,
    ) -> IntegrityResult: ...

    @abstractmethod
    def health(self) -> StorageHealth: ...


class FilesystemStorage(StorageService):
    """Confined filesystem backend with durable, atomic publication."""

    def __init__(self, root: str | Path, *, create_root: bool) -> None:
        self.root = Path(root).resolve(strict=False)
        if create_root:
            self.root.mkdir(parents=True, exist_ok=True)

    def _require_root(self) -> None:
        if not self.root.is_dir():
            raise StorageUnavailable("Kho lưu trữ hiện không khả dụng.")

    def _resolve(self, storage_key: str) -> Path:
        key = validate_storage_key(storage_key)
        target = (self.root / Path(*key.split("/"))).resolve(strict=False)
        if target == self.root or self.root not in target.parents:
            raise ValueError("Storage key nằm ngoài vùng lưu trữ được quản lý.")
        return target

    def put(
        self,
        storage_key: str,
        content: bytes,
        *,
        expected_sha256: str | None = None,
        expected_size: int | None = None,
    ) -> StoredObject:
        self._require_root()
        if not isinstance(content, bytes):
            raise TypeError("content must be bytes")
        actual_size = len(content)
        actual_sha256 = hashlib.sha256(content).hexdigest()
        if expected_size is not None and actual_size != expected_size:
            raise StorageIntegrityError("Kích thước nội dung không khớp metadata.")
        if expected_sha256 is not None and actual_sha256 != expected_sha256.lower():
            raise StorageIntegrityError("SHA-256 nội dung không khớp metadata.")

        target = self._resolve(storage_key)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageUnavailable("Không thể chuẩn bị vùng công bố tệp.") from exc
        if target.exists():
            result = self.verify(
                storage_key,
                expected_sha256=actual_sha256,
                expected_size=actual_size,
            )
            if not result.valid:
                raise StorageConflict("Storage key đã chứa nội dung khác.")
            return StoredObject(storage_key, actual_size, actual_sha256, True)

        temporary = target.parent / f".{target.name}.{uuid4().hex}.uploading"
        try:
            with temporary.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if temporary.stat().st_size != actual_size:
                raise StorageIntegrityError("Temporary publication size mismatch.")
            if _sha256_file(temporary) != actual_sha256:
                raise StorageIntegrityError("Temporary publication checksum mismatch.")
            os.replace(temporary, target)
            _fsync_directory(target.parent)
        except OSError as exc:
            raise StorageUnavailable("Không thể công bố tệp vào kho lưu trữ.") from exc
        finally:
            temporary.unlink(missing_ok=True)
        return StoredObject(storage_key, actual_size, actual_sha256)

    def read(self, storage_key: str) -> bytes:
        self._require_root()
        target = self._resolve(storage_key)
        try:
            return target.read_bytes()
        except FileNotFoundError:
            raise FileNotFoundError("Managed file does not exist.") from None
        except OSError as exc:
            raise StorageUnavailable("Không thể đọc kho lưu trữ.") from exc

    def exists(self, storage_key: str) -> bool:
        self._require_root()
        return self._resolve(storage_key).is_file()

    def archive(self, storage_key: str, archive_key: str) -> str:
        self._require_root()
        source = self._resolve(storage_key)
        target = self._resolve(archive_key)
        if not source.is_file():
            raise FileNotFoundError("Managed file does not exist.")
        if target.exists():
            raise StorageConflict("Archive key already exists.")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageUnavailable("Không thể chuẩn bị vùng lưu trữ phiên bản.") from exc
        try:
            os.replace(source, target)
            _fsync_directory(target.parent)
        except OSError as exc:
            raise StorageUnavailable("Không thể lưu trữ phiên bản tệp.") from exc
        return archive_key

    def delete(self, storage_key: str) -> None:
        self._require_root()
        try:
            self._resolve(storage_key).unlink(missing_ok=True)
        except OSError as exc:
            raise StorageUnavailable("Không thể xóa tệp được quản lý.") from exc

    def verify(
        self,
        storage_key: str,
        *,
        expected_sha256: str,
        expected_size: int,
    ) -> IntegrityResult:
        self._require_root()
        target = self._resolve(storage_key)
        if not target.is_file():
            return IntegrityResult(storage_key, False, False, reason="MISSING")
        try:
            actual_size = target.stat().st_size
            actual_sha256 = _sha256_file(target)
        except OSError as exc:
            raise StorageUnavailable("Không thể xác minh kho lưu trữ.") from exc
        valid = actual_size == expected_size and actual_sha256 == expected_sha256.lower()
        reason = None if valid else "SIZE_OR_SHA256_MISMATCH"
        return IntegrityResult(storage_key, True, valid, actual_size, actual_sha256, reason)

    def health(self) -> StorageHealth:
        if not self.root.is_dir():
            return StorageHealth(HealthState.UNAVAILABLE, False, "Storage root unavailable")
        writable = os.access(self.root, os.W_OK)
        state = HealthState.HEALTHY if writable else HealthState.UNAVAILABLE
        return StorageHealth(state, writable, "Storage ready" if writable else "Storage not writable")


class LocalDevStorage(FilesystemStorage):
    """Development/test backend.  The caller must pass the controlled test root."""

    def __init__(self, root: str | Path) -> None:
        super().__init__(root, create_root=True)


class NasFilesystemStorage(FilesystemStorage):
    """NAS-ready adapter contract; it never creates or falls back from its root.

    Real NAS writes remain unauthorized in R008.  Machine A must supply the UNC
    root and OS-level bounded I/O policy through external configuration.
    """

    def __init__(self, root: str | Path) -> None:
        raw = str(root)
        if not raw.startswith("\\\\"):
            raise ValueError("NAS root must be an externally configured UNC path.")
        super().__init__(root, create_root=False)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    """Best-effort directory durability; Windows does not expose POSIX dir fsync."""

    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
