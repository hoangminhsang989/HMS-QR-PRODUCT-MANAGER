"""Payload serialization and status policy for signed licenses."""

import base64
import json
from dataclasses import dataclass

from hms_license.crypto import sign, verify

GRACE_DAYS: int = 5


class InvalidSignature(Exception):
    """Raised when a signed license cannot be verified or decoded."""


@dataclass
class LicensePayload:
    key_id: int
    product: str
    hwid: str
    max_devices: int
    expires_at: int | None
    issued_at: int


def canonical_json(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_payload(key_id, product, hwid, max_devices, expires_at, issued_at) -> dict:
    return {
        "key_id": key_id,
        "product": product,
        "hwid": hwid,
        "max_devices": max_devices,
        "expires_at": expires_at,
        "issued_at": issued_at,
    }


def sign_payload(payload: dict, private_pem: bytes) -> dict:
    signature = sign(canonical_json(payload), private_pem)
    return {"payload": payload, "signature": base64.b64encode(signature).decode("ascii")}


def load_signed(signed: dict, public_pem: bytes) -> LicensePayload:
    try:
        payload = signed["payload"]
        signature = base64.b64decode(signed["signature"], validate=True)
        if not isinstance(payload, dict) or not verify(canonical_json(payload), signature, public_pem):
            raise InvalidSignature("license signature is invalid")
        return LicensePayload(**payload)
    except InvalidSignature:
        raise
    except Exception as exc:
        raise InvalidSignature("signed license is invalid") from exc


def license_status(payload: LicensePayload, now: int, revoked: bool) -> str:
    if revoked:
        return "revoked"
    if payload.expires_at is None or now <= payload.expires_at:
        return "ok"
    if now <= payload.expires_at + GRACE_DAYS * 86400:
        return "grace"
    return "expired"
