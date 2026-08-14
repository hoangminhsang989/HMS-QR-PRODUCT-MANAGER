"""Centralized upload limits and bounded MIME/signature validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .keys import normalized_extension


class UploadKind(StrEnum):
    IMAGE = "IMAGE"
    DOCUMENT = "DOCUMENT"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class UploadLimits:
    image_bytes: int = 25 * 1024 * 1024
    document_bytes: int = 100 * 1024 * 1024
    other_bytes: int = 100 * 1024 * 1024

    def for_kind(self, kind: UploadKind) -> int:
        return {
            UploadKind.IMAGE: self.image_bytes,
            UploadKind.DOCUMENT: self.document_bytes,
            UploadKind.OTHER: self.other_bytes,
        }[kind]


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    original_filename: str
    extension: str
    media_type: str
    kind: UploadKind
    size_bytes: int


_MIME_EXTENSIONS: dict[str, frozenset[str]] = {
    "image/jpeg": frozenset({".jpg", ".jpeg"}),
    "image/png": frozenset({".png"}),
    "image/gif": frozenset({".gif"}),
    "image/webp": frozenset({".webp"}),
    "application/pdf": frozenset({".pdf"}),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": frozenset({".docx"}),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": frozenset({".xlsx"}),
    "text/plain": frozenset({".txt"}),
    "text/csv": frozenset({".csv"}),
    "application/zip": frozenset({".zip"}),
    "application/dxf": frozenset({".dxf"}),
    "image/vnd.dwg": frozenset({".dwg"}),
    "application/octet-stream": frozenset({".step", ".stp", ".iges", ".igs"}),
}
_IMAGE_MIMES = frozenset(mime for mime in _MIME_EXTENSIONS if mime.startswith("image/") and mime != "image/vnd.dwg")
_DOCUMENT_MIMES = frozenset({
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
})


def validate_upload(
    *,
    filename: str,
    declared_mime: str,
    content: bytes,
    expected_kind: UploadKind | None = None,
    limits: UploadLimits = UploadLimits(),
) -> ValidatedUpload:
    extension = normalized_extension(filename)
    media_type = declared_mime.strip().lower().split(";", 1)[0]
    permitted = _MIME_EXTENSIONS.get(media_type)
    if permitted is None or extension not in permitted:
        raise ValueError("MIME type và phần mở rộng không khớp allowlist.")
    kind = UploadKind.IMAGE if media_type in _IMAGE_MIMES else (
        UploadKind.DOCUMENT if media_type in _DOCUMENT_MIMES else UploadKind.OTHER
    )
    if expected_kind is not None and kind is not expected_kind:
        raise ValueError("Loại nội dung không phù hợp với thao tác tải lên.")
    if not content:
        raise ValueError("Tệp rỗng không được phép.")
    if len(content) > limits.for_kind(kind):
        raise ValueError("Tệp vượt quá giới hạn kích thước cấu hình.")
    sniffed = sniff_media_type(content)
    if sniffed is not None and sniffed != media_type:
        zip_family = media_type in {
            "application/zip",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        if not (sniffed == "application/zip" and zip_family):
            raise ValueError("Chữ ký tệp không khớp MIME đã khai báo.")
    if media_type in _STRONG_SIGNATURE_MIMES and sniffed != media_type:
        raise ValueError("Không xác minh được chữ ký tệp bắt buộc.")
    return ValidatedUpload(filename, extension, media_type, kind, len(content))


_STRONG_SIGNATURE_MIMES = frozenset({
    "image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf", "image/vnd.dwg",
})


def sniff_media_type(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"PK\x03\x04"):
        return "application/zip"
    if content.startswith(b"AC10"):
        return "image/vnd.dwg"
    return None
