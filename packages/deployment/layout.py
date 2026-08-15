"""Symbolic deployment directory contract; physical roots are resolved later."""
from dataclasses import dataclass
from typing import Final

SYMBOLIC_ROOTS: Final = (
    "APP_INSTALL_ROOT", "APP_DATA_ROOT", "APP_LOG_ROOT", "LOCAL_INGEST_ROOT",
    "SECRET_STORE", "POSTGRESQL_DATA_ROOT", "DEPLOYMENT_STAGING_ROOT", "ROLLBACK_RELEASE_ROOT",
)

@dataclass(frozen=True)
class RootSpec:
    name: str
    purpose: str
    persistent: bool
    owner_role: str
    write_requirement: str
    backup_class: str
    purge_policy: str
    rollback_semantics: str

ROOT_SPECS = {
    "APP_INSTALL_ROOT": RootSpec("APP_INSTALL_ROOT", "immutable versioned releases", False, "service", "read", "release", "retain by policy", "active release selection"),
    "APP_DATA_ROOT": RootSpec("APP_DATA_ROOT", "mutable application state", True, "service", "read/write", "application", "never on release removal", "preserve"),
    "APP_LOG_ROOT": RootSpec("APP_LOG_ROOT", "rotated service logs", True, "service", "read/write", "logs", "bounded retention", "preserve evidence"),
    "LOCAL_INGEST_ROOT": RootSpec("LOCAL_INGEST_ROOT", "durable local-first files", True, "service", "read/write", "ingest", "never on release removal", "preserve"),
    "SECRET_STORE": RootSpec("SECRET_STORE", "service-private secret references", True, "service identity", "read/write by authorized rotation", "secrets", "never automatically", "preserve"),
    "POSTGRESQL_DATA_ROOT": RootSpec("POSTGRESQL_DATA_ROOT", "PostgreSQL persistent data", True, "postgresql", "database-owned", "database", "never by app removal", "operator recovery"),
    "DEPLOYMENT_STAGING_ROOT": RootSpec("DEPLOYMENT_STAGING_ROOT", "hash-verified temporary staging", False, "operator", "read/write", "staging", "purge after acceptance", "discard"),
    "ROLLBACK_RELEASE_ROOT": RootSpec("ROLLBACK_RELEASE_ROOT", "retained known-good release", True, "operator/service", "read", "release", "retain previous", "activate previous"),
}

def validate_layout() -> None:
    if set(ROOT_SPECS) != set(SYMBOLIC_ROOTS):
        raise ValueError("layout root contract is incomplete")
    if any("\\" in s.name or ":" in s.name for s in ROOT_SPECS.values()):
        raise ValueError("physical machine paths are not permitted in symbolic layout")
