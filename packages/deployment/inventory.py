"""Strictly read-only future host inventory collector and schema validator."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

INVENTORY_SCHEMA = "r011.machine-inventory.v1"
STATES = {"KNOWN", "NOT_PRESENT", "UNKNOWN", "ACCESS_DENIED", "NOT_APPLICABLE", "UNSUPPORTED"}
REQUIRED = {"inventory_schema_version", "captured_at", "machine_identity", "os", "hardware", "volumes", "network", "listeners", "firewall", "services", "postgresql", "python", "hms_qr", "tls", "time", "security", "pending_reboot", "unknowns", "collector_version"}
FORBIDDEN_ACTIONS = frozenset({"New-Item", "Remove-Item", "Set-Item", "Set-ItemProperty", "New-NetFirewallRule", "Set-NetFirewallRule", "Remove-NetFirewallRule", "sc create", "sc config", "sc delete", "net user", "ACL write", "service start", "service stop", "package install", "package uninstall", "database mutation", "reboot"})
READ_ONLY_COMMANDS = frozenset({"os_info", "hostname", "domain", "execution_context", "hardware", "volumes", "network", "listeners", "firewall_profiles", "firewall_rules", "services", "postgresql", "python", "hms_services", "time", "certificates_metadata", "pending_reboot", "security"})
class InventoryValidationError(ValueError): pass

def validate_inventory(doc: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(doc, dict) or doc.get("inventory_schema_version") != INVENTORY_SCHEMA: raise InventoryValidationError("unsupported inventory schema")
    missing = REQUIRED - set(doc)
    if missing: raise InventoryValidationError("missing inventory fields")
    if not isinstance(doc["unknowns"], list): raise InventoryValidationError("unknowns must be a list")
    for item in doc["unknowns"]:
        if not isinstance(item, dict) or item.get("state") not in STATES: raise InventoryValidationError("unknown state must be explicit")
    for section in ("listeners", "services", "postgresql"):
        value = doc.get(section)
        if isinstance(value, dict) and value.get("state") == "NOT_PRESENT" and value.get("items"):
            raise InventoryValidationError(f"contradictory {section} state")
    import json
    forbidden = ("password", "private_key", "private key", "credential_value", "connection_string")
    if any(x in json.dumps(doc, sort_keys=True).lower() for x in forbidden): raise InventoryValidationError("secret material in inventory")
    return doc

@dataclass
class ReadOnlyInventoryCollector:
    runner: Callable[[str], Any] | None = None
    collector_version: str = "r011-wp1a-1"
    def collect(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for command in sorted(READ_ONLY_COMMANDS):
            if command not in READ_ONLY_COMMANDS or command in FORBIDDEN_ACTIONS: raise RuntimeError("collector command is not read-only")
            try: data[command] = self.runner(command) if self.runner else {"state": "UNKNOWN"}
            except PermissionError: data[command] = {"state": "ACCESS_DENIED"}
            except NotImplementedError: data[command] = {"state": "UNSUPPORTED"}
        doc = {"inventory_schema_version": INVENTORY_SCHEMA, "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "machine_identity": data.get("hostname", {"state": "UNKNOWN"}),
               "os": data.get("os_info", {"state": "UNKNOWN"}), "hardware": data.get("hardware", {"state": "UNKNOWN"}), "volumes": data.get("volumes", {"state": "UNKNOWN"}), "network": data.get("network", {"state": "UNKNOWN"}), "listeners": data.get("listeners", {"state": "UNKNOWN"}), "firewall": {"profiles": data.get("firewall_profiles", {"state": "UNKNOWN"}), "rules": data.get("firewall_rules", {"state": "UNKNOWN"})}, "services": data.get("services", {"state": "UNKNOWN"}), "postgresql": data.get("postgresql", {"state": "UNKNOWN"}), "python": data.get("python", {"state": "UNKNOWN"}), "hms_qr": data.get("hms_services", {"state": "UNKNOWN"}), "tls": data.get("certificates_metadata", {"state": "UNKNOWN"}), "time": data.get("time", {"state": "UNKNOWN"}), "security": data.get("security", {"state": "UNKNOWN"}), "pending_reboot": data.get("pending_reboot", {"state": "UNKNOWN"}), "unknowns": [], "collector_version": self.collector_version}
        return validate_inventory(doc)
