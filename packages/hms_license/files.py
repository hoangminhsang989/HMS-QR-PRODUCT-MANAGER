"""Encrypted offline request and license file formats."""

import json
import secrets

from hms_license.crypto import decrypt_blob, encrypt_blob, new_file_key


def new_request(hwid: str, product: str, app_version: str, ts: int) -> dict:
    """Create a request payload with a fresh 16-byte hexadecimal nonce."""
    return {
        "hwid": hwid,
        "product": product,
        "app_version": app_version,
        "ts": ts,
        "nonce": secrets.token_hex(16),
    }


def _write(path: str, obj: dict, file_key: bytes) -> None:
    plaintext = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    with open(path, "wb") as stream:
        stream.write(encrypt_blob(plaintext, file_key))


def _read(path: str, file_key: bytes) -> dict:
    try:
        with open(path, "rb") as stream:
            plaintext = decrypt_blob(stream.read(), file_key)
        obj = json.loads(plaintext.decode("utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("encrypted file must contain a JSON object")
        return obj
    except ValueError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid encrypted request/license file") from exc


def write_request_file(path: str, request: dict, file_key: bytes) -> None:
    _write(path, request, file_key)


def read_request_file(path: str, file_key: bytes) -> dict:
    return _read(path, file_key)


def write_license_file(path: str, signed: dict, file_key: bytes) -> None:
    _write(path, signed, file_key)


def read_license_file(path: str, file_key: bytes) -> dict:
    return _read(path, file_key)
