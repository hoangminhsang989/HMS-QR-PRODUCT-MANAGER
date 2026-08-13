from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class StorageService(ABC):
    @abstractmethod
    def put(self, object_key: str, content: bytes) -> str: ...


class LocalDevStorage(StorageService):
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, object_key: str, content: bytes) -> str:
        target = (self.root / object_key).resolve()
        if self.root not in target.parents:
            raise ValueError("Storage key không hợp lệ.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return object_key
