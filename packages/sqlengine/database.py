"""HMS SQL database facade.

One :class:`Database` owns one database directory.  Reads run against the
current in-memory state without locking; writes serialize on a single-writer
lock and use copy-on-write rows so a rolled-back transaction leaves no trace
and a committed transaction swaps its rows in atomically.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import threading
from typing import Any, Iterable, Iterator

from . import parser as sql_parser
from .errors import TransactionError
from .executor import Executor
from .parser import (
    AddColumnStatement,
    AddUniqueConstraintStatement,
    CreateTableStatement,
    DeleteStatement,
    DropTableStatement,
    InsertStatement,
    SelectStatement,
    UpdateStatement,
)
from .schema import Schema
from .storage import Storage
from .types import serialize_value


class Transaction:
    """One all-or-nothing write transaction."""

    def __init__(self, database: "Database") -> None:
        self.database = database
        self.operations: list[dict] = []
        self._executor: Executor | None = None
        self._saved_rows: dict[str, list[dict]] | None = None
        self._saved_tables: dict[str, object] | None = None
        self._closed = False

    def __enter__(self) -> "Transaction":
        self.database._write_lock.acquire()
        self._saved_rows = self.database.schema.clone_rows()
        self._saved_tables = _snapshot_tables(self.database.schema)
        self._executor = Executor(self.database.schema)
        return self

    def execute(self, sql: str, parameters: Iterable | None = None) -> Any:
        if self._executor is None:
            raise TransactionError("Transaction is not active")
        statement = sql_parser.parse(sql)
        parameters = list(parameters or [])
        affected = self._affected_keys(statement, parameters)
        result = self._executor.execute(statement, parameters)
        self._record(statement, sql, result, affected)
        return result

    def _affected_keys(self, statement, parameters: list) -> list[tuple]:
        """Capture the keys an UPDATE will touch before it mutates them."""

        if not isinstance(statement, UpdateStatement):
            return []
        schema = self.database.schema
        table = schema.table(statement.table)
        return [
            table.key_of(row)
            for row in schema.rows(statement.table)
            if self._executor.matches(statement.where, row, parameters)
        ]

    def _record(self, statement, sql: str, result: Any, affected: list[tuple]) -> None:
        schema = self.database.schema
        if isinstance(
            statement,
            (
                CreateTableStatement,
                DropTableStatement,
                AddColumnStatement,
                AddUniqueConstraintStatement,
            ),
        ):
            self.operations.append({"op": "ddl", "sql": sql})
            return
        if isinstance(statement, InsertStatement):
            row = self._find(statement.table, result["inserted"])
            if row is not None:
                self.operations.append(
                    {"op": "insert", "table": statement.table, "row": _plain(row)}
                )
            return
        if isinstance(statement, UpdateStatement):
            for key in affected:
                row = self._find(statement.table, key)
                if row is None:
                    continue
                self.operations.append(
                    {
                        "op": "update",
                        "table": statement.table,
                        "key": _plain_values(key),
                        "row": _plain(row),
                    }
                )
            return
        if isinstance(statement, DeleteStatement):
            keys = [_plain_values(key) for key in result["deleted"]]
            self.operations.append(
                {"op": "delete", "table": statement.table, "keys": keys}
            )
            return

    def _find(self, table_name: str, key: tuple) -> dict | None:
        table = self.database.schema.table(table_name)
        for row in self.database.schema.rows(table_name):
            if table.key_of(row) == key:
                return row
        return None

    def commit(self) -> None:
        if self._closed:
            raise TransactionError("Transaction already finished")
        try:
            if self.operations:
                self.database.storage.append(self.operations)
                if self.database.storage.should_compact():
                    self.database.compact()
        finally:
            self._closed = True
            self.database._write_lock.release()

    def rollback(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._saved_rows is not None:
            self.database.schema.replace_rows(self._saved_rows)
        if self._saved_tables is not None:
            self.database.schema.tables = self._saved_tables
        self.database._write_lock.release()

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


class Database:
    """The engine entry point."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.storage = Storage(self.path)
        self._write_lock = threading.RLock()
        if self.storage.exists():
            self.schema = self.storage.load()
        else:
            self.schema = Schema()
            self.storage.initialize(self.schema)

    # -- statements ------------------------------------------------------

    def execute(self, sql: str, parameters: Iterable | None = None) -> Any:
        """Run one statement; writes auto-commit in their own transaction."""

        statement = sql_parser.parse(sql)
        if isinstance(statement, SelectStatement):
            return Executor(self.schema).execute(statement, list(parameters or []))
        with self.transaction() as transaction:
            return transaction.execute(sql, parameters)

    def query(self, sql: str, parameters: Iterable | None = None) -> list[dict]:
        """Run one SELECT and return its rows."""

        result = self.execute(sql, parameters)
        if isinstance(result, list):
            return result
        raise TransactionError("Statement did not return rows")

    def scalar(self, sql: str, parameters: Iterable | None = None) -> Any:
        rows = self.query(sql, parameters)
        if not rows:
            return None
        return next(iter(rows[0].values()))

    # -- transactions ----------------------------------------------------

    @contextmanager
    def transaction(self) -> Iterator[Transaction]:
        transaction = Transaction(self)
        try:
            with transaction:
                yield transaction
        except Exception:
            if not transaction._closed:
                transaction.rollback()
            raise

    # -- maintenance -----------------------------------------------------

    def compact(self) -> None:
        self.storage.compact(self.schema)

    def close(self) -> None:
        self.storage.close()

    def readiness(self) -> dict[str, object]:
        """One bounded, secret-free probe used by the server health route."""

        return {"state": "READY", "tables": len(self.schema.tables)}

    def table_names(self) -> list[str]:
        return sorted(self.schema.tables)

    def row_count(self, table: str) -> int:
        return len(self.schema.rows(table))


def _plain(row: dict) -> dict:
    return {key: serialize_value(value) for key, value in row.items()}


def _plain_values(values: Iterable) -> list:
    return [serialize_value(value) for value in values]


def _snapshot_tables(schema: Schema) -> dict:
    """Copy the table definitions so a rolled-back DDL leaves no trace."""

    from .schema import Table

    saved = {}
    for name, table in schema.tables.items():
        saved[name] = Table(
            name=table.name,
            columns=list(table.columns),
            primary_key=list(table.primary_key),
            unique_constraints=list(table.unique_constraints),
            foreign_keys=list(table.foreign_keys),
        )
    return saved


def connect(path: Path | str) -> Database:
    """Open (or create) the database stored at ``path``."""

    return Database(path)
