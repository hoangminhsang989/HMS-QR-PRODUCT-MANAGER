from __future__ import annotations
import os
from alembic import context
from sqlalchemy import engine_from_config, pool
from packages.persistence.sqlalchemy_models import Base
from packages.persistence import tracking_models as _tracking_models  # noqa: F401

config=context.config
# Server deployment keeps the connection string outside source and alembic.ini.
database_url = os.environ.get("HMS_QR_DATABASE_URL", "").strip()
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)
target_metadata=Base.metadata

def run_migrations_offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle":"named"})
    with context.begin_transaction(): context.run_migrations()

def run_migrations_online():
    connectable=engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction(): context.run_migrations()

if context.is_offline_mode(): run_migrations_offline()
else: run_migrations_online()
