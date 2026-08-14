from alembic.config import Config
from alembic.script import ScriptDirectory
import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy import create_engine, inspect

STAGE6_TABLES = {"managed_files", "product_file_relations"}


def _config(database) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    return config


def _tables(database) -> set[str]:
    return set(inspect(create_engine(f"sqlite:///{database.as_posix()}")).get_table_names())


def _alembic_subprocess(database, operation: str, revision: str) -> None:
    code = (
        "import sys; "
        "from alembic.config import Config; "
        "from alembic import command; "
        "cfg=Config('alembic.ini'); "
        "cfg.set_main_option('sqlalchemy.url', 'sqlite:///' + sys.argv[1]); "
        f"command.{operation}(cfg, sys.argv[2])"
    )
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [sys.executable, "-B", "-c", code, database.as_posix(), revision],
        cwd=Path.cwd(),
        env=environment,
        check=True,
    )


def _table_contract(inspector, table_name: str) -> dict[str, object]:
    return {
        "columns": tuple(
            (
                column["name"],
                str(column["type"]),
                column["nullable"],
                column["primary_key"],
                str(column["default"]),
            )
            for column in inspector.get_columns(table_name)
        ),
        "foreign_keys": tuple(sorted(
            (
                tuple(foreign_key["constrained_columns"]),
                foreign_key["referred_table"],
                tuple(foreign_key["referred_columns"]),
            )
            for foreign_key in inspector.get_foreign_keys(table_name)
        )),
        "indexes": tuple(sorted(
            (tuple(index["column_names"]), index["unique"])
            for index in inspector.get_indexes(table_name)
        )),
        "unique_constraints": tuple(sorted(
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table_name)
        )),
    }


def test_0004_revision_boundary_roundtrip_and_schema_equivalence(tmp_path):
    migration_database = tmp_path / "migration-boundary.sqlite"
    config = _config(migration_database)
    assert ScriptDirectory.from_config(config).get_heads() == ["0004_managed_files"]

    _alembic_subprocess(migration_database, "upgrade", "0003_qc_packing_delivery")
    previous_revision_tables = _tables(migration_database)
    assert STAGE6_TABLES.isdisjoint(previous_revision_tables)

    _alembic_subprocess(migration_database, "upgrade", "head")
    assert STAGE6_TABLES <= _tables(migration_database)

    from packages.persistence.sqlalchemy_models import Base
    from packages.persistence import storage_models  # noqa: F401

    orm_database = tmp_path / "orm-contract.sqlite"
    orm_engine = create_engine(f"sqlite:///{orm_database.as_posix()}")
    Base.metadata.create_all(orm_engine)
    migration_inspector = inspect(create_engine(f"sqlite:///{migration_database.as_posix()}"))
    orm_inspector = inspect(orm_engine)
    for table_name in sorted(STAGE6_TABLES):
        assert _table_contract(migration_inspector, table_name) == _table_contract(
            orm_inspector, table_name
        )

    _alembic_subprocess(migration_database, "downgrade", "0003_qc_packing_delivery")
    assert _tables(migration_database) == previous_revision_tables

    _alembic_subprocess(migration_database, "upgrade", "head")
    assert STAGE6_TABLES <= _tables(migration_database)
