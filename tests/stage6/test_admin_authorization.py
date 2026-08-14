import inspect
import os
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from apps.server.files import build_files_api
from config.environments import AppConfig, Environment, load_config
from packages.domain.store_forward import StorageCapacity


CONFIG_PAYLOAD = {
    "local_ingest_root": r"F:\machine-a-local",
    "archive_target_root": r"\\archive-server\hms-qr",
    "grace_period_hours": 24,
    "retry_schedule_seconds": [60, 300],
    "warning_free_bytes": 300,
    "critical_free_bytes": 200,
    "upload_refusal_free_bytes": 100,
}
FILE_ID = UUID("00000000-0000-0000-0000-000000000901")


def _config(environment: Environment) -> AppConfig:
    return AppConfig(
        environment=environment,
        database_url="sqlite:///explicit-auth-test.sqlite",
        storage_backend="configured",
    )


class _ManagedSpy:
    repository = object()


class _RepositorySpy:
    def get_active_configuration(self):
        raise AssertionError("admin handler must not execute")


class _TransferSpy:
    def __init__(self):
        self.repository = _RepositorySpy()
        self.configure_count = 0
        self.retry_count = 0
        self.run_count = 0
        self.purge_count = 0

    @property
    def mutation_count(self):
        return self.configure_count + self.retry_count + self.run_count + self.purge_count

    def configure(self, configuration, *, validate_write=False):
        self.configure_count += 1
        return configuration

    def retry_now(self, _file_id):
        self.retry_count += 1
        raise AssertionError("response body is irrelevant to auth test")

    def transfer_one(self, *, worker_id):
        self.run_count += 1
        return None

    def purge_ready_local_copies(self):
        self.purge_count += 1
        return ()

    def health(self):
        return {
            "local": {"state": "UNAVAILABLE", "writable": False},
            "archive": {"state": "UNAVAILABLE", "writable": False},
            "capacity": StorageCapacity(0, 0, 0, 0, 0, None, "UPLOAD_REFUSAL"),
            "last_successful_transfer": None,
        }


def _client(environment, transfer, *, authorizer=None):
    return TestClient(build_files_api(
        _ManagedSpy(), transfer,
        app_config=_config(environment),
        admin_authorizer=authorizer,
    ))


def _put_configuration(client, **headers):
    return client.put(
        "/api/v1/admin/storage/configuration",
        json=CONFIG_PAYLOAD,
        headers=headers,
    )


def test_explicit_dev_header_allowed_and_missing_header_denied():
    transfer = _TransferSpy()
    with _client(Environment.DEV, transfer) as client:
        denied = _put_configuration(client)
        allowed = _put_configuration(client, **{"x-storage-admin": "true"})
    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert transfer.configure_count == 1


@pytest.mark.parametrize("environment", [Environment.STAGING, Environment.PROD])
def test_missing_real_auth_backend_fails_closed_before_all_mutating_handlers(environment):
    transfer = _TransferSpy()
    header = {"x-storage-admin": "true"}
    with _client(environment, transfer) as client:
        responses = (
            client.put("/api/v1/admin/storage/configuration", json=CONFIG_PAYLOAD, headers=header),
            client.post(f"/api/v1/admin/transfers/{FILE_ID}/retry", headers=header),
            client.post("/api/v1/admin/transfers/run-once", headers=header),
            client.post("/api/v1/admin/purge", headers=header),
        )
    assert [response.status_code for response in responses] == [503, 503, 503, 503]
    assert transfer.mutation_count == 0
    for response in responses:
        body = response.json()
        assert body["detail"]["code"] == "PRODUCTION_ADMIN_AUTH_NOT_CONFIGURED"
        assert "F:\\" not in str(body) and "archive-server" not in str(body)


def test_prod_authority_is_frozen_against_post_build_environment_mutation(monkeypatch):
    prod_transfer = _TransferSpy()
    prod_api = build_files_api(
        _ManagedSpy(), prod_transfer, app_config=_config(Environment.PROD)
    )
    monkeypatch.setenv("HMS_QR_ENV", "dev")
    with TestClient(prod_api) as client:
        denied = _put_configuration(client, **{"x-storage-admin": "true"})
    assert denied.status_code == 503
    assert prod_transfer.configure_count == 0

    dev_transfer = _TransferSpy()
    dev_api = build_files_api(
        _ManagedSpy(), dev_transfer, app_config=_config(Environment.DEV)
    )
    monkeypatch.setenv("HMS_QR_ENV", "prod")
    with TestClient(dev_api) as client:
        allowed = _put_configuration(client, **{"x-storage-admin": "true"})
    assert allowed.status_code == 200
    assert dev_transfer.configure_count == 1


def test_zero_arg_default_dev_cannot_override_explicit_prod():
    assert load_config().environment is Environment.DEV
    transfer = _TransferSpy()
    with _client(Environment.PROD, transfer) as client:
        response = _put_configuration(client, **{"x-storage-admin": "true"})
    assert response.status_code == 503
    assert transfer.configure_count == 0


def test_prod_real_authorizer_positive_allows_mutation():
    transfer = _TransferSpy()
    seen = []

    def authorize(request):
        seen.append(request.url.path)
        return True

    with _client(Environment.PROD, transfer, authorizer=authorize) as client:
        response = _put_configuration(client, **{"x-storage-admin": "true"})
    assert response.status_code == 200
    assert transfer.configure_count == 1
    assert seen == ["/api/v1/admin/storage/configuration"]


def test_prod_real_authorizer_negative_denies_before_mutation():
    transfer = _TransferSpy()
    with _client(Environment.PROD, transfer, authorizer=lambda _request: False) as client:
        response = _put_configuration(client, **{"x-storage-admin": "true"})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "STORAGE_ADMIN_FORBIDDEN"
    assert transfer.configure_count == 0


def test_client_environment_spoof_headers_cannot_override_prod_authority():
    transfer = _TransferSpy()
    with _client(Environment.PROD, transfer) as client:
        response = _put_configuration(client, **{
            "x-storage-admin": "true",
            "x-environment": "dev",
            "x-app-env": "dev",
        })
    assert response.status_code == 503
    assert transfer.configure_count == 0


def test_authorizer_failure_is_bounded_and_secret_free():
    transfer = _TransferSpy()

    def broken(_request):
        raise RuntimeError(r"secret at F:\private\archive")

    with _client(Environment.PROD, transfer, authorizer=broken) as client:
        response = _put_configuration(client)
    assert response.status_code == 503
    rendered = str(response.json())
    assert response.json()["detail"]["code"] == "ADMIN_AUTHORIZATION_UNAVAILABLE"
    assert "secret" not in rendered.lower() and "F:\\" not in rendered
    assert transfer.configure_count == 0


def test_admin_route_boundary_audit_has_four_mutations_and_no_zero_arg_config_load():
    import apps.server.files as files_module

    source = inspect.getsource(files_module)
    assert "load_config(" not in source
    transfer = _TransferSpy()
    api = build_files_api(
        _ManagedSpy(), transfer, app_config=_config(Environment.PROD)
    )
    mutating = {
        (method, route.path)
        for route in api.routes
        for method in getattr(route, "methods", set())
        if method in {"POST", "PUT", "PATCH", "DELETE"}
        and route.path.startswith("/api/v1/admin/")
    }
    assert mutating == {
        ("POST", "/api/v1/admin/transfers/{file_id}/retry"),
        ("POST", "/api/v1/admin/transfers/run-once"),
        ("POST", "/api/v1/admin/purge"),
        ("PUT", "/api/v1/admin/storage/configuration"),
    }
