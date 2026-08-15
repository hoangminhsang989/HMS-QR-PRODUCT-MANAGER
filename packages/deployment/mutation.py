"""Future mutation manifest schema.  This module has no execution interface."""
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Mutation:
    id: str
    category: str
    requires_admin: bool
    precondition: str
    intended_change: str
    verification: str
    rollback: str
    irreversible: bool
    reboot_impact: str
    affected_resource: str
    wp_owner: str

@dataclass(frozen=True)
class MutationManifest:
    schema: str = "r011.mutation-manifest.v1"
    mutations: tuple[Mutation, ...] = ()
    machine_execution_allowed: bool = False
    def __post_init__(self):
        if self.machine_execution_allowed: raise ValueError("WP1A live machine execution is disabled")
        if len({m.id for m in self.mutations}) != len(self.mutations): raise ValueError("mutation ids must be unique")
    def to_dict(self): return {"schema": self.schema, "mutations": [asdict(m) for m in self.mutations], "machine_execution_allowed": False}
