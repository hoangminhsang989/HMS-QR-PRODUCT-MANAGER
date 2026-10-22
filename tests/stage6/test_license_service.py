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
from packages.application.license_service import (
    LicenseError,
    LicenseService,
    PaymentError,
)
from packages.contracts.api import (
    LicenseActivatePayload,
    LicenseValidatePayload,
    PaymentCreatePayload,
    PaymentWebhookPayload,
)


def _service(tmp_path, name="license.db"):
    database = _engine_database(tmp_path, name)
    return LicenseService(database)


def _seed_pending_license(
    database,
    *,
    license_key="HMSQR-AAAA-BBBB-CCCC-DDDD",
    payment_id="pay-001",
    customer_email="test@example.com",
    product_tier="standard",
):
    key_id = "key-" + license_key[:8]
    now = datetime.now(timezone.utc).isoformat()
    with database.transaction() as tx:
        tx.execute(
            "INSERT INTO license_keys (key_id, license_key, product_tier, status,"
            " created_at, customer_email, payment_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            [key_id, license_key, product_tier, "pending", now, customer_email, payment_id],
        )


def _seed_active_license(
    database,
    *,
    license_key="HMSQR-AAAA-BBBB-CCCC-DDDD",
    hwid="HWID-001",
    expires_at=None,
    customer_email="test@example.com",
    payment_id="pay-001",
):
    key_id = "key-" + license_key[:8]
    now = datetime.now(timezone.utc).isoformat()
    with database.transaction() as tx:
        tx.execute(
            "INSERT INTO license_keys (key_id, license_key, product_tier, status,"
            " created_at, activated_at, expires_at, customer_email, payment_id, hwid)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                key_id,
                license_key,
                "standard",
                "active",
                now,
                now,
                expires_at,
                customer_email,
                payment_id,
                hwid,
            ],
        )


class TestCreatePayment:
    def test_create_payment_returns_qr_payload(self, tmp_path):
        service = _service(tmp_path)
        result = service.create_payment(
            customer_email="buyer@example.com", amount=500000, product_tier="standard"
        )
        assert result["amount"] == 500000
        assert result["currency"] == "VND"
        assert result["status"] == "pending"
        assert result["customer_email"] == "buyer@example.com"
        assert result["vietqr_reference"]
        assert result["qr_payload"].startswith("https://img.vietqr.io/image/")
        assert result["payment_id"]

    def test_create_payment_persists_row(self, tmp_path):
        service = _service(tmp_path)
        result = service.create_payment(
            customer_email="buyer@example.com", amount=250000
        )
        rows = service._db.query(
            "SELECT * FROM payments WHERE payment_id = ?", [result["payment_id"]]
        )
        assert len(rows) == 1
        assert rows[0]["amount"] == 250000
        assert rows[0]["status"] == "pending"

    def test_create_payment_reference_matches_payment_id(self, tmp_path):
        service = _service(tmp_path)
        result = service.create_payment(
            customer_email="buyer@example.com", amount=100000
        )
        assert result["vietqr_reference"] == result["payment_id"][:8].upper()


class TestConfirmPayment:
    def test_confirm_unknown_payment_raises(self, tmp_path):
        service = _service(tmp_path)
        with pytest.raises(PaymentError, match="Payment not found"):
            service.confirm_payment(payment_id="nope", webhook_payload="{}")

    def test_confirm_payment_generates_license(self, tmp_path):
        service = _service(tmp_path)
        payment = service.create_payment(
            customer_email="buyer@example.com", amount=500000
        )
        result = service.confirm_payment(
            payment_id=payment["payment_id"], webhook_payload='{"status":"success"}'
        )
        assert result["status"] == "confirmed"
        assert result["license_key"].startswith("HMSQR-")

    def test_confirm_payment_twice_returns_same_license(self, tmp_path):
        service = _service(tmp_path)
        payment = service.create_payment(
            customer_email="buyer@example.com", amount=500000
        )
        first = service.confirm_payment(
            payment_id=payment["payment_id"], webhook_payload="{}"
        )
        second = service.confirm_payment(
            payment_id=payment["payment_id"], webhook_payload="{}"
        )
        assert first["license_key"] == second["license_key"]


class TestGenerateLicenseKey:
    def test_generate_returns_formatted_key(self, tmp_path):
        service = _service(tmp_path)
        key = service.generate_license_key(
            payment_id="pay-x", customer_email="a@b.com", product_tier="standard"
        )
        assert key.startswith("HMSQR-")
        assert len(key) == len("HMSQR-") + 24

    def test_generate_existing_payment_returns_same_key(self, tmp_path):
        service = _service(tmp_path)
        first = service.generate_license_key(
            payment_id="pay-y", customer_email="a@b.com"
        )
        second = service.generate_license_key(
            payment_id="pay-y", customer_email="a@b.com"
        )
        assert first == second


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
    def test_payment_to_activation_to_validation(self, tmp_path):
        service = _service(tmp_path)
        payment = service.create_payment(
            customer_email="flow@example.com", amount=500000
        )
        confirmed = service.confirm_payment(
            payment_id=payment["payment_id"], webhook_payload='{"ok":true}'
        )
        license_key = confirmed["license_key"]
        activated = service.activate_license(
            license_key=license_key, hwid="HW-FLOW"
        )
        assert activated["status"] == "active"
        validated = service.validate_license(
            license_key=license_key, hwid="HW-FLOW"
        )
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

    def test_api_payment_create(self, client_and_service):
        client, service = client_and_service
        resp = client.post(
            "/api/v1/payments/create",
            json={
                "amount": 500000,
                "customer_email": "api@example.com",
                "product_tier": "standard",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["amount"] == 500000
        assert body["currency"] == "VND"
        assert body["qr_payload"].startswith("https://")

    def test_api_webhook_confirms_and_returns_license(self, client_and_service):
        client, service = client_and_service
        payment = service.create_payment(
            customer_email="hook@example.com", amount=500000
        )
        resp = client.post(
            "/api/v1/payments/webhook",
            json={
                "payment_id": payment["payment_id"],
                "status": "success",
                "amount": 500000,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "confirmed"
        assert body["license_key"].startswith("HMSQR-")

    def test_api_webhook_unknown_payment_returns_400(self, client_and_service):
        client, service = client_and_service
        resp = client.post(
            "/api/v1/payments/webhook",
            json={"payment_id": "nope", "status": "success", "amount": 100000},
        )
        assert resp.status_code == 400


class TestVietQrConfig:
    def test_env_vars_used_when_no_explicit_args(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HMS_QR_VIETQR_BANK_ID", "TESTBANK")
        monkeypatch.setenv("HMS_QR_VIETQR_ACCOUNT_NUMBER", "1234567890")
        monkeypatch.setenv("HMS_QR_VIETQR_ACCOUNT_NAME", "Test Account")
        service = _service(tmp_path)
        result = service.create_payment(customer_email="test@example.com", amount=100000)
        assert "TESTBANK" in result["qr_payload"]
        assert "1234567890" in result["qr_payload"]
        assert "Test Account" in result["qr_payload"]
