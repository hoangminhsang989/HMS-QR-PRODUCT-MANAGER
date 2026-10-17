"""Private-LAN discovery for an HMS QR API server."""

from __future__ import annotations

import json
import os
import secrets
import socket
import threading
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


DISCOVERY_PORT = 8011
DISCOVERY_REQUEST = "HMS_QR_DISCOVER_V1"
DISCOVERY_RESPONSE = "HMS_QR_SERVER_V1"
READINESS_PATH = "/health/readiness/database"


def desktop_server_url_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "HMS QR Desktop"
    return root / "server.json"


def normalize_server_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        raise ValueError("Địa chỉ HMS QR Server không hợp lệ.")
    return value


def server_is_ready(server_url: str, *, opener=urlopen) -> bool:
    try:
        with opener(f"{normalize_server_url(server_url)}{READINESS_PATH}", timeout=1.5) as response:
            return 200 <= getattr(response, "status", 200) < 300
    except (OSError, URLError, ValueError):
        return False


def load_saved_server_url(path: Path | None = None) -> str | None:
    try:
        value = json.loads((path or desktop_server_url_path()).read_text(encoding="utf-8"))["server_url"]
        return normalize_server_url(str(value))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def save_server_url(server_url: str, path: Path | None = None) -> None:
    target = path or desktop_server_url_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"server_url": normalize_server_url(server_url)}), encoding="utf-8")


def discover_server_url(*, timeout: float = 1.5, socket_factory=socket.socket, opener=urlopen) -> str | None:
    nonce = secrets.token_urlsafe(16)
    request = json.dumps({"type": DISCOVERY_REQUEST, "nonce": nonce}).encode("utf-8")
    client = socket_factory(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        client.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        client.settimeout(timeout)
        client.sendto(request, ("255.255.255.255", DISCOVERY_PORT))
        while True:
            try:
                payload, _address = client.recvfrom(4096)
            except socket.timeout:
                return None
            try:
                result = json.loads(payload.decode("utf-8"))
                server_url = normalize_server_url(str(result["server_url"]))
            except (UnicodeDecodeError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
            if result.get("type") == DISCOVERY_RESPONSE and result.get("nonce") == nonce and server_is_ready(server_url, opener=opener):
                return server_url
    finally:
        client.close()


def resolve_server_url(*, configured_url: str = "", saved_path: Path | None = None, discover=discover_server_url, ready=server_is_ready, save=save_server_url) -> str:
    explicit = configured_url.strip()
    if explicit:
        server_url = normalize_server_url(explicit)
        if not ready(server_url):
            raise RuntimeError("HMS QR Server đã cấu hình chưa sẵn sàng.")
        save(server_url, saved_path)
        return server_url
    saved = load_saved_server_url(saved_path)
    if saved and ready(saved):
        return saved
    discovered = discover()
    if discovered and ready(discovered):
        save(discovered, saved_path)
        return discovered
    raise RuntimeError("Không tìm thấy HMS QR Server trong mạng LAN. Kiểm tra Máy 1 đang chạy và mạng Private.")


class DiscoveryResponder:
    def __init__(self, *, port: int = DISCOVERY_PORT, socket_factory=socket.socket) -> None:
        self.port = port
        self.socket_factory = socket_factory
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket: socket.socket | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._socket = self.socket_factory(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("0.0.0.0", self.port))
        self._socket.settimeout(0.5)
        self._thread = threading.Thread(target=self._serve, name="hms-qr-discovery", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        if self._socket:
            self._socket.close()
        self._thread = None
        self._socket = None

    def _serve(self) -> None:
        assert self._socket is not None
        while not self._stop.is_set():
            try:
                payload, address = self._socket.recvfrom(4096)
                request = json.loads(payload.decode("utf-8"))
                if request.get("type") != DISCOVERY_REQUEST or not isinstance(request.get("nonce"), str):
                    continue
                # Route lookup picks the LAN address associated with this client.
                probe = self.socket_factory(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    probe.connect(address)
                    host = probe.getsockname()[0]
                finally:
                    probe.close()
                response = json.dumps({"type": DISCOVERY_RESPONSE, "nonce": request["nonce"], "server_url": f"http://{host}:8010"}).encode("utf-8")
                self._socket.sendto(response, address)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
