"""HMS SQL durable storage.

The database file is a directory holding two artifacts:

- ``snapshot.json`` — the full schema and rows at the last compaction
- ``journal.log`` — one checksummed JSON record per committed transaction

On open the snapshot loads first and the journal replays on top.  A torn final
record (crash mid-append) is detected by its checksum and discarded together
with everything after it, so a committed transaction is either fully present
or fully absent.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import threading

from .errors import StorageError
from .schema import Schema
from .types import deserialize_value, dumps

SNAPSHOT_NAME = "snapshot.json"
JOURNAL_NAME = "journal.log"
COMPACTION_THRESHOLD = 512


def _checksum(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Storage:
    """Owns the on-disk artifacts for one database directory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.snapshot_path = self.root / SNAPSHOT_NAME
        self.journal_path = self.root / JOURNAL_NAME
        self._write_lock = threading.Lock()
        self._journal_handle = None
        self.journal_records = 0

    # -- lifecycle -------------------------------------------------------

    def exists(self) -> bool:
        return self.snapshot_path.is_file() or self.journal_path.is_file()

    def initialize(self, schema: Schema) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._write_snapshot(schema)
        self._open_journal(truncate=True)

    def load(self) -> Schema:
        schema = self._read_snapshot()
        self._open_journal(truncate=False)
        self._replay(schema)
        return schema

    def close(self) -> None:
        with self._write_lock:
            if self._journal_handle is not None:
                try:
                    self._journal_handle.flush()
                    os.fsync(self._journal_handle.fileno())
                except OSError:
                    pass
                self._journal_handle.close()
                self._journal_handle = None

    # -- snapshot --------------------------------------------------------

    def _read_snapshot(self) -> Schema:
        if not self.snapshot_path.is_file():
            return Schema()
        try:
            payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Snapshot is unreadable: {exc}") from None
        return Schema.from_dict(payload)

    def _write_snapshot(self, schema: Schema) -> None:
        temporary = self.snapshot_path.with_suffix(".json.tmp")
        payload = dumps(schema.to_dict())
        try:
            temporary.write_text(payload, encoding="utf-8")
            os.replace(temporary, self.snapshot_path)
            _fsync_directory(self.root)
        except OSError as exc:
            raise StorageError(f"Snapshot could not be written: {exc}") from None

    # -- journal ---------------------------------------------------------

    def _open_journal(self, *, truncate: bool) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            mode = "w" if truncate else "a"
            self._journal_handle = open(self.journal_path, mode, encoding="utf-8")
            if truncate:
                self._journal_handle.flush()
                os.fsync(self._journal_handle.fileno())
        except OSError as exc:
            raise StorageError(f"Journal could not be opened: {exc}") from None

    def _replay(self, schema: Schema) -> None:
        from .executor import Executor

        if not self.journal_path.is_file():
            self.journal_records = 0
            return
        executor = Executor(schema)
        applied = 0
        try:
            lines = self.journal_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise StorageError(f"Journal could not be read: {exc}") from None
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                payload = record["payload"]
                if _checksum(payload) != record.get("checksum"):
                    break
                operations = json.loads(payload)
            except (json.JSONDecodeError, KeyError, TypeError):
                break
            for operation in operations:
                self._apply_journal_operation(schema, executor, operation)
            applied += 1
        self.journal_records = applied

    def _apply_journal_operation(self, schema: Schema, executor, operation: dict) -> None:
        from . import parser as sql_parser

        kind = operation.get("op")
        if kind == "ddl":
            statement = sql_parser.parse(operation["sql"])
            executor.execute(statement)
            return
        table_name = operation["table"]
        if kind == "insert":
            row = {
                key: deserialize_value(value) for key, value in operation["row"].items()
            }
            schema.rows(table_name).append(row)
            return
        if kind == "delete":
            keys = {tuple(deserialize_value(value) for value in item) for item in operation["keys"]}
            table = schema.table(table_name)
            schema.set_rows(
                table_name,
                [row for row in schema.rows(table_name) if table.key_of(row) not in keys],
            )
            return
        if kind == "update":
            table = schema.table(table_name)
            key = tuple(deserialize_value(value) for value in operation["key"])
            row = {
                name: deserialize_value(value) for name, value in operation["row"].items()
            }
            rows = schema.rows(table_name)
            for index, existing in enumerate(rows):
                if table.key_of(existing) == key:
                    rows[index] = row
                    return
            rows.append(row)
            return
        raise StorageError(f"Unknown journal operation '{kind}'")

    def append(self, operations: list[dict]) -> None:
        """Append one committed transaction and flush it to disk."""

        if not operations:
            return
        payload = dumps(operations)
        record = dumps({"payload": payload, "checksum": _checksum(payload)})
        with self._write_lock:
            if self._journal_handle is None:
                raise StorageError("Journal is not open")
            try:
                self._journal_handle.write(record + "\n")
                self._journal_handle.flush()
                os.fsync(self._journal_handle.fileno())
            except OSError as exc:
                raise StorageError(f"Journal append failed: {exc}") from None
            self.journal_records += 1

    def compact(self, schema: Schema) -> None:
        """Write a fresh snapshot and truncate the journal."""

        with self._write_lock:
            self._write_snapshot(schema)
            if self._journal_handle is not None:
                self._journal_handle.close()
            self._open_journal(truncate=True)
            self.journal_records = 0

    def should_compact(self) -> bool:
        return self.journal_records >= COMPACTION_THRESHOLD


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(str(path), os.O_RDONLY)
    except (OSError, AttributeError):
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)
