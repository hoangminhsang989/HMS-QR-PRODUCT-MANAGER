"""Native operations desktop for a local HMS QR Server instance."""

from __future__ import annotations

import json
import ipaddress
import hashlib
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QPlainTextEdit,
    QVBoxLayout, QWidget, QFileDialog, QGridLayout, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QProgressBar, QScrollArea, QCheckBox,
)


SERVER_URL = "http://127.0.0.1:8010"
LAN_PORT = 8010
MAX_ACTIVITY_LOG_LINES = 160
LOW_DISK_BYTES = 5 * 1024**3
CRITICAL_DISK_BYTES = 1 * 1024**3
DEFAULT_DATA_ROOT = Path("D:/HMS-QR-PROD")
SETTINGS_PATH = DEFAULT_DATA_ROOT / "server-tool-settings.json"
SECRETS_PATH = DEFAULT_DATA_ROOT / "server-tool-secrets.json"
POSTGRESQL_WINGET_ID = "PostgreSQL.PostgreSQL.17"
POSTGRESQL_INSTALLER_NAME = "postgresql-17.11-4-windows-x64.exe"
POSTGRESQL_INSTALLER_SHA256 = "c9828fd3a4daebbeeace19bec2de5f38d73c047fce47278148b525cfbe28a5e4"
POSTGRESQL_INSTALL_ROOT = Path("C:/Program Files/PostgreSQL/17")
POSTGRESQL_DATA_ROOT = DEFAULT_DATA_ROOT / "postgresql"
POSTGRESQL_PORT = 5432
POSTGRESQL_SERVICE = "postgresql-x64-17"
PRODUCTION_DATABASE = "hms_qr"
PRODUCTION_DATABASE_USER = "hms_qr_app"
DEFAULT_ADMIN_PASSWORD = "admin"
AUTO_START_TASK_NAME = "HMS QR Server (Current User)"


def _validated_root(value: str) -> Path:
    root = Path(value).expanduser().resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    probe = root / ".hms-qr-write-probe"
    probe.write_text("ok", encoding="ascii")
    probe.unlink()
    return root


def load_tool_settings(path: Path | None = None) -> dict[str, str | bool]:
    path = path or SETTINGS_PATH
    defaults: dict[str, str | bool] = {
        "data_root": str(DEFAULT_DATA_ROOT),
        "backup_root": str(DEFAULT_DATA_ROOT / "backups"),
        "start_server_with_windows": True,
    }
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    if not isinstance(stored, dict):
        return defaults
    return {
        "data_root": str(stored.get("data_root") or defaults["data_root"]),
        "backup_root": str(stored.get("backup_root") or defaults["backup_root"]),
        "start_server_with_windows": bool(stored.get("start_server_with_windows", True)),
    }


def save_tool_settings(
    data_root: str,
    backup_root: str,
    path: Path | None = None,
    *,
    start_server_with_windows: bool | None = None,
) -> None:
    path = path or SETTINGS_PATH
    data = _validated_root(data_root)
    backup = _validated_root(backup_root)
    if data == backup or data in backup.parents or backup in data.parents:
        raise ValueError("Thư mục backup phải tách biệt với thư mục data vận hành.")
    path.parent.mkdir(parents=True, exist_ok=True)
    settings: dict[str, str | bool] = {"data_root": str(data), "backup_root": str(backup)}
    if start_server_with_windows is not None:
        settings["start_server_with_windows"] = start_server_with_windows
    else:
        settings["start_server_with_windows"] = bool(load_tool_settings(path)["start_server_with_windows"])
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def save_autostart_preference(enabled: bool, path: Path | None = None) -> None:
    path = path or SETTINGS_PATH
    settings = load_tool_settings(path)
    settings["start_server_with_windows"] = bool(enabled)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def _dpapi(secret: str, *, unprotect: bool) -> str:
    action = "Unprotect" if unprotect else "Protect"
    script = (
        "Add-Type -AssemblyName System.Security; "
        "$value = [Console]::In.ReadToEnd(); "
        "$scope = [Security.Cryptography.DataProtectionScope]::CurrentUser; "
        "if ($env:HMS_QR_DPAPI_ACTION -eq 'unprotect') { "
        "$bytes = [Security.Cryptography.ProtectedData]::Unprotect([Convert]::FromBase64String($value), $null, $scope); "
        "[Text.Encoding]::UTF8.GetString($bytes) "
        "} else { "
        "$bytes = [Text.Encoding]::UTF8.GetBytes($value); "
        "[Convert]::ToBase64String([Security.Cryptography.ProtectedData]::Protect($bytes, $null, $scope)) "
        "}"
    )
    environment = os.environ.copy()
    environment["HMS_QR_DPAPI_ACTION"] = "unprotect" if unprotect else "protect"
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script], input=secret, env=environment,
            capture_output=True, text=True, check=False, timeout=15,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Windows DPAPI không phản hồi trong 15 giây.") from exc
    if result.returncode or not result.stdout.strip():
        raise RuntimeError("Windows không thể mở kho bí mật của HMS QR Server Tool.")
    return result.stdout.strip()


def save_server_secret(name: str, value: str, path: Path = SECRETS_PATH) -> None:
    if not name or not value:
        raise ValueError("Tên và giá trị bí mật là bắt buộc.")
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        stored = {}
    stored[name] = _dpapi(value, unprotect=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(stored, indent=2), encoding="utf-8")


def load_server_secret(name: str, path: Path = SECRETS_PATH) -> str:
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        protected = str(stored[name])
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError("Không tìm thấy bí mật đã lưu cho Server này.") from None
    return _dpapi(protected, unprotect=True)


def create_production_secrets(path: Path = SECRETS_PATH) -> None:
    """Create required DPAPI-protected secrets once without rotating a live Server."""
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        stored = {}
    required = {
        "postgres_password": secrets.token_urlsafe(32),
        "database_password": secrets.token_urlsafe(32),
        "auth_secret": secrets.token_urlsafe(48),
        "admin_password": DEFAULT_ADMIN_PASSWORD,
    }
    for name, value in required.items():
        if not stored.get(name):
            save_server_secret(name, value, path)
            stored[name] = "created"


def generate_admin_password() -> str:
    return DEFAULT_ADMIN_PASSWORD


def production_paths(root: Path = DEFAULT_DATA_ROOT) -> dict[str, Path]:
    """Return the fixed local-only production layout selected for Machine 1."""
    return {
        "root": root,
        "storage": root / "storage",
        "backups": root / "backups",
        "logs": root / "logs",
        "postgresql": root / "postgresql",
    }


def postgresql_unattended_options(*, data_root: Path, superpassword: str) -> str:
    """Build EDB's short-lived option file so database credentials never enter argv."""
    return "\n".join((
        "mode=unattended",
        "unattendedmodeui=minimal",
        f"prefix={POSTGRESQL_INSTALL_ROOT}",
        f"datadir={data_root}",
        f"serverport={POSTGRESQL_PORT}",
        f"servicename={POSTGRESQL_SERVICE}",
        f"superpassword={superpassword}",
        "",
    ))


def postgresql_unattended_command(installer: Path, option_file: Path) -> list[str]:
    return [str(installer), "--optionfile", str(option_file)]


def restrict_option_file_to_current_user(option_file: Path) -> None:
    """Remove inherited access from the temporary installer secret file."""
    environment = os.environ.copy()
    environment["HMS_QR_OPTION_FILE"] = str(option_file)
    script = (
        "$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name; "
        "& icacls $env:HMS_QR_OPTION_FILE /inheritance:r /grant:r \"$user`:(F)\" | Out-Null; "
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script], env=environment,
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise RuntimeError("Không thể giới hạn quyền truy cập file cài đặt PostgreSQL tạm thời.")


def run_postgresql_offline_installer(installer: Path, option_file: Path, options: str) -> subprocess.CompletedProcess[str]:
    option_file.write_text(options, encoding="utf-8")
    try:
        restrict_option_file_to_current_user(option_file)
        return subprocess.run(
            postgresql_unattended_command(installer, option_file),
            capture_output=True, text=True, check=False,
        )
    finally:
        option_file.unlink(missing_ok=True)


def production_server_environment(root: Path = DEFAULT_DATA_ROOT, secrets_path: Path = SECRETS_PATH) -> dict[str, str]:
    """Load only DPAPI-protected secrets into the child Server process environment."""
    database_password = load_server_secret("database_password", secrets_path)
    return {
        "HMS_QR_ENV": "prod",
        "HMS_QR_DATABASE_URL": (
            f"postgresql+psycopg://{PRODUCTION_DATABASE_USER}:{database_password}"
            f"@127.0.0.1:{POSTGRESQL_PORT}/{PRODUCTION_DATABASE}"
        ),
        "HMS_QR_STORAGE_ROOT": str(production_paths(root)["storage"]),
        "HMS_QR_AUTH_SECRET": load_server_secret("auth_secret", secrets_path),
        "HMS_QR_BOOTSTRAP_ADMIN_USERNAME": "admin",
        "HMS_QR_BOOTSTRAP_ADMIN_PASSWORD": load_server_secret("admin_password", secrets_path),
    }


def production_setup_requirements(source_root: Path | None = None) -> list[str]:
    """Return missing offline release prerequisites without contacting the Internet."""
    source = source_root or Path(__file__).resolve().parents[2]
    missing: list[str] = []
    if not list((source / "installer" / "python").glob("*.exe")):
        missing.append("Python offline installer")
    if not list((source / "installer" / "wheels").glob("*.whl")):
        missing.append("Python offline wheels")
    try:
        verified_postgresql_offline_installer(source / "installer" / "postgresql" / POSTGRESQL_INSTALLER_NAME)
    except ValueError:
        missing.append("PostgreSQL 17 offline installer đã xác minh")
    return missing


def postgresql_backup_path(backup_root: Path, *, now: datetime | None = None) -> Path:
    backup_root = _validated_root(str(backup_root))
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S_%f")
    return backup_root / f"hms_qr_{timestamp}.dump"


def latest_postgresql_backup(backup_root: Path) -> Path | None:
    try:
        return max(backup_root.glob("hms_qr_*.dump"), key=lambda item: item.name)
    except (OSError, ValueError):
        return None


def postgresql_backup_inventory(backup_root: Path) -> str:
    try:
        backups = list(backup_root.glob("hms_qr_*.dump"))
        total_bytes = sum(item.stat().st_size for item in backups)
    except OSError:
        return "KHÔNG ĐỌC ĐƯỢC"
    return f"{len(backups)} file ({total_bytes / 1024**2:.1f} MB)"


def production_postgresql_is_installed() -> bool:
    return (POSTGRESQL_INSTALL_ROOT / "bin" / "pg_dump.exe").is_file()


def postgresql_restore_command(backup: Path) -> list[str]:
    """Build a destructive restore command only after caller verifies the custom dump."""
    return [
        str(POSTGRESQL_INSTALL_ROOT / "bin" / "pg_restore.exe"), "-h", "127.0.0.1",
        "-p", str(POSTGRESQL_PORT), "-U", PRODUCTION_DATABASE_USER, "-d", PRODUCTION_DATABASE,
        "--clean", "--if-exists", "--exit-on-error", str(backup),
    ]


def current_user_autostart_command(source_root: Path | None = None) -> list[str]:
    """Create an on-logon task; it contains no HMS QR secret values."""
    root = source_root or Path(__file__).resolve().parents[2]
    task_run = f'cmd.exe /d /s /c ""cd /d "{root}" && py -3.14 -m apps.server.production_launcher""'
    return ["schtasks.exe", "/Create", "/TN", AUTO_START_TASK_NAME, "/SC", "ONLOGON", "/RL", "LIMITED", "/TR", task_run, "/F"]


def current_user_autostart_exists() -> bool:
    """Report whether the current-user logon task is present."""
    result = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", AUTO_START_TASK_NAME],
        capture_output=True, text=True, check=False,
    )
    return result.returncode == 0


def set_current_user_autostart(enabled: bool, source_root: Path | None = None) -> None:
    if enabled:
        command = current_user_autostart_command(source_root)
    elif not current_user_autostart_exists():
        return
    else:
        command = ["schtasks.exe", "/Delete", "/TN", AUTO_START_TASK_NAME, "/F"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Không thể cập nhật tác vụ tự khởi động cùng Windows. {detail}".strip())


def backup_sqlite(database: Path, backup_root: Path) -> Path:
    if not database.is_file():
        raise ValueError("Chưa có database SQLite để sao lưu.")
    backup_root = _validated_root(str(backup_root))
    target = backup_root / f"hms_qr_{datetime.now():%Y%m%d_%H%M%S_%f}.sqlite"
    sequence = 1
    while target.exists():
        target = backup_root / f"hms_qr_{datetime.now():%Y%m%d_%H%M%S_%f}_{sequence}.sqlite"
        sequence += 1
    source = sqlite3.connect(database)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def latest_sqlite_backup(backup_root: Path) -> Path | None:
    try:
        return max(backup_root.glob("hms_qr_*.sqlite"), key=lambda item: item.stat().st_mtime)
    except (OSError, ValueError):
        return None


def backup_freshness(backup: Path | None, *, now: datetime | None = None) -> str:
    if backup is None:
        return "CHƯA CÓ BACKUP"
    try:
        age_hours = max(0, int(((now or datetime.now()).timestamp() - backup.stat().st_mtime) // 3600))
    except OSError:
        return "KHÔNG ĐỌC ĐƯỢC BACKUP"
    state = "MỚI" if age_hours < 24 else "QUÁ 24 GIỜ"
    return f"{state} ({age_hours} giờ)"


def backup_inventory(backup_root: Path) -> str:
    try:
        backups = list(backup_root.glob("hms_qr_*.sqlite"))
        total_bytes = sum(item.stat().st_size for item in backups)
    except OSError:
        return "KHÔNG ĐỌC ĐƯỢC"
    return f"{len(backups)} file ({total_bytes / 1024**2:.1f} MB)"


def backup_integrity_inventory(backup_root: Path) -> str:
    summary, _invalid = backup_integrity_details(backup_root)
    return summary


def backup_integrity_details(backup_root: Path) -> tuple[str, list[str]]:
    try:
        backups = sorted(backup_root.glob("hms_qr_*.sqlite"))
    except OSError:
        return "KHÔNG ĐỌC ĐƯỢC", []
    valid = 0
    invalid: list[str] = []
    for backup in backups:
        try:
            check_sqlite_backup(backup)
            valid += 1
        except (OSError, ValueError, sqlite3.Error):
            invalid.append(backup.name)
    return f"{valid} hợp lệ, {len(invalid)} lỗi", invalid


def disk_space_status(folder: Path) -> str:
    try:
        free_bytes = shutil.disk_usage(folder).free
    except OSError:
        return "KHÔNG ĐỌC ĐƯỢC"
    free_gb = free_bytes / 1024**3
    state = "GẦN HẾT" if free_bytes < CRITICAL_DISK_BYTES else "SẮP ĐẦY" if free_bytes < LOW_DISK_BYTES else "ĐỦ DUNG LƯỢNG"
    return f"{state} ({free_gb:.1f} GB trống)"


def locations_are_saved(data_root: str, backup_root: str, settings: dict[str, str]) -> bool:
    return (
        Path(data_root).expanduser().resolve(strict=False) == Path(settings["data_root"]).expanduser().resolve(strict=False)
        and Path(backup_root).expanduser().resolve(strict=False) == Path(settings["backup_root"]).expanduser().resolve(strict=False)
    )


def check_sqlite_backup(backup: Path) -> str:
    if not backup.is_file():
        raise ValueError("Không tìm thấy file backup SQLite để kiểm tra.")
    # URI read-only prevents an operational check from ever modifying the backup.
    connection = sqlite3.connect(f"{backup.resolve().as_uri()}?mode=ro", uri=True)
    try:
        result = connection.execute("PRAGMA quick_check").fetchone()
    finally:
        connection.close()
    if result != ("ok",):
        raise ValueError(f"Backup không hợp lệ: {result[0] if result else 'không có kết quả kiểm tra'}")
    return f"BACKUP HỢP LỆ: {backup.name}"


def restore_sqlite_database(database: Path, backup: Path, safety_root: Path) -> Path | None:
    """Replace a stopped local SQLite runtime only after source and copy validation."""
    check_sqlite_backup(backup)
    safety_backup = backup_sqlite(database, safety_root) if database.is_file() else None
    temporary = database.with_name(f"{database.stem}.restore-{datetime.now():%Y%m%d%H%M%S%f}.tmp")
    try:
        shutil.copy2(backup, temporary)
        check_sqlite_backup(temporary)
        os.replace(temporary, database)
    finally:
        if temporary.exists():
            temporary.unlink()
    return safety_backup


def _is_windows_admin() -> bool:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", "([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)"],
        capture_output=True, text=True, check=False,
    ).stdout.strip().casefold() == "true"


def postgresql_offline_installer_path() -> Path:
    return Path(__file__).resolve().parents[2] / "installer" / "postgresql" / POSTGRESQL_INSTALLER_NAME


def verified_postgresql_offline_installer(path: Path | None = None) -> Path:
    installer = path or postgresql_offline_installer_path()
    if not installer.is_file():
        raise ValueError("Không tìm thấy bộ cài PostgreSQL offline trong gói HMS QR.")
    digest = hashlib.sha256(installer.read_bytes()).hexdigest()
    if digest != POSTGRESQL_INSTALLER_SHA256:
        raise ValueError("Bộ cài PostgreSQL offline không khớp checksum đã xác minh.")
    return installer


def firewall_private_status() -> str:
    rule_name = f"HMS QR Server TCP {LAN_PORT}"
    command = (
        f"$rule = Get-NetFirewallRule -DisplayName '{rule_name}' -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Enabled -eq 'True' -and $_.Direction -eq 'Inbound' -and $_.Action -eq 'Allow' -and $_.Profile -match 'Private' }; "
        "if ($rule) { 'ĐÃ MỞ PRIVATE' } else { 'CHƯA MỞ' }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return "KHÔNG KIỂM TRA ĐƯỢC"
    if result.returncode:
        return "KHÔNG KIỂM TRA ĐƯỢC"
    return result.stdout.strip() or "CHƯA MỞ"


def active_lan_network_status() -> str:
    """Report the gateway-backed adapter profile without exposing network names."""
    command = (
        "$adapter = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } | Select-Object -First 1; "
        "if (-not $adapter) { 'KHÔNG TÌM THẤY ADAPTER LAN' } else { "
        "$profile = Get-NetConnectionProfile -InterfaceIndex $adapter.InterfaceIndex; "
        "if ($profile) { $profile.NetworkCategory.ToString().ToUpperInvariant() } else { 'KHÔNG KIỂM TRA ĐƯỢC' } }"
    )
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, check=False)
    except OSError:
        return "KHÔNG KIỂM TRA ĐƯỢC"
    if result.returncode:
        return "KHÔNG KIỂM TRA ĐƯỢC"
    return result.stdout.strip() or "KHÔNG KIỂM TRA ĐƯỢC"


def repair_private_lan_command() -> str:
    """Limit network changes to the default-gateway adapter and HMS QR rules."""
    return (
        "$adapter = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } | Select-Object -First 1; "
        "if (-not $adapter) { throw 'Không tìm thấy adapter LAN có gateway.' }; "
        "Set-NetConnectionProfile -InterfaceIndex $adapter.InterfaceIndex -NetworkCategory Private -ErrorAction Stop; "
        f"$tcp = Get-NetFirewallRule -DisplayName 'HMS QR Server TCP {LAN_PORT}' -ErrorAction SilentlyContinue; "
        f"if (-not $tcp) {{ $tcp = New-NetFirewallRule -DisplayName 'HMS QR Server TCP {LAN_PORT}' -Direction Inbound -Action Allow -Protocol TCP -LocalPort {LAN_PORT} -Profile Private }}; "
        "$tcp | Set-NetFirewallRule -Enabled True -Profile Private -Direction Inbound -Action Allow; "
        "$udp = Get-NetFirewallRule -DisplayName 'HMS QR Discovery UDP 8011' -ErrorAction SilentlyContinue; "
        "if (-not $udp) { $udp = New-NetFirewallRule -DisplayName 'HMS QR Discovery UDP 8011' -Direction Inbound -Action Allow -Protocol UDP -LocalPort 8011 -Profile Private }; "
        "$udp | Set-NetFirewallRule -Enabled True -Profile Private -Direction Inbound -Action Allow"
    )


def external_hms_server_pid_command() -> str:
    """Find only the expected HMS QR Uvicorn command, never a generic Python process."""
    return (
        "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | "
        "Where-Object { $_.CommandLine -match 'uvicorn\\s+apps\\.server\\.app:app' "
        "-and $_.CommandLine -match '--port\\s+8010' } | "
        "ForEach-Object { $_.ProcessId }"
    )


def external_hms_server_pids() -> list[int]:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", external_hms_server_pid_command()],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return []
    if result.returncode:
        return []
    return [int(value) for value in result.stdout.split() if value.isdigit()]


def lan_listener_status() -> str:
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, check=False,
        )
    except OSError:
        return "KHÔNG KIỂM TRA ĐƯỢC"
    if result.returncode:
        return "KHÔNG KIỂM TRA ĐƯỢC"
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[0].upper() != "TCP" or parts[3].upper() != "LISTENING":
            continue
        local_address = parts[1]
        if not local_address.endswith(f":{LAN_PORT}"):
            continue
        host = local_address.rsplit(":", 1)[0].strip("[]")
        if host in {"0.0.0.0", "::"}:
            return "SẴN SÀNG LAN"
        if host in {"127.0.0.1", "::1"}:
            return "CHỈ LOCALHOST"
        return f"LẮNG NGHE: {host}"
    return "CHƯA LẮNG NGHE"


def operational_readiness_report(settings: dict[str, str]) -> str:
    backup = latest_sqlite_backup(Path(settings["backup_root"]))
    return "\n".join((
        "HMS QR SERVER - BÁO CÁO SẴN SÀNG VẬN HÀNH",
        f"Thời điểm: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"Máy chủ: {socket.gethostname()}",
        f"Địa chỉ Desktop: {ServerToolWindow._lan_address()}",
        f"TCP {LAN_PORT}: {lan_listener_status()}",
        f"Firewall Private: {firewall_private_status()}",
        "Data runtime: ĐÃ CẤU HÌNH",
        f"Backup gần nhất: {backup.name if backup else 'CHƯA CÓ BACKUP'}",
        "Ghi chú: Báo cáo không chứa thông tin đăng nhập hoặc đường dẫn dữ liệu.",
    ))


def lan_readiness_assessment(database_ready: bool, listener: str, firewall: str) -> str:
    missing = []
    if not database_ready:
        missing.append("SERVER/DATABASE")
    if listener != "SẴN SÀNG LAN":
        missing.append(f"TCP {LAN_PORT}: {listener}")
    if firewall != "ĐÃ MỞ PRIVATE":
        missing.append(f"FIREWALL: {firewall}")
    return "SẴN SÀNG LAN" if not missing else "CẦN XỬ LÝ - " + "; ".join(missing)


def lan_readiness_checklist(database_ready: bool, listener: str, firewall: str) -> tuple[str, ...]:
    return (
        f"{'OK' if database_ready else 'CẦN XỬ LÝ'} Server/database: {'SẴN SÀNG' if database_ready else 'không phản hồi readiness'}",
        f"{'OK' if listener == 'SẴN SÀNG LAN' else 'CẦN XỬ LÝ'} TCP {LAN_PORT}: {listener}" + ("" if listener == "SẴN SÀNG LAN" else "; chạy Server Tool để bind 0.0.0.0"),
        f"{'OK' if firewall == 'ĐÃ MỞ PRIVATE' else 'CẦN XỬ LÝ'} Firewall Private: {firewall}" + ("" if firewall == "ĐÃ MỞ PRIVATE" else "; mở rule TCP 8010 Private bằng Administrator"),
    )


def _request(path: str, *, token: str = "", method: str = "GET", payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{SERVER_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=2) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(detail) from None
    except (URLError, OSError) as exc:
        raise RuntimeError("Không thể kết nối HMS QR Server.") from exc


class ServerToolWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HMS QR Server Tool")
        self.resize(1060, 700)
        self._token = ""
        self._server_process: QProcess | None = None
        self._settings = load_tool_settings()
        self._build_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_status)
        self._timer.start(3000)
        self.refresh_status()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        title = QLabel("HMS QR SERVER TOOL")
        title.setObjectName("title")
        subtitle = QLabel("Trung tâm vận hành dữ liệu, mạng LAN và sao lưu cho HMS QR Desktop")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        overview = QGroupBox("TỔNG QUAN VẬN HÀNH")
        overview.setObjectName("overviewCard")
        overview_grid = QGridLayout(overview)
        overview_grid.setContentsMargins(8, 8, 8, 6)
        overview_grid.setHorizontalSpacing(10)
        self.overview_server = QLabel("ĐANG KIỂM TRA")
        self.overview_lan = QLabel(self._lan_address())
        self.overview_data = QLabel(Path(self._settings["data_root"]).name or self._settings["data_root"])
        self.overview_backup = QLabel("CHƯA CÓ BACKUP")
        self.overview_backup_freshness = QLabel("CHƯA CÓ BACKUP")
        self.overview_disk = QLabel("Chưa kiểm tra")
        self.overview_inventory = QLabel("Chưa kiểm tra")
        for label in (self.overview_server, self.overview_lan, self.overview_data, self.overview_backup, self.overview_backup_freshness, self.overview_disk, self.overview_inventory):
            label.setObjectName("overviewValue")
        for index, (caption, value) in enumerate((
            ("SERVER", self.overview_server),
            ("ĐỊA CHỈ LAN", self.overview_lan),
            ("DATA VẬN HÀNH", self.overview_data),
            ("BACKUP GẦN NHẤT", self.overview_backup),
            ("TÌNH TRẠNG BACKUP", self.overview_backup_freshness),
            ("DUNG LƯỢNG DATA", self.overview_disk),
            ("KHO BACKUP", self.overview_inventory),
        )):
            caption_label = QLabel(caption)
            caption_label.setObjectName("overviewCaption")
            row, column = divmod(index, 4)
            overview_grid.addWidget(caption_label, row * 2, column)
            overview_grid.addWidget(value, row * 2 + 1, column)
        self.copy_lan_button = QPushButton("SAO CHÉP URL DESKTOP")
        self.copy_lan_button.setObjectName("outlineButton")
        self.report_button = QPushButton("SAO CHÉP BÁO CÁO SẴN SÀNG")
        self.report_button.setObjectName("outlineButton")
        overview_actions = QHBoxLayout()
        overview_actions.addWidget(self.copy_lan_button)
        overview_actions.addWidget(self.report_button)
        overview_grid.addLayout(overview_actions, 4, 0, 1, 4)
        layout.addWidget(overview)

        service = QGroupBox("01  TRẠNG THÁI SERVER")
        service.setObjectName("heroCard")
        service_form = QFormLayout(service)
        service_form.setContentsMargins(8, 9, 8, 7)
        service_form.setSpacing(3)
        self.server_url = QLabel(self._lan_address())
        self.server_url.setObjectName("serverUrl")
        self.status_label = QLabel("Đang kiểm tra...")
        self.status_label.setObjectName("status")
        self.start_button = QPushButton("KHỞI ĐỘNG SERVER")
        self.start_button.setObjectName("primaryButton")
        self.stop_button = QPushButton("DỪNG SERVER CỦA TOOL")
        self.stop_button.setObjectName("secondaryButton")
        self.stop_button.setEnabled(False)
        self.restart_external_button = QPushButton("KHỞI ĐỘNG LẠI SERVER ĐANG CHẠY")
        self.restart_external_button.setObjectName("secondaryButton")
        self.listener_button = QPushButton("KIỂM TRA LẮNG NGHE LAN")
        self.listener_button.setObjectName("outlineButton")
        self.listener_state = QLabel("Chưa kiểm tra")
        self.listener_state.setObjectName("listenerState")
        self.lan_readiness_button = QPushButton("ĐÁNH GIÁ SẴN SÀNG LAN")
        self.lan_readiness_button.setObjectName("primaryButton")
        self.lan_readiness_state = QLabel("Chưa đánh giá")
        self.lan_readiness_state.setObjectName("lanReadinessState")
        self.lan_checklist = QPlainTextEdit()
        self.lan_checklist.setReadOnly(True)
        self.lan_checklist.setPlaceholderText("Đánh giá LAN sẽ hiển thị checklist tại đây.")
        self.lan_checklist.setFixedHeight(52)
        buttons = QHBoxLayout()
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        service_form.addRow(self.restart_external_button)
        service_form.addRow("Desktop kết nối tới:", self.server_url)
        service_form.addRow("Trạng thái:", self.status_label)
        service_form.addRow(self.listener_button, self.listener_state)
        service_form.addRow(self.lan_readiness_button, self.lan_readiness_state)
        service_form.addRow("Checklist LAN:", self.lan_checklist)
        service_form.addRow(buttons)
        layout.addWidget(service)

        self.start_with_windows_checkbox = QCheckBox("Khởi động Server cùng Windows")
        self.start_with_windows_checkbox.setChecked(bool(self._settings["start_server_with_windows"]))
        layout.addWidget(self.start_with_windows_checkbox)
        self._popups: dict[str, QMainWindow] = {}
        self.popup_buttons: list[QPushButton] = []
        self._autostart_reconciled = False

        lan = QGroupBox("02  KẾT NỐI MẠNG LAN")
        lan_grid = QGridLayout(lan)
        lan_grid.setContentsMargins(8, 9, 8, 7)
        lan_grid.setHorizontalSpacing(6)
        lan_grid.setVerticalSpacing(3)
        lan_grid.setColumnMinimumWidth(0, 125)
        lan_grid.setColumnStretch(1, 1)
        self.lan_address = QLabel(self._lan_address())
        self.lan_address.setObjectName("lanAddress")
        self.firewall_button = QPushButton("MỞ FIREWALL LAN (TCP 8010)")
        self.firewall_button.setObjectName("primaryButton")
        self.repair_lan_button = QPushButton("TỰ SỬA PROFILE PRIVATE + FIREWALL")
        self.repair_lan_button.setObjectName("primaryButton")
        self.install_postgresql_button = QPushButton("CÀI POSTGRESQL 17")
        self.install_postgresql_button.setObjectName("outlineButton")
        self.setup_production_button = QPushButton("THIẾT LẬP SERVER 1 CLICK")
        self.setup_production_button.setObjectName("primaryButton")
        self.setup_progress = QProgressBar()
        self.setup_progress.setObjectName("setupProgress")
        self.setup_progress.setRange(0, 7)
        self.setup_progress.setValue(0)
        self.setup_progress.setTextVisible(True)
        self.setup_progress.setFormat("Sẵn sàng thiết lập")
        self.check_firewall_button = QPushButton("KIỂM TRA FIREWALL PRIVATE")
        self.check_firewall_button.setObjectName("outlineButton")
        self.firewall_state = QLabel("Chưa kiểm tra")
        self.firewall_state.setObjectName("firewallState")
        self.network_profile_state = QLabel("Chưa kiểm tra")
        self.network_profile_state.setObjectName("firewallState")
        self.adapter = QLineEdit()
        self.adapter.setPlaceholderText("Ví dụ: Ethernet")
        self.static_ip = QLineEdit()
        self.static_ip.setPlaceholderText("Ví dụ: 192.168.1.50")
        self.subnet = QLineEdit("24")
        self.gateway = QLineEdit()
        self.gateway.setPlaceholderText("Ví dụ: 192.168.1.1")
        self.dns = QLineEdit()
        self.dns.setPlaceholderText("Ví dụ: 1.1.1.1, 8.8.8.8")
        self.apply_ip_button = QPushButton("ÁP DỤNG IP TĨNH")
        self.apply_ip_button.setObjectName("outlineButton")
        lan_grid.addWidget(QLabel("Địa chỉ LAN hiện tại:"), 0, 0)
        lan_grid.addWidget(self.lan_address, 0, 1)
        lan_grid.addWidget(self.firewall_button, 1, 0, 1, 2)
        lan_grid.addWidget(self.repair_lan_button, 2, 0, 1, 2)
        lan_grid.addWidget(self.install_postgresql_button, 3, 0, 1, 2)
        lan_grid.addWidget(self.setup_production_button, 4, 0, 1, 2)
        lan_grid.addWidget(self.setup_progress, 5, 0, 1, 2)
        lan_grid.addWidget(self.check_firewall_button, 6, 0)
        lan_grid.addWidget(self.firewall_state, 6, 1)
        lan_grid.addWidget(QLabel("Profile mạng LAN:"), 7, 0)
        lan_grid.addWidget(self.network_profile_state, 7, 1)
        lan_grid.addWidget(QLabel("Tên network adapter:"), 8, 0)
        lan_grid.addWidget(self.adapter, 8, 1)
        lan_grid.addWidget(QLabel("IP tĩnh:"), 9, 0)
        lan_grid.addWidget(self.static_ip, 9, 1)
        lan_grid.addWidget(QLabel("Prefix subnet (ví dụ 24):"), 10, 0)
        lan_grid.addWidget(self.subnet, 10, 1)
        lan_grid.addWidget(QLabel("Gateway:"), 11, 0)
        lan_grid.addWidget(self.gateway, 11, 1)
        lan_grid.addWidget(QLabel("DNS (phân cách dấu phẩy):"), 12, 0)
        lan_grid.addWidget(self.dns, 12, 1)
        lan_grid.addWidget(self.apply_ip_button, 11, 0, 1, 2)

        data = QGroupBox("03  DATA VÀ SAO LƯU")
        data_form = QFormLayout(data)
        data_form.setContentsMargins(8, 9, 8, 7)
        data_form.setSpacing(3)
        self.data_root = QLineEdit(self._settings["data_root"])
        self.backup_root = QLineEdit(self._settings["backup_root"])
        choose_data = QPushButton("CHỌN...")
        choose_backup = QPushButton("CHỌN...")
        self.save_locations_button = QPushButton("LƯU VỊ TRÍ DATA")
        self.save_locations_button.setObjectName("primaryButton")
        self.locations_state = QLabel("ĐÃ LƯU")
        self.locations_state.setObjectName("locationsState")
        self.backup_button = QPushButton("SAO LƯU DATABASE NGAY")
        self.backup_button.setObjectName("secondaryButton")
        self.restore_button = QPushButton("KHÔI PHỤC DATABASE TỪ BACKUP")
        self.restore_button.setObjectName("secondaryButton")
        self.check_backup_button = QPushButton("KIỂM TRA BACKUP GẦN NHẤT")
        self.check_backup_button.setObjectName("outlineButton")
        self.open_data_button = QPushButton("MỞ THƯ MỤC DATA")
        self.open_data_button.setObjectName("outlineButton")
        self.open_backup_button = QPushButton("MỞ THƯ MỤC BACKUP")
        self.open_backup_button.setObjectName("outlineButton")
        self.check_space_button = QPushButton("KIỂM TRA DUNG LƯỢNG")
        self.check_space_button.setObjectName("outlineButton")
        self.inventory_button = QPushButton("KIỂM TRA KHO BACKUP")
        self.inventory_button.setObjectName("outlineButton")
        self.integrity_inventory_button = QPushButton("KIỂM TRA TOÀN VẸN KHO")
        self.integrity_inventory_button.setObjectName("outlineButton")
        data_row = QHBoxLayout(); data_row.addWidget(self.data_root); data_row.addWidget(choose_data)
        backup_row = QHBoxLayout(); backup_row.addWidget(self.backup_root); backup_row.addWidget(choose_backup)
        data_form.addRow("Data vận hành:", data_row)
        data_form.addRow("Data backup:", backup_row)
        location_actions = QHBoxLayout()
        location_actions.addWidget(self.save_locations_button)
        location_actions.addWidget(self.locations_state)
        location_actions.addWidget(self.backup_button)
        data_form.addRow(location_actions)
        data_form.addRow(self.restore_button)
        data_form.addRow(self.check_backup_button)
        data_form.addRow(self.check_space_button)
        data_form.addRow(self.inventory_button)
        data_form.addRow(self.integrity_inventory_button)
        folder_actions = QHBoxLayout()
        folder_actions.addWidget(self.open_data_button)
        folder_actions.addWidget(self.open_backup_button)
        data_form.addRow(folder_actions)
        login_group = QGroupBox("04  ĐĂNG NHẬP QUẢN TRỊ")
        login_form = QFormLayout(login_group)
        login_form.setContentsMargins(8, 9, 8, 7)
        login_form.setSpacing(3)
        self.username = QLineEdit()
        self.username.setPlaceholderText("Tài khoản quản trị")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Mật khẩu")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_button = QPushButton("ĐĂNG NHẬP")
        self.login_button.setObjectName("primaryButton")
        self.reveal_admin_password_button = QPushButton("XEM MẬT KHẨU ADMIN ĐÃ LƯU")
        self.reveal_admin_password_button.setObjectName("outlineButton")
        self.login_state = QLabel("Chưa đăng nhập")
        login_form.addRow("Tên đăng nhập:", self.username)
        login_form.addRow("Mật khẩu:", self.password)
        login_form.addRow(self.login_button, self.login_state)
        login_form.addRow(self.reveal_admin_password_button)

        accounts = QGroupBox("05  TÀI KHOẢN LAN")
        accounts_form = QFormLayout(accounts)
        accounts_form.setContentsMargins(8, 9, 8, 7)
        accounts_form.setSpacing(3)
        self.account_username = QLineEdit()
        self.account_username.setPlaceholderText("Tên đăng nhập mới")
        self.account_password = QLineEdit()
        self.account_password.setPlaceholderText("Mật khẩu tài khoản mới")
        self.account_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.account_role = QComboBox()
        self.account_role.addItems(["EDITOR", "VIEWER", "ADMIN"])
        self.create_button = QPushButton("TẠO TÀI KHOẢN")
        self.create_button.setObjectName("primaryButton")
        self.create_button.setEnabled(False)
        accounts_form.addRow("Tên đăng nhập:", self.account_username)
        accounts_form.addRow("Mật khẩu:", self.account_password)
        accounts_form.addRow("Quyền:", self.account_role)
        accounts_form.addRow(self.create_button)
        registered = QGroupBox("06  QUẢN LÝ TÀI KHOẢN ĐÃ ĐĂNG KÝ")
        registered_layout = QVBoxLayout(registered)
        registered_layout.setContentsMargins(8, 9, 8, 7)
        self.accounts_table = QTableWidget(0, 4)
        self.accounts_table.setHorizontalHeaderLabels(["Tên đăng nhập", "Quyền", "Trạng thái", "Mã nội bộ"])
        self.accounts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.accounts_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.accounts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.accounts_table.setFixedHeight(92)
        self.accounts_table.horizontalHeader().setStretchLastSection(True)
        registered_layout.addWidget(self.accounts_table)
        account_filter_actions = QHBoxLayout()
        self.account_filter = QLineEdit()
        self.account_filter.setPlaceholderText("Lọc theo tên hoặc mã nội bộ")
        self.account_role_filter = QComboBox()
        self.account_role_filter.addItems(["TẤT CẢ QUYỀN", "ADMIN", "EDITOR", "VIEWER"])
        self.account_status_filter = QComboBox()
        self.account_status_filter.addItems(["TẤT CẢ TRẠNG THÁI", "ĐANG HOẠT ĐỘNG", "ĐÃ TẮT"])
        account_filter_actions.addWidget(self.account_filter)
        account_filter_actions.addWidget(self.account_role_filter)
        account_filter_actions.addWidget(self.account_status_filter)
        registered_layout.addLayout(account_filter_actions)
        account_actions = QHBoxLayout()
        self.refresh_accounts_button = QPushButton("LÀM MỚI DANH SÁCH")
        self.selected_role = QComboBox()
        self.selected_role.addItems(["EDITOR", "VIEWER", "ADMIN"])
        self.change_role_button = QPushButton("CẬP NHẬT QUYỀN")
        self.toggle_account_button = QPushButton("BẬT / TẮT TÀI KHOẢN")
        self.new_selected_password = QLineEdit()
        self.new_selected_password.setPlaceholderText("Mật khẩu mới cho tài khoản đã chọn")
        self.new_selected_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.reset_password_button = QPushButton("ĐỔI MẬT KHẨU")
        for button in (self.refresh_accounts_button, self.change_role_button, self.toggle_account_button):
            button.setObjectName("outlineButton")
            button.setEnabled(False)
            account_actions.addWidget(button)
        account_actions.insertWidget(1, self.selected_role)
        registered_layout.addLayout(account_actions)
        password_actions = QHBoxLayout()
        password_actions.addWidget(self.new_selected_password)
        self.reset_password_button.setObjectName("primaryButton")
        self.reset_password_button.setEnabled(False)
        password_actions.addWidget(self.reset_password_button)
        registered_layout.addLayout(password_actions)
        rename_actions = QHBoxLayout()
        self.new_selected_username = QLineEdit()
        self.new_selected_username.setPlaceholderText("Tên đăng nhập mới cho tài khoản đã chọn")
        self.rename_account_button = QPushButton("ĐỔI TÊN ĐĂNG NHẬP")
        self.rename_account_button.setObjectName("outlineButton")
        self.rename_account_button.setEnabled(False)
        rename_actions.addWidget(self.new_selected_username)
        rename_actions.addWidget(self.rename_account_button)
        registered_layout.addLayout(rename_actions)
        activity = QGroupBox("NHẬT KÝ VẬN HÀNH")
        activity_layout = QVBoxLayout(activity)
        activity_actions = QHBoxLayout()
        self.refresh_button = QPushButton("LÀM MỚI TRẠNG THÁI")
        self.refresh_button.setObjectName("outlineButton")
        self.copy_log_button = QPushButton("SAO CHÉP NHẬT KÝ")
        self.copy_log_button.setObjectName("outlineButton")
        self.clear_log_button = QPushButton("XÓA NHẬT KÝ HIỂN THỊ")
        self.clear_log_button.setObjectName("outlineButton")
        self.last_refresh_label = QLabel("Chưa làm mới")
        self.last_refresh_label.setObjectName("refreshTime")
        activity_actions.addWidget(self.refresh_button)
        activity_actions.addWidget(self.copy_log_button)
        activity_actions.addWidget(self.clear_log_button)
        activity_actions.addStretch()
        activity_actions.addWidget(self.last_refresh_label)
        activity_layout.addLayout(activity_actions)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Trạng thái database và tài khoản sẽ hiển thị ở đây.")
        self.details.setFixedHeight(72)
        activity_layout.addWidget(self.details)
        popup_specs = (
            ("Mạng & cài đặt", "MỞ MẠNG & CÀI ĐẶT", (lan,)),
            ("Dữ liệu & sao lưu", "MỞ DỮ LIỆU & SAO LƯU", (data,)),
            ("Tài khoản", "MỞ TÀI KHOẢN", (login_group, accounts, registered)),
            ("Nhật ký & kiểm tra", "MỞ NHẬT KÝ & KIỂM TRA", (activity,)),
        )
        popup_bar = QGridLayout()
        for index, (_, text, _) in enumerate(popup_specs):
            button = QPushButton(text)
            button.setObjectName("outlineButton")
            self.popup_buttons.append(button)
            popup_bar.addWidget(button, 0, index)
        layout.addLayout(popup_bar)
        for index, (popup_title, _, widgets) in enumerate(popup_specs):
            popup = QMainWindow(self)
            popup.setWindowTitle(popup_title)
            popup.resize(780, 620)
            popup_root = QWidget()
            popup_layout = QVBoxLayout(popup_root)
            for widget in widgets:
                popup_layout.addWidget(widget)
            popup.setCentralWidget(popup_root)
            self._popups[popup_title] = popup
            self.popup_buttons[index].clicked.connect(popup.show)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(root)
        self.setCentralWidget(scroll)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f4f7fb; color: #182230; font: 8pt 'Segoe UI'; }
            QLabel#title { color: #0d3b66; font: 700 16pt 'Segoe UI'; letter-spacing: 1px; }
            QLabel#subtitle { color: #5d6b7b; font: 8pt 'Segoe UI'; padding-bottom: 1px; }
            QGroupBox { background: #ffffff; border: 1px solid #d9e2ec; border-radius: 6px; margin-top: 7px; padding: 7px 5px 5px 5px; font: 700 8pt 'Segoe UI'; color: #274c77; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; background: #ffffff; }
            QGroupBox#heroCard { border: 1px solid #b9d8e8; background: #f8fcff; }
            QGroupBox#heroCard::title { background: #f8fcff; }
            QGroupBox#overviewCard { border: 1px solid #d3e4dc; background: #fbfffd; }
            QGroupBox#overviewCard::title { background: #fbfffd; }
            QLineEdit, QComboBox { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px; min-height: 16px; color: #182230; }
            QLineEdit:focus, QComboBox:focus { border: 2px solid #168aad; }
            QPushButton { border-radius: 4px; padding: 4px 7px; min-height: 16px; font: 700 8pt 'Segoe UI'; }
            QPushButton#primaryButton { background: #0b7285; color: white; border: 1px solid #0b7285; }
            QPushButton#primaryButton:hover { background: #095c6d; }
            QPushButton#secondaryButton { background: #edf5f7; color: #0b5563; border: 1px solid #aad7dd; }
            QPushButton#outlineButton { background: #ffffff; color: #155e75; border: 1px solid #9fc6d1; }
            QPushButton#outlineButton:hover { background: #edf8fa; }
            QPushButton:disabled { background: #e5e7eb; color: #9ca3af; border-color: #e5e7eb; }
            QLabel#serverUrl, QLabel#lanAddress { color: #0b7285; font: 700 8pt 'Consolas'; }
            QLabel#status, QLabel#listenerState, QLabel#lanReadinessState, QLabel#firewallState { font: 700 8pt 'Segoe UI'; }
            QLabel#status, QLabel#lanReadinessState { color: #176b42; }
            QLabel#listenerState { color: #155e75; }
            QLabel#firewallState { color: #9a3412; }
            QLabel#locationsState { color: #9a3412; font: 700 8pt 'Segoe UI'; }
            QLabel#sectionLabel { color: #526779; font: 700 8pt 'Segoe UI'; letter-spacing: 1px; }
            QLabel#refreshTime { color: #617487; font: 8pt 'Segoe UI'; }
            QLabel#overviewCaption { color: #617487; font: 700 8pt 'Segoe UI'; }
            QLabel#overviewValue { color: #155e75; font: 700 9pt 'Segoe UI'; }
            QProgressBar { border: 1px solid #9fc6d1; border-radius: 4px; text-align: center; min-height: 16px; background: #ffffff; }
            QProgressBar::chunk { background: #0b7285; border-radius: 3px; }
            QPlainTextEdit { background: #102a43; color: #d9e2ec; border: 0; border-radius: 5px; padding: 5px; font: 8pt 'Consolas'; }
            QTableWidget { background: #ffffff; alternate-background-color: #f5f9fc; border: 1px solid #d9e2ec; border-radius: 6px; gridline-color: #e5edf3; }
            QHeaderView::section { background: #eaf3f8; color: #274c77; border: 0; border-bottom: 1px solid #cddfe8; padding: 5px; font-weight: 700; }
            QTableWidget::item:selected { background: #cfeef2; color: #12303b; }
        """)
        self.start_button.clicked.connect(self.start_server)
        self.stop_button.clicked.connect(self.stop_server)
        self.restart_external_button.clicked.connect(self.restart_external_server)
        self.listener_button.clicked.connect(self.check_listener_status)
        self.lan_readiness_button.clicked.connect(self.assess_lan_readiness)
        self.copy_lan_button.clicked.connect(self.copy_desktop_url)
        self.report_button.clicked.connect(self.copy_readiness_report)
        self.check_firewall_button.clicked.connect(self.check_firewall_status)
        self.refresh_button.clicked.connect(self.refresh_status)
        self.copy_log_button.clicked.connect(self.copy_activity_log)
        self.clear_log_button.clicked.connect(self.clear_activity_log)
        self.check_backup_button.clicked.connect(self.check_latest_backup)
        self.check_space_button.clicked.connect(self.check_disk_space)
        self.inventory_button.clicked.connect(self.check_backup_inventory)
        self.integrity_inventory_button.clicked.connect(self.check_backup_integrity_inventory)
        self.open_data_button.clicked.connect(lambda: self.open_folder(Path(self.data_root.text())))
        self.open_backup_button.clicked.connect(lambda: self.open_folder(Path(self.backup_root.text())))
        self.login_button.clicked.connect(self.login)
        self.reveal_admin_password_button.clicked.connect(self.reveal_saved_admin_password)
        self.create_button.clicked.connect(self.create_account)
        self.refresh_accounts_button.clicked.connect(self.refresh_accounts)
        self.change_role_button.clicked.connect(self.change_selected_role)
        self.toggle_account_button.clicked.connect(self.toggle_selected_account)
        self.reset_password_button.clicked.connect(self.reset_selected_password)
        self.rename_account_button.clicked.connect(self.rename_selected_account)
        self.accounts_table.itemSelectionChanged.connect(self.select_account)
        self.account_filter.textChanged.connect(self.apply_account_filters)
        self.account_role_filter.currentTextChanged.connect(self.apply_account_filters)
        self.account_status_filter.currentTextChanged.connect(self.apply_account_filters)
        self.firewall_button.clicked.connect(self.open_firewall)
        self.repair_lan_button.clicked.connect(self.repair_private_lan)
        self.install_postgresql_button.clicked.connect(self.install_postgresql)
        self.setup_production_button.clicked.connect(self.setup_production_server)
        self.apply_ip_button.clicked.connect(self.apply_static_ip)
        choose_data.clicked.connect(lambda: self.choose_directory(self.data_root))
        choose_backup.clicked.connect(lambda: self.choose_directory(self.backup_root))
        self.save_locations_button.clicked.connect(self.save_locations)
        self.data_root.textChanged.connect(self.update_locations_state)
        self.backup_root.textChanged.connect(self.update_locations_state)
        self.backup_button.clicked.connect(self.backup_database)
        self.restore_button.clicked.connect(self.restore_database)
        self.start_with_windows_checkbox.toggled.connect(self.update_autostart_preference)

    def update_autostart_preference(self, enabled: bool) -> None:
        previous = bool(self._settings["start_server_with_windows"])
        try:
            set_current_user_autostart(enabled)
        except Exception as exc:
            self._restore_autostart_checkbox(previous)
            QMessageBox.critical(self, "Không thể cập nhật tự khởi động", str(exc))
            return
        try:
            save_autostart_preference(enabled)
        except Exception as exc:
            try:
                set_current_user_autostart(previous)
            except Exception:
                pass
            self._restore_autostart_checkbox(previous)
            QMessageBox.critical(
                self,
                "Không thể lưu tùy chọn tự khởi động",
                f"Đã hoàn tác tác vụ tự khởi động về trạng thái trước. {exc}",
            )
            return
        self._settings["start_server_with_windows"] = enabled

    def _restore_autostart_checkbox(self, checked: bool) -> None:
        self.start_with_windows_checkbox.blockSignals(True)
        self.start_with_windows_checkbox.setChecked(checked)
        self.start_with_windows_checkbox.blockSignals(False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._autostart_reconciled:
            self._autostart_reconciled = True
            self._reconcile_autostart_task()

    def _reconcile_autostart_task(self) -> None:
        """Align the logon task with the saved preference when the Tool opens."""
        enabled = bool(self._settings["start_server_with_windows"])
        try:
            exists = current_user_autostart_exists()
            if enabled and not exists:
                set_current_user_autostart(True)
            elif not enabled and exists:
                set_current_user_autostart(False)
        except Exception as exc:
            self.append_activity(f"TỰ KHỞI ĐỘNG: Không đồng bộ được tác vụ. {exc}")
            try:
                self._restore_autostart_checkbox(current_user_autostart_exists())
            except Exception:
                pass

    @staticmethod
    def _server_listening() -> bool:
        try:
            with socket.create_connection(("127.0.0.1", 8010), timeout=0.3):
                return True
        except OSError:
            return False

    @staticmethod
    def _lan_address() -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                probe.connect(("8.8.8.8", 80))
                return f"http://{probe.getsockname()[0]}:{LAN_PORT}"
        except OSError:
            return "Không xác định được IP LAN"

    def choose_directory(self, target: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Chọn thư mục")
        if selected:
            target.setText(selected)

    def update_locations_state(self) -> None:
        saved = locations_are_saved(self.data_root.text(), self.backup_root.text(), self._settings)
        self.locations_state.setText("ĐÃ LƯU" if saved else "CHƯA LƯU THAY ĐỔI")

    def copy_desktop_url(self) -> None:
        url = self._lan_address()
        QApplication.clipboard().setText(url)
        self.status_label.setText("Đã sao chép URL kết nối cho HMS QR Desktop.")

    def copy_activity_log(self) -> None:
        QApplication.clipboard().setText(self.details.toPlainText())
        self.status_label.setText("Đã sao chép nhật ký vận hành.")

    def reveal_saved_admin_password(self) -> None:
        if not _is_windows_admin():
            QMessageBox.warning(self, "Cần quyền Administrator", "Hãy mở HMS QR Server Tool bằng Run as administrator để xem mật khẩu ADMIN đã lưu.")
            return
        if QMessageBox.question(
            self,
            "Xem mật khẩu ADMIN",
            "Hiển thị mật khẩu ADMIN đã lưu trên màn hình này? Không sao chép vào clipboard và không ghi vào nhật ký.",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            password = load_server_secret("admin_password")
        except (RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Không thể mở mật khẩu", str(exc))
            return
        QMessageBox.information(self, "Mật khẩu ADMIN đã lưu", password)

    def clear_activity_log(self) -> None:
        message = "Chỉ xóa nội dung nhật ký đang hiển thị trong HMS QR Server Tool. Database, audit Server và Windows Event Log không bị thay đổi."
        if QMessageBox.question(self, "Xóa nhật ký hiển thị", message) != QMessageBox.StandardButton.Yes:
            return
        self.details.clear()
        self.status_label.setText("Đã xóa nhật ký hiển thị trong Tool.")

    def append_activity(self, message: str) -> None:
        lines = self.details.toPlainText().splitlines()
        timestamp = datetime.now().strftime("%H:%M:%S")
        lines.extend(f"[{timestamp}] {line}" for line in message.splitlines() if line.strip())
        self.details.setPlainText("\n".join(lines[-MAX_ACTIVITY_LOG_LINES:]))
        self.details.verticalScrollBar().setValue(self.details.verticalScrollBar().maximum())

    def copy_readiness_report(self) -> None:
        QApplication.clipboard().setText(operational_readiness_report(self._settings))
        self.status_label.setText("Đã sao chép báo cáo sẵn sàng vận hành.")

    def check_firewall_status(self) -> None:
        status = firewall_private_status()
        network = active_lan_network_status()
        self.firewall_state.setText(status)
        self.network_profile_state.setText(network)
        self.append_activity(f"FIREWALL TCP {LAN_PORT} PRIVATE: {status}\nPROFILE MẠNG LAN: {network}")

    def check_listener_status(self) -> None:
        status = lan_listener_status()
        self.listener_state.setText(status)
        self.append_activity(f"LẮNG NGHE TCP {LAN_PORT}: {status}")

    def assess_lan_readiness(self) -> None:
        try:
            _request("/health/readiness/database")
            database_ready = True
        except RuntimeError:
            database_ready = False
        listener = lan_listener_status()
        firewall = firewall_private_status()
        network = active_lan_network_status()
        assessment = lan_readiness_assessment(database_ready, listener, firewall)
        self.listener_state.setText(listener)
        self.firewall_state.setText(firewall)
        self.network_profile_state.setText(network)
        self.lan_readiness_state.setText(assessment)
        self.lan_checklist.setPlainText("\n".join(lan_readiness_checklist(database_ready, listener, firewall)))
        self.append_activity(f"ĐÁNH GIÁ LAN: {assessment}")

    def save_locations(self) -> None:
        try:
            save_tool_settings(self.data_root.text(), self.backup_root.text())
            self._settings = load_tool_settings()
            self.update_locations_state()
            QMessageBox.information(self, "Đã lưu", "Đã kiểm tra và lưu vị trí data. Khởi động lại Server Tool để áp dụng data vận hành mới.")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Không thể lưu", str(exc))

    def backup_database(self) -> None:
        try:
            pg_dump = POSTGRESQL_INSTALL_ROOT / "bin" / "pg_dump.exe"
            if pg_dump.is_file():
                target = postgresql_backup_path(Path(self._settings["backup_root"]))
                environment = os.environ.copy()
                environment["PGPASSWORD"] = load_server_secret("database_password")
                result = subprocess.run(
                    [str(pg_dump), "-h", "127.0.0.1", "-p", str(POSTGRESQL_PORT), "-U", PRODUCTION_DATABASE_USER, "-d", PRODUCTION_DATABASE, "-Fc", "-f", str(target)],
                    env=environment, capture_output=True, text=True, check=False,
                )
                if result.returncode or not target.is_file() or not target.stat().st_size:
                    target.unlink(missing_ok=True)
                    raise RuntimeError("PostgreSQL backup không hoàn tất.")
                pg_restore = POSTGRESQL_INSTALL_ROOT / "bin" / "pg_restore.exe"
                verified = subprocess.run([str(pg_restore), "-l", str(target)], capture_output=True, text=True, check=False)
                if verified.returncode:
                    target.unlink(missing_ok=True)
                    raise RuntimeError("PostgreSQL backup không thể kiểm tra.")
                self.overview_backup.setText(target.name)
                self.overview_backup_freshness.setText(backup_freshness(target))
                self.append_activity(f"SAO LƯU POSTGRESQL: Đã tạo và kiểm tra {target.name}")
                QMessageBox.information(self, "Sao lưu đã xác minh", f"Đã tạo PostgreSQL backup: {target.name}")
                return
            database = Path(self._settings["data_root"]) / "hms_qr_test.sqlite"
            target = backup_sqlite(database, Path(self._settings["backup_root"]))
            verification = check_sqlite_backup(target)
            self.overview_backup.setText(target.name)
            self.overview_backup_freshness.setText(backup_freshness(target))
            self.append_activity(f"SAO LƯU: Đã tạo {target.name}\n{verification}")
            QMessageBox.information(self, "Sao lưu đã xác minh", f"Đã tạo backup: {target.name}\n{verification}")
        except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Backup chưa được xác minh", str(exc))

    def restore_database(self) -> None:
        if production_postgresql_is_installed():
            self.restore_postgresql_database()
            return
        if self._server_listening() and (not self._server_process or self._server_process.state() == QProcess.ProcessState.NotRunning):
            QMessageBox.warning(self, "Không thể khôi phục", "Server hiện do process bên ngoài Tool quản lý. Hãy dừng Server đó và thực hiện restore theo runbook.")
            return
        backup_root = Path(self._settings["backup_root"]).resolve(strict=False)
        selected, _ = QFileDialog.getOpenFileName(self, "Chọn SQLite backup để khôi phục", str(backup_root), "HMS QR SQLite backup (hms_qr_*.sqlite)")
        if not selected:
            return
        backup = Path(selected).resolve(strict=False)
        if backup.parent != backup_root or not backup.match("hms_qr_*.sqlite"):
            QMessageBox.warning(self, "Backup không hợp lệ", "Chỉ được khôi phục snapshot HMS QR trong thư mục Backup đã cấu hình.")
            return
        try:
            check_sqlite_backup(backup)
        except (OSError, ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Backup không hợp lệ", str(exc))
            return
        warning = f"Khôi phục '{backup.name}' sẽ thay database hiện tại. Tool sẽ tạo safety backup trước khi thay thế và khởi động lại Server do Tool quản lý. Tiếp tục?"
        if QMessageBox.question(self, "Xác nhận khôi phục SQLite", warning) != QMessageBox.StandardButton.Yes:
            return
        owned_server_running = bool(self._server_process and self._server_process.state() != QProcess.ProcessState.NotRunning)
        if owned_server_running:
            self.stop_server()
        try:
            database = Path(self._settings["data_root"]) / "hms_qr_test.sqlite"
            safety_backup = restore_sqlite_database(database, backup, backup_root)
            self.append_activity(f"KHÔI PHỤC SQLITE: Đã dùng {backup.name}\nSAFETY BACKUP: {safety_backup.name if safety_backup else 'Không có database trước đó'}")
            QMessageBox.information(self, "Khôi phục hoàn tất", "Database đã được thay thế từ backup đã xác minh.")
        except (OSError, ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Khôi phục không hoàn tất", str(exc))
            return
        finally:
            if owned_server_running:
                self.start_server()

    def restore_postgresql_database(self) -> None:
        if self._server_listening() and (not self._server_process or self._server_process.state() == QProcess.ProcessState.NotRunning):
            QMessageBox.warning(self, "Không thể khôi phục", "Server hiện do process bên ngoài Tool quản lý. Hãy dừng Server đó trước khi khôi phục.")
            return
        backup_root = Path(self._settings["backup_root"]).resolve(strict=False)
        selected, _ = QFileDialog.getOpenFileName(self, "Chọn PostgreSQL backup để khôi phục", str(backup_root), "HMS QR PostgreSQL backup (hms_qr_*.dump)")
        if not selected:
            return
        backup = Path(selected).resolve(strict=False)
        if backup.parent != backup_root or not backup.match("hms_qr_*.dump"):
            QMessageBox.warning(self, "Backup không hợp lệ", "Chỉ được khôi phục dump HMS QR trong thư mục Backup đã cấu hình.")
            return
        pg_restore = POSTGRESQL_INSTALL_ROOT / "bin" / "pg_restore.exe"
        verified = subprocess.run([str(pg_restore), "-l", str(backup)], capture_output=True, text=True, check=False)
        if verified.returncode:
            QMessageBox.warning(self, "Backup không hợp lệ", "Không thể kiểm tra PostgreSQL dump đã chọn.")
            return
        warning = f"Khôi phục '{backup.name}' sẽ thay toàn bộ database PostgreSQL hiện tại. Tool tạo safety dump trước khi thay thế. Tiếp tục?"
        if QMessageBox.question(self, "Xác nhận khôi phục PostgreSQL", warning) != QMessageBox.StandardButton.Yes:
            return
        owned_server_running = bool(self._server_process and self._server_process.state() != QProcess.ProcessState.NotRunning)
        if owned_server_running:
            self.stop_server()
        try:
            safety = postgresql_backup_path(backup_root)
            environment = os.environ.copy()
            environment["PGPASSWORD"] = load_server_secret("database_password")
            dumped = subprocess.run([str(POSTGRESQL_INSTALL_ROOT / "bin" / "pg_dump.exe"), "-h", "127.0.0.1", "-p", str(POSTGRESQL_PORT), "-U", PRODUCTION_DATABASE_USER, "-d", PRODUCTION_DATABASE, "-Fc", "-f", str(safety)], env=environment, capture_output=True, text=True, check=False)
            if dumped.returncode or not safety.is_file() or not safety.stat().st_size:
                safety.unlink(missing_ok=True)
                raise RuntimeError("Không tạo được safety backup PostgreSQL.")
            restored = subprocess.run(postgresql_restore_command(backup), env=environment, capture_output=True, text=True, check=False)
            if restored.returncode:
                raise RuntimeError("Khôi phục PostgreSQL không hoàn tất. Safety backup vẫn được giữ lại.")
            self.append_activity(f"KHÔI PHỤC POSTGRESQL: Đã dùng {backup.name}\nSAFETY BACKUP: {safety.name}")
            QMessageBox.information(self, "Khôi phục hoàn tất", "PostgreSQL đã được khôi phục từ backup đã xác minh.")
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Khôi phục không hoàn tất", str(exc))
        finally:
            if owned_server_running:
                self.start_server()

    def check_latest_backup(self) -> None:
        backup = latest_sqlite_backup(Path(self.backup_root.text()))
        if backup is None:
            QMessageBox.information(self, "Chưa có backup", "Chưa tìm thấy backup SQLite trong thư mục đã chọn.")
            return
        try:
            message = check_sqlite_backup(backup)
            self.overview_backup.setText(backup.name)
            QMessageBox.information(self, "Kiểm tra backup", message)
        except (OSError, ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Backup không hợp lệ", str(exc))

    def check_disk_space(self) -> None:
        data_status = disk_space_status(Path(self.data_root.text()))
        backup_status = disk_space_status(Path(self.backup_root.text()))
        self.overview_disk.setText(data_status)
        self.append_activity(f"DUNG LƯỢNG DATA: {data_status}\nDUNG LƯỢNG BACKUP: {backup_status}")

    def check_backup_inventory(self) -> None:
        inventory = backup_inventory(Path(self.backup_root.text()))
        self.overview_inventory.setText(inventory)
        self.append_activity(f"KHO BACKUP: {inventory}")

    def check_backup_integrity_inventory(self) -> None:
        summary, invalid = backup_integrity_details(Path(self.backup_root.text()))
        details = "\n".join(f"- {name}" for name in invalid[:10])
        more = f"\n- ... và {len(invalid) - 10} file khác" if len(invalid) > 10 else ""
        self.append_activity(f"TOÀN VẸN KHO BACKUP: {summary}" + (f"\nFILE LỖI:\n{details}{more}" if invalid else ""))
        QMessageBox.information(self, "Toàn vẹn kho backup", summary)

    def open_folder(self, folder: Path) -> None:
        try:
            folder = _validated_root(str(folder))
            os.startfile(str(folder))
        except OSError as exc:
            QMessageBox.warning(self, "Không thể mở thư mục", str(exc))

    def refresh_accounts(self) -> None:
        if not self._token:
            return
        try:
            items = _request("/admin-api/api/v1/admin/accounts", token=self._token)["items"]
        except (KeyError, RuntimeError) as exc:
            QMessageBox.warning(self, "Không thể tải tài khoản", str(exc))
            return
        self.accounts_table.setRowCount(len(items))
        for row, account in enumerate(items):
            values = (
                str(account["username"]),
                str(account["role"]),
                "ĐANG HOẠT ĐỘNG" if account["active"] else "ĐÃ TẮT",
                str(account["internal_id"]),
            )
            for column, value in enumerate(values):
                self.accounts_table.setItem(row, column, QTableWidgetItem(value))
        self.accounts_table.resizeColumnsToContents()
        self.apply_account_filters()
        self.append_activity(f"TÀI KHOẢN: Đã tải {len(items)} tài khoản.")

    def apply_account_filters(self) -> None:
        query = self.account_filter.text().strip().casefold()
        role = self.account_role_filter.currentText()
        status = self.account_status_filter.currentText()
        for row in range(self.accounts_table.rowCount()):
            username = self.accounts_table.item(row, 0).text().casefold()
            account_role = self.accounts_table.item(row, 1).text()
            account_status = self.accounts_table.item(row, 2).text()
            identifier = self.accounts_table.item(row, 3).text().casefold()
            self.accounts_table.setRowHidden(
                row,
                (bool(query) and query not in username and query not in identifier)
                or (role != "TẤT CẢ QUYỀN" and role != account_role)
                or (status != "TẤT CẢ TRẠNG THÁI" and status != account_status),
            )

    def _selected_account(self) -> tuple[str, str, bool] | None:
        row = self.accounts_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Chọn tài khoản", "Chọn một tài khoản trong danh sách trước khi cập nhật.")
            return None
        return (
            self.accounts_table.item(row, 3).text(),
            self.accounts_table.item(row, 0).text(),
            self.accounts_table.item(row, 2).text() == "ĐANG HOẠT ĐỘNG",
        )

    def select_account(self) -> None:
        selected = self._selected_account()
        if selected is None:
            return
        row = self.accounts_table.currentRow()
        self.selected_role.setCurrentText(self.accounts_table.item(row, 1).text())
        self.change_role_button.setEnabled(True)
        self.toggle_account_button.setEnabled(True)
        self.reset_password_button.setEnabled(True)
        self.rename_account_button.setEnabled(True)

    def change_selected_role(self) -> None:
        selected = self._selected_account()
        if selected is None:
            return
        identifier, username, _active = selected
        role = self.selected_role.currentText()
        if QMessageBox.question(self, "Cập nhật quyền", f"Đổi quyền của '{username}' thành {role}?") != QMessageBox.StandardButton.Yes:
            return
        try:
            _request(f"/admin-api/api/v1/admin/accounts/{identifier}", token=self._token, method="PATCH", payload={"role": role})
            self.refresh_accounts()
            self.append_activity(f"TÀI KHOẢN: Đã đổi quyền '{username}' thành {role}.")
        except RuntimeError as exc:
            QMessageBox.warning(self, "Không thể cập nhật quyền", str(exc))

    def toggle_selected_account(self) -> None:
        selected = self._selected_account()
        if selected is None:
            return
        identifier, username, active = selected
        next_active = not active
        action = "bật" if next_active else "tắt"
        if QMessageBox.question(self, "Cập nhật tài khoản", f"{action.capitalize()} tài khoản '{username}'?") != QMessageBox.StandardButton.Yes:
            return
        try:
            _request(f"/admin-api/api/v1/admin/accounts/{identifier}", token=self._token, method="PATCH", payload={"active": next_active})
            self.refresh_accounts()
            self.append_activity(f"TÀI KHOẢN: Đã {action} '{username}'.")
        except RuntimeError as exc:
            QMessageBox.warning(self, "Không thể cập nhật tài khoản", str(exc))

    def reset_selected_password(self) -> None:
        selected = self._selected_account()
        if selected is None:
            return
        password = self.new_selected_password.text()
        if not password:
            QMessageBox.warning(self, "Thiếu mật khẩu", "Nhập mật khẩu mới trước khi xác nhận.")
            return
        identifier, username, _active = selected
        if QMessageBox.question(self, "Đổi mật khẩu", f"Đổi mật khẩu cho tài khoản '{username}'?") != QMessageBox.StandardButton.Yes:
            return
        try:
            _request(
                f"/admin-api/api/v1/admin/accounts/{identifier}",
                token=self._token,
                method="PATCH",
                payload={"password": password},
            )
            self.new_selected_password.clear()
            self.append_activity(f"TÀI KHOẢN: Đã đổi mật khẩu cho '{username}'.")
            QMessageBox.information(self, "Đã đổi mật khẩu", f"Mật khẩu của '{username}' đã được cập nhật.")
        except RuntimeError as exc:
            QMessageBox.warning(self, "Không thể đổi mật khẩu", str(exc))

    def rename_selected_account(self) -> None:
        selected = self._selected_account()
        if selected is None:
            return
        username = self.new_selected_username.text().strip()
        if not username:
            QMessageBox.warning(self, "Thiếu tên đăng nhập", "Nhập tên đăng nhập mới trước khi xác nhận.")
            return
        identifier, current_username, _active = selected
        if QMessageBox.question(self, "Đổi tên đăng nhập", f"Đổi '{current_username}' thành '{username}'?") != QMessageBox.StandardButton.Yes:
            return
        try:
            _request(
                f"/admin-api/api/v1/admin/accounts/{identifier}",
                token=self._token,
                method="PATCH",
                payload={"username": username},
            )
            self.new_selected_username.clear()
            self.refresh_accounts()
            self.append_activity(f"TÀI KHOẢN: Đã đổi tên '{current_username}' thành '{username}'.")
        except RuntimeError as exc:
            QMessageBox.warning(self, "Không thể đổi tên đăng nhập", str(exc))

    def open_firewall(self) -> None:
        if not _is_windows_admin():
            QMessageBox.warning(self, "Cần quyền Administrator", "Hãy mở HMS QR Server Tool bằng Run as administrator để mở Firewall LAN.")
            return
        if QMessageBox.question(self, "Mở Firewall LAN", "Cho phép TCP 8010 với profile Private để HMS QR Desktop trong LAN kết nối?") != QMessageBox.StandardButton.Yes:
            return
        command = (
            f"if (-not (Get-NetFirewallRule -DisplayName 'HMS QR Server TCP {LAN_PORT}' -ErrorAction SilentlyContinue)) "
            f"{{ New-NetFirewallRule -DisplayName 'HMS QR Server TCP {LAN_PORT}' -Direction Inbound -Action Allow -Protocol TCP -LocalPort {LAN_PORT} -Profile Private -ErrorAction Stop | Out-Null }}"
        )
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, check=False)
        if result.returncode:
            QMessageBox.warning(self, "Không thể mở Firewall", result.stderr or "Lệnh Firewall thất bại.")
            return
        QMessageBox.information(self, "Firewall đã mở", f"TCP {LAN_PORT} đã được cho phép trên mạng Private.")

    def repair_private_lan(self) -> None:
        if not _is_windows_admin():
            QMessageBox.warning(self, "Cần quyền Administrator", "Hãy mở HMS QR Server Tool bằng Run as administrator để đổi profile mạng và sửa Firewall.")
            return
        message = (
            "Tool sẽ đổi adapter đang có default gateway sang profile Private và bật/cập nhật Firewall "
            f"TCP {LAN_PORT}, UDP 8011. Không thay đổi IP, DNS, PostgreSQL hoặc dữ liệu Server. Tiếp tục?"
        )
        if QMessageBox.question(self, "Tự sửa kết nối LAN", message) != QMessageBox.StandardButton.Yes:
            return
        result = subprocess.run(["powershell", "-NoProfile", "-Command", repair_private_lan_command()], capture_output=True, text=True, check=False)
        if result.returncode:
            QMessageBox.warning(self, "Không thể tự sửa LAN", "Windows hoặc Group Policy từ chối thay đổi profile/firewall. Kiểm tra quyền Administrator và Network List Manager Policies.")
            return
        self.check_firewall_status()
        self.append_activity("TỰ SỬA LAN: Đã đặt profile Private và đảm bảo rule TCP 8010 / UDP 8011.")
        QMessageBox.information(self, "Đã tự sửa kết nối LAN", "Đã áp dụng profile Private và Firewall HMS QR. Chạy lại kiểm tra từ Máy 2.")

    def install_postgresql(self) -> None:
        if not _is_windows_admin():
            QMessageBox.warning(self, "Cần quyền Administrator", "Hãy mở HMS QR Server Tool bằng Run as administrator để cài PostgreSQL.")
            return
        message = (
            "Tool sẽ mở installer PostgreSQL 17 chính thức qua Windows Package Manager.\n\n"
            "Bạn phải tự đặt mật khẩu database và thư mục dữ liệu trong installer. Tool không lưu mật khẩu, "
            "không mở cổng PostgreSQL ra LAN, và không thay đổi Firewall.\n\nTiếp tục cài đặt?"
        )
        if QMessageBox.question(self, "Cài PostgreSQL 17", message) != QMessageBox.StandardButton.Yes:
            return
        try:
            installer = verified_postgresql_offline_installer()
            subprocess.Popen([str(installer)])
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Không thể mở installer", f"Không thể chạy Windows Package Manager: {exc}")
            return
        self.append_activity("POSTGRESQL: Đã mở installer PostgreSQL 17 offline đã xác minh.")
        QMessageBox.information(
            self,
            "Installer PostgreSQL đã mở",
            "Hoàn tất installer PostgreSQL offline, sau đó dùng bước thiết lập Server để tạo cấu hình và chạy migration.",
        )

    def setup_production_server(self) -> None:
        if not _is_windows_admin():
            QMessageBox.warning(self, "Cần quyền Administrator", "Mở HMS QR Server Tool bằng Run as administrator để thiết lập Server production.")
            return
        if QMessageBox.question(
            self,
            "Thiết lập Server 1 Click",
            "Tool sẽ tạo data local tại D:\\HMS-QR-PROD, cài/cấu hình PostgreSQL local-only, tạo Server database, "
            "mở Firewall Private TCP 8010 và sinh tài khoản admin. Không có mật khẩu nào được ghi vào log. Tiếp tục?",
        ) != QMessageBox.StandardButton.Yes:
            return
        self.setup_production_button.setEnabled(False)
        try:
            self._set_setup_progress(1, "1/7 Kiểm tra gói cài đặt offline...")
            missing = production_setup_requirements()
            if missing:
                raise ValueError("Release offline chưa đầy đủ: " + ", ".join(missing) + ".")
            installer = verified_postgresql_offline_installer()
            paths = production_paths()
            self._set_setup_progress(2, "2/7 Tạo thư mục local...")
            for folder in paths.values():
                _validated_root(str(folder))
            self._set_setup_progress(2, "2/7 Bảo vệ bí mật Server bằng Windows DPAPI...")
            create_production_secrets()
            psql = POSTGRESQL_INSTALL_ROOT / "bin" / "psql.exe"
            if not psql.is_file():
                self._set_setup_progress(3, "3/7 Đang cài PostgreSQL 17 offline...")
                option_file = paths["root"] / "postgresql-install-options.conf"
                result = run_postgresql_offline_installer(
                    installer,
                    option_file,
                    postgresql_unattended_options(
                        data_root=paths["postgresql"],
                        superpassword=load_server_secret("postgres_password"),
                    ),
                )
                if result.returncode:
                    raise RuntimeError("Cài PostgreSQL offline không hoàn tất.")
            else:
                self._set_setup_progress(3, "3/7 PostgreSQL 17 đã sẵn sàng.")
            self._set_setup_progress(4, "4/7 Tạo database PostgreSQL local-only...")
            self._provision_production_database(psql)
            self._set_setup_progress(5, "5/7 Cập nhật database schema...")
            self._run_production_migrations()
            self._set_setup_progress(6, "6/7 Mở Firewall Private TCP 8010...")
            self._open_production_firewall()
            self.data_root.setText(str(paths["storage"]))
            self.backup_root.setText(str(paths["backups"]))
            save_tool_settings(str(paths["storage"]), str(paths["backups"]))
            self._settings = load_tool_settings()
            self._set_setup_progress(7, "7/7 Đang khởi động HMS QR Server...")
            self.start_server()
            self.setup_progress.setFormat("Hoàn tất thiết lập Server")
            self.append_activity("THIẾT LẬP: Production Server local đã được cấu hình. Tài khoản admin được lưu DPAPI.")
            QMessageBox.information(self, "Thiết lập hoàn tất", "Server đang khởi động. Dùng nút XEM MẬT KHẨU ADMIN ĐÃ LƯU để đăng nhập lần đầu.")
        except Exception as exc:
            self.status_label.setText("THIẾT LẬP CHƯA HOÀN TẤT")
            self.setup_progress.setFormat("Thiết lập chưa hoàn tất")
            self.append_activity(f"THIẾT LẬP LỖI Ở {self.setup_progress.value()}/7: {type(exc).__name__}")
            QMessageBox.warning(self, "Thiết lập chưa hoàn tất", f"Thiết lập dừng ở bước {self.setup_progress.value()}/7 ({type(exc).__name__}). Không có mật khẩu nào được hiển thị; xem Nhật ký hoạt động để xử lý tiếp.")
        finally:
            self.setup_production_button.setEnabled(True)

    def _set_setup_progress(self, value: int, text: str) -> None:
        self.setup_progress.setValue(value)
        self.setup_progress.setFormat(text)
        self.status_label.setText(text)
        QApplication.processEvents()

    def _provision_production_database(self, psql: Path) -> None:
        if not psql.is_file():
            raise RuntimeError("Không tìm thấy PostgreSQL command-line tools sau khi cài đặt.")
        environment = os.environ.copy()
        environment["PGPASSWORD"] = load_server_secret("postgres_password")
        app_password = load_server_secret("database_password").replace("'", "''")
        role_sql = (
            "DO $$ BEGIN "
            f"IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{PRODUCTION_DATABASE_USER}') THEN "
            f"CREATE ROLE {PRODUCTION_DATABASE_USER} LOGIN PASSWORD '{app_password}'; "
            f"ELSE ALTER ROLE {PRODUCTION_DATABASE_USER} LOGIN PASSWORD '{app_password}'; END IF; END $$;"
        )
        command = [str(psql), "-v", "ON_ERROR_STOP=1", "-h", "127.0.0.1", "-p", str(POSTGRESQL_PORT), "-U", "postgres", "-d", "postgres"]
        if subprocess.run(command, input=role_sql, env=environment, capture_output=True, text=True, check=False).returncode:
            raise RuntimeError("Không thể tạo application role PostgreSQL.")
        exists = subprocess.run([str(psql), "-v", "ON_ERROR_STOP=1", "-h", "127.0.0.1", "-p", str(POSTGRESQL_PORT), "-U", "postgres", "-d", "postgres", "-tAc", f"SELECT 1 FROM pg_database WHERE datname = '{PRODUCTION_DATABASE}'"], env=environment, capture_output=True, text=True, check=False)
        if exists.returncode:
            raise RuntimeError("Không thể kiểm tra PostgreSQL database.")
        if exists.stdout.strip() != "1":
            created = subprocess.run([str(psql), "-v", "ON_ERROR_STOP=1", "-h", "127.0.0.1", "-p", str(POSTGRESQL_PORT), "-U", "postgres", "-d", "postgres", "-c", f"CREATE DATABASE {PRODUCTION_DATABASE} OWNER {PRODUCTION_DATABASE_USER}"], env=environment, capture_output=True, text=True, check=False)
            if created.returncode:
                raise RuntimeError("Không thể tạo HMS QR PostgreSQL database.")
        listener = subprocess.run(
            [str(psql), "-h", "127.0.0.1", "-p", str(POSTGRESQL_PORT), "-U", "postgres", "-d", "postgres", "-tAc", "SHOW listen_addresses"],
            env=environment, capture_output=True, text=True, check=False,
        )
        if listener.returncode:
            raise RuntimeError("Không thể kiểm tra PostgreSQL listener.")
        if listener.stdout.strip() != "127.0.0.1":
            if subprocess.run(command, input="ALTER SYSTEM SET listen_addresses = '127.0.0.1';", env=environment, capture_output=True, text=True, check=False).returncode:
                raise RuntimeError("Không thể khóa PostgreSQL về localhost.")
            restarted = subprocess.run(["powershell", "-NoProfile", "-Command", f"Restart-Service -Name '{POSTGRESQL_SERVICE}' -ErrorAction Stop"], capture_output=True, text=True, check=False)
            if restarted.returncode:
                raise RuntimeError("Không thể khởi động lại PostgreSQL sau khi khóa localhost.")

    def _run_production_migrations(self) -> None:
        environment = os.environ.copy()
        environment.update(production_server_environment())
        subprocess.run(["py", "-3.14", "-m", "alembic", "upgrade", "head"], cwd=Path(__file__).resolve().parents[2], env=environment, check=True, capture_output=True, text=True)

    @staticmethod
    def _open_production_firewall() -> None:
        command = (
            f"if (-not (Get-NetFirewallRule -DisplayName 'HMS QR Server TCP {LAN_PORT}' -ErrorAction SilentlyContinue)) "
            f"{{ New-NetFirewallRule -DisplayName 'HMS QR Server TCP {LAN_PORT}' -Direction Inbound -Action Allow -Protocol TCP -LocalPort {LAN_PORT} -Profile Private -ErrorAction Stop | Out-Null }}; "
            "if (-not (Get-NetFirewallRule -DisplayName 'HMS QR Discovery UDP 8011' -ErrorAction SilentlyContinue)) "
            "{ New-NetFirewallRule -DisplayName 'HMS QR Discovery UDP 8011' -Direction Inbound -Action Allow -Protocol UDP -LocalPort 8011 -Profile Private -ErrorAction Stop | Out-Null }"
        )
        if subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, check=False).returncode:
            raise RuntimeError("Không thể mở Windows Firewall Private cho HMS QR Server.")

    def apply_static_ip(self) -> None:
        adapter, address, prefix, gateway = (self.adapter.text().strip(), self.static_ip.text().strip(), self.subnet.text().strip(), self.gateway.text().strip())
        try:
            ipaddress.IPv4Address(address)
            ipaddress.IPv4Address(gateway)
            prefix_value = int(prefix)
            if not 1 <= prefix_value <= 30:
                raise ValueError
            dns_servers = [str(ipaddress.IPv4Address(item.strip())) for item in self.dns.text().split(",") if item.strip()]
            if not adapter or not dns_servers:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Thông tin IP không hợp lệ", "Nhập adapter, IPv4, prefix 1-30, gateway và ít nhất một DNS hợp lệ.")
            return
        if not _is_windows_admin():
            QMessageBox.warning(self, "Cần quyền Administrator", "Hãy mở HMS QR Server Tool bằng Run as administrator để đổi IP tĩnh.")
            return
        message = f"Đổi adapter '{adapter}' sang IP {address}/{prefix_value}, gateway {gateway}, DNS {', '.join(dns_servers)}? Kết nối mạng hiện tại có thể bị ngắt."
        if QMessageBox.question(self, "Xác nhận đổi IP tĩnh", message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        script = (
            f"Get-NetIPAddress -InterfaceAlias '{adapter.replace("'", "''")}' -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
            "Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue; "
            f"New-NetIPAddress -InterfaceAlias '{adapter.replace("'", "''")}' -IPAddress '{address}' -PrefixLength {prefix_value} -DefaultGateway '{gateway}' -ErrorAction Stop; "
            f"Set-DnsClientServerAddress -InterfaceAlias '{adapter.replace("'", "''")}' -ServerAddresses @({','.join(repr(item) for item in dns_servers)}) -ErrorAction Stop"
        )
        result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, check=False)
        if result.returncode:
            QMessageBox.warning(self, "Không thể đổi IP", result.stderr or "Lệnh cấu hình IP thất bại.")
            return
        self.lan_address.setText(self._lan_address())
        self.server_url.setText(self._lan_address())
        QMessageBox.information(self, "Đã áp dụng IP tĩnh", "Đã áp dụng cấu hình. Dùng địa chỉ LAN mới hiển thị để cấu hình HMS QR Desktop.")

    def _server_environment(self) -> QProcessEnvironment:
        environment = QProcessEnvironment.systemEnvironment()
        for name, value in production_server_environment().items():
            environment.insert(name, value)
        return environment

    def start_server(self) -> None:
        if self._server_listening():
            self.status_label.setText("Server đã chạy. Tool đang kết nối đến service hiện có.")
            return
        try:
            migration_environment = os.environ.copy()
            migration_environment.update(production_server_environment())
            subprocess.run(["py", "-3.14", "-m", "alembic", "upgrade", "head"], cwd=Path(__file__).resolve().parents[2], env=migration_environment, check=True, capture_output=True, text=True)
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            QMessageBox.warning(self, "Không thể chuẩn bị Server", getattr(exc, "stderr", "") or str(exc))
            return
        process = QProcess(self)
        process.setProgram("py")
        process.setArguments(["-3.14", "-m", "uvicorn", "apps.server.app:app", "--host", "0.0.0.0", "--port", str(LAN_PORT)])
        process.setWorkingDirectory(str(__import__("pathlib").Path(__file__).resolve().parents[2]))
        process.setProcessEnvironment(self._server_environment())
        process.readyReadStandardError.connect(self._show_server_log)
        process.finished.connect(self._server_finished)
        process.start()
        self._server_process = process
        self.stop_button.setEnabled(True)
        self.status_label.setText("Đang khởi động Server...")

    def restart_external_server(self) -> None:
        if not _is_windows_admin():
            QMessageBox.warning(self, "Cần quyền Administrator", "Hãy mở HMS QR Server Tool bằng Run as administrator để khởi động lại Server đang chạy.")
            return
        if self._server_process and self._server_process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, "Server do Tool quản lý", "Server hiện do Tool này quản lý. Dùng DỪNG SERVER CỦA TOOL rồi KHỞI ĐỘNG SERVER.")
            return
        pids = external_hms_server_pids()
        if not pids:
            QMessageBox.information(self, "Không có Server ngoài Tool", "Không tìm thấy HMS QR Server ngoài Tool cần khởi động lại.")
            return
        if QMessageBox.question(
            self,
            "Khởi động lại HMS QR Server",
            "Tool sẽ dừng đúng process HMS QR đang nghe cổng 8010 rồi khởi động bản Server hiện tại. Không thay đổi PostgreSQL hoặc dữ liệu. Tiếp tục?",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            for pid in pids:
                stopped = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, check=False)
                if stopped.returncode:
                    raise RuntimeError("Windows không dừng được HMS QR Server đang chạy.")
            deadline = datetime.now().timestamp() + 5
            while self._server_listening() and datetime.now().timestamp() < deadline:
                QApplication.processEvents()
            if self._server_listening():
                raise RuntimeError("Cổng 8010 vẫn đang được process khác sử dụng.")
        except (OSError, RuntimeError) as exc:
            QMessageBox.warning(self, "Không thể khởi động lại Server", str(exc))
            return
        self.append_activity("KHỞI ĐỘNG LẠI SERVER: Đã dừng process HMS QR cũ; đang chạy bản hiện tại.")
        self.start_server()

    def _server_finished(self) -> None:
        self.stop_button.setEnabled(False)

    def closeEvent(self, event) -> None:
        for popup in self._popups.values():
            popup.close()
        self.stop_server()
        super().closeEvent(event)

    def stop_server(self) -> None:
        if self._server_process and self._server_process.state() != QProcess.ProcessState.NotRunning:
            self._server_process.terminate()
            if not self._server_process.waitForFinished(3000):
                self._server_process.kill()
        self.stop_button.setEnabled(False)
        self.refresh_status()

    def _show_server_log(self) -> None:
        if self._server_process:
            self.append_activity(bytes(self._server_process.readAllStandardError()).decode(errors="replace").strip())

    def refresh_status(self) -> None:
        self.overview_lan.setText(self._lan_address())
        self.overview_data.setText(Path(self._settings["data_root"]).name or self._settings["data_root"])
        backup_root = Path(self._settings["backup_root"])
        latest_backup = latest_postgresql_backup(backup_root) or latest_sqlite_backup(backup_root)
        self.overview_backup.setText(
            latest_backup.name if latest_backup else "CHƯA CÓ BACKUP"
        )
        self.overview_backup_freshness.setText(backup_freshness(latest_backup))
        self.overview_disk.setText(disk_space_status(Path(self._settings["data_root"])))
        self.overview_inventory.setText(postgresql_backup_inventory(backup_root) if latest_postgresql_backup(backup_root) else backup_inventory(backup_root))
        try:
            database = _request("/health/readiness/database")
            self.status_label.setText("SERVER SẴN SÀNG")
            self.overview_server.setText("SẴN SÀNG")
        except RuntimeError:
            self.status_label.setText("SERVER CHƯA CHẠY")
            self.overview_server.setText("CHƯA CHẠY")
            self.last_refresh_label.setText(f"Cập nhật: {datetime.now():%H:%M:%S}")
            self.append_activity("SERVER: CHƯA CHẠY\nDatabase và File transfer chưa thể kiểm tra.")
            return
        try:
            files: dict | str = _request("/files/health/readiness/files")
        except RuntimeError as exc:
            files = f"FILE TRANSFER CHƯA SẴN SÀNG: {exc}"
        database_state = database.get("status", "SẴN SÀNG") if isinstance(database, dict) else "SẴN SÀNG"
        files_state = files.get("status", "SẴN SÀNG") if isinstance(files, dict) else files
        self.append_activity(
            f"SERVER: SẴN SÀNG\nDATABASE: {database_state}\nFILE TRANSFER: {files_state}\n\n"
            f"Chi tiết kỹ thuật:\n{json.dumps({'database': database, 'files': files}, ensure_ascii=False, indent=2)}"
        )
        self.last_refresh_label.setText(f"Cập nhật: {datetime.now():%H:%M:%S}")

    def login(self) -> None:
        try:
            result = _request("/admin-api/api/v1/auth/login", method="POST", payload={"username": self.username.text(), "password": self.password.text()})
            self._token = result["access_token"]
            self.login_state.setText(f"Đã đăng nhập: {result['username']} ({result['role']})")
            self.create_button.setEnabled(result["role"] == "ADMIN")
            self.refresh_accounts_button.setEnabled(result["role"] == "ADMIN")
            self.refresh_accounts()
        except RuntimeError as exc:
            QMessageBox.warning(self, "Đăng nhập không thành công", str(exc))

    def create_account(self) -> None:
        try:
            _request("/admin-api/api/v1/admin/accounts", token=self._token, method="POST", payload={"username": self.account_username.text(), "password": self.account_password.text(), "role": self.account_role.currentText()})
            self.account_username.clear()
            self.account_password.clear()
            self.refresh_accounts()
        except RuntimeError as exc:
            QMessageBox.warning(self, "Không thể tạo tài khoản", str(exc))


def run() -> None:
    app = QApplication.instance() or QApplication([])
    window = ServerToolWindow()
    window.show()
    app.exec()


def is_running_as_admin() -> bool:
    if os.name != "nt":
        return True
    import ctypes

    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def request_admin_restart() -> bool:
    if os.name != "nt":
        return False
    import ctypes

    executable = sys.executable
    parameters = subprocess.list2cmdline(["-m", "apps.server.tool"])
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, parameters, str(Path(__file__).resolve().parents[2]), 1)
    return int(result) > 32


def start_with_admin(run_application=run) -> bool:
    if not is_running_as_admin():
        request_admin_restart()
        return False
    run_application()
    return True


if __name__ == "__main__":
    start_with_admin()
