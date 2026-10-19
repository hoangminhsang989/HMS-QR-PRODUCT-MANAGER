"""Engine unit tests: parser, executor, constraints, transactions, recovery."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from packages.sqlengine import connect
from packages.sqlengine.errors import IntegrityError, SyntaxError_
from packages.sqlengine.migrations import applied_versions, run_migrations

DDL = """
CREATE TABLE items (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    price NUMERIC(18,4),
    active BOOLEAN,
    created DATE
)
"""


@pytest.fixture()
def database(tmp_path: Path):
    db = connect(tmp_path / "db")
    db.execute(DDL)
    return db


def insert(db, identifier, name, price=None, active=None, created=None):
    db.execute(
        "INSERT INTO items (id, name, price, active, created) VALUES (?, ?, ?, ?, ?)",
        [identifier, name, price, active, created],
    )


class TestParser:
    def test_insert_and_select_roundtrip(self, database):
        insert(database, 1, "widget", "12.5000", True, "2026-01-02")
        rows = database.query("SELECT * FROM items WHERE id = ?", [1])
        assert rows == [
            {
                "id": 1,
                "name": "widget",
                "price": Decimal("12.5000"),
                "active": True,
                "created": date(2026, 1, 2),
            }
        ]

    def test_select_literal_probe(self, database):
        assert database.query("SELECT 1") == [{"1": 1}]

    def test_star_column_selection(self, database):
        insert(database, 1, "a")
        assert database.query("SELECT * FROM items")[0]["name"] == "a"

    def test_explicit_columns(self, database):
        insert(database, 1, "a")
        assert database.query("SELECT name FROM items") == [{"name": "a"}]

    def test_syntax_error_names_position(self, database):
        with pytest.raises(SyntaxError_) as excinfo:
            database.query("SELECT FROM")
        assert "Expected" in str(excinfo.value)

    def test_unterminated_string(self, database):
        with pytest.raises(SyntaxError_):
            database.query("SELECT * FROM items WHERE name = 'abc")


class TestPredicates:
    def test_comparison_operators(self, database):
        for identifier in range(1, 6):
            insert(database, identifier, f"n{identifier}")
        assert len(database.query("SELECT * FROM items WHERE id >= 3")) == 3
        assert len(database.query("SELECT * FROM items WHERE id != 3")) == 4
        assert len(database.query("SELECT * FROM items WHERE id < 2")) == 1
        assert len(database.query("SELECT * FROM items WHERE id <= 2")) == 2
        assert len(database.query("SELECT * FROM items WHERE id > 4")) == 1

    def test_like(self, database):
        insert(database, 1, "alpha")
        insert(database, 2, "beta")
        insert(database, 3, "alphabet")
        rows = database.query("SELECT name FROM items WHERE name LIKE ?", ["alph%"])
        assert sorted(row["name"] for row in rows) == ["alpha", "alphabet"]
        assert database.query("SELECT * FROM items WHERE name LIKE ?", ["a%a"]) == [
            {"id": 1, "name": "alpha", "price": None, "active": None, "created": None},
        ]

    def test_not_like(self, database):
        insert(database, 1, "alpha")
        insert(database, 2, "beta")
        rows = database.query("SELECT name FROM items WHERE name NOT LIKE ?", ["a%"])
        assert rows == [{"name": "beta"}]

    def test_in_list(self, database):
        for identifier in range(1, 5):
            insert(database, identifier, f"n{identifier}")
        rows = database.query("SELECT id FROM items WHERE id IN (?, ?)", [2, 4])
        assert sorted(row["id"] for row in rows) == [2, 4]

    def test_not_in_list(self, database):
        for identifier in range(1, 4):
            insert(database, identifier, f"n{identifier}")
        rows = database.query("SELECT id FROM items WHERE id NOT IN (?, ?)", [1, 2])
        assert rows == [{"id": 3}]

    def test_is_null(self, database):
        insert(database, 1, "a", None)
        insert(database, 2, "b", "5.0000")
        assert database.query("SELECT id FROM items WHERE price IS NULL") == [{"id": 1}]
        assert database.query("SELECT id FROM items WHERE price IS NOT NULL") == [{"id": 2}]

    def test_and_or_precedence(self, database):
        insert(database, 1, "a", "1.0000")
        insert(database, 2, "b", "2.0000")
        insert(database, 3, "c", "3.0000")
        rows = database.query(
            "SELECT id FROM items WHERE (id = ? OR id = ?) AND price > ?",
            [1, 3, "2.0000"],
        )
        assert rows == [{"id": 3}]

    def test_order_by_limit_offset(self, database):
        for identifier in (3, 1, 4, 7, 5, 9, 2, 6):
            insert(database, identifier, f"n{identifier}")
        rows = database.query("SELECT id FROM items ORDER BY id DESC LIMIT ? OFFSET ?", [3, 2])
        assert [row["id"] for row in rows] == [6, 5, 4]

    def test_count_star(self, database):
        insert(database, 1, "a")
        insert(database, 2, "b")
        assert database.query("SELECT COUNT(*) FROM items") == [{"count": 2}]
        assert database.query("SELECT COUNT(*) FROM items WHERE id = ?", [1]) == [
            {"count": 1}
        ]

    def test_distinct(self, database):
        db = database
        db.execute("CREATE TABLE tags (id INTEGER PRIMARY KEY, label TEXT)")
        db.execute("INSERT INTO tags (id, label) VALUES (?, ?)", [1, "x"])
        db.execute("INSERT INTO tags (id, label) VALUES (?, ?)", [2, "x"])
        db.execute("INSERT INTO tags (id, label) VALUES (?, ?)", [3, "y"])
        rows = db.query("SELECT DISTINCT label FROM tags")
        assert sorted(row["label"] for row in rows) == ["x", "y"]

    def test_null_comparison_semantics(self, database):
        insert(database, 1, "a", None)
        assert database.query("SELECT * FROM items WHERE price = NULL") == []
        assert database.query("SELECT * FROM items WHERE price != 1") == []


class TestConstraints:
    def test_primary_key_violation(self, database):
        insert(database, 1, "a")
        with pytest.raises(IntegrityError) as excinfo:
            insert(database, 1, "b")
        assert excinfo.value.constraint == "primary_key"

    def test_not_null_violation(self, database):
        with pytest.raises(IntegrityError) as excinfo:
            database.execute("INSERT INTO items (id, name) VALUES (?, ?)", [1, None])
        assert excinfo.value.constraint == "not_null"

    def test_unique_violation(self, database):
        db = database
        db.execute("CREATE TABLE codes (id INTEGER PRIMARY KEY, code TEXT UNIQUE)")
        db.execute("INSERT INTO codes (id, code) VALUES (?, ?)", [1, "A"])
        with pytest.raises(IntegrityError) as excinfo:
            db.execute("INSERT INTO codes (id, code) VALUES (?, ?)", [2, "A"])
        assert excinfo.value.constraint == "unique"

    def test_composite_unique(self, database):
        db = database
        db.execute(
            "CREATE TABLE pairs (id INTEGER PRIMARY KEY, a TEXT, b TEXT, UNIQUE (a, b))"
        )
        db.execute("INSERT INTO pairs (id, a, b) VALUES (?, ?, ?)", [1, "x", "y"])
        db.execute("INSERT INTO pairs (id, a, b) VALUES (?, ?, ?)", [2, "x", "z"])
        with pytest.raises(IntegrityError):
            db.execute("INSERT INTO pairs (id, a, b) VALUES (?, ?, ?)", [3, "x", "y"])

    def test_composite_primary_key(self, database):
        db = database
        db.execute(
            "CREATE TABLE pairs (a TEXT, b TEXT, note TEXT, PRIMARY KEY (a, b))"
        )
        db.execute("INSERT INTO pairs (a, b, note) VALUES (?, ?, ?)", ["x", "y", "first"])
        db.execute("INSERT INTO pairs (a, b, note) VALUES (?, ?, ?)", ["x", "z", "second"])
        with pytest.raises(IntegrityError) as excinfo:
            db.execute("INSERT INTO pairs (a, b, note) VALUES (?, ?, ?)", ["x", "y", "dup"])
        assert excinfo.value.constraint == "primary_key"
        assert db.row_count("pairs") == 2

    def test_composite_primary_key_update_same_key_is_allowed(self, database):
        db = database
        db.execute("CREATE TABLE pairs (a TEXT, b TEXT, note TEXT, PRIMARY KEY (a, b))")
        db.execute("INSERT INTO pairs (a, b, note) VALUES (?, ?, ?)", ["x", "y", "first"])
        db.execute("UPDATE pairs SET note = ? WHERE a = ? AND b = ?", ["changed", "x", "y"])
        assert db.query("SELECT note FROM pairs") == [{"note": "changed"}]

    def test_primary_key_columns_are_not_null(self, database):
        db = database
        db.execute("CREATE TABLE pairs (a TEXT, b TEXT, PRIMARY KEY (a, b))")
        with pytest.raises(IntegrityError) as excinfo:
            db.execute("INSERT INTO pairs (a, b) VALUES (?, ?)", [None, "y"])
        assert excinfo.value.constraint == "not_null"

    def test_foreign_key_insert_blocked(self, database):
        db = database
        db.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        db.execute(
            "CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER, "
            "FOREIGN KEY (parent_id) REFERENCES parent(id))"
        )
        with pytest.raises(IntegrityError) as excinfo:
            db.execute("INSERT INTO child (id, parent_id) VALUES (?, ?)", [1, 99])
        assert excinfo.value.constraint == "foreign_key"

    def test_foreign_key_delete_blocked(self, database):
        db = database
        db.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        db.execute(
            "CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER, "
            "FOREIGN KEY (parent_id) REFERENCES parent(id))"
        )
        db.execute("INSERT INTO parent (id) VALUES (?)", [1])
        db.execute("INSERT INTO child (id, parent_id) VALUES (?, ?)", [1, 1])
        with pytest.raises(IntegrityError) as excinfo:
            db.execute("DELETE FROM parent WHERE id = ?", [1])
        assert excinfo.value.constraint == "foreign_key"

    def test_foreign_key_delete_allowed_when_unreferenced(self, database):
        db = database
        db.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        db.execute(
            "CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER, "
            "FOREIGN KEY (parent_id) REFERENCES parent(id))"
        )
        db.execute("INSERT INTO parent (id) VALUES (?)", [1])
        db.execute("INSERT INTO parent (id) VALUES (?)", [2])
        db.execute("INSERT INTO child (id, parent_id) VALUES (?, ?)", [1, 1])
        db.execute("DELETE FROM parent WHERE id = ?", [2])
        assert db.query("SELECT id FROM parent") == [{"id": 1}]

    def test_unknown_column_rejected(self, database):
        with pytest.raises(IntegrityError):
            database.execute("INSERT INTO items (id, nope) VALUES (?, ?)", [1, "x"])

    def test_unknown_table_rejected(self, database):
        with pytest.raises(IntegrityError):
            database.query("SELECT * FROM ghost")


class TestUpdateDelete:
    def test_update_where(self, database):
        insert(database, 1, "a")
        insert(database, 2, "b")
        result = database.execute("UPDATE items SET name = ? WHERE id = ?", ["z", 1])
        assert result == {"updated": 1}
        assert database.query("SELECT name FROM items WHERE id = ?", [1]) == [{"name": "z"}]

    def test_update_can_invalidate_its_own_filter(self, database):
        insert(database, 1, "a")
        insert(database, 2, "b")
        database.execute("UPDATE items SET name = ? WHERE name = ?", ["done", "a"])
        assert database.query("SELECT name FROM items ORDER BY id") == [
            {"name": "done"},
            {"name": "b"},
        ]

    def test_update_unique_conflict(self, database):
        db = database
        db.execute("CREATE TABLE codes (id INTEGER PRIMARY KEY, code TEXT UNIQUE)")
        db.execute("INSERT INTO codes (id, code) VALUES (?, ?)", [1, "A"])
        db.execute("INSERT INTO codes (id, code) VALUES (?, ?)", [2, "B"])
        with pytest.raises(IntegrityError):
            db.execute("UPDATE codes SET code = ? WHERE id = ?", ["A", 2])

    def test_update_same_value_is_not_a_conflict(self, database):
        db = database
        db.execute("CREATE TABLE codes (id INTEGER PRIMARY KEY, code TEXT UNIQUE)")
        db.execute("INSERT INTO codes (id, code) VALUES (?, ?)", [1, "A"])
        db.execute("UPDATE codes SET code = ? WHERE id = ?", ["A", 1])
        assert db.query("SELECT code FROM codes") == [{"code": "A"}]

    def test_delete_where(self, database):
        insert(database, 1, "a")
        insert(database, 2, "b")
        result = database.execute("DELETE FROM items WHERE id = ?", [1])
        assert result == {"deleted": [(1,)]}
        assert database.query("SELECT id FROM items") == [{"id": 2}]

    def test_delete_all(self, database):
        insert(database, 1, "a")
        insert(database, 2, "b")
        database.execute("DELETE FROM items")
        assert database.query("SELECT * FROM items") == []


class TestTypes:
    def test_numeric_quantized(self, database):
        insert(database, 1, "a", "1.23456")
        assert database.query("SELECT price FROM items")[0]["price"] == Decimal("1.2346")

    def test_integer_coercion_from_string(self, database):
        insert(database, "7", "a")
        assert database.query("SELECT id FROM items")[0]["id"] == 7

    def test_boolean_coercion(self, database):
        insert(database, 1, "a", None, "true")
        insert(database, 2, "b", None, "0")
        rows = database.query("SELECT active FROM items ORDER BY id")
        assert [row["active"] for row in rows] == [True, False]

    def test_datetime_roundtrip(self, tmp_path: Path):
        db = connect(tmp_path / "db")
        db.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, at DATETIME)")
        moment = datetime(2026, 10, 18, 12, 30, tzinfo=timezone.utc)
        db.execute("INSERT INTO events (id, at) VALUES (?, ?)", [1, moment])
        assert db.query("SELECT at FROM events")[0]["at"] == moment

    def test_bad_type_rejected(self, database):
        with pytest.raises(IntegrityError) as excinfo:
            insert(database, "not-a-number", "a")
        assert excinfo.value.constraint == "type"


class TestTransactions:
    def test_commit_persists(self, tmp_path: Path):
        path = tmp_path / "db"
        db = connect(path)
        db.execute(DDL)
        with db.transaction() as transaction:
            transaction.execute("INSERT INTO items (id, name) VALUES (?, ?)", [1, "a"])
            transaction.execute("INSERT INTO items (id, name) VALUES (?, ?)", [2, "b"])
        db.close()

        reopened = connect(path)
        assert reopened.query("SELECT COUNT(*) FROM items") == [{"count": 2}]

    def test_rollback_leaves_no_trace(self, database):
        insert(database, 1, "a")
        with pytest.raises(RuntimeError):
            with database.transaction() as transaction:
                transaction.execute(
                    "INSERT INTO items (id, name) VALUES (?, ?)", [2, "b"]
                )
                raise RuntimeError("boom")
        assert database.query("SELECT id FROM items") == [{"id": 1}]

    def test_rollback_after_constraint_failure(self, database):
        insert(database, 1, "a")
        with pytest.raises(IntegrityError):
            with database.transaction() as transaction:
                transaction.execute(
                    "INSERT INTO items (id, name) VALUES (?, ?)", [2, "b"]
                )
                transaction.execute(
                    "INSERT INTO items (id, name) VALUES (?, ?)", [1, "dup"]
                )
        assert database.query("SELECT id FROM items") == [{"id": 1}]

    def test_update_rollback(self, database):
        insert(database, 1, "a")
        with pytest.raises(RuntimeError):
            with database.transaction() as transaction:
                transaction.execute(
                    "UPDATE items SET name = ? WHERE id = ?", ["changed", 1]
                )
                raise RuntimeError("boom")
        assert database.query("SELECT name FROM items") == [{"name": "a"}]

    def test_delete_rollback(self, database):
        insert(database, 1, "a")
        with pytest.raises(RuntimeError):
            with database.transaction() as transaction:
                transaction.execute("DELETE FROM items WHERE id = ?", [1])
                raise RuntimeError("boom")
        assert database.query("SELECT id FROM items") == [{"id": 1}]

    def test_ddl_rollback(self, database):
        with pytest.raises(RuntimeError):
            with database.transaction() as transaction:
                transaction.execute("CREATE TABLE scratch (id INTEGER PRIMARY KEY)")
                raise RuntimeError("boom")
        assert not database.schema.has_table("scratch")


class TestDurability:
    def test_journal_replay_after_reopen(self, tmp_path: Path):
        path = tmp_path / "db"
        db = connect(path)
        db.execute(DDL)
        insert(db, 1, "a", "1.0000", True, "2026-02-03")
        insert(db, 2, "b")
        db.execute("UPDATE items SET name = ? WHERE id = ?", ["z", 2])
        db.execute("DELETE FROM items WHERE id = ?", [1])
        db.close()

        reopened = connect(path)
        assert reopened.query("SELECT id, name FROM items ORDER BY id") == [
            {"id": 2, "name": "z"}
        ]

    def test_torn_final_record_discarded(self, tmp_path: Path):
        path = tmp_path / "db"
        db = connect(path)
        db.execute(DDL)
        insert(db, 1, "a")
        db.close()

        journal = path / "journal.log"
        with journal.open("a", encoding="utf-8") as handle:
            handle.write('{"payload":"[{\\"op\\":\\"insert\\"')

        reopened = connect(path)
        assert reopened.query("SELECT id FROM items") == [{"id": 1}]

    def test_compaction_then_reopen(self, tmp_path: Path):
        path = tmp_path / "db"
        db = connect(path)
        db.execute(DDL)
        for identifier in range(1, 6):
            insert(db, identifier, f"n{identifier}")
        db.execute("DELETE FROM items WHERE id = ?", [3])
        db.compact()
        db.close()

        reopened = connect(path)
        assert reopened.query("SELECT COUNT(*) FROM items") == [{"count": 4}]
        assert not (path / "journal.log").read_text(encoding="utf-8").strip()

    def test_compaction_keeps_later_writes(self, tmp_path: Path):
        path = tmp_path / "db"
        db = connect(path)
        db.execute(DDL)
        insert(db, 1, "a")
        db.compact()
        insert(db, 2, "b")
        db.close()

        reopened = connect(path)
        assert reopened.query("SELECT COUNT(*) FROM items") == [{"count": 2}]

    def test_auto_compaction_after_threshold(self, tmp_path: Path):
        path = tmp_path / "db"
        db = connect(path)
        db.execute(DDL)
        for identifier in range(1, 520):
            insert(db, identifier, f"n{identifier}")
        assert db.storage.journal_records < 512
        db.close()

        reopened = connect(path)
        assert reopened.query("SELECT COUNT(*) FROM items") == [{"count": 519}]

    def test_schema_survives_reopen(self, tmp_path: Path):
        path = tmp_path / "db"
        db = connect(path)
        db.execute(DDL)
        db.close()

        reopened = connect(path)
        assert reopened.schema.has_table("items")
        assert reopened.schema.table("items").column_names == [
            "id",
            "name",
            "price",
            "active",
            "created",
        ]

    def test_alter_table_add_column_persists(self, tmp_path: Path):
        path = tmp_path / "db"
        db = connect(path)
        db.execute(DDL)
        insert(db, 1, "a")
        db.execute("ALTER TABLE items ADD COLUMN note TEXT")
        db.close()

        reopened = connect(path)
        assert reopened.schema.table("items").has_column("note")
        assert reopened.query("SELECT note FROM items") == [{"note": None}]

    def test_alter_table_add_unique_constraint(self, tmp_path: Path):
        path = tmp_path / "db"
        db = connect(path)
        db.execute(DDL)
        insert(db, 1, "a")
        db.execute("ALTER TABLE items ADD COLUMN code TEXT")
        db.execute("ALTER TABLE items ADD CONSTRAINT uq_items_code UNIQUE (code)")
        with pytest.raises(IntegrityError) as excinfo:
            insert(db, 2, "b", None, None, None)
            db.execute("UPDATE items SET code = ? WHERE id = ?", ["same", 1])
            db.execute("UPDATE items SET code = ? WHERE id = ?", ["same", 2])
        assert excinfo.value.constraint == "unique"
        db.close()

        reopened = connect(path)
        assert ("code",) in reopened.schema.table("items").unique_constraints

    def test_alter_table_add_unique_constraint_rejects_existing_duplicates(self, database):
        insert(database, 1, "a")
        insert(database, 2, "b")
        database.execute("ALTER TABLE items ADD COLUMN code TEXT")
        database.execute("UPDATE items SET code = ?", ["dup"])
        with pytest.raises(IntegrityError) as excinfo:
            database.execute(
                "ALTER TABLE items ADD CONSTRAINT uq_items_code UNIQUE (code)"
            )
        assert excinfo.value.constraint == "unique"

    def test_drop_table_persists(self, tmp_path: Path):
        path = tmp_path / "db"
        db = connect(path)
        db.execute(DDL)
        db.execute("DROP TABLE items")
        db.close()

        reopened = connect(path)
        assert not reopened.schema.has_table("items")


class TestMigrations:
    def test_runner_applies_each_version_once(self, tmp_path: Path):
        path = tmp_path / "db"
        db = connect(path)
        calls: list[int] = []

        def first(transaction):
            calls.append(1)
            transaction.execute("CREATE TABLE one (id INTEGER PRIMARY KEY)")

        def second(transaction):
            calls.append(2)
            transaction.execute("CREATE TABLE two (id INTEGER PRIMARY KEY)")

        migrations = [(1, "one", first), (2, "two", second)]
        assert run_migrations(db, migrations, now=lambda: "2026-10-18T00:00:00Z") == [1, 2]
        assert calls == [1, 2]
        assert applied_versions(db) == {1, 2}

        assert run_migrations(db, migrations, now=lambda: "2026-10-19T00:00:00Z") == []
        assert calls == [1, 2]

        db.close()
        reopened = connect(path)
        assert applied_versions(reopened) == {1, 2}
        assert reopened.schema.has_table("two")

    def test_failed_migration_rolls_back(self, tmp_path: Path):
        db = connect(tmp_path / "db")

        def broken(transaction):
            transaction.execute("CREATE TABLE half (id INTEGER PRIMARY KEY)")
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            run_migrations(db, [(1, "broken", broken)], now=lambda: "now")
        assert not db.schema.has_table("half")
        assert applied_versions(db) == set()
