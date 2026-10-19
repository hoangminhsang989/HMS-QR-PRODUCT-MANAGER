"""HMS SQL — a small, dependency-free SQL engine for the QR product.

Public surface::

    from packages.sqlengine import connect

    database = connect(path)
    database.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    with database.transaction() as transaction:
        transaction.execute("INSERT INTO t (id, name) VALUES (?, ?)", [1, "a"])
    rows = database.query("SELECT * FROM t WHERE name = ?", ["a"])
"""

from .database import Database, Transaction, connect
from .errors import (
    EngineError,
    ExecutionError,
    IntegrityError,
    StorageError,
    SyntaxError_,
    TransactionError,
)
from .executor import Executor, execute
from .parser import parse
from .schema import Column, ForeignKey, Schema, Table
from .storage import Storage
from .types import (
    BOOLEAN,
    DATE,
    DATETIME,
    INTEGER,
    NUMERIC,
    TEXT,
    ColumnType,
    type_from_name,
)

__all__ = [
    "BOOLEAN",
    "Column",
    "ColumnType",
    "DATE",
    "DATETIME",
    "Database",
    "EngineError",
    "ExecutionError",
    "Executor",
    "ForeignKey",
    "INTEGER",
    "IntegrityError",
    "NUMERIC",
    "Schema",
    "Storage",
    "StorageError",
    "SyntaxError_",
    "TEXT",
    "Table",
    "Transaction",
    "TransactionError",
    "connect",
    "execute",
    "parse",
    "type_from_name",
]
