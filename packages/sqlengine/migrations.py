"""HMS SQL migration runner.

Migrations are versioned, ordered Python callables that receive a live
:class:`~packages.sqlengine.database.Transaction`.  The runner records each
applied version inside the ``_hms_migrations`` table so a database converges to
the newest version exactly once per step, and a failed step rolls the whole
transaction back.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from .database import Database
from .errors import ExecutionError

Migration = Callable[[object], None]

VERSION_TABLE = "_hms_migrations"


def ensure_version_table(database: Database) -> None:
    if database.schema.has_table(VERSION_TABLE):
        return
    database.execute(
        f"CREATE TABLE {VERSION_TABLE} ("
        "version INTEGER PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "applied_at TEXT NOT NULL)"
    )


def applied_versions(database: Database) -> set[int]:
    if not database.schema.has_table(VERSION_TABLE):
        return set()
    rows = database.query(f"SELECT version FROM {VERSION_TABLE}")
    return {int(row["version"]) for row in rows}


def record_version(database: Database, version: int, name: str, applied_at: str) -> None:
    database.execute(
        f"INSERT INTO {VERSION_TABLE} (version, name, applied_at) VALUES (?, ?, ?)",
        [version, name, applied_at],
    )


def run_migrations(
    database: Database,
    migrations: Iterable[tuple[int, str, Migration]],
    *,
    now: Callable[[], str],
) -> list[int]:
    """Apply every pending migration in order and return the versions applied."""

    ensure_version_table(database)
    done = applied_versions(database)
    applied: list[int] = []
    for version, name, migration in sorted(migrations, key=lambda item: item[0]):
        if version in done:
            continue
        with database.transaction() as transaction:
            migration(transaction)
            transaction.execute(
                f"INSERT INTO {VERSION_TABLE} (version, name, applied_at) "
                "VALUES (?, ?, ?)",
                [version, name, now()],
            )
        applied.append(version)
    return applied


def load_migration_modules(directory: Path) -> list[tuple[int, str, Migration]]:
    """Import ``NNNN_name.py`` files from ``directory`` as migrations."""

    import importlib.util

    migrations: list[tuple[int, str, Migration]] = []
    for path in sorted(Path(directory).glob("[0-9]*.py")):
        prefix = path.stem.split("_", 1)[0]
        if not prefix.isdigit():
            continue
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise ExecutionError(f"Cannot import migration {path.name}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        upgrade = getattr(module, "upgrade", None)
        if upgrade is None:
            raise ExecutionError(f"Migration {path.name} has no upgrade()")
        migrations.append((int(prefix), path.stem, upgrade))
    return migrations
