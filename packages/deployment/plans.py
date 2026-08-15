"""Versioned deployment, service, database, firewall, and TLS plan schemas."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib, json
from typing import Any

PLAN_SCHEMA = "r011.deployment-plan.v1"
LIVE_MACHINE_EXECUTION_MODE = "DISABLED"

def inventory_identity(inventory: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(inventory, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()

@dataclass(frozen=True)
class ServiceRestartPolicy:
    on_crash: bool = True
    rapid_failure_window_seconds: int = 300
    backoff_seconds: tuple[int, ...] = (5, 15, 30, 60)
    max_rapid_failures: int = 5
    operator_failed_state: str = "FAILED_REQUIRES_OPERATOR"
    def __post_init__(self):
        if self.rapid_failure_window_seconds <= 0 or self.max_rapid_failures <= 0 or not self.backoff_seconds: raise ValueError("bounded restart policy required")

@dataclass(frozen=True)
class ServiceConfig:
    service_name: str = "<resolved-service-name>"
    display_name: str = "HMS QR Service"
    release_entrypoint: str = "<resolved-runtime-entrypoint>"
    working_directory: str = "APP_INSTALL_ROOT"
    service_account_ref: str = "ref:service-identity"
    startup_mode: str = "AUTO"
    config_ref: str = "ref:production-config"
    stdout_log_root: str = "APP_LOG_ROOT"
    stop_timeout_seconds: int = 30
    restart_policy: ServiceRestartPolicy = ServiceRestartPolicy()

@dataclass(frozen=True)
class PostgreSQLPlan:
    decision: str
    major: int = 17
    service_identity_ref: str = "ref:postgresql-service"
    data_root: str = "POSTGRESQL_DATA_ROOT"
    bind_policy: str = "LOOPBACK_ONLY"
    port: int = 0
    pg_hba_policy: str = "LOCAL_APPLICATION_ONLY"
    database: str = "<resolved-database>"
    application_role: str = "<resolved-application-role>"
    secret_ref: str = "ref:service/database"
    alembic_head: str = "0005_store_forward"
    backup_required: bool = True
    readiness_commands: tuple[str, ...] = ("database-connectivity-probe", "alembic-current")

@dataclass(frozen=True)
class FirewallPlan:
    pre_state_hash: str
    rule_id: str
    allowed_scope: str
    verification: str = "listener-and-rule-readback"
    rollback: str = "remove-only-planned-rule"

@dataclass(frozen=True)
class TLSPlan:
    termination: str
    certificate_source: str
    certificate_ref: str
    private_key_principal_ref: str
    listener_binding: str
    rotation_policy: str

@dataclass(frozen=True)
class NetworkPlan:
    selected_interface: str
    bind_address: str
    port: int
    allowed_lan_scope: str
    firewall: FirewallPlan
    tls: TLSPlan
    postgresql_local_only: bool = True

@dataclass(frozen=True)
class DeploymentPlan:
    inventory_sha256: str
    release_id: str
    release_git_head: str
    resolved_roots: dict[str, str]
    python_runtime: str
    service_wrapper: str
    service_identity_ref: str
    service_name: str
    postgresql: PostgreSQLPlan
    network: NetworkPlan
    secret_store_ref: str
    backup_prerequisite: bool
    rollback_actions: tuple[str, ...]
    planned_mutations: tuple[dict[str, Any], ...]
    required_uac_class: str
    reboot_expectation: str
    min_free_bytes: int
    schema: str = PLAN_SCHEMA

def validate_plan(plan: DeploymentPlan, inventory: dict[str, Any], manifest: dict[str, Any]) -> None:
    if plan.schema != PLAN_SCHEMA: raise ValueError("unsupported deployment plan schema")
    if plan.inventory_sha256 != inventory_identity(inventory): raise ValueError("deployment plan inventory binding mismatch")
    if plan.release_id != manifest.get("release_id") or plan.release_git_head != manifest.get("git_head"): raise ValueError("deployment plan release binding mismatch")
    if plan.postgresql.major != 17 or not plan.postgresql.bind_policy.startswith("LOOPBACK"): raise ValueError("PostgreSQL production policy mismatch")
    if not plan.network.postgresql_local_only or plan.network.port <= 0: raise ValueError("network decision unresolved")
    if not plan.secret_store_ref.startswith("ref:") or not plan.service_identity_ref.startswith("ref:"): raise ValueError("secret/service reference unresolved")

def postgresql_existing_decision(state: str, *, discovered_major: int | None = None, compatible_major: int = 17, unambiguous: bool = True) -> str:
    if state == "ABSENT": return "INSTALL"
    if state == "COMPATIBLE_CANDIDATE" and discovered_major == compatible_major and unambiguous: return "ADOPT"
    if state == "INCOMPATIBLE" and discovered_major is not None: return "SIDE_BY_SIDE"
    return "BLOCK"

def service_config_template() -> dict[str, Any]:
    cfg = ServiceConfig(); d = asdict(cfg); d["restart_policy"] = asdict(cfg.restart_policy); return d
