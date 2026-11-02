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

    def test_malformed_number_literal_is_a_syntax_error(self, database):
        """A number the tokenizer accepted but Decimal rejects must not escape.

        ``tokenize`` consumes any run of digits plus ``.eE+-`` as one number
        token, so ``1.2.3``, ``1e`` and ``1..2`` each become a single number.
        ``_number`` hands that text straight to ``Decimal``, which raises
        ``decimal.InvalidOperation`` - not a ``ValueError``, not an
        ``EngineError`` - so a caller holding the engine's error contract cannot
        catch it.

        Every other malformed token raises ``SyntaxError_`` with a position: an
        unterminated string, an unterminated quoted identifier, a stray ``!``.
        This is the one path that does not. The positions that fail are the ones
        where the literal is actually converted - a WHERE predicate and a VALUES
        list - because a malformed number in a SELECT column list is rejected by
        an earlier check for an unrelated reason.
        """

        for sql in (
            "SELECT * FROM items WHERE id = 1.2.3",
            "INSERT INTO items (id, name) VALUES (1e, 'x')",
            "SELECT * FROM items WHERE id = 1..2",
        ):
            with pytest.raises(SyntaxError_):
                database.query(sql)


class TestPredicates:
    def test_comparison_operators(self, database):
        for identifier in range(1, 6):
            insert(database, identifier, f"n{identifier}")
        assert len(database.query("SELECT * FROM items WHERE id >= 3")) == 3
        assert len(database.query("SELECT * FROM items WHERE id != 3")) == 4
        assert len(database.query("SELECT * FROM items WHERE id < 2")) == 1
        assert len(database.query("SELECT * FROM items WHERE id <= 2")) == 2
        assert len(database.query("SELECT * FROM items WHERE id > 4")) == 1

    def test_numeric_column_compared_to_a_string_parameter_is_numeric(self, tmp_path: Path):
        """A NUMERIC column compared to a string must compare as a number.

        ``_compare`` starts with
        ``if isinstance(left, str) != isinstance(right, str): left, right = str(left), str(right)``,
        so a Decimal column against a string parameter becomes a **lexicographic**
        comparison of the two strings. ``"12.5000" > "9"`` is false because '1'
        sorts before '9', so ``WHERE price > '9'`` returns nothing for a row
        holding 12.5.

        It also makes the Decimal branch further down unreachable for string
        parameters: that branch exists precisely to coerce a non-Decimal right
        side into a Decimal, but by the time it runs the right side is already a
        string. Code written to handle a case an earlier line prevents from
        arriving.

        The wrong answer is silent - no error, just missing rows.
        """

        db = connect(tmp_path / "cmp")
        try:
            db.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, price NUMERIC(18,4))")
            db.execute("INSERT INTO items (id, price) VALUES (?, ?)", [1, "12.5000"])
            db.execute("INSERT INTO items (id, price) VALUES (?, ?)", [2, "20.0000"])

            assert db.query("SELECT id FROM items WHERE price > ?", ["9"]) == [
                {"id": 1},
                {"id": 2},
            ]
            assert db.query("SELECT id FROM items WHERE price = ?", ["12.5"]) == [{"id": 1}]
            assert db.query("SELECT id FROM items WHERE price < ?", ["20"]) == [{"id": 1}]
            assert db.query("SELECT id FROM items WHERE price >= ?", ["20"]) == [{"id": 2}]

            # A non-numeric parameter simply matches nothing, rather than
            # raising: the coercion failure is swallowed by design.
            assert db.query("SELECT id FROM items WHERE price = ?", ["not-a-number"]) == []
        finally:
            db.close()

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

    def test_distinct_star_keeps_every_distinct_row(self, database):
        """``SELECT DISTINCT *`` must not collapse to one row.

        The DISTINCT branch builds its marker from ``statement.columns``:

            marker = tuple(row.get(name) for name in statement.columns)

        For ``SELECT *`` the parser sets ``columns`` to ``["*"]``, and no row has
        a column named ``*`` - so every marker is ``(None,)``, identical for
        every row, and only the first survives. Six distinct rows come back as
        one, with no error.

        ``test_distinct`` above covers the same branch with an explicit column
        list, which is why this survived: the marker is only wrong when the
        column list is the ``*`` placeholder.
        """

        db = database
        db.execute("CREATE TABLE tags (id INTEGER PRIMARY KEY, label TEXT)")
        for identifier in range(1, 7):
            db.execute("INSERT INTO tags (id, label) VALUES (?, ?)", [identifier, f"n{identifier}"])

        assert len(db.query("SELECT * FROM tags")) == 6
        assert len(db.query("SELECT DISTINCT * FROM tags")) == 6

        # A row that differs in any column is a distinct whole row, so DISTINCT *
        # keeps it even when another column repeats. (With a primary key no two
        # rows can be wholly identical, so DISTINCT * is equivalent to the plain
        # count here - which is exactly the point: it must not collapse them.)
        db.execute("INSERT INTO tags (id, label) VALUES (?, ?)", [7, "n1"])
        assert len(db.query("SELECT DISTINCT * FROM tags")) == 7
        assert len(db.query("SELECT DISTINCT label FROM tags")) == 6

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

    def test_update_on_a_table_without_a_primary_key_is_not_a_self_conflict(self, tmp_path: Path):
        """A table whose only uniqueness is a UNIQUE column must accept an UPDATE.

        ``check_unique`` computes ``skip`` as
        ``ignore_key if (ignore_key is not None and self.primary_key) else None``,
        so the row being updated is excluded only when the table has a primary
        key. Without one, ``skip`` stays ``None`` and the conflict scan includes
        the row itself, so an UPDATE that leaves the unique column at its current
        value - or changes only some other column - violates a constraint it
        already satisfies.

        ``test_update_same_value_is_not_a_conflict`` above covers the same
        behaviour against a table with ``id INTEGER PRIMARY KEY``. That is why
        this survived: every table in migrations/engine has a primary key, so the
        path is unreachable in production today. It is reachable through the
        public SQL interface for any table created without one, which the parser
        accepts without complaint.
        """

        db = connect(tmp_path / "nopk")
        try:
            db.execute("CREATE TABLE tags (label TEXT UNIQUE, note TEXT)")
            db.execute("INSERT INTO tags (label, note) VALUES (?, ?)", ["alpha", "first"])

            db.execute("UPDATE tags SET note = ? WHERE label = ?", ["second", "alpha"])
            assert db.query("SELECT note FROM tags") == [{"note": "second"}]

            db.execute("UPDATE tags SET label = ? WHERE label = ?", ["alpha", "alpha"])
            assert db.query("SELECT label FROM tags") == [{"label": "alpha"}]

            with pytest.raises(IntegrityError) as excinfo:
                db.execute("INSERT INTO tags (label, note) VALUES (?, ?)", ["alpha", "x"])
            assert excinfo.value.constraint == "unique"
        finally:
            db.close()

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

    def test_numeric_precision_overflow_is_a_type_error(self, database):
        """A value too wide for NUMERIC(18,4) must fail like every other bad value.

        Two defects met here. ``NumericType._coerce`` wrapped its ``Decimal``
        construction in try/except but left ``number.quantize(quantum)``
        outside it, so a precision overflow raised ``decimal.InvalidOperation``
        instead of ``ValueError``; ``Table.coerce_row`` catches only
        ``ValueError``, so the raw decimal exception escaped the engine - it is
        neither a ``ValueError`` nor an ``EngineError``, and nothing holding the
        engine's error contract could catch it.

        NUMERIC(18,4) means 18 digits in total, scale 4, so 14 integer digits is
        the widest allowed and 15 is not. Both sides are checked so a fix that
        merely catches the exception without honouring the declared width cannot
        pass.
        """

        with pytest.raises(IntegrityError) as excinfo:
            insert(database, 1, "too-wide", "1" * 15)
        assert excinfo.value.constraint == "type"

        insert(database, 2, "widest-allowed", "1" * 14)
        assert database.query("SELECT price FROM items WHERE id = 2")[0]["price"] == Decimal(
            "1" * 14 + ".0000"
        )

    def test_numeric_declared_precision_is_enforced(self, database):
        """NUMERIC(18,4) rejects 24 integer digits, which it used to accept.

        The declared precision was never checked at all: a value was stored as
        long as ``quantize`` succeeded under the ambient decimal context (28
        digits), so a 24-digit integer landed in a column the schema declared as
        18 digits wide. ``test_sqlengine_schema_parity.py`` pins the type name
        ``NUMERIC(18,4)``, so that declaration is part of the frozen contract.
        """

        for digits in (15, 19, 24):
            with pytest.raises(IntegrityError) as excinfo:
                insert(database, digits, f"digits-{digits}", "1" * digits)
            assert excinfo.value.constraint == "type"

        insert(database, 99, "fits", "1234.5678")
        assert database.query("SELECT price FROM items WHERE id = 99")[0]["price"] == Decimal(
            "1234.5678"
        )


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

    def test_a_commit_after_a_torn_record_survives_the_next_reopen(self, tmp_path: Path):
        """A commit acknowledged after a tear must not vanish on the next reopen.

        The docstring promises a torn record is discarded "together with
        everything after it, so a committed transaction is either fully present
        or fully absent". ``_replay`` does stop at the bad record, so the load
        that meets the tear honours that. It never removes the tear from disk,
        though, and the tear here is written without a trailing newline - which
        is exactly what a crash mid-append leaves - so the next ``append()``
        concatenates its record onto the torn fragment instead of starting a new
        line.

        The result is one unparseable line where a committed transaction used to
        be. ``test_torn_final_record_discarded`` stops before this point: it
        reopens once and asserts the earlier row, so the loss is invisible.

        Observed before the fix: the commit succeeded, the in-memory query saw
        both rows, the journal line count did not increase, and the row was gone
        after the next reopen.
        """

        path = tmp_path / "db"
        db = connect(path)
        db.execute(DDL)
        insert(db, 1, "a")
        db.close()

        journal = path / "journal.log"
        with journal.open("a", encoding="utf-8") as handle:
            handle.write('{"payload":"[{\\"op\\":\\"insert\\"')

        reopened = connect(path)
        insert(reopened, 2, "b")
        assert reopened.query("SELECT id FROM items ORDER BY id") == [{"id": 1}, {"id": 2}]
        reopened.close()

        final = connect(path)
        try:
            assert final.query("SELECT id FROM items ORDER BY id") == [{"id": 1}, {"id": 2}]
        finally:
            final.close()

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
