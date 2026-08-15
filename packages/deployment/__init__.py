"""Source-side deployment foundation for R011-WP1A.

All operations in this package are model/build/validation operations.  Target
machine mutation is deliberately represented as a plan and is never executed.
"""

from .artifact import ArtifactBuildError, build_release, verify_release
from .configuration import ConfigValidationError, validate_production_config
from .inventory import InventoryValidationError, ReadOnlyInventoryCollector, validate_inventory
from .lifecycle import LocalDeploymentBackend, activate_release, install_release, rollback_release, uninstall, update_release
from .preflight import PreflightResult, run_preflight

__all__ = [
    "ArtifactBuildError", "build_release", "verify_release",
    "ConfigValidationError", "validate_production_config",
    "InventoryValidationError", "ReadOnlyInventoryCollector", "validate_inventory",
    "LocalDeploymentBackend", "activate_release", "install_release", "rollback_release", "uninstall", "update_release",
    "PreflightResult", "run_preflight",
]
