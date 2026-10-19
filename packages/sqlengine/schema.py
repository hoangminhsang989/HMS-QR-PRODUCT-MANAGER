"""HMS SQL schema objects.

A schema is a set of tables; a table is an ordered set of typed columns plus
primary-key, unique, not-null, and foreign-key rules.  The engine keeps the
whole schema in memory and persists it inside every snapshot, so a database
file is self-describing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .errors import IntegrityError
from .types import BOOLEAN, ColumnType, type_from_name


@dataclass(frozen=True)
class Column:
    name: str
    type: ColumnType
    nullable: bool = True
    primary_key: bool = False
    unique: bool = False
    default: object = None
    has_default: bool = False

    def ddl(self) -> str:
        parts = [self.name, self.type.name]
        if self.primary_key:
            parts.append("PRIMARY KEY")
        if self.unique and not self.primary_key:
            parts.append("UNIQUE")
        if not self.nullable and not self.primary_key:
            parts.append("NOT NULL")
        if self.has_default:
            parts.append(f"DEFAULT {self.default!r}")
        return " ".join(parts)


@dataclass(frozen=True)
class ForeignKey:
    column: str
    target_table: str
    target_column: str

    def ddl(self) -> str:
        return f"FOREIGN KEY ({self.column}) REFERENCES {self.target_table}({self.target_column})"


@dataclass
class Table:
    name: str
    columns: list[Column]
    primary_key: list[str]
    unique_constraints: list[tuple[str, ...]] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)

    @property
    def column_names(self) -> list[str]:
        return [column.name for column in self.columns]

    def column(self, name: str) -> Column:
        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError(name)

    def has_column(self, name: str) -> bool:
        return any(column.name == name for column in self.columns)

    def ddl(self) -> str:
        body = [column.ddl() for column in self.columns]
        if len(self.primary_key) > 1:
            body.append(f"PRIMARY KEY ({', '.join(self.primary_key)})")
        for constraint in self.unique_constraints:
            body.append(f"UNIQUE ({', '.join(constraint)})")
        for foreign_key in self.foreign_keys:
            body.append(foreign_key.ddl())
        return f"CREATE TABLE {self.name} (\n  " + ",\n  ".join(body) + "\n)"

    # -- validation -----------------------------------------------------

    def coerce_row(self, row: dict, *, applying_defaults: bool = True) -> dict:
        """Return ``row`` coerced to the table's column types and rules."""

        coerced: dict = {}
        for column in self.columns:
            if column.name in row:
                value = row[column.name]
            elif applying_defaults and column.has_default:
                value = column.default
            else:
                value = None
            if value is None:
                if not column.nullable and not column.primary_key:
                    raise IntegrityError(
                        f"Column '{self.name}.{column.name}' cannot be null",
                        constraint="not_null",
                        table=self.name,
                    )
                coerced[column.name] = None
                continue
            try:
                coerced[column.name] = column.type.coerce(value, column=column.name)
            except ValueError as exc:
                raise IntegrityError(str(exc), constraint="type", table=self.name) from None
        unknown = set(row) - set(self.column_names)
        if unknown:
            raise IntegrityError(
                f"Unknown columns for '{self.name}': {', '.join(sorted(unknown))}",
                constraint="unknown_column",
                table=self.name,
            )
        return coerced

    def check_unique(self, row: dict, *, ignore_key: tuple | None, existing: list[dict]) -> None:
        """Raise when ``row`` breaks a single-column unique or primary key."""

        skip = ignore_key if (ignore_key is not None and self.primary_key) else None
        for column in self.columns:
            if not (column.unique or column.primary_key):
                continue
            value = row.get(column.name)
            if value is None:
                continue
            for other in existing:
                if skip is not None and self.key_of(other) == skip:
                    continue
                if other.get(column.name) == value:
                    label = "primary key" if column.primary_key else "unique"
                    raise IntegrityError(
                        f"{label.capitalize()} violation on '{self.name}.{column.name}'",
                        constraint="primary_key" if column.primary_key else "unique",
                        table=self.name,
                    )
        if len(self.primary_key) > 1:
            marker = tuple(row.get(name) for name in self.primary_key)
            if not any(value is None for value in marker):
                for other in existing:
                    if skip is not None and self.key_of(other) == skip:
                        continue
                    if tuple(other.get(name) for name in self.primary_key) == marker:
                        raise IntegrityError(
                            f"Primary key violation on '{self.name}"
                            f"({', '.join(self.primary_key)})'",
                            constraint="primary_key",
                            table=self.name,
                        )
        for constraint in self.unique_constraints:
            values = tuple(row.get(name) for name in constraint)
            if any(value is None for value in values):
                continue
            for other in existing:
                if skip is not None and self.key_of(other) == skip:
                    continue
                if tuple(other.get(name) for name in constraint) == values:
                    raise IntegrityError(
                        f"Unique violation on '{self.name}({', '.join(constraint)})'",
                        constraint="unique",
                        table=self.name,
                    )

    def key_of(self, row: dict) -> tuple:
        return tuple(row.get(name) for name in self.primary_key)

    def check_foreign_keys(self, row: dict, schema: "Schema") -> None:
        for foreign_key in self.foreign_keys:
            value = row.get(foreign_key.column)
            if value is None:
                continue
            target = schema.table(foreign_key.target_table)
            if not any(
                other.get(foreign_key.target_column) == value for other in schema.rows(target.name)
            ):
                raise IntegrityError(
                    f"Foreign key violation on '{self.name}.{foreign_key.column}'",
                    constraint="foreign_key",
                    table=self.name,
                )

    def children_reference(self, schema: "Schema", key: tuple) -> bool:
        """Report whether any row in the schema references this table's key."""

        for other_table in schema.tables.values():
            if other_table.name == self.name:
                continue
            for foreign_key in other_table.foreign_keys:
                if foreign_key.target_table != self.name:
                    continue
                for row in schema.rows(other_table.name):
                    if row.get(foreign_key.column) in key:
                        return True
        return False

    # -- serialization --------------------------------------------------

    def to_dict(self) -> dict:
        from .types import serialize_value

        return {
            "name": self.name,
            "columns": [
                {
                    "name": column.name,
                    "type": column.type.name,
                    "nullable": column.nullable,
                    "primary_key": column.primary_key,
                    "unique": column.unique,
                    "has_default": column.has_default,
                    "default": serialize_value(column.default),
                }
                for column in self.columns
            ],
            "primary_key": list(self.primary_key),
            "unique_constraints": [list(item) for item in self.unique_constraints],
            "foreign_keys": [
                {
                    "column": foreign_key.column,
                    "target_table": foreign_key.target_table,
                    "target_column": foreign_key.target_column,
                }
                for foreign_key in self.foreign_keys
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "Table":
        columns = [
            _column_from_dict(item)
            for item in payload["columns"]
        ]
        return cls(
            name=payload["name"],
            columns=columns,
            primary_key=list(payload["primary_key"]),
            unique_constraints=[tuple(item) for item in payload.get("unique_constraints", [])],
            foreign_keys=[
                ForeignKey(
                    column=item["column"],
                    target_table=item["target_table"],
                    target_column=item["target_column"],
                )
                for item in payload.get("foreign_keys", [])
            ],
        )


def _column_from_dict(payload: dict) -> Column:
    column_type = type_from_name(payload["type"])
    default = payload.get("default")
    if payload.get("has_default") and default is not None:
        default = column_type.coerce(default, column=payload["name"])
    return Column(
        name=payload["name"],
        type=column_type,
        nullable=payload.get("nullable", True),
        primary_key=payload.get("primary_key", False),
        unique=payload.get("unique", False),
        default=default,
        has_default=payload.get("has_default", False),
    )


class Schema:
    """An in-memory collection of tables with their rows."""

    def __init__(self) -> None:
        self.tables: dict[str, Table] = {}
        self._rows: dict[str, list[dict]] = {}

    # -- tables ---------------------------------------------------------

    def create_table(self, table: Table) -> None:
        if table.name in self.tables:
            raise IntegrityError(f"Table '{table.name}' already exists", constraint="ddl")
        self.tables[table.name] = table
        self._rows[table.name] = []

    def drop_table(self, name: str) -> None:
        if name not in self.tables:
            raise IntegrityError(f"Table '{name}' does not exist", constraint="ddl")
        del self.tables[name]
        del self._rows[name]

    def add_column(self, table_name: str, column: Column) -> None:
        table = self.table(table_name)
        if table.has_column(column.name):
            raise IntegrityError(
                f"Column '{table_name}.{column.name}' already exists", constraint="ddl"
            )
        table.columns.append(column)
        if column.primary_key:
            table.primary_key.append(column.name)
            if column.nullable:
                table.columns[-1] = replace(column, nullable=False)
        for row in self._rows[table_name]:
            row[column.name] = column.default if column.has_default else None

    def add_unique_constraint(self, table_name: str, columns: tuple[str, ...]) -> None:
        table = self.table(table_name)
        for name in columns:
            if not table.has_column(name):
                raise IntegrityError(
                    f"Column '{table_name}.{name}' does not exist", constraint="ddl"
                )
        constraint = tuple(columns)
        if constraint in table.unique_constraints:
            return
        seen: set[tuple] = set()
        for row in self._rows[table_name]:
            marker = tuple(row.get(name) for name in constraint)
            if all(value is None for value in marker):
                continue
            if marker in seen:
                raise IntegrityError(
                    f"Unique violation on '{table_name}({', '.join(constraint)})'",
                    constraint="unique",
                    table=table_name,
                )
            seen.add(marker)
        table.unique_constraints.append(constraint)

    def table(self, name: str) -> Table:
        try:
            return self.tables[name]
        except KeyError:
            raise IntegrityError(f"Table '{name}' does not exist", constraint="ddl") from None

    def has_table(self, name: str) -> bool:
        return name in self.tables

    def rows(self, name: str) -> list[dict]:
        return self._rows[name]

    def set_rows(self, name: str, rows: list[dict]) -> None:
        self._rows[name] = rows

    # -- serialization --------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "tables": [table.to_dict() for table in self.tables.values()],
            "rows": {
                name: [
                    {key: _plain(value) for key, value in row.items()} for row in rows
                ]
                for name, rows in self._rows.items()
            },
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "Schema":
        from .types import deserialize_value

        schema = cls()
        for table_payload in payload["tables"]:
            table = Table.from_dict(table_payload)
            schema.tables[table.name] = table
            schema._rows[table.name] = []
        for name, rows in payload.get("rows", {}).items():
            if name not in schema._rows:
                continue
            table = schema.tables[name]
            restored = []
            for row in rows:
                rebuilt = {}
                for column in table.columns:
                    if column.name in row:
                        rebuilt[column.name] = column.type.deserialize(
                            deserialize_value(row[column.name])
                        )
                restored.append(rebuilt)
            schema._rows[name] = restored
        return schema

    def clone_rows(self) -> dict[str, list[dict]]:
        """Deep-copy every row list so a transaction can mutate privately."""

        return {name: [dict(row) for row in rows] for name, rows in self._rows.items()}

    def replace_rows(self, rows: dict[str, list[dict]]) -> None:
        self._rows = rows


def _plain(value):
    from .types import serialize_value

    return serialize_value(value)


def boolean_default() -> bool:
    return BOOLEAN.coerce(False, column="default")
