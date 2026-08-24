"""Deterministic, non-elevated preparation for R011's D2 deployment path.

This module never requests elevation and must not be imported by product runtime.
It renders the literal Stage-0 command consumed by OS-trusted Windows PowerShell.
"""

from __future__ import annotations

import base64
import ctypes
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
from types import MappingProxyType
from typing import Final, Mapping
import zipfile


COMMAND_LINE_SAFETY_LIMIT = 30_000
RUNTIME_ARCHIVE_SHA256 = "df901e84a896ff1ee720ad03377e0c8d8c2244fda79808aeeaff6316df1cb75c"
RUNTIME_ARCHIVE_SIZE = 12_570_832
AUTHORITY_MAX_LIFETIME = timedelta(minutes=15)
REQUIRED_ROLES = ("releases", "runtime", "staging")
AUTHORITY_ID = "R011_OS_TRUSTED_ONE_SHOT_DEPLOYMENT_IMPLEMENTATION"
MACHINE_NAME = "HMS-PC"
TARGET_ROOT = r"D:\HMS-QR-PROD"
SERVICE_ACCOUNT = r"HMS-PC\HMSQRService"
SERVICE_SID = "S-1-5-21-170807328-2858633000-3406472961-1009"
STAGING_ROLE = "staging"
STAGING_NAMESPACE = ".hms-qr-d2"
REVIEWED_LINEAGE_PARENT = "3f3c2406e26c1796d5b7509ac2eee5902080955a"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TRUSTED_STAGE0_PATH = _REPOSITORY_ROOT / "scripts" / "r011_d2_stage0.ps1"
TRUSTED_PAYLOAD_PATH = _REPOSITORY_ROOT / "scripts" / "r011_d2_protected_payload.ps1"
TRUSTED_STAGE0_SHA256 = "766cd212793056aab413d1f425a1adb696d39001e5ef0863685c37ee82b98c27"
TRUSTED_PAYLOAD_SHA256 = "9a499a48573f57b8cca0a63cb5b3043c7d940c42c160debfae87251db61a7e53"
TRUSTED_BUNDLE_SHA256 = "2e8d699cd83d1362976dd21c580aad6e33e7f904b6eae471b5c267c318b853af"
TRUSTED_BUNDLE_FILES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "config/paths.py": "bd684afb40cb3601a89250c9f771c4169b3ffe3a6fa07e7d0d4225564a8aee7b",
        "packages/deployment/__init__.py": "2ab2ffdb4ef62448e4a2a57b0a00cd87921c8168bc5a77aba6c86b9911ac05e5",
        "packages/deployment/artifact.py": "ffa9beb40bb50095fb49cc8c1cb0e769a24a3c80df58553cfff630d0f5d3e84f",
        "packages/deployment/configuration.py": "b2db2db58081c18286a641b17a7a82fd5410317c84f70d722276b40b4509a3ee",
        "packages/deployment/evidence.py": "a4b3c8389a47fbac38ff92b4974c366b974b684a2b90ede62af92eff6c9f6de2",
        "packages/deployment/inventory.py": "8feb2fa272580ece1385194db74fe9e30cd260d45da155a21cc52b523545d89e",
        "packages/deployment/layout.py": "90fae12917e70c2a81cc9d8a404e36eaa7ddf515be392d4bd11ad0353b32cd7f",
        "packages/deployment/lifecycle.py": "fa00e6690ece64d9f84edde505847902de7f5502e409cb16825f2add09b0ecc6",
        "packages/deployment/mutation.py": "49694b808fd9ec3fede6ae12ebfa99bd1eb8040e02ca8730a5b6e86aa4c8051d",
        "packages/deployment/plans.py": "b38d6d8feae8d45e47e318ee4c7f5dbc66476904592bbfe405245f8bac5ea126",
        "packages/deployment/preflight.py": "27bfe436939b97be9ab9c51725742644135253c31e2ca95cde39292807a19dda",
        "packages/deployment/provisioning.py": "e7c6b4ed2c5d9c6210bbbcf1b6ec471efe4b7e5379a0257e9796e6f9a88c58a4",
        "packages/deployment/secret_store.py": "b2b4b63cbfe4e49a327b6ba21623007fa241e83dba7aaa7cf15543a5c24ee087",
    }
)
TRUST_MANIFEST_SHA256 = "a531187b8d600c2d8ec001615f5a3e028ccb37ad64965aefd04aa09472a091ea"
PROVISIONER_ARGUMENTS = (
    "-B", "-m", "packages.deployment.provisioning", "--target-root", "{target_root}",
    "--service-account", "{service_account}", "--roles", *REQUIRED_ROLES, "--apply",
)


class D2ContractError(ValueError):
    """An input cannot safely enter the D2 administrative deployment path."""


@dataclass(frozen=True, slots=True)
class D2Authority:
    authority_id: str
    attempt_id: str
    created_utc: str
    expires_utc: str
    machine_name: str
    target_root: str
    payload_source: str
    payload_sha256: str
    runtime_archive: str
    runtime_sha256: str
    bundle_source: str
    bundle_sha256: str
    service_account: str = SERVICE_ACCOUNT
    service_sid: str = SERVICE_SID
    roles: tuple[str, ...] = REQUIRED_ROLES

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if item.name == "roles":
                if type(value) is not tuple or any(type(role) is not str for role in value):
                    raise D2ContractError("roles must be an exact tuple of strings")
            elif type(value) is not str:
                raise D2ContractError(f"{item.name} must be a string")
        if self.authority_id != AUTHORITY_ID:
            raise D2ContractError("authority_id must match the frozen D2 authority")
        if self.machine_name.casefold() != MACHINE_NAME.casefold():
            raise D2ContractError("machine_name must match frozen Machine A identity")
        if _canonical_windows_path(self.target_root) != _canonical_windows_path(TARGET_ROOT):
            raise D2ContractError("target_root must match frozen production target")
        if self.service_account.casefold() != SERVICE_ACCOUNT.casefold() or self.service_sid != SERVICE_SID:
            raise D2ContractError("service identity must match frozen production binding")
        _validate_attempt_id(self.attempt_id)
        if tuple(self.roles) != REQUIRED_ROLES:
            raise D2ContractError("D2 roles must be the exact currently approved role list")
        if not self.target_root or not Path(self.target_root).is_absolute():
            raise D2ContractError("target root must be absolute")
        for field, suffix in (("payload_source", ".ps1"), ("runtime_archive", ".zip"), ("bundle_source", ".zip")):
            value = Path(getattr(self, field))
            if not value.is_absolute() or value.suffix.casefold() != suffix:
                raise D2ContractError(f"{field} must be an absolute {suffix} path")
        try:
            created = datetime.fromisoformat(self.created_utc.replace("Z", "+00:00"))
            expires = datetime.fromisoformat(self.expires_utc.replace("Z", "+00:00"))
        except ValueError as exc:
            raise D2ContractError("authority timestamps must be ISO-8601") from exc
        if created.tzinfo is None or expires.tzinfo is None or created >= expires:
            raise D2ContractError("authority timestamps must be ordered UTC instants")
        if expires - created > AUTHORITY_MAX_LIFETIME:
            raise D2ContractError("authority lifetime exceeds the frozen maximum")
        for field in ("payload_sha256", "runtime_sha256", "bundle_sha256"):
            value = getattr(self, field)
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
                raise D2ContractError(f"{field} must be a SHA-256 hex digest")
        if self.runtime_sha256.casefold() != RUNTIME_ARCHIVE_SHA256:
            raise D2ContractError("runtime_sha256 must match the frozen CPython artifact")


@dataclass(frozen=True, slots=True)
class TrustedD2Snapshot:
    authority_id: str
    attempt_id: str
    created_utc: str
    expires_utc: str
    machine_name: str
    target_root: str
    payload_source: str
    payload_sha256: str
    runtime_archive: str
    runtime_sha256: str
    bundle_source: str
    bundle_sha256: str
    service_account: str
    service_sid: str
    roles: tuple[str, ...]
    trust_manifest_sha256: str
    reviewed_lineage_parent: str


@dataclass(frozen=True, slots=True)
class TrustedFileIdentity:
    path: Path
    canonical_sha256: str
    checkout_sha256: str
    checkout_eol: str


def _canonical_windows_path(value: str) -> str:
    return value.replace("/", "\\").rstrip("\\").casefold()


def _validate_attempt_id(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", value):
        raise D2ContractError("attempt identifier must be an ASCII bounded simple token")
    if ".." in value or value[-1] in ". " or any(token in value for token in (":", "/", "\\")):
        raise D2ContractError("attempt identifier is not a safe direct child")
    stem = value.split(".", 1)[0].upper()
    if stem in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise D2ContractError("attempt identifier uses a reserved Windows device basename")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _manifest_document() -> dict[str, object]:
    return {
        "schema": "r011.d2.trusted-committed-byte-manifest.v1",
        "lineage_parent": REVIEWED_LINEAGE_PARENT,
        "canonical_eol": "LF",
        "stage0": {"path": "scripts/r011_d2_stage0.ps1", "sha256": TRUSTED_STAGE0_SHA256},
        "protected_payload": {
            "path": "scripts/r011_d2_protected_payload.ps1",
            "sha256": TRUSTED_PAYLOAD_SHA256,
        },
        "bundle_files": dict(TRUSTED_BUNDLE_FILES),
        "bundle_sha256": TRUSTED_BUNDLE_SHA256,
    }


def trusted_manifest_bytes() -> bytes:
    return (
        json.dumps(_manifest_document(), ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")


def _validate_embedded_manifest() -> None:
    if _sha256_bytes(trusted_manifest_bytes()) != TRUST_MANIFEST_SHA256:
        raise RuntimeError("embedded D2 trust manifest identity is internally inconsistent")


def _exact_path(value: str | Path, expected: Path, label: str) -> Path:
    supplied = Path(value)
    if not supplied.is_absolute():
        raise D2ContractError(f"{label} must use the trusted absolute path")
    supplied_absolute = Path(os.path.abspath(supplied))
    expected_absolute = Path(os.path.abspath(expected))
    if os.path.normcase(str(supplied_absolute)) != os.path.normcase(str(expected_absolute)):
        raise D2ContractError(f"{label} path does not match the trusted manifest")
    if supplied_absolute.resolve(strict=True) != expected_absolute.resolve(strict=True):
        raise D2ContractError(f"{label} path alias is forbidden")
    if supplied_absolute.is_symlink():
        raise D2ContractError(f"{label} may not be a symlink")
    return supplied_absolute


def _canonical_trusted_bytes(path: Path, expected_sha256: str, label: str) -> bytes:
    raw = path.read_bytes()
    if _sha256_bytes(raw) == expected_sha256:
        return raw
    canonical = raw.replace(b"\r\n", b"\n")
    if b"\r" in canonical or canonical.replace(b"\n", b"\r\n") != raw:
        raise D2ContractError(f"{label} has unsupported or mixed line endings")
    if _sha256_bytes(canonical) != expected_sha256:
        raise D2ContractError(f"{label} committed-byte identity mismatch")
    return canonical


def _trusted_text_identity(
    value: str | Path, expected_path: Path, expected_sha256: str, label: str
) -> TrustedFileIdentity:
    path = _exact_path(value, expected_path, label)
    raw = path.read_bytes()
    raw_hash = _sha256_bytes(raw)
    canonical = _canonical_trusted_bytes(path, expected_sha256, label)
    eol = "LF" if raw == canonical else "CRLF"
    return TrustedFileIdentity(path, expected_sha256, raw_hash, eol)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


_validate_embedded_manifest()


def _native_system_directory() -> Path:
    if os.name != "nt":
        raise D2ContractError("Windows native System32 identity is required")
    size = 32768
    buffer = ctypes.create_unicode_buffer(size)
    result = ctypes.WinDLL("kernel32", use_last_error=True).GetSystemDirectoryW(buffer, size)
    if result == 0 or result >= size:
        raise OSError(ctypes.get_last_error(), "GetSystemDirectoryW failed")
    return Path(buffer.value).resolve(strict=True)


def resolve_native_powershell() -> Path:
    """Resolve PowerShell 5.1 directly from native System32, never from PATH."""

    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise D2ContractError("32-bit/WOW64 preparation is forbidden for the amd64 D2 runtime")
    system_directory = _native_system_directory()
    candidate = (system_directory / "WindowsPowerShell" / "v1.0" / "powershell.exe").resolve(strict=True)
    if system_directory not in candidate.parents or candidate.name.casefold() != "powershell.exe":
        raise D2ContractError("PowerShell did not resolve under native System32")
    if "syswow64" in str(candidate).casefold():
        raise D2ContractError("WOW64 redirected PowerShell is forbidden")
    return candidate


def _ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def render_authority_assignments(authority: TrustedD2Snapshot) -> str:
    """Render only the reconstructed primitive allowlist as inert literals."""

    if type(authority) is not TrustedD2Snapshot:
        raise D2ContractError("only a reconstructed trusted authority snapshot may be rendered")
    lines = ["$authority = @{"]
    for item in fields(TrustedD2Snapshot):
        key = item.name
        value = getattr(authority, key)
        rendered = "@(" + ",".join(_ps_literal(str(item)) for item in value) + ")" if isinstance(value, tuple) else _ps_literal(str(value))
        lines.append(f"    {key} = {rendered}")
    return "\n".join((*lines, "}"))


def render_stage0(stage0_template: str | Path, authority: TrustedD2Snapshot) -> str:
    identity = _trusted_text_identity(
        stage0_template, TRUSTED_STAGE0_PATH, TRUSTED_STAGE0_SHA256, "Stage-0"
    )
    template = _canonical_trusted_bytes(
        identity.path, TRUSTED_STAGE0_SHA256, "Stage-0"
    ).decode("utf-8")
    assignments = render_authority_assignments(authority)
    if "__AUTHORITY_ASSIGNMENTS__" not in template or template.count("__AUTHORITY_ASSIGNMENTS__") != 1:
        raise D2ContractError("Stage-0 template must contain exactly one authority placeholder")
    return template.replace("__AUTHORITY_ASSIGNMENTS__", assignments).replace("\r\n", "\n").rstrip() + "\n"


def encode_stage0(stage0_source: str) -> str:
    return base64.b64encode(stage0_source.encode("utf-16le")).decode("ascii")


def build_trusted_snapshot(authority: D2Authority) -> TrustedD2Snapshot:
    if type(authority) is not D2Authority:
        raise D2ContractError("authority must be the exact D2Authority type")
    primitive: dict[str, object] = {}
    for item in fields(D2Authority):
        value = getattr(authority, item.name)
        if item.name == "roles":
            if type(value) is not tuple or any(type(role) is not str for role in value):
                raise D2ContractError("authority roles changed after validation")
            primitive[item.name] = tuple(value)
        else:
            if type(value) is not str:
                raise D2ContractError(f"authority field changed type after validation: {item.name}")
            primitive[item.name] = value
    reconstructed = D2Authority(**primitive)
    created = datetime.fromisoformat(reconstructed.created_utc.replace("Z", "+00:00"))
    expires = datetime.fromisoformat(reconstructed.expires_utc.replace("Z", "+00:00"))
    now = _utc_now()
    if now < created or now > expires:
        raise D2ContractError("authority is not active at trusted snapshot construction")
    payload = _trusted_text_identity(
        reconstructed.payload_source,
        TRUSTED_PAYLOAD_PATH,
        TRUSTED_PAYLOAD_SHA256,
        "protected payload",
    )
    if reconstructed.payload_sha256.casefold() != payload.checkout_sha256:
        raise D2ContractError("payload_sha256 must come from the trusted committed-byte manifest")
    bundle = Path(reconstructed.bundle_source)
    if not bundle.is_absolute() or not bundle.is_file() or bundle.is_symlink():
        raise D2ContractError("deployment bundle source is not an exact regular file")
    if reconstructed.bundle_sha256.casefold() != TRUSTED_BUNDLE_SHA256:
        raise D2ContractError("bundle_sha256 must match the trusted committed-byte manifest")
    if sha256_file(bundle) != TRUSTED_BUNDLE_SHA256:
        raise D2ContractError("deployment bundle bytes do not match the trusted manifest")
    runtime = Path(reconstructed.runtime_archive)
    if not runtime.is_file() or runtime.is_symlink() or runtime.stat().st_size != RUNTIME_ARCHIVE_SIZE:
        raise D2ContractError("private runtime source identity is not exact")
    if sha256_file(runtime) != RUNTIME_ARCHIVE_SHA256:
        raise D2ContractError("private runtime bytes do not match the frozen identity")
    return TrustedD2Snapshot(
        authority_id=reconstructed.authority_id,
        attempt_id=reconstructed.attempt_id,
        created_utc=reconstructed.created_utc,
        expires_utc=reconstructed.expires_utc,
        machine_name=reconstructed.machine_name,
        target_root=reconstructed.target_root,
        payload_source=str(payload.path),
        payload_sha256=payload.checkout_sha256,
        runtime_archive=str(runtime.resolve(strict=True)),
        runtime_sha256=RUNTIME_ARCHIVE_SHA256,
        bundle_source=str(bundle.resolve(strict=True)),
        bundle_sha256=TRUSTED_BUNDLE_SHA256,
        service_account=reconstructed.service_account,
        service_sid=reconstructed.service_sid,
        roles=REQUIRED_ROLES,
        trust_manifest_sha256=TRUST_MANIFEST_SHA256,
        reviewed_lineage_parent=REVIEWED_LINEAGE_PARENT,
    )


def build_powershell_command(authority: D2Authority, stage0_template: str | Path) -> tuple[Path, tuple[str, ...], dict[str, str | int]]:
    snapshot = build_trusted_snapshot(authority)
    source = render_stage0(stage0_template, snapshot)
    encoded = encode_stage0(source)
    executable = resolve_native_powershell()
    arguments = ("-NoProfile", "-NonInteractive", "-NoLogo", "-EncodedCommand", encoded)
    command_length = len(" ".join((str(executable), *arguments)))
    if command_length > COMMAND_LINE_SAFETY_LIMIT:
        raise D2ContractError("Stage-0 command line exceeds the pre-UAC safety limit")
    return executable, arguments, {
        "stage0_template_sha256": TRUSTED_STAGE0_SHA256,
        "stage0_raw_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "stage0_encoded_sha256": hashlib.sha256(encoded.encode("ascii")).hexdigest(),
        "trust_manifest_sha256": TRUST_MANIFEST_SHA256,
        "command_line_length": command_length,
    }


def _safe_member(name: str) -> PurePosixPath:
    value = PurePosixPath(name)
    if not name or value.is_absolute() or "\\" in name or ".." in value.parts or value.parts[:1] == ("",):
        raise D2ContractError(f"unsafe ZIP member: {name!r}")
    return value


def safe_extract_zip(archive: str | Path, destination: str | Path) -> tuple[str, ...]:
    """Extract regular, unique relative ZIP files into a caller-controlled namespace."""

    target = Path(destination).resolve(strict=False)
    seen: set[PurePosixPath] = set()
    with zipfile.ZipFile(archive) as bundle:
        entries = sorted(bundle.infolist(), key=lambda item: item.filename)
        for entry in entries:
            member = _safe_member(entry.filename)
            unix_type = (entry.external_attr >> 16) & 0o170000
            dos_attributes = entry.external_attr & 0xFFFF
            supported_type = unix_type in {0, 0o100000}
            if not supported_type or dos_attributes & 0x400 or member in seen:
                raise D2ContractError(f"unsafe ZIP member: {entry.filename!r}")
            seen.add(member)
        for entry in entries:
            member = _safe_member(entry.filename)
            output = (target / Path(*member.parts)).resolve(strict=False)
            if output != target and target not in output.parents:
                raise D2ContractError(f"ZIP member escapes destination: {entry.filename!r}")
            if entry.is_dir():
                output.mkdir(parents=True, exist_ok=False)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                if output.exists():
                    raise D2ContractError(f"ZIP member collision: {entry.filename!r}")
                with bundle.open(entry) as source, output.open("xb") as result:
                    shutil.copyfileobj(source, result)
    return tuple(item.filename for item in entries)


def verify_exact_files(root: str | Path, expected: dict[str, str]) -> None:
    """Reject missing, unexpected, or hash-mismatched regular files after extraction."""

    base = Path(root).resolve(strict=True)
    actual = {
        item.relative_to(base).as_posix(): sha256_file(item)
        for item in base.rglob("*")
        if item.is_file()
    }
    if actual != expected:
        raise D2ContractError("exact extracted file set/hash mismatch")


def build_deployment_bundle(source_root: str | Path, output: str | Path) -> dict[str, object]:
    """Build only manifest-authorized canonical bytes from the reviewed source root."""

    root = _exact_path(source_root, _REPOSITORY_ROOT, "deployment source root")
    expected_python = {
        path for path in TRUSTED_BUNDLE_FILES if path.startswith("packages/deployment/")
    }
    actual_python = {
        item.relative_to(root).as_posix()
        for item in (root / "packages" / "deployment").glob("*.py")
    }
    if actual_python != expected_python | {"packages/deployment/os_trusted_one_shot.py"}:
        raise D2ContractError("deployment source contains a missing or unexpected executable artifact")
    canonical: dict[str, bytes] = {}
    for relative, expected_hash in TRUSTED_BUNDLE_FILES.items():
        item = root / relative
        if not item.is_file() or item.is_symlink():
            raise D2ContractError(f"trusted bundle source is absent or aliased: {relative}")
        canonical[relative] = _canonical_trusted_bytes(item, expected_hash, relative)
    destination = Path(output)
    if not destination.is_absolute() or destination.exists() or destination.is_symlink():
        raise D2ContractError("deployment bundle destination must be a fresh absolute path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for relative in sorted(TRUSTED_BUNDLE_FILES):
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, canonical[relative])
        info = zipfile.ZipInfo("bundle-manifest.txt", date_time=(1980, 1, 1, 0, 0, 0))
        info.external_attr = 0o100644 << 16
        manifest_bytes = "".join(
            f"{TRUSTED_BUNDLE_FILES[path]} {path}\n" for path in sorted(TRUSTED_BUNDLE_FILES)
        ).encode("ascii")
        bundle.writestr(info, manifest_bytes)
    if sha256_file(destination) != TRUSTED_BUNDLE_SHA256:
        raise D2ContractError("published deployment bundle hash does not match the trusted manifest")
    with zipfile.ZipFile(destination) as bundle:
        names = set(bundle.namelist())
        if names != set(TRUSTED_BUNDLE_FILES) | {"bundle-manifest.txt"}:
            raise D2ContractError("published deployment bundle file set mismatch")
        for relative, expected_hash in TRUSTED_BUNDLE_FILES.items():
            if _sha256_bytes(bundle.read(relative)) != expected_hash:
                raise D2ContractError(f"published deployment bundle byte mismatch: {relative}")
        if bundle.read("bundle-manifest.txt") != manifest_bytes:
            raise D2ContractError("published deployment bundle manifest readback mismatch")
    return {
        "files": dict(TRUSTED_BUNDLE_FILES),
        "file_count": len(TRUSTED_BUNDLE_FILES),
        "sha256": TRUSTED_BUNDLE_SHA256,
        "trust_manifest_sha256": TRUST_MANIFEST_SHA256,
    }


def exact_provisioner_argv(authority: D2Authority) -> tuple[str, ...]:
    return tuple(value.format(target_root=authority.target_root, service_account=authority.service_account) for value in PROVISIONER_ARGUMENTS)


__all__ = ["AUTHORITY_ID", "AUTHORITY_MAX_LIFETIME", "COMMAND_LINE_SAFETY_LIMIT", "D2Authority", "D2ContractError", "MACHINE_NAME", "REQUIRED_ROLES", "REVIEWED_LINEAGE_PARENT", "RUNTIME_ARCHIVE_SHA256", "RUNTIME_ARCHIVE_SIZE", "SERVICE_ACCOUNT", "SERVICE_SID", "STAGING_NAMESPACE", "STAGING_ROLE", "TARGET_ROOT", "TRUSTED_BUNDLE_FILES", "TRUSTED_BUNDLE_SHA256", "TRUSTED_PAYLOAD_PATH", "TRUSTED_PAYLOAD_SHA256", "TRUSTED_STAGE0_PATH", "TRUSTED_STAGE0_SHA256", "TRUST_MANIFEST_SHA256", "TrustedD2Snapshot", "build_deployment_bundle", "build_powershell_command", "build_trusted_snapshot", "encode_stage0", "exact_provisioner_argv", "render_authority_assignments", "resolve_native_powershell", "safe_extract_zip", "sha256_file", "trusted_manifest_bytes", "verify_exact_files"]
