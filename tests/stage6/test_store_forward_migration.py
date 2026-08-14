from alembic.config import Config
from alembic.script import ScriptDirectory
import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy import create_engine, inspect


R009_TABLES = {"storage_configurations", "archive_transfer_jobs"}


def _config(database):
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database.as_posix()}")
    return config


def _tables(database):
    return set(inspect(create_engine(f"sqlite:///{database.as_posix()}")).get_table_names())


def _run(database, operation, revision):
    code = (
        "import sys; from alembic.config import Config; from alembic import command; "
        "cfg=Config('alembic.ini'); cfg.set_main_option('sqlalchemy.url','sqlite:///'+sys.argv[1]); "
        f"command.{operation}(cfg,sys.argv[2])"
    )
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    subprocess.run(
        [sys.executable, "-B", "-c", code, database.as_posix(), revision],
        cwd=Path.cwd(), env=environment, check=True,
    )


def test_0005_revision_boundary_downgrade_and_reupgrade(tmp_path):
    database = tmp_path / "r009-boundary.sqlite"
    config = _config(database)
    assert ScriptDirectory.from_config(config).get_heads() == ["0005_store_forward"]
    _run(database, "upgrade", "0004_managed_files")
    assert R009_TABLES.isdisjoint(_tables(database))
    _run(database, "upgrade", "head")
    assert R009_TABLES <= _tables(database)
    _run(database, "downgrade", "0004_managed_files")
    assert R009_TABLES.isdisjoint(_tables(database))
    _run(database, "upgrade", "head")
    assert R009_TABLES <= _tables(database)


def test_0005_orm_and_migration_schema_contract_match(tmp_path):
    migrated = tmp_path / "migrated.sqlite"
    config = _config(migrated)
    _run(migrated, "upgrade", "head")
    from packages.persistence.sqlalchemy_models import Base
    from packages.persistence import storage_models, store_forward_models  # noqa: F401
    orm = tmp_path / "orm.sqlite"
    orm_engine = create_engine(f"sqlite:///{orm.as_posix()}")
    Base.metadata.create_all(orm_engine)
    migration_inspector = inspect(create_engine(f"sqlite:///{migrated.as_posix()}"))
    orm_inspector = inspect(orm_engine)
    for table in R009_TABLES:
        assert {column["name"] for column in migration_inspector.get_columns(table)} == {
            column["name"] for column in orm_inspector.get_columns(table)
        }
        assert {
            tuple(index["column_names"]) for index in migration_inspector.get_indexes(table)
        } == {
            tuple(index["column_names"]) for index in orm_inspector.get_indexes(table)
        }
