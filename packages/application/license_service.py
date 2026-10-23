from __future__ import annotations

import secrets
from datetime import datetime, timezone
from uuid import uuid4


class LicenseError(Exception):
    pass


class LicenseService:
    """Issues and validates license keys.

    There is no payment path here. LO asked for the VietQR QR-payment code to be
    removed, and with it the ``payments`` table, the two payment routes and the
    portal's payment tab. What is left is the license system itself, because the
    portal's "KICH HOAT BAN QUYEN" tab still needs a key to activate.

    Consequence worth knowing: with no payment flow there is no self-service way
    to obtain a key. ``generate_license_key`` is the only issuer and it takes an
    optional ``payment_id`` that is stored for reference only - nothing reads it
    back and no table constrains it. A key is issued by whoever can call this
    method.
    """

    def __init__(self, database) -> None:
        self._db = database

    def generate_license_key(
        self,
        *,
        payment_id: str | None = None,
        customer_email: str,
        product_tier: str = "standard",
    ) -> str:
        if payment_id is not None:
            existing = self._db.query(
                "SELECT license_key FROM license_keys WHERE payment_id = ?",
                [payment_id],
            )
            if existing:
                return existing[0]["license_key"]
        key_id = str(uuid4())
        license_key = self._format_key()
        now = datetime.now(timezone.utc).isoformat()
        with self._db.transaction() as tx:
            tx.execute(
                "INSERT INTO license_keys (key_id, license_key, product_tier, status, "
                "created_at, customer_email, payment_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    key_id,
                    license_key,
                    product_tier,
                    "pending",
                    now,
                    customer_email,
                    payment_id,
                ],
            )
        return license_key

    def validate_license(self, *, license_key: str, hwid: str) -> dict:
        rows = self._db.query(
            "SELECT key_id, license_key, product_tier, status, activated_at, "
            "expires_at, customer_email, hwid FROM license_keys WHERE license_key = ?",
            [license_key],
        )
        if not rows:
            raise LicenseError("Invalid license key")
        lic = rows[0]
        if lic["status"] != "active":
            raise LicenseError(f"License is {lic['status']}")
        if lic["hwid"] and lic["hwid"] != hwid:
            raise LicenseError("License bound to different machine")
        if lic["expires_at"]:
            # The engine deserializes DATETIME columns to tz-aware ``datetime``
            # objects and rejects non-ISO text on write, so the comparison below
            # is always between two aware datetimes.
            if lic["expires_at"] < datetime.now(timezone.utc):
                raise LicenseError("License expired")
        return {
            "valid": True,
            "license_key": lic["license_key"],
            "product_tier": lic["product_tier"],
            "status": lic["status"],
            "expires_at": lic["expires_at"],
        }

    def activate_license(
        self,
        *,
        license_key: str,
        hwid: str,
        customer_email: str | None = None,
    ) -> dict:
        rows = self._db.query(
            "SELECT key_id, license_key, status, hwid, customer_email, activated_at "
            "FROM license_keys WHERE license_key = ?",
            [license_key],
        )
        if not rows:
            raise LicenseError("Invalid license key")
        lic = rows[0]
        if lic["status"] == "active" and lic["hwid"] == hwid:
            return {"status": "active", "license_key": license_key}
        if lic["status"] == "active" and lic["hwid"] != hwid:
            raise LicenseError("License already activated on another machine")
        if lic["status"] != "pending":
            raise LicenseError(f"License is {lic['status']}")
        now = datetime.now(timezone.utc).isoformat()
        email = customer_email or lic["customer_email"]
        with self._db.transaction() as tx:
            tx.execute(
                "UPDATE license_keys SET status = ?, activated_at = ?, hwid = ?, "
                "customer_email = ? WHERE key_id = ?",
                ["active", now, hwid, email, lic["key_id"]],
            )
        return {
            "status": "active",
            "license_key": license_key,
            "activated_at": now,
            "hwid": hwid,
        }

    @staticmethod
    def _format_key() -> str:
        raw = secrets.token_hex(10).upper()
        parts = [raw[i : i + 4] for i in range(0, 20, 4)]
        return "HMSQR-" + "-".join(parts)
