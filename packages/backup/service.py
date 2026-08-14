"""Atomic backup bundle publication and non-destructive restore verification."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
from typing import Iterable
from uuid import UUID, uuid4

from packages.domain.attachments import ManagedFile, ManagedFileStatus
from packages.storage.keys import validate_storage_key
from packages.storage.service import StorageService


MANIFEST_VERSION = 1


@dataclass(frozen=True, slots=True)
class BackupFileEntry:
    file_id: str
    storage_key: str
    bundle_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class BackupManifest:
    manifest_version: int
    backup_id: str
    created_at: str
    application_version: str
    schema_revision: str
    metadata_export_reference: str | None
    metadata_export_sha256: str | None
    files: tuple[BackupFileEntry, ...]
    status: str


@dataclass(frozen=True, slots=True)
class BackupVerification:
    valid: bool
    backup_id: str | None
    checked_files: int
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BackupRetentionPolicy:
    latest_n: int = 7
    daily_days: int = 30
    weekly_weeks: int = 12

    def __post_init__(self) -> None:
        if self.latest_n < 1 or self.daily_days < 0 or self.weekly_weeks < 0:
            raise ValueError("Backup retention values are invalid.")


class BackupService:
    def __init__(self, *, backup_root: str | Path, storage: StorageService) -> None:
        self.backup_root = Path(backup_root).resolve(strict=False)
        self.storage = storage
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        *,
        managed_files: Iterable[ManagedFile],
        application_version: str,
        schema_revision: str,
        metadata_export: str | Path | None = None,
        backup_id: UUID | None = None,
    ) -> Path:
        identifier = backup_id or uuid4()
        final = self.backup_root / str(identifier)
        staging = self.backup_root / f".{identifier}.staging"
        if final.exists() or staging.exists():
            raise FileExistsError("Backup identity already exists.")
        staging.mkdir(parents=False)
        entries: list[BackupFileEntry] = []
        try:
            for managed in sorted(managed_files, key=lambda item: item.storage_key):
                if managed.status is not ManagedFileStatus.READY:
                    raise ValueError("Only READY managed files can enter a valid backup.")
                validate_storage_key(managed.storage_key)
                content = self.storage.read(managed.storage_key)
                digest = hashlib.sha256(content).hexdigest()
                if len(content) != managed.size_bytes or digest != managed.sha256:
                    raise ValueError(f"Managed file integrity failed: {managed.file_id}")
                bundle_path = f"files/{managed.storage_key}"
                destination = _resolve_bundle_path(staging, bundle_path)
                destination.parent.mkdir(parents=True, exist_ok=True)
                _write_durable(destination, content)
                entries.append(BackupFileEntry(
                    file_id=str(managed.file_id),
                    storage_key=managed.storage_key,
                    bundle_path=bundle_path,
                    size_bytes=managed.size_bytes,
                    sha256=managed.sha256,
                ))

            metadata_reference = None
            metadata_sha256 = None
            if metadata_export is not None:
                source = Path(metadata_export).resolve(strict=True)
                if not source.is_file():
                    raise FileNotFoundError("Metadata export is not a file.")
                metadata_reference = f"metadata/{source.name}"
                metadata_bytes = source.read_bytes()
                metadata_sha256 = hashlib.sha256(metadata_bytes).hexdigest()
                destination = _resolve_bundle_path(staging, metadata_reference)
                destination.parent.mkdir(parents=True, exist_ok=True)
                _write_durable(destination, metadata_bytes)

            manifest = BackupManifest(
                manifest_version=MANIFEST_VERSION,
                backup_id=str(identifier),
                created_at=datetime.now(timezone.utc).isoformat(),
                application_version=application_version,
                schema_revision=schema_revision,
                metadata_export_reference=metadata_reference,
                metadata_export_sha256=metadata_sha256,
                files=tuple(entries),
                status="VERIFIED",
            )
            manifest_bytes = json.dumps(
                _manifest_dict(manifest), ensure_ascii=False, sort_keys=True, indent=2
            ).encode("utf-8") + b"\n"
            _write_durable(staging / "manifest.json", manifest_bytes)
            _write_durable(
                staging / "manifest.sha256",
                (hashlib.sha256(manifest_bytes).hexdigest() + "\n").encode("ascii"),
            )
            verification = RestoreVerifier().verify(staging)
            if not verification.valid:
                raise ValueError("Staged backup verification failed: " + "; ".join(verification.issues))
            os.replace(staging, final)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return final

    def retention_candidates(self, policy: BackupRetentionPolicy) -> tuple[Path, ...]:
        """Return candidates only; R008 never hard-deletes backup bundles."""

        bundles = sorted(
            (path for path in self.backup_root.iterdir() if path.is_dir() and not path.name.startswith(".")),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return tuple(bundles[policy.latest_n:])


class RestoreVerifier:
    """Verify a bundle without mutating any database or managed storage."""

    def verify(self, bundle: str | Path) -> BackupVerification:
        root = Path(bundle).resolve(strict=False)
        manifest_path = root / "manifest.json"
        checksum_path = root / "manifest.sha256"
        if not manifest_path.is_file() or not checksum_path.is_file():
            return BackupVerification(False, None, 0, ("MANIFEST_MISSING",))
        try:
            manifest_bytes = manifest_path.read_bytes()
            expected_manifest_sha256 = checksum_path.read_text(encoding="ascii").strip().lower()
            if (
                len(expected_manifest_sha256) != 64
                or any(character not in "0123456789abcdef" for character in expected_manifest_sha256)
                or hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_sha256
            ):
                return BackupVerification(False, None, 0, ("MANIFEST_CHECKSUM_MISMATCH",))
            raw = json.loads(manifest_bytes.decode("utf-8"))
            manifest = _parse_manifest(raw)
        except (OSError, UnicodeError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return BackupVerification(False, None, 0, ("MANIFEST_INVALID",))
        issues: list[str] = []
        checked = 0
        if manifest.manifest_version != MANIFEST_VERSION or manifest.status != "VERIFIED":
            issues.append("MANIFEST_VERSION_OR_STATUS_INVALID")
        seen_keys: set[str] = set()
        for entry in manifest.files:
            try:
                validate_storage_key(entry.storage_key)
                target = _resolve_bundle_path(root, entry.bundle_path)
            except ValueError:
                issues.append(f"UNSAFE_PATH:{entry.file_id}")
                continue
            if entry.storage_key in seen_keys:
                issues.append(f"DUPLICATE_STORAGE_KEY:{entry.file_id}")
                continue
            seen_keys.add(entry.storage_key)
            if not target.is_file():
                issues.append(f"MISSING:{entry.file_id}")
                continue
            checked += 1
            try:
                size = target.stat().st_size
                digest = _sha256_file(target)
            except OSError:
                issues.append(f"UNREADABLE:{entry.file_id}")
                continue
            if size != entry.size_bytes or digest != entry.sha256:
                issues.append(f"TAMPERED:{entry.file_id}")
        if manifest.metadata_export_reference:
            try:
                metadata_path = _resolve_bundle_path(root, manifest.metadata_export_reference)
            except ValueError:
                issues.append("METADATA_UNSAFE_PATH")
            else:
                if not metadata_path.is_file():
                    issues.append("METADATA_MISSING")
                elif _sha256_file(metadata_path) != manifest.metadata_export_sha256:
                    issues.append("METADATA_TAMPERED")
        return BackupVerification(not issues, manifest.backup_id, checked, tuple(issues))


def _manifest_dict(manifest: BackupManifest) -> dict[str, object]:
    value = asdict(manifest)
    value["files"] = [asdict(entry) for entry in manifest.files]
    return value


def _parse_manifest(raw: dict[str, object]) -> BackupManifest:
    required = {
        "manifest_version", "backup_id", "created_at", "application_version",
        "schema_revision", "metadata_export_reference", "metadata_export_sha256",
        "files", "status",
    }
    if set(raw) != required or not isinstance(raw["files"], list):
        raise ValueError("Unexpected backup manifest schema.")
    files = tuple(BackupFileEntry(
        file_id=str(entry["file_id"]),
        storage_key=str(entry["storage_key"]),
        bundle_path=str(entry["bundle_path"]),
        size_bytes=int(entry["size_bytes"]),
        sha256=str(entry["sha256"]),
    ) for entry in raw["files"] if isinstance(entry, dict))
    if len(files) != len(raw["files"]):
        raise ValueError("Invalid backup file entry.")
    return BackupManifest(
        manifest_version=int(raw["manifest_version"]),
        backup_id=str(raw["backup_id"]),
        created_at=str(raw["created_at"]),
        application_version=str(raw["application_version"]),
        schema_revision=str(raw["schema_revision"]),
        metadata_export_reference=(
            str(raw["metadata_export_reference"]) if raw["metadata_export_reference"] is not None else None
        ),
        metadata_export_sha256=(
            str(raw["metadata_export_sha256"]) if raw["metadata_export_sha256"] is not None else None
        ),
        files=files,
        status=str(raw["status"]),
    )


def _resolve_bundle_path(root: Path, relative: str) -> Path:
    if not relative or "\\" in relative or ":" in relative or "//" in relative:
        raise ValueError("Unsafe backup-relative path.")
    path = PurePosixPath(relative)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Unsafe backup-relative path.")
    target = (root / Path(*path.parts)).resolve(strict=False)
    if root != target and root not in target.parents:
        raise ValueError("Backup path escapes bundle.")
    return target


def _write_durable(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
