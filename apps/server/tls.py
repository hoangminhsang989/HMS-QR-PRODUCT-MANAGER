"""Locally generated self-signed TLS so phone cameras work over the private LAN.

The certificate is created on Machine 1 by the Server Tool with the bundled
``cryptography`` wheel.  Nothing is downloaded and no external certificate
authority is involved; phones trust the certificate once through the browser
warning, then ``getUserMedia`` is allowed because the page is a secure context.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import ipaddress
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


CERTIFICATE_VALID_DAYS = 3650
KEY_SIZE = 2048
TLS_CERTIFICATE_ENV = "HMS_QR_TLS_CERT"
TLS_KEY_ENV = "HMS_QR_TLS_KEY"


def production_tls_paths(root: Path) -> dict[str, Path]:
    """Return the fixed local-only TLS layout for Machine 1."""

    tls_root = root / "tls"
    return {
        "certificate": tls_root / "hms-qr-lan.crt.pem",
        "key": tls_root / "hms-qr-lan.key.pem",
    }


def tls_is_enabled(root: Path) -> bool:
    """Report whether a usable local certificate pair is present."""

    paths = production_tls_paths(root)
    return paths["certificate"].is_file() and paths["key"].is_file()


def lan_url_scheme(root: Path | None = None) -> str:
    """Return the scheme the running Server advertises on the LAN.

    With ``root`` the certificate pair on disk decides, which is the same
    signal the Server Tool uses when it starts uvicorn with TLS.  Without it
    the environment of the calling process decides, for code running inside
    the Server itself.
    """

    if root is not None:
        return "https" if tls_is_enabled(root) else "http"
    return "https" if os.environ.get(TLS_CERTIFICATE_ENV) else "http"


def generate_self_signed_certificate(
    certificate_path: Path,
    key_path: Path,
    *,
    hostname: str | None = None,
    lan_addresses: list[str] | None = None,
    valid_days: int = CERTIFICATE_VALID_DAYS,
) -> None:
    """Create a self-signed certificate covering localhost, hostname, and LAN IPs."""

    key = rsa.generate_private_key(public_exponent=65537, key_size=KEY_SIZE)
    common_name = hostname or "HMS QR Server"
    name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "HMS QR"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])
    san_entries: list[x509.GeneralName] = [x509.DNSName("localhost")]
    if hostname:
        san_entries.append(x509.DNSName(hostname))
    for address in lan_addresses or []:
        try:
            san_entries.append(x509.IPAddress(ipaddress.ip_address(address)))
        except ValueError:
            continue
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=valid_days))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    certificate_path.parent.mkdir(parents=True, exist_ok=True)
    certificate_path.write_bytes(
        certificate.public_bytes(serialization.Encoding.PEM)
    )
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )


def ensure_lan_certificate(root: Path, *, lan_addresses: list[str] | None = None) -> dict[str, Path]:
    """Create the certificate pair once; an existing pair is never rotated silently."""

    paths = production_tls_paths(root)
    if not (paths["certificate"].is_file() and paths["key"].is_file()):
        generate_self_signed_certificate(
            paths["certificate"], paths["key"], lan_addresses=lan_addresses
        )
    return paths


def certificate_environment(paths: dict[str, Path]) -> dict[str, str]:
    """Return the uvicorn TLS environment variables for an existing certificate pair."""

    return {
        TLS_CERTIFICATE_ENV: str(paths["certificate"]),
        TLS_KEY_ENV: str(paths["key"]),
    }
