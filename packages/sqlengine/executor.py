"""HMS SQL executor.

Executes parsed statements against an in-memory :class:`Schema`.  Every
mutating statement returns the list of row operations it performed so the
transaction layer can journal them and the storage layer can persist them.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from . import parser as sql_parser
from .errors import ExecutionError, IntegrityError
from .parser import (
    AddColumnStatement,
    AddUniqueConstraintStatement,
    BooleanExpression,
    ColumnRef,
    Comparison,
    CreateTableStatement,
    DeleteStatement,
    DropTableStatement,
    InList,
    InsertStatement,
    IsNull,
    LikeExpression,
    Literal,
    NotExpression,
    Parameter,
    SelectStatement,
    UpdateStatement,
)
from .schema import Schema


def _like_to_pattern(pattern: str) -> str:
    import re

    parts = ["^"]
    for character in pattern:
        if character == "%":
            parts.append(".*")
        elif character == "_":
            parts.append(".")
        else:
            parts.append(re.escape(character))
    parts.append("$")
    return "".join(parts)


class Executor:
    """Executes statements against a mutable schema."""

    def __init__(self, schema: Schema) -> None:
        self.schema = schema

    # -- dispatch --------------------------------------------------------

    def execute(self, statement, parameters: Iterable | None = None) -> Any:
        parameters = list(parameters or [])
        if isinstance(statement, SelectStatement):
            return self.execute_select(statement, parameters)
        if isinstance(statement, InsertStatement):
            return self.execute_insert(statement, parameters)
        if isinstance(statement, UpdateStatement):
            return self.execute_update(statement, parameters)
        if isinstance(statement, DeleteStatement):
            return self.execute_delete(statement, parameters)
        if isinstance(statement, CreateTableStatement):
            self.schema.create_table(statement.table)
            return {"created": statement.table.name}
        if isinstance(statement, DropTableStatement):
            self.schema.drop_table(statement.table)
            return {"dropped": statement.table}
        if isinstance(statement, AddColumnStatement):
            self.schema.add_column(statement.table, statement.column)
            return {"added_column": [statement.table, statement.column.name]}
        if isinstance(statement, AddUniqueConstraintStatement):
            self.schema.add_unique_constraint(statement.table, statement.columns)
            return {"added_unique": [statement.table, list(statement.columns)]}
        raise ExecutionError(f"Unsupported statement {type(statement).__name__}")

    # -- select ----------------------------------------------------------

    def execute_select(self, statement: SelectStatement, parameters: list) -> list[dict]:
        if statement.literal is not None:
            return [{"1": self.value(statement.literal, parameters)}]
        table = self.schema.table(statement.table)
        rows = self.schema.rows(statement.table)
        if statement.joins:
            rows = self._joined_rows(statement, rows)
        selected = [
            row for row in rows if self.matches(statement.where, row, parameters)
        ]
        if statement.count_only:
            return [{"count": len(selected)}]
        for column, direction in reversed(statement.order_by):
            reverse = direction == "DESC"
            selected.sort(key=lambda row, name=column: _sort_key(row.get(name)), reverse=reverse)
        if statement.distinct:
            seen: list[tuple] = []
            unique_rows = []
            for row in selected:
                marker = tuple(row.get(name) for name in statement.columns)
                if marker in seen:
                    continue
                seen.append(marker)
                unique_rows.append(row)
            selected = unique_rows
        offset = self.int_value(statement.offset, parameters) if statement.offset is not None else 0
        limit = self.int_value(statement.limit, parameters) if statement.limit is not None else None
        if offset:
            selected = selected[offset:]
        if limit is not None:
            selected = selected[:limit]
        if statement.columns and statement.columns != ["*"]:
            pairs = list(zip(statement.columns, statement.sources)) if statement.sources else [
                (name, name) for name in statement.columns
            ]
            return [
                {alias: row.get(self.column_name(ColumnRef(source))) for alias, source in pairs}
                for row in selected
            ]
        return [dict(row) for row in selected]

    def _joined_rows(self, statement: SelectStatement, rows: list[dict]) -> list[dict]:
        """Join ``statement.joins`` onto ``rows`` on qualified column names.

        Left rows without a match survive with the joined table's columns set
        to ``None`` so ``IS NULL`` predicates keep working.
        """

        def plain(name: str) -> str:
            return name.rsplit(".", 1)[1] if "." in name else name

        joined = [dict(row) for row in rows]
        for clause in statement.joins:
            right_rows = self.schema.rows(clause.table)
            right_columns = self.schema.table(clause.table).column_names
            left_key = plain(clause.on_left)
            right_key = plain(clause.on_right)
            # Resolve each ON key against the table that owns the column so a
            # shared name such as internal_id cannot bind to the wrong side.
            left_columns = set()
            for row in joined:
                left_columns.update(row)
            if left_key not in left_columns and right_key in left_columns:
                left_key, right_key = right_key, left_key
            elif left_key in left_columns and right_key in left_columns:
                # Both names exist on the left; the ON clause's qualified
                # prefix decides which side each one belongs to.
                if clause.on_left.startswith(clause.table + "."):
                    left_key, right_key = right_key, left_key
            merged: list[dict] = []
            for left in joined:
                left_value = left.get(left_key)
                matches = [
                    right for right in right_rows
                    if left_value is not None and left_value == right.get(right_key)
                ]
                if matches:
                    for right in matches:
                        candidate = dict(left)
                        for column in right_columns:
                            if column != left_key:
                                candidate[column] = right.get(column)
                        merged.append(candidate)
                else:
                    candidate = dict(left)
                    for column in right_columns:
                        if column != left_key:
                            candidate.setdefault(column, None)
                    merged.append(candidate)
            joined = merged
        return joined

    # -- insert ----------------------------------------------------------

    def execute_insert(self, statement: InsertStatement, parameters: list) -> dict:
        table = self.schema.table(statement.table)
        columns = statement.columns or table.column_names
        if len(columns) != len(statement.values):
            raise ExecutionError(
                f"INSERT into '{statement.table}' has {len(columns)} columns "
                f"but {len(statement.values)} values"
            )
        values = [self.value(item, parameters) for item in statement.values]
        row = dict(zip(columns, values))
        row = table.coerce_row(row)
        table.check_unique(row, ignore_key=None, existing=self.schema.rows(statement.table))
        table.check_foreign_keys(row, self.schema)
        self.schema.rows(statement.table).append(row)
        return {"inserted": table.key_of(row)}

    # -- update ----------------------------------------------------------

    def execute_update(self, statement: UpdateStatement, parameters: list) -> dict:
        table = self.schema.table(statement.table)
        rows = self.schema.rows(statement.table)
        assignments = {
            column: self.value(item, parameters) for column, item in statement.assignments
        }
        for column in assignments:
            if not table.has_column(column):
                raise ExecutionError(f"Unknown column '{statement.table}.{column}'")
        updated = 0
        for row in rows:
            if not self.matches(statement.where, row, parameters):
                continue
            candidate = dict(row)
            candidate.update(assignments)
            candidate = table.coerce_row(candidate, applying_defaults=False)
            table.check_unique(
                candidate, ignore_key=table.key_of(row), existing=rows
            )
            table.check_foreign_keys(candidate, self.schema)
            row.clear()
            row.update(candidate)
            updated += 1
        return {"updated": updated}

    # -- delete ----------------------------------------------------------

    def execute_delete(self, statement: DeleteStatement, parameters: list) -> dict:
        table = self.schema.table(statement.table)
        rows = self.schema.rows(statement.table)
        keep: list[dict] = []
        deleted: list[tuple] = []
        for row in rows:
            if self.matches(statement.where, row, parameters):
                key = table.key_of(row)
                if table.children_reference(self.schema, key):
                    raise IntegrityError(
                        f"Cannot delete '{statement.table}' row referenced by another table",
                        constraint="foreign_key",
                        table=statement.table,
                    )
                deleted.append(key)
            else:
                keep.append(row)
        self.schema.set_rows(statement.table, keep)
        return {"deleted": deleted}

    # -- expressions -----------------------------------------------------

    def value(self, node, parameters: list):
        if isinstance(node, Parameter):
            try:
                return parameters[node.index]
            except IndexError:
                raise ExecutionError(
                    f"Missing parameter {node.index}"
                ) from None
        if isinstance(node, Literal):
            return node.value
        raise ExecutionError(f"Unsupported value node {type(node).__name__}")

    def int_value(self, node, parameters: list) -> int:
        value = self.value(node, parameters)
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ExecutionError("LIMIT/OFFSET expect integers") from None

    def matches(self, node, row: dict, parameters: list) -> bool:
        if node is None:
            return True
        if isinstance(node, BooleanExpression):
            results = [self.matches(operand, row, parameters) for operand in node.operands]
            return all(results) if node.operator == "AND" else any(results)
        if isinstance(node, NotExpression):
            return not self.matches(node.operand, row, parameters)
        if isinstance(node, IsNull):
            return (row.get(self.column_name(node.operand)) is None) != node.negated
        if isinstance(node, InList):
            left = row.get(self.column_name(node.operand))
            items = [self.value(item, parameters) for item in node.items]
            found = left in items
            return found != node.negated
        if isinstance(node, LikeExpression):
            import re

            left = row.get(self.column_name(node.operand))
            pattern = self.value(node.pattern, parameters)
            if left is None or pattern is None:
                return False
            matched = (
                re.match(_like_to_pattern(str(pattern)), str(left), re.IGNORECASE)
                is not None
            )
            return matched != node.negated
        if isinstance(node, Comparison):
            left = row.get(self.column_name(node.left))
            right = self.value(node.right, parameters)
            return _compare(left, node.operator, right)
        raise ExecutionError(f"Unsupported predicate {type(node).__name__}")

    def column_name(self, node) -> str:
        if isinstance(node, ColumnRef):
            name = node.name
            if "." in name:
                name = name.rsplit(".", 1)[1]
            return name
        raise ExecutionError(f"Expected a column reference, got {type(node).__name__}")


def _sort_key(value):
    if value is None:
        return (0, 0)
    if isinstance(value, bool):
        return (1, int(value))
    if isinstance(value, (int, float, Decimal)):
        return (2, value)
    if isinstance(value, (datetime, date)):
        return (3, value.isoformat())
    return (4, str(value))


def _compare(left, operator: str, right) -> bool:
    if left is None or right is None:
        return False
    if isinstance(left, str) != isinstance(right, str):
        left, right = str(left), str(right)
    if isinstance(left, datetime) and isinstance(right, str):
        right = DateTimeType_().coerce(right, column="compare")
    if isinstance(left, date) and not isinstance(left, datetime) and isinstance(right, str):
        right = date.fromisoformat(right)
    if isinstance(left, Decimal) and not isinstance(right, Decimal):
        try:
            right = Decimal(str(right))
        except (ArithmeticError, ValueError):
            return False
    if isinstance(left, bool) != isinstance(right, bool):
        left, right = bool(left), bool(right)
    try:
        if operator == "=":
            return left == right
        if operator in ("!=", "<>"):
            return left != right
        if operator == "<":
            return left < right
        if operator == "<=":
            return left <= right
        if operator == ">":
            return left > right
        if operator == ">=":
            return left >= right
    except TypeError:
        return False
    raise ExecutionError(f"Unsupported operator {operator}")


def DateTimeType_():
    from .types import DateTimeType

    return DateTimeType()


def execute(schema: Schema, sql: str, parameters: Iterable | None = None) -> Any:
    """Parse and execute one statement against ``schema``."""

    statement = sql_parser.parse(sql)
    return Executor(schema).execute(statement, parameters)
