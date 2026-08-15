"""Secret-free deployment evidence schema and redaction."""
from __future__ import annotations
import re
from typing import Any

EVIDENCE_SCHEMA = "r011.deployment-evidence.v1"
_SECRET_KEY = re.compile(r"(password|secret|token|private.?key|credential)", re.I)
_SECRET_VALUE = re.compile(r"(?i)(postgres(?:ql)?://[^\s]+|bearer\s+[^\s]+|-----begin [^-]+ private key-----)")

def redact(value: Any) -> Any:
    if isinstance(value, dict): return {k: "[REDACTED]" if _SECRET_KEY.search(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, list): return [redact(v) for v in value]
    if isinstance(value, str): return _SECRET_VALUE.sub("[REDACTED]", value)
    return value

def make_evidence(**fields: Any) -> dict[str, Any]:
    required = {"authority", "wp", "timestamp", "baseline", "target_machine_inventory_hash", "release_identity", "pre_state", "planned_mutations", "executed_mutations", "post_state", "verification", "rollback_events", "service_state", "database_state", "network_state", "secret_scan_result", "verdict"}
    doc = {"evidence_schema": EVIDENCE_SCHEMA, **fields}
    missing = required - set(doc)
    if missing: raise ValueError("evidence missing required fields")
    return redact(doc)
