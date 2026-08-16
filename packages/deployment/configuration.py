"""Production configuration contract with secret-reference-only values."""
from __future__ import annotations
from typing import Any
from config.paths import PathConfigurationError, validate_external_runtime_path

CONFIG_SCHEMA = "r011.production-config.v1"
REQUIRED = {"environment", "bind_address", "port", "database_secret_ref", "app_data_root", "app_log_root", "local_ingest_root", "archive", "secret_store_ref", "tls", "service_identity_ref", "release_id", "logging", "health"}
class ConfigValidationError(ValueError): pass

def validate_production_config(config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict) or config.get("schema_version") != CONFIG_SCHEMA: raise ConfigValidationError("unsupported config schema")
    missing = REQUIRED - set(config)
    if missing: raise ConfigValidationError("missing required config fields")
    if config.get("environment") not in {"STAGING", "PRODUCTION"}: raise ConfigValidationError("environment must be explicit")
    if not isinstance(config.get("port"), int) or not 1 <= config["port"] <= 65535: raise ConfigValidationError("invalid port")
    for k in ("database_secret_ref", "secret_store_ref", "service_identity_ref"):
        v = config.get(k)
        if not isinstance(v, str) or not v.startswith("ref:") or len(v) <= 4: raise ConfigValidationError(f"invalid secret/identity reference: {k}")
    unsafe = {"changeme", "replace-me", "todo", "placeholder", "localhost", "0.0.0.0", "<resolved-after-inventory>", "<resolved-later>", "<certified-release>"}
    def values(v):
        if isinstance(v, dict):
            for child in v.values(): yield from values(child)
        elif isinstance(v, list):
            for child in v: yield from values(child)
        elif isinstance(v, str): yield v.lower()
    if any(x in unsafe or any(token in x for token in ("changeme", "replace-me", "<resolved", "<certified")) for x in values(config)):
        raise ConfigValidationError("unsafe placeholder or broad bind value")
    for key in ("app_data_root", "app_log_root", "local_ingest_root"):
        try:
            validate_external_runtime_path(config.get(key, ""), authority=key)
        except PathConfigurationError as exc:
            raise ConfigValidationError(str(exc)) from None
    if config.get("tls", {}).get("mode") == "PLAINTEXT": raise ConfigValidationError("plaintext production traffic is forbidden")
    return config

def production_config_template() -> dict[str, Any]:
    return {"schema_version": CONFIG_SCHEMA, "environment": "PRODUCTION", "bind_address": "<resolved-after-inventory>", "port": 0,
            "database_secret_ref": "ref:service/database", "app_data_root": "APP_DATA_ROOT", "app_log_root": "APP_LOG_ROOT", "local_ingest_root": "LOCAL_INGEST_ROOT",
            "archive": {"mode": "OPTIONAL_LOCAL_FIRST", "identity": "<resolved-later>"}, "secret_store_ref": "ref:service-private", "tls": {"mode": "REVERSE_PROXY_TERMINATED", "certificate_ref": "ref:tls/certificate"},
            "service_identity_ref": "ref:service-identity", "release_id": "<certified-release>", "logging": {"retention": "policy"}, "health": {"readiness": "process-database-local-storage"}}
