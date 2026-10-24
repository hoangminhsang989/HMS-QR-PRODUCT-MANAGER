"""Machine fingerprint collection and normalization for offline licensing."""

import hashlib
import json
import re
import subprocess
from collections.abc import Callable


class HwidError(Exception):
    """Raised when there is not enough machine identity to form an HWID."""


_min_components = 2
_COMPONENTS = ("cpu", "disk", "mainboard", "mac")
_VIRTUAL_ADAPTER_PATTERN = re.compile(
    r"virtual|vpn|loopback|docker|virtualbox|vmware|hyper-v|bluetooth", re.IGNORECASE
)


def is_virtual_adapter(description: str) -> bool:
    return bool(_VIRTUAL_ADAPTER_PATTERN.search(description or ""))


def _powershell_value(script: str) -> str | None:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        value = result.stdout.strip()
        return value or None
    except (OSError, subprocess.SubprocessError):
        return None


def _wmic_value(alias: str, field: str) -> str | None:
    try:
        result = subprocess.run(
            ["wmic", alias, "get", field, "/value"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        for line in result.stdout.splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip().casefold() == field.casefold() and value.strip():
                return value.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _read_cpu() -> str | None:
    value = _powershell_value(
        "(Get-CimInstance Win32_Processor | Select-Object -First 1 "
        "-ExpandProperty ProcessorId)"
    )
    return value or _wmic_value("cpu", "ProcessorId")


def _read_disk() -> str | None:
    value = _powershell_value(
        "(Get-CimInstance Win32_DiskDrive | Select-Object -First 1 "
        "-ExpandProperty SerialNumber)"
    )
    return value or _wmic_value("diskdrive", "SerialNumber")


def _read_mainboard() -> str | None:
    value = _powershell_value(
        "(Get-CimInstance Win32_BaseBoard | Select-Object -First 1 "
        "-ExpandProperty SerialNumber)"
    )
    return value or _wmic_value("baseboard", "SerialNumber")


def _read_mac() -> str | None:
    script = (
        "Get-NetAdapter -Physical | Where-Object { $_.HardwareInterface -and "
        "$_.MacAddress -and $_.Status -ne 'Not Present' } | "
        "Select-Object Name, InterfaceDescription, MacAddress | ConvertTo-Json -Compress"
    )
    output = _powershell_value(script)
    if not output:
        return None
    try:
        adapters = json.loads(output)
        if isinstance(adapters, dict):
            adapters = [adapters]
        for adapter in adapters:
            if not is_virtual_adapter(adapter.get("InterfaceDescription", "")):
                mac = adapter.get("MacAddress")
                if mac:
                    return mac.strip()
    except (json.JSONDecodeError, AttributeError, TypeError):
        return None
    return None


def collect_components(
    readers: dict[str, Callable[[], str | None]] | None = None,
) -> dict[str, str | None]:
    if readers is None:
        readers = {
            "cpu": _read_cpu,
            "disk": _read_disk,
            "mainboard": _read_mainboard,
            "mac": _read_mac,
        }
    components: dict[str, str | None] = {}
    for name in _COMPONENTS:
        reader = readers.get(name)
        try:
            components[name] = reader() if reader is not None else None
        except Exception:
            components[name] = None
    return components


def compute_hwid(components: dict) -> str:
    parts = [
        value
        for key in _COMPONENTS
        if isinstance((value := components.get(key)), str) and value.strip()
    ]
    parts = [part.strip() for part in parts]
    if len(parts) < _min_components:
        raise HwidError(f"at least {_min_components} usable components are required")
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32].upper()
    return "-".join(digest[index : index + 8] for index in range(0, 32, 8))


def get_hwid() -> str:
    return compute_hwid(collect_components())
