"""Deterministic, non-elevated preparation for R011's D2 deployment path.

This module never requests elevation and must not be imported by product runtime.
It renders the literal Stage-0 command consumed by OS-trusted Windows PowerShell.
"""

from __future__ import annotations

import base64
import ctypes
from dataclasses import dataclass
from datetime import datetime
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile


COMMAND_LINE_SAFETY_LIMIT = 30_000
RUNTIME_ARCHIVE_SHA256 = "df901e84a896ff1ee720ad03377e0c8d8c2244fda79808aeeaff6316df1cb75c"
RUNTIME_ARCHIVE_SIZE = 12_570_832
REQUIRED_ROLES = ("releases", "runtime", "staging")
AUTHORITY_ID = "R011_OS_TRUSTED_ONE_SHOT_DEPLOYMENT_IMPLEMENTATION"
MACHINE_NAME = "HMS-PC"
TARGET_ROOT = r"D:\HMS-QR-PROD"
SERVICE_ACCOUNT = r"HMS-PC\HMSQRService"
SERVICE_SID = "S-1-5-21-170807328-2858633000-3406472961-1009"
STAGING_ROLE = "staging"
STAGING_NAMESPACE = ".hms-qr-d2"
PROVISIONER_ARGUMENTS = (
    "-B", "-m", "packages.deployment.provisioning", "--target-root", "{target_root}",
    "--service-account", "{service_account}", "--roles", *REQUIRED_ROLES, "--apply",
)


class D2ContractError(ValueError):
    """An input cannot safely enter the D2 administrative deployment path."""


@dataclass(frozen=True)
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
        for field in ("payload_sha256", "runtime_sha256", "bundle_sha256"):
            value = getattr(self, field)
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
                raise D2ContractError(f"{field} must be a SHA-256 hex digest")
        if self.runtime_sha256.casefold() != RUNTIME_ARCHIVE_SHA256:
            raise D2ContractError("runtime_sha256 must match the frozen CPython artifact")


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


def render_authority_assignments(authority: D2Authority) -> str:
    """Render a direct PowerShell hashtable; Stage-0 cannot depend on JSON cmdlets."""

    fields = authority.__dict__
    lines = ["$authority = @{"]
    for key in sorted(fields):
        value = fields[key]
        rendered = "@(" + ",".join(_ps_literal(str(item)) for item in value) + ")" if isinstance(value, tuple) else _ps_literal(str(value))
        lines.append(f"    {key} = {rendered}")
    return "\n".join((*lines, "}"))


def render_stage0(stage0_template: str | Path, authority: D2Authority) -> str:
    template = Path(stage0_template).read_text(encoding="utf-8")
    assignments = render_authority_assignments(authority)
    if "__AUTHORITY_ASSIGNMENTS__" not in template or template.count("__AUTHORITY_ASSIGNMENTS__") != 1:
        raise D2ContractError("Stage-0 template must contain exactly one authority placeholder")
    return template.replace("__AUTHORITY_ASSIGNMENTS__", assignments).replace("\r\n", "\n").rstrip() + "\n"


def encode_stage0(stage0_source: str) -> str:
    return base64.b64encode(stage0_source.encode("utf-16le")).decode("ascii")


def build_powershell_command(authority: D2Authority, stage0_template: str | Path) -> tuple[Path, tuple[str, ...], dict[str, str | int]]:
    _verify_pre_uac_artifacts(authority)
    source = render_stage0(stage0_template, authority)
    encoded = encode_stage0(source)
    executable = resolve_native_powershell()
    arguments = ("-NoProfile", "-NonInteractive", "-NoLogo", "-EncodedCommand", encoded)
    command_length = len(" ".join((str(executable), *arguments)))
    if command_length > COMMAND_LINE_SAFETY_LIMIT:
        raise D2ContractError("Stage-0 command line exceeds the pre-UAC safety limit")
    return executable, arguments, {
        "stage0_raw_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "stage0_encoded_sha256": hashlib.sha256(encoded.encode("ascii")).hexdigest(),
        "command_line_length": command_length,
    }


def _verify_pre_uac_artifacts(authority: D2Authority) -> None:
    for path, expected, label, size in (
        (authority.payload_source, authority.payload_sha256, "payload", None),
        (authority.runtime_archive, authority.runtime_sha256, "runtime archive", RUNTIME_ARCHIVE_SIZE),
        (authority.bundle_source, authority.bundle_sha256, "deployment bundle", None),
    ):
        item = Path(path)
        if not item.is_file():
            raise D2ContractError(f"pre-UAC {label} source is absent")
        if size is not None and item.stat().st_size != size:
            raise D2ContractError(f"pre-UAC {label} size does not match frozen artifact")
        if sha256_file(item) != expected.casefold():
            raise D2ContractError(f"pre-UAC {label} hash does not match frozen artifact")


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
    """Build a sorted, timestamp-stable provisioner closure without tests or artifacts."""

    root = Path(source_root)
    allowed = [root / "config" / "paths.py", *sorted((root / "packages" / "deployment").glob("*.py"))]
    if any(not item.is_file() for item in allowed):
        raise D2ContractError("deployment bundle source closure is incomplete")
    manifest = {item.relative_to(root).as_posix(): sha256_file(item) for item in allowed}
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for relative in sorted(manifest):
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, (root / relative).read_bytes())
        info = zipfile.ZipInfo("bundle-manifest.txt", date_time=(1980, 1, 1, 0, 0, 0))
        info.external_attr = 0o100644 << 16
        bundle.writestr(info, "".join(f"{manifest[path]} {path}\n" for path in sorted(manifest)).encode("ascii"))
    return {"files": manifest, "file_count": len(manifest), "sha256": sha256_file(destination)}


def exact_provisioner_argv(authority: D2Authority) -> tuple[str, ...]:
    return tuple(value.format(target_root=authority.target_root, service_account=authority.service_account) for value in PROVISIONER_ARGUMENTS)


__all__ = ["AUTHORITY_ID", "COMMAND_LINE_SAFETY_LIMIT", "D2Authority", "D2ContractError", "MACHINE_NAME", "REQUIRED_ROLES", "RUNTIME_ARCHIVE_SHA256", "RUNTIME_ARCHIVE_SIZE", "SERVICE_ACCOUNT", "SERVICE_SID", "STAGING_NAMESPACE", "STAGING_ROLE", "TARGET_ROOT", "build_deployment_bundle", "build_powershell_command", "encode_stage0", "exact_provisioner_argv", "render_authority_assignments", "resolve_native_powershell", "safe_extract_zip", "sha256_file", "verify_exact_files"]
