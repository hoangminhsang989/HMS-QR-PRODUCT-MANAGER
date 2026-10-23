from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_STAGE6_DIR = Path(__file__).resolve().parent
for _p in (str(_PROJECT_ROOT), str(_STAGE6_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from conftest import _engine_database

from fastapi.testclient import TestClient

from apps.server.app import SERVER_LICENSE_SERVICE, app
from packages.application.license_service import LicenseError, LicenseService
from packages.contracts.api import (
    LicenseActivatePayload,
    LicenseValidatePayload,
)


def _service(tmp_path, name="license.db"):
    database = _engine_database(tmp_path, name)
    return LicenseService(database)


def _seed_pending_license(
    database,
    *,
    license_key="HMSQR-AAAA-BBBB-CCCC-DDDD",
    customer_email="test@example.com",
    product_tier="standard",
):
    key_id = "key-" + license_key[:8]
    now = datetime.now(timezone.utc).isoformat()
    with database.transaction() as tx:
        tx.execute(
            "INSERT INTO license_keys (key_id, license_key, product_tier, status,"
            " created_at, customer_email)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [key_id, license_key, product_tier, "pending", now, customer_email],
        )


def _seed_active_license(
    database,
    *,
    license_key="HMSQR-AAAA-BBBB-CCCC-DDDD",
    hwid="HWID-001",
    expires_at=None,
    customer_email="test@example.com",
):
    key_id = "key-" + license_key[:8]
    now = datetime.now(timezone.utc).isoformat()
    with database.transaction() as tx:
        tx.execute(
            "INSERT INTO license_keys (key_id, license_key, product_tier, status,"
            " created_at, activated_at, expires_at, customer_email, hwid)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                key_id,
                license_key,
                "standard",
                "active",
                now,
                now,
                expires_at,
                customer_email,
                hwid,
            ],
        )


class TestGenerateLicenseKey:
    def test_generate_returns_formatted_key(self, tmp_path):
        service = _service(tmp_path)
        key = service.generate_license_key(
            customer_email="a@b.com", product_tier="standard"
        )
        assert key.startswith("HMSQR-")
        assert len(key) == len("HMSQR-") + 24

    def test_generate_without_a_payment_id(self, tmp_path):
        """The QR payment flow is gone, so a key no longer needs a payment."""

        service = _service(tmp_path)
        key = service.generate_license_key(customer_email="a@b.com")
        rows = service._db.query(
            "SELECT payment_id FROM license_keys WHERE license_key = ?", [key]
        )
        assert rows[0]["payment_id"] is None

    def test_generate_is_idempotent_per_payment_id(self, tmp_path):
        service = _service(tmp_path)
        first = service.generate_license_key(
            payment_id="pay-y", customer_email="a@b.com"
        )
        second = service.generate_license_key(
            payment_id="pay-y", customer_email="a@b.com"
        )
        assert first == second

    def test_generate_persists_row(self, tmp_path):
        service = _service(tmp_path)
        key = service.generate_license_key(
            customer_email="persist@example.com", product_tier="pro"
        )
        rows = service._db.query(
            "SELECT product_tier, status, customer_email FROM license_keys"
            " WHERE license_key = ?",
            [key],
        )
        assert len(rows) == 1
        assert rows[0]["product_tier"] == "pro"
        assert rows[0]["status"] == "pending"
        assert rows[0]["customer_email"] == "persist@example.com"


class TestActivateLicense:
    def test_activate_invalid_key_raises(self, tmp_path):
        service = _service(tmp_path)
        with pytest.raises(LicenseError, match="Invalid license key"):
            service.activate_license(license_key="BOGUS", hwid="HW-1")

    def test_activate_pending_succeeds(self, tmp_path):
        service = _service(tmp_path)
        _seed_pending_license(service._db)
        result = service.activate_license(
            license_key="HMSQR-AAAA-BBBB-CCCC-DDDD", hwid="HW-NEW"
        )
        assert result["status"] == "active"
        assert result["hwid"] == "HW-NEW"
        assert result["activated_at"]

    def test_activate_already_active_same_hwid(self, tmp_path):
        service = _service(tmp_path)
        _seed_active_license(service._db, hwid="HW-SAME")
        result = service.activate_license(
            license_key="HMSQR-AAAA-BBBB-CCCC-DDDD", hwid="HW-SAME"
        )
        assert result["status"] == "active"

    def test_activate_already_active_different_hwid_raises(self, tmp_path):
        service = _service(tmp_path)
        _seed_active_license(service._db, hwid="HW-ORIG")
        with pytest.raises(LicenseError, match="another machine"):
            service.activate_license(
                license_key="HMSQR-AAAA-BBBB-CCCC-DDDD", hwid="HW-OTHER"
            )

    def test_activate_non_pending_status_raises(self, tmp_path):
        service = _service(tmp_path)
        _seed_active_license(service._db, hwid="HW-1")
        service._db.execute(
            "UPDATE license_keys SET status = ? WHERE license_key = ?",
            ["revoked", "HMSQR-AAAA-BBBB-CCCC-DDDD"],
        )
        with pytest.raises(LicenseError, match="revoked"):
            service.activate_license(
                license_key="HMSQR-AAAA-BBBB-CCCC-DDDD", hwid="HW-2"
            )

    def test_activate_updates_database(self, tmp_path):
        service = _service(tmp_path)
        _seed_pending_license(service._db)
        service.activate_license(
            license_key="HMSQR-AAAA-BBBB-CCCC-DDDD", hwid="HW-DB"
        )
        rows = service._db.query(
            "SELECT status, hwid FROM license_keys WHERE license_key = ?",
            ["HMSQR-AAAA-BBBB-CCCC-DDDD"],
        )
        assert rows[0]["status"] == "active"
        assert rows[0]["hwid"] == "HW-DB"


class TestValidateLicense:
    def test_validate_invalid_key_raises(self, tmp_path):
        service = _service(tmp_path)
        with pytest.raises(LicenseError, match="Invalid license key"):
            service.validate_license(license_key="BOGUS", hwid="HW-1")

    def test_validate_pending_status_raises(self, tmp_path):
        service = _service(tmp_path)
        _seed_pending_license(service._db)
        with pytest.raises(LicenseError, match="pending"):
            service.validate_license(
                license_key="HMSQR-AAAA-BBBB-CCCC-DDDD", hwid="HW-1"
            )

    def test_validate_hwid_mismatch_raises(self, tmp_path):
        service = _service(tmp_path)
        _seed_active_license(service._db, hwid="HW-A")
        with pytest.raises(LicenseError, match="different machine"):
            service.validate_license(
                license_key="HMSQR-AAAA-BBBB-CCCC-DDDD", hwid="HW-B"
            )

    def test_validate_expired_raises(self, tmp_path):
        service = _service(tmp_path)
        _seed_active_license(
            service._db, hwid="HW-1", expires_at="2020-01-01T00:00:00+00:00"
        )
        with pytest.raises(LicenseError, match="expired"):
            service.validate_license(
                license_key="HMSQR-AAAA-BBBB-CCCC-DDDD", hwid="HW-1"
            )

    def test_validate_active_returns_valid(self, tmp_path):
        service = _service(tmp_path)
        _seed_active_license(service._db, hwid="HW-OK")
        result = service.validate_license(
            license_key="HMSQR-AAAA-BBBB-CCCC-DDDD", hwid="HW-OK"
        )
        assert result["valid"] is True
        assert result["license_key"] == "HMSQR-AAAA-BBBB-CCCC-DDDD"
        assert result["product_tier"] == "standard"
        assert result["status"] == "active"

    def test_validate_active_no_expiry_returns_valid(self, tmp_path):
        service = _service(tmp_path)
        _seed_active_license(service._db, hwid="HW-OK", expires_at=None)
        result = service.validate_license(
            license_key="HMSQR-AAAA-BBBB-CCCC-DDDD", hwid="HW-OK"
        )
        assert result["valid"] is True
        assert result["expires_at"] is None


class TestFullFlow:
    def test_issue_activation_to_validation(self, tmp_path):
        service = _service(tmp_path)
        license_key = service.generate_license_key(customer_email="flow@example.com")
        activated = service.activate_license(
            license_key=license_key, hwid="HW-FLOW"
        )
        assert activated["status"] == "active"
        validated = service.validate_license(license_key=license_key, hwid="HW-FLOW")
        assert validated["valid"] is True
        assert validated["license_key"] == license_key


class TestLicenseApi:
    @pytest.fixture
    def client_and_service(self, tmp_path, monkeypatch):
        database = _engine_database(tmp_path, "api-license.db")
        service = LicenseService(database)
        monkeypatch.setattr("apps.server.app.SERVER_LICENSE_SERVICE", service)
        return TestClient(app), service

    def test_api_validate_success(self, client_and_service):
        client, service = client_and_service
        _seed_active_license(service._db, hwid="HW-API")
        resp = client.post(
            "/api/v1/license/validate",
            json={"license_key": "HMSQR-AAAA-BBBB-CCCC-DDDD", "hwid": "HW-API"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True

    def test_api_validate_invalid_key_returns_400(self, client_and_service):
        client, service = client_and_service
        resp = client.post(
            "/api/v1/license/validate",
            json={"license_key": "BOGUS", "hwid": "HW-1"},
        )
        assert resp.status_code == 400

    def test_api_activate_success(self, client_and_service):
        client, service = client_and_service
        _seed_pending_license(service._db)
        resp = client.post(
            "/api/v1/license/activate",
            json={
                "license_key": "HMSQR-AAAA-BBBB-CCCC-DDDD",
                "hwid": "HW-ACT",
                "customer_email": "act@example.com",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    def test_api_license_service_is_wired_without_payment_config(self):
        """The service no longer takes VietQR credentials."""

        import inspect

        parameters = inspect.signature(LicenseService.__init__).parameters
        assert set(parameters) == {"self", "database"}
        assert SERVER_LICENSE_SERVICE is not None
