"""DPAPI-shaped interface only; no machine-bound operation is implemented."""
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class SecretReference:
    name: str
    version: str
    binding: str
    algorithm: str = "DPAPI-SERVICE-PRIVATE-INTERFACE"

class SecretStore(Protocol):
    def get(self, reference: SecretReference) -> bytes: ...
    def put(self, reference: SecretReference, value: bytes) -> None: ...

class InMemorySecretStore:
    def __init__(self): self._values: dict[SecretReference, bytes] = {}
    def get(self, reference): return self._values[reference]
    def put(self, reference, value):
        if not isinstance(value, bytes): raise TypeError("secret values are bytes in fake backend")
        self._values[reference] = value
