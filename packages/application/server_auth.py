"""Server-owned accounts, password verification, and signed access tokens."""

from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import hashlib
import hmac
import json
import os
import secrets
from uuid import uuid4

from packages.persistence.database import DatabaseRuntime


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    VIEWER = "VIEWER"


class AuthenticationError(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _password_hash(password: str, salt: bytes | None = None) -> str:
    if not password and os.environ.get("HMS_QR_ALLOW_EMPTY_PASSWORDS", "").strip().lower() != "true":
        raise ValueError("Mật khẩu trống chỉ được phép khi HMS_QR_ALLOW_EMPTY_PASSWORDS=true.")
    if password and len(password) < 3:
        raise ValueError("Mật khẩu phải có ít nhất 3 ký tự hoặc để trống trong chế độ nội bộ.")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${urlsafe_b64encode(salt).decode()}${urlsafe_b64encode(digest).decode()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        scheme, encoded_salt, encoded_digest = stored.split("$", 2)
        if scheme != "scrypt":
            return False
        salt = urlsafe_b64decode(encoded_salt.encode())
        expected = urlsafe_b64decode(encoded_digest.encode())
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, UnicodeError):
        return False


class ServerAuthService:
    def __init__(self, runtime: DatabaseRuntime, *, token_secret: str | None = None) -> None:
        self.runtime = runtime
        self._token_secret = token_secret or os.environ.get("HMS_QR_AUTH_SECRET", "")

    def require_production_configuration(self) -> None:
        """Fail startup before a LAN server can issue unsigned or empty-password sessions."""
        if self.runtime.config.environment.value == "dev":
            return
        if len(self._token_secret) < 32:
            raise AuthenticationError("HMS_QR_AUTH_SECRET must contain at least 32 characters in production.")
        if os.environ.get("HMS_QR_ALLOW_EMPTY_PASSWORDS", "").strip().lower() == "true":
            raise AuthenticationError("Empty passwords are not allowed outside the DEV environment.")

    def bootstrap_admin(self) -> None:
        username = os.environ.get("HMS_QR_BOOTSTRAP_ADMIN_USERNAME", "").strip()
        password = os.environ.get("HMS_QR_BOOTSTRAP_ADMIN_PASSWORD", "")
        with self.runtime.database.transaction() as transaction:
            existing = transaction.execute(
                "SELECT internal_id FROM user_accounts LIMIT 1"
            )
            if existing:
                return
            if not username:
                raise AuthenticationError("Server has no administrator account. Configure bootstrap admin credentials.")
            self._validate_username(username)
            transaction.execute(
                "INSERT INTO user_accounts (internal_id, username, password_hash, role,"
                " active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    str(uuid4()), username.casefold(), _password_hash(password),
                    UserRole.ADMIN.value, True, _now(), _now(),
                ],
            )

    @staticmethod
    def _validate_username(username: str) -> None:
        if not 3 <= len(username) <= 64 or not all(char.isalnum() or char in "._-" for char in username):
            raise ValueError("Tên đăng nhập chỉ gồm chữ, số, dấu chấm, gạch dưới hoặc gạch ngang.")

    def login(self, username: str, password: str) -> dict[str, str]:
        if not self._token_secret:
            raise AuthenticationError("Server authentication is not configured.")
        if not password and os.environ.get("HMS_QR_ALLOW_EMPTY_PASSWORDS", "").strip().lower() != "true":
            raise AuthenticationError("Đăng nhập không mật khẩu chưa được bật trên server nội bộ.")
        rows = self.runtime.database.query(
            "SELECT internal_id, username, password_hash, role, active FROM user_accounts"
            " WHERE username = ?",
            [username.strip().casefold()],
        )
        account = rows[0] if rows else None
        if account is None or not account["active"] or not _verify_password(password, account["password_hash"]):
            raise AuthenticationError("Tên đăng nhập hoặc mật khẩu không đúng.")
        return {
            "access_token": self._issue(account),
            "token_type": "bearer",
            "role": account["role"],
            "username": account["username"],
        }

    def _issue(self, account) -> str:
        payload = {
            "sub": account["internal_id"],
            "usr": account["username"],
            "role": account["role"],
            "exp": int((_now() + timedelta(hours=8)).timestamp()),
        }
        encoded = urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
        signature = hmac.new(self._token_secret.encode(), encoded.encode(), hashlib.sha256).digest()
        return f"{encoded}.{urlsafe_b64encode(signature).decode().rstrip('=')}"

    def authenticate(self, token: str) -> dict[str, str]:
        if not self._token_secret:
            raise AuthenticationError("Server authentication is not configured.")
        try:
            encoded, given = token.split(".", 1)
            expected = hmac.new(self._token_secret.encode(), encoded.encode(), hashlib.sha256).digest()
            if not hmac.compare_digest(expected, urlsafe_b64decode(given + "=" * (-len(given) % 4))):
                raise AuthenticationError("Phiên đăng nhập không hợp lệ.")
            payload = json.loads(urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            if int(payload["exp"]) <= int(_now().timestamp()):
                raise AuthenticationError("Phiên đăng nhập đã hết hạn.")
            rows = self.runtime.database.query(
                "SELECT internal_id, username, role, active FROM user_accounts"
                " WHERE internal_id = ?",
                [payload["sub"]],
            )
            if not rows or not rows[0]["active"]:
                raise AuthenticationError("Tài khoản không còn hoạt động.")
            account = rows[0]
            return {
                "internal_id": account["internal_id"],
                "username": account["username"],
                "role": account["role"],
            }
        except AuthenticationError:
            raise
        except (KeyError, ValueError, UnicodeError, json.JSONDecodeError):
            raise AuthenticationError("Phiên đăng nhập không hợp lệ.") from None

    def list_accounts(self) -> list[dict[str, object]]:
        rows = self.runtime.database.query(
            "SELECT internal_id, username, role, active FROM user_accounts"
            " ORDER BY username ASC, internal_id ASC"
        )
        return [
            {
                "internal_id": row["internal_id"],
                "username": row["username"],
                "role": row["role"],
                "active": row["active"],
            }
            for row in rows
        ]

    def create_account(self, username: str, password: str, role: str) -> dict[str, object]:
        self._validate_username(username)
        parsed_role = UserRole(role)
        with self.runtime.database.transaction() as transaction:
            duplicate = transaction.execute(
                "SELECT internal_id FROM user_accounts WHERE username = ?",
                [username.casefold()],
            )
            if duplicate:
                raise ValueError("Tên đăng nhập đã tồn tại.")
            account = {
                "internal_id": str(uuid4()),
                "username": username.casefold(),
                "role": parsed_role.value,
                "active": True,
            }
            transaction.execute(
                "INSERT INTO user_accounts (internal_id, username, password_hash, role,"
                " active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    account["internal_id"], account["username"], _password_hash(password),
                    account["role"], True, _now(), _now(),
                ],
            )
        return account

    def update_account(
        self,
        identifier: str,
        *,
        username: str | None = None,
        active: bool | None = None,
        role: str | None = None,
        password: str | None = None,
    ) -> dict[str, object]:
        with self.runtime.database.transaction() as transaction:
            rows = transaction.execute(
                "SELECT internal_id, username, role, active, password_hash"
                " FROM user_accounts WHERE internal_id = ?",
                [identifier],
            )
            if not rows:
                raise ValueError("Không tìm thấy tài khoản.")
            account = rows[0]
            next_username = account["username"] if username is None else username.casefold().strip()
            if username is not None:
                self._validate_username(next_username)
                duplicate = transaction.execute(
                    "SELECT internal_id FROM user_accounts WHERE username = ?"
                    " AND internal_id != ?",
                    [next_username, identifier],
                )
                if duplicate:
                    raise ValueError("Tên đăng nhập đã tồn tại.")
            next_active = account["active"] if active is None else active
            next_role = account["role"] if role is None else UserRole(role).value
            removes_admin_access = (
                account["active"]
                and account["role"] == UserRole.ADMIN.value
                and (not next_active or next_role != UserRole.ADMIN.value)
            )
            if removes_admin_access:
                active_admins = len(transaction.execute(
                    "SELECT internal_id FROM user_accounts WHERE active = ? AND role = ?",
                    [True, UserRole.ADMIN.value],
                ))
                if active_admins <= 1:
                    raise ValueError("Không thể vô hiệu hóa hoặc hạ quyền quản trị viên cuối cùng.")
            transaction.execute(
                "UPDATE user_accounts SET username = ?, role = ?, active = ?,"
                " password_hash = ?, updated_at = ? WHERE internal_id = ?",
                [
                    next_username, next_role, next_active,
                    _password_hash(password) if password is not None else account["password_hash"],
                    _now(), identifier,
                ],
            )
        return {
            "internal_id": identifier,
            "username": next_username,
            "role": next_role,
            "active": next_active,
        }

    def settings(self) -> dict[str, str]:
        rows = self.runtime.database.query(
            "SELECT setting_key, setting_value FROM server_settings"
        )
        return {row["setting_key"]: row["setting_value"] for row in rows}

    def update_settings(self, values: dict[str, str]) -> None:
        allowed = {"site_title", "site_message"}
        if set(values) - allowed:
            raise ValueError("Cài đặt không hợp lệ.")
        with self.runtime.database.transaction() as transaction:
            for key, value in values.items():
                current = transaction.execute(
                    "SELECT setting_key FROM server_settings WHERE setting_key = ?", [key]
                )
                if not current:
                    transaction.execute(
                        "INSERT INTO server_settings (setting_key, setting_value, updated_at)"
                        " VALUES (?, ?, ?)",
                        [key, str(value)[:500], _now()],
                    )
                else:
                    transaction.execute(
                        "UPDATE server_settings SET setting_value = ?, updated_at = ?"
                        " WHERE setting_key = ?",
                        [str(value)[:500], _now(), key],
                    )


__all__ = ["AuthenticationError", "ServerAuthService", "UserRole"]
