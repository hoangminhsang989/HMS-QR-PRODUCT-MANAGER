from __future__ import annotations

import secrets
from datetime import datetime, timezone
from uuid import uuid4


class LicenseError(Exception):
    pass


class PaymentError(Exception):
    pass


class LicenseService:
    def __init__(
        self,
        database,
        *,
        bank_id: str = "",
        account_number: str = "",
        account_name: str = "",
        template: str = "compact",
    ) -> None:
        self._db = database
        self._bank_id = bank_id
        self._account_number = account_number
        self._account_name = account_name
        self._template = template

    def create_payment(
        self,
        *,
        customer_email: str,
        amount: int,
        product_tier: str = "standard",
    ) -> dict:
        payment_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        vietqr_reference = payment_id[:8].upper()
        qr_payload = self._build_vietqr_url(amount, vietqr_reference)
        with self._db.transaction() as tx:
            tx.execute(
                "INSERT INTO payments (payment_id, amount, currency, status, "
                "vietqr_reference, qr_payload, created_at, customer_email) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    payment_id,
                    amount,
                    "VND",
                    "pending",
                    vietqr_reference,
                    qr_payload,
                    now,
                    customer_email,
                ],
            )
        return {
            "payment_id": payment_id,
            "amount": amount,
            "currency": "VND",
            "status": "pending",
            "vietqr_reference": vietqr_reference,
            "qr_payload": qr_payload,
            "created_at": now,
            "customer_email": customer_email,
        }

    def confirm_payment(self, *, payment_id: str, webhook_payload: str) -> dict:
        rows = self._db.query(
            "SELECT payment_id, amount, currency, status, created_at, customer_email "
            "FROM payments WHERE payment_id = ?",
            [payment_id],
        )
        if not rows:
            raise PaymentError(f"Payment not found: {payment_id}")
        payment = rows[0]
        if payment["status"] == "confirmed":
            existing = self._db.query(
                "SELECT license_key FROM license_keys WHERE payment_id = ?",
                [payment_id],
            )
            return {
                "payment_id": payment_id,
                "status": "confirmed",
                "license_key": existing[0]["license_key"] if existing else None,
            }
        now = datetime.now(timezone.utc).isoformat()
        with self._db.transaction() as tx:
            tx.execute(
                "UPDATE payments SET status = ?, confirmed_at = ?, webhook_payload = ? "
                "WHERE payment_id = ?",
                ["confirmed", now, webhook_payload, payment_id],
            )
        license_key = self.generate_license_key(
            payment_id=payment_id,
            customer_email=payment["customer_email"],
            product_tier="standard",
        )
        return {
            "payment_id": payment_id,
            "status": "confirmed",
            "confirmed_at": now,
            "license_key": license_key,
        }

    def generate_license_key(
        self,
        *,
        payment_id: str,
        customer_email: str,
        product_tier: str = "standard",
    ) -> str:
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
            expires = lic["expires_at"]
            if isinstance(expires, str):
                expires = datetime.fromisoformat(expires)
            if expires < datetime.now(timezone.utc):
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

    def _build_vietqr_url(self, amount: int, reference: str) -> str:
        add_info = f"HMSQR {reference}"
        return (
            f"https://img.vietqr.io/image/"
            f"{self._bank_id}-{self._account_number}-{self._template}.png"
            f"?amount={amount}&addInfo={add_info}&accountName={self._account_name}"
        )

    @staticmethod
    def _format_key() -> str:
        raw = secrets.token_hex(10).upper()
        parts = [raw[i : i + 4] for i in range(0, 20, 4)]
        return "HMSQR-" + "-".join(parts)
