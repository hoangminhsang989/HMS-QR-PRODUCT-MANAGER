"""Standalone SQLite LAN concurrency: WAL, busy timeout, and parallel writers."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import threading

from sqlalchemy import text

from config.environments import AppConfig, Environment
from packages.persistence.database import (
    SQLITE_BUSY_TIMEOUT_SECONDS,
    create_database_runtime,
)


def _runtime(tmp_path: Path, name: str):
    database = tmp_path / name
    return create_database_runtime(
        AppConfig(Environment.DEV, f"sqlite:///{database.as_posix()}", "local")
    )


def test_sqlite_engine_enables_wal_and_busy_timeout(tmp_path):
    runtime = _runtime(tmp_path, "wal.sqlite")
    try:
        with runtime.engine.connect() as connection:
            journal = connection.execute(text("PRAGMA journal_mode")).scalar_one()
            busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar_one()
            synchronous = connection.execute(text("PRAGMA synchronous")).scalar_one()
        assert journal.lower() == "wal"
        assert busy_timeout == int(SQLITE_BUSY_TIMEOUT_SECONDS * 1000)
        assert synchronous == 1
    finally:
        runtime.dispose()


def test_reader_is_not_blocked_while_writer_holds_transaction(tmp_path):
    runtime = _runtime(tmp_path, "concurrent.sqlite")
    try:
        with runtime.engine.begin() as connection:
            connection.execute(text("CREATE TABLE sample (value TEXT)"))
        writer = sqlite3.connect(tmp_path / "concurrent.sqlite", timeout=30)
        reader = sqlite3.connect(tmp_path / "concurrent.sqlite", timeout=30)
        try:
            writer.execute("BEGIN IMMEDIATE")
            writer.execute("INSERT INTO sample (value) VALUES ('held')")
            assert reader.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 0
            writer.commit()
            assert reader.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 1
        finally:
            writer.close()
            reader.close()
    finally:
        runtime.dispose()


def test_parallel_writers_commit_without_locked_errors(tmp_path):
    runtime = _runtime(tmp_path, "writers.sqlite")
    try:
        with runtime.engine.begin() as connection:
            connection.execute(text("CREATE TABLE writes (worker TEXT, seq INTEGER)"))
        failures: list[Exception] = []

        def write_rows(worker: str, count: int) -> None:
            try:
                connection = sqlite3.connect(tmp_path / "writers.sqlite", timeout=30)
                try:
                    for seq in range(count):
                        connection.execute(
                            "INSERT INTO writes (worker, seq) VALUES (?, ?)", (worker, seq)
                        )
                        connection.commit()
                finally:
                    connection.close()
            except Exception as exc:  # noqa: BLE001 - surfaced through failures
                failures.append(exc)

        threads = [
            threading.Thread(target=write_rows, args=(f"worker-{index}", 25))
            for index in range(4)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        assert not failures
        with runtime.engine.connect() as connection:
            total = connection.execute(text("SELECT COUNT(*) FROM writes")).scalar_one()
        assert total == 100
    finally:
        runtime.dispose()
