"""Read-only physical LAN acceptance check intended to run on Machine 2."""

from __future__ import annotations

import getpass

from packages.application.product_api_client import ProductApiClient
from packages.application.server_discovery import discover_server_url, server_is_ready
from packages.application.stage2_api_client import Stage2ApiClient


def run_check(*, discover=discover_server_url, ready=server_is_ready, client_factory=ProductApiClient,
              stage2_factory=Stage2ApiClient, username: str, password: str) -> tuple[str, str]:
    """Discover and read from central services without modifying server data."""
    server_url = discover()
    if not server_url:
        raise RuntimeError("UDP 8011 không tìm thấy Máy 1. Kiểm tra Private LAN và Firewall.")
    if not ready(server_url):
        raise RuntimeError("Máy 1 được tìm thấy nhưng database readiness chưa đạt.")
    product_client = client_factory(server_url)
    product_client.verify_server_readiness()
    session = product_client.login(username, password)
    stage2_factory(server_url, access_token=product_client.access_token or "").list_customers()
    return server_url, str(session["role"])


def main() -> None:
    print("HMS QR Machine 2 LAN diagnostic")
    print("Khong nhap URL: kiem tra UDP discovery truc tiep tu May 2.")
    username = input("Ten dang nhap: ").strip()
    password = getpass.getpass("Mat khau: ")
    if not username or not password:
        raise SystemExit("Can ten dang nhap va mat khau.")
    try:
        server_url, role = run_check(username=username, password=password)
    except RuntimeError as exc:
        raise SystemExit(f"KHONG DAT: {exc}") from exc
    print(f"DAT: UDP discovery, database readiness, login va Stage 2 read qua {server_url} ({role}).")


if __name__ == "__main__":
    main()
