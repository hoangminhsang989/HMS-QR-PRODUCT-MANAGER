"""Safe logical storage-key and server-generated filename helpers."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
import re
from uuid import UUID


_RESERVED_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_ILLEGAL_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_KEY_SEGMENT = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_CATEGORY = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


def validate_original_filename(filename: str) -> str:
    if not isinstance(filename, str):
        raise TypeError("filename must be text")
    value = filename.strip()
    if not value or value in {".", ".."}:
        raise ValueError("Tên tệp không hợp lệ.")
    if value != filename or value.endswith((".", " ")):
        raise ValueError("Tên tệp không được có khoảng trắng hoặc dấu chấm ở cuối.")
    if _ILLEGAL_FILENAME.search(value):
        raise ValueError("Tên tệp chứa ký tự hoặc đường dẫn không an toàn.")
    if PureWindowsPath(value).name != value or PurePosixPath(value).name != value:
        raise ValueError("Tên tệp không được chứa đường dẫn.")
    if value.split(".", 1)[0].upper() in _RESERVED_WINDOWS_NAMES:
        raise ValueError("Tên tệp dành riêng của Windows không được phép.")
    return value


def normalized_extension(filename: str) -> str:
    value = validate_original_filename(filename)
    suffix = PurePosixPath(value).suffix.lower()
    if not suffix or len(suffix) > 16 or not re.fullmatch(r"\.[a-z0-9]+", suffix):
        raise ValueError("Phần mở rộng tệp không hợp lệ.")
    return suffix


def generate_storage_key(
    *,
    product_id: UUID,
    file_id: UUID,
    version: int,
    category: str,
    extension: str,
) -> tuple[str, str]:
    if version < 1:
        raise ValueError("version must be positive")
    category_value = category.lower()
    if not _CATEGORY.fullmatch(category_value):
        raise ValueError("Managed-file category is invalid.")
    suffix = extension.lower()
    if not re.fullmatch(r"\.[a-z0-9]+", suffix):
        raise ValueError("Managed-file extension is invalid.")
    stored_filename = f"{file_id.hex}{suffix}"
    storage_key = (
        f"products/{product_id}/" f"{category_value}/{file_id}/v{version:04d}/{stored_filename}"
    )
    return validate_storage_key(storage_key), stored_filename


def validate_storage_key(storage_key: str) -> str:
    if not isinstance(storage_key, str):
        raise TypeError("storage_key must be text")
    if not storage_key or storage_key.startswith(("/", "\\")):
        raise ValueError("Storage key must be relative.")
    if "\\" in storage_key or ":" in storage_key:
        raise ValueError("Storage key cannot contain a drive or UNC path.")
    raw_parts = storage_key.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError("Storage key contains unsafe traversal.")
    path = PurePosixPath(storage_key)
    if path.is_absolute():
        raise ValueError("Storage key contains unsafe traversal.")
    if any(not _KEY_SEGMENT.fullmatch(part) for part in path.parts):
        raise ValueError("Storage key contains an invalid segment.")
    return "/".join(path.parts)
