"""R011-WP1A-R1A1 inventory source-minimization security tests."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
COLLECTOR = ROOT / "scripts" / "r011_collect_inventory_readonly.ps1"
SAFE_SERVICE_FIELDS = ("Name", "DisplayName", "State", "StartMode", "StartName")
CANARIES = (
    "R011_SECRET_CANARY",
    "R011_PASSWORD_CANARY",
    "R011_TOKEN_CANARY",
    "R011_BEARER_CANARY",
)


def _source() -> str:
    return COLLECTOR.read_text(encoding="utf-8")


def test_service_queries_use_only_the_safe_property_allowlist():
    source = _source()
    query = "SELECT Name, DisplayName, State, StartMode, StartName FROM Win32_Service"
    assert source.count(query) == 3
    assert "PathName" not in source
    assert "ImagePath" not in source
    assert "CommandLine" not in source
    assert "Arguments" not in source
    for projection in (
        "Select-Object Name, DisplayName, State, StartMode, StartName",
        "Name = $_.Name",
        "DisplayName = $_.DisplayName",
        "State = $_.State",
        "StartMode = $_.StartMode",
        "StartName = $_.StartName",
    ):
        assert projection in source


def test_collector_has_no_broader_raw_execution_or_secret_dump_surface():
    source = _source().casefold()
    forbidden = (
        "win32_process", "get-childitem env:", "credential manager", "cmdkey",
        "connectionstring", "database_url", "privatekeybytes", "browser credential",
        "invoke-expression", "start-process", "invoke-command", "new-pssession",
        "enter-pssession", "out-file", "set-content", "add-content", "export-csv",
    )
    assert not any(token in source for token in forbidden)
    assert "convertto-securestring" not in source
    assert "get-credential" not in source


def test_secret_bearing_service_source_is_minimized_before_serialization():
    command = r'''
$raw = @(
  [pscustomobject]@{
    Name='postgresql-safe'; DisplayName='PostgreSQL Safe'; State='Running'; StartMode='Auto'; StartName='svc-pg';
    PathName='postgresql://user:R011_SECRET_CANARY@host/db --password=R011_PASSWORD_CANARY --token=R011_TOKEN_CANARY Authorization:Bearer R011_BEARER_CANARY'
  },
  [pscustomobject]@{
    Name='HMS-QR'; DisplayName='HMS QR'; State='Stopped'; StartMode='Auto'; StartName='svc-hms';
    PathName='--password=R011_PASSWORD_CANARY --token=R011_TOKEN_CANARY'
  }
)
$services = @($raw | Select-Object Name, DisplayName, State, StartMode, StartName)
$postgresql = @($services | Where-Object { $_.Name -like 'postgresql*' -or $_.DisplayName -like 'PostgreSQL*' } | ForEach-Object {
  [pscustomobject]@{ Name=$_.Name; DisplayName=$_.DisplayName; State=$_.State; StartMode=$_.StartMode; StartName=$_.StartName; executable_path=@{state='UNKNOWN';reason='UNSAFE_SOURCE_OMITTED'}; version=@{state='UNKNOWN';reason='SAFE_SOURCE_NOT_AVAILABLE'} }
})
$hms = @($services | Where-Object { $_.Name -like 'HMS*' -or $_.DisplayName -like 'HMS*' })
@{services=$services;postgresql=$postgresql;hms=$hms} | ConvertTo-Json -Depth 8 -Compress
'''
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert all(canary not in result.stdout for canary in CANARIES)
    payload = json.loads(result.stdout)
    serialized = json.dumps(payload, sort_keys=True)
    assert all(field in payload["services"][0] for field in SAFE_SERVICE_FIELDS)
    assert not any(field.casefold() in serialized.casefold() for field in ("PathName", "ImagePath", "CommandLine", "Arguments"))
    assert payload["postgresql"][0]["executable_path"]["state"] == "UNKNOWN"
    assert payload["postgresql"][0]["version"]["state"] == "UNKNOWN"
    assert payload["hms"][0]["Name"] == "HMS-QR"


def test_unknown_semantics_are_explicit_for_security_omissions():
    source = _source()
    assert 'executable_path = @{ state = "UNKNOWN"; reason = "UNSAFE_SOURCE_OMITTED" }' in source
    assert 'version = @{ state = "UNKNOWN"; reason = "SAFE_SOURCE_NOT_AVAILABLE" }' in source
    for state in ("KNOWN", "NOT_PRESENT", "UNKNOWN", "ACCESS_DENIED", "UNSUPPORTED"):
        assert state in source
