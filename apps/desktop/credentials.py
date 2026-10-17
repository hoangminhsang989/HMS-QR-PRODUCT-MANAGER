"""Current-user DPAPI storage for optional saved Desktop login credentials."""

from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _crypt(data: bytes, *, unprotect: bool) -> bytes:
    if os.name != "nt":
        raise OSError("Windows DPAPI is required to store Desktop credentials.")
    source_buffer = ctypes.create_string_buffer(data)
    source = _DataBlob(len(data), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
    destination = _DataBlob()
    function = ctypes.windll.crypt32.CryptUnprotectData if unprotect else ctypes.windll.crypt32.CryptProtectData
    if unprotect:
        ok = function(ctypes.byref(source), None, None, None, None, 0x1, ctypes.byref(destination))
    else:
        ok = function(ctypes.byref(source), "HMS QR Desktop credentials", None, None, None, 0x1, ctypes.byref(destination))
    if not ok:
        raise OSError("Windows DPAPI could not process Desktop credentials.")
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(destination.pbData)


def credentials_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "HMS QR Desktop"
    return root / "credentials.json"


def load_credentials(path: Path | None = None) -> tuple[str, str] | None:
    try:
        record = json.loads((path or credentials_path()).read_text(encoding="utf-8"))
        username = str(record["username"]).strip()
        password = _crypt(base64.b64decode(record["password"], validate=True), unprotect=True).decode("utf-8")
        return (username, password) if username and password else None
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, json.JSONDecodeError):
        return None


def save_credentials(username: str, password: str, path: Path | None = None) -> None:
    if not username.strip() or not password:
        raise ValueError("Username and password are required.")
    target = path or credentials_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    record = {"username": username.strip(), "password": base64.b64encode(_crypt(password.encode("utf-8"), unprotect=False)).decode("ascii")}
    target.write_text(json.dumps(record), encoding="utf-8")


def delete_credentials(path: Path | None = None) -> None:
    try:
        (path or credentials_path()).unlink()
    except FileNotFoundError:
        pass
