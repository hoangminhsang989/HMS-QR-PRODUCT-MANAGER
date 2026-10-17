"""LAN TLS: locally generated self-signed certificate for phone camera access."""

from __future__ import annotations

import json
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
import pytest

from apps.server.tls import (
    TLS_CERTIFICATE_ENV,
    TLS_KEY_ENV,
    certificate_environment,
    ensure_lan_certificate,
    generate_self_signed_certificate,
    lan_url_scheme,
    production_tls_paths,
    tls_is_enabled,
)
from packages.application.server_discovery import DiscoveryResponder, lan_scheme


def test_generated_certificate_covers_localhost_and_lan_addresses(tmp_path):
    certificate_path = tmp_path / "tls" / "hms-qr-lan.crt.pem"
    key_path = tmp_path / "tls" / "hms-qr-lan.key.pem"

    generate_self_signed_certificate(
        certificate_path, key_path, hostname="MACHINE-1", lan_addresses=["192.168.1.50", "not-an-ip"]
    )

    certificate = x509.load_pem_x509_certificate(certificate_path.read_bytes())
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    assert key.key_size == 2048
    san = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    names = {("DNS", "localhost"), ("DNS", "MACHINE-1"), ("IP", "192.168.1.50")}
    assert {(kind, str(value)) for kind, value in ((entry.__class__.__name__ and ("DNS" if isinstance(entry, x509.DNSName) else "IP"), entry.value) for entry in san)} >= names
    common_names = certificate.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
    assert common_names[0].value == "MACHINE-1"


def test_ensure_lan_certificate_is_idempotent_and_reports_enabled(tmp_path):
    assert not tls_is_enabled(tmp_path)
    first = ensure_lan_certificate(tmp_path, lan_addresses=["192.168.1.50"])
    assert tls_is_enabled(tmp_path)
    assert first["certificate"].read_bytes() == production_tls_paths(tmp_path)["certificate"].read_bytes()

    second = ensure_lan_certificate(tmp_path, lan_addresses=["10.0.0.5"])
    assert second["certificate"].read_bytes() == first["certificate"].read_bytes()


def test_certificate_environment_and_scheme_helpers(tmp_path, monkeypatch):
    paths = ensure_lan_certificate(tmp_path)
    environment = certificate_environment(paths)
    assert environment == {TLS_CERTIFICATE_ENV: str(paths["certificate"]), TLS_KEY_ENV: str(paths["key"])}

    monkeypatch.delenv(TLS_CERTIFICATE_ENV, raising=False)
    assert lan_url_scheme() == "http"
    assert lan_scheme() == "http"
    monkeypatch.setenv(TLS_CERTIFICATE_ENV, str(paths["certificate"]))
    assert lan_url_scheme() == "https"
    assert lan_scheme() == "https"


def test_discovery_responder_advertises_https_when_tls_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv(TLS_CERTIFICATE_ENV, str(tmp_path / "cert.pem"))
    assert DiscoveryResponder().scheme == "https"
    monkeypatch.delenv(TLS_CERTIFICATE_ENV)
    assert DiscoveryResponder().scheme == "http"
    assert DiscoveryResponder(scheme="https").scheme == "https"


def test_production_server_environment_includes_tls_when_enabled(tmp_path, monkeypatch):
    from apps.server import tool

    root = tmp_path / "HMS-QR-PROD"
    secrets_path = root / "server-tool-secrets.json"
    monkeypatch.setattr(tool, "load_server_secret", lambda name, _path=None: f"secret-{name}")
    environment = tool.production_server_environment(root, secrets_path)
    assert environment["HMS_QR_DATABASE_URL"].startswith("sqlite:///")
    assert TLS_CERTIFICATE_ENV not in environment

    ensure_lan_certificate(root)
    environment = tool.production_server_environment(root, secrets_path)
    assert environment[TLS_CERTIFICATE_ENV].endswith("hms-qr-lan.crt.pem")
    assert environment[TLS_KEY_ENV].endswith("hms-qr-lan.key.pem")


def test_production_launcher_passes_tls_to_uvicorn(tmp_path, monkeypatch):
    import apps.server.production_launcher as launcher

    captured: dict[str, object] = {}

    class _Uvicorn:
        @staticmethod
        def run(app, **kwargs):
            captured["app"] = app
            captured.update(kwargs)

    monkeypatch.setattr(launcher, "uvicorn", _Uvicorn)
    monkeypatch.setattr(launcher, "production_server_environment", lambda: {"HMS_QR_TLS_CERT": str(tmp_path / "cert.pem"), "HMS_QR_TLS_KEY": str(tmp_path / "key.pem")})
    launcher.main()
    assert captured["ssl_certfile"] == str(tmp_path / "cert.pem")
    assert captured["ssl_keyfile"] == str(tmp_path / "key.pem")


def test_lan_urlopen_accepts_self_signed_https(tmp_path):
    import http.server
    import threading

    from packages.application.lan_transport import lan_urlopen

    certificate = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    generate_self_signed_certificate(certificate, key, hostname="localhost")

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - http.server API
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"lan-ok")

        def log_message(self, *_args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    context = __import__("ssl").SSLContext(__import__("ssl").PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=certificate, keyfile=key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with lan_urlopen(f"https://127.0.0.1:{server.server_port}/health", timeout=5) as response:
            assert response.read() == b"lan-ok"
    finally:
        server.shutdown()
        server.server_close()
