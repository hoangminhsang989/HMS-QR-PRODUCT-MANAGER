"""HMS SQL engine errors.

Every failure the engine raises is secret-free and deterministic so callers can
map them onto stable API error codes.
"""

from __future__ import annotations


class EngineError(RuntimeError):
    """Base class for every engine failure."""


class SyntaxError_(EngineError):
    """The statement could not be tokenized or parsed."""


class ExecutionError(EngineError):
    """The statement parsed but could not be executed."""


class IntegrityError(EngineError):
    """A primary-key, unique, not-null, or foreign-key rule was violated."""

    def __init__(self, message: str, *, constraint: str = "", table: str = "") -> None:
        super().__init__(message)
        self.constraint = constraint
        self.table = table


class TransactionError(EngineError):
    """A transaction was used outside its allowed lifecycle."""


class StorageError(EngineError):
    """The on-disk journal or snapshot could not be read or written."""
