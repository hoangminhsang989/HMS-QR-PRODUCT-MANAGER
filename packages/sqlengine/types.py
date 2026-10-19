"""HMS SQL type system.

The engine stores a deliberately small set of column types that cover every
table the product owns.  Values live in memory as native Python objects and are
serialized to JSON-compatible form for the journal and snapshot files.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json


class ColumnType:
    """One storable column type with coercion and serialization rules."""

    __slots__ = ("name", "python_type")

    def __init__(self, name: str, python_type: type) -> None:
        self.name = name
        self.python_type = python_type

    def coerce(self, value, *, column: str = ""):
        """Return ``value`` as this type, or raise for an unusable value."""

        if value is None:
            return None
        if isinstance(value, self.python_type) and not isinstance(value, bool):
            return value
        return self._coerce(value, column)

    def _coerce(self, value, column: str):
        raise NotImplementedError

    def serialize(self, value):
        """Return a JSON-compatible representation for durable storage."""

        raise NotImplementedError

    def deserialize(self, value):
        """Rebuild the native value from its durable representation."""

        raise NotImplementedError

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"<ColumnType {self.name}>"


class TextType(ColumnType):
    def __init__(self) -> None:
        super().__init__("TEXT", str)

    def _coerce(self, value, column: str):
        if isinstance(value, (int, float, Decimal, bool)):
            return str(value)
        if isinstance(value, str):
            return value
        raise ValueError(f"Column '{column}' expects text, got {type(value).__name__}")

    def serialize(self, value):
        return None if value is None else str(value)

    def deserialize(self, value):
        return None if value is None else str(value)


class IntegerType(ColumnType):
    def __init__(self) -> None:
        super().__init__("INTEGER", int)

    def _coerce(self, value, column: str):
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                raise ValueError(f"Column '{column}' expects an integer") from None
        if isinstance(value, (Decimal, float)) and float(value).is_integer():
            return int(value)
        raise ValueError(f"Column '{column}' expects an integer, got {type(value).__name__}")

    def serialize(self, value):
        return None if value is None else int(value)

    def deserialize(self, value):
        return None if value is None else int(value)


class NumericType(ColumnType):
    def __init__(self, precision: int = 18, scale: int = 4) -> None:
        super().__init__(f"NUMERIC({precision},{scale})", Decimal)
        self.precision = precision
        self.scale = scale

    def coerce(self, value, *, column: str = ""):
        if value is None:
            return None
        return self._coerce(value, column)

    def _coerce(self, value, column: str):
        try:
            number = value if isinstance(value, Decimal) else Decimal(str(value).strip())
        except (ArithmeticError, ValueError, AttributeError):
            raise ValueError(f"Column '{column}' expects a number") from None
        if not number.is_finite():
            raise ValueError(f"Column '{column}' expects a finite number")
        quantum = Decimal(1).scaleb(-self.scale)
        return number.quantize(quantum)

    def serialize(self, value):
        return None if value is None else format(value, "f")

    def deserialize(self, value):
        return None if value is None else Decimal(str(value))


class BooleanType(ColumnType):
    def __init__(self) -> None:
        super().__init__("BOOLEAN", bool)

    def _coerce(self, value, column: str):
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("1", "true", "yes", "on"):
                return True
            if lowered in ("0", "false", "no", "off"):
                return False
        raise ValueError(f"Column '{column}' expects a boolean")

    def serialize(self, value):
        return None if value is None else bool(value)

    def deserialize(self, value):
        return None if value is None else bool(value)


class DateType(ColumnType):
    def __init__(self) -> None:
        super().__init__("DATE", date)

    def _coerce(self, value, column: str):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return date.fromisoformat(value.strip())
            except ValueError:
                raise ValueError(f"Column '{column}' expects an ISO date") from None
        raise ValueError(f"Column '{column}' expects a date, got {type(value).__name__}")

    def serialize(self, value):
        return None if value is None else value.isoformat()

    def deserialize(self, value):
        return None if value is None else date.fromisoformat(str(value))


class DateTimeType(ColumnType):
    def __init__(self, *, timezone_aware: bool = True) -> None:
        super().__init__("DATETIME", datetime)
        self.timezone_aware = timezone_aware

    def _coerce(self, value, column: str):
        if isinstance(value, str):
            text = value.strip().replace("Z", "+00:00")
            try:
                value = datetime.fromisoformat(text)
            except ValueError:
                raise ValueError(f"Column '{column}' expects an ISO datetime") from None
        if isinstance(value, datetime):
            if self.timezone_aware and value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            if not self.timezone_aware and value.tzinfo is not None:
                return value.replace(tzinfo=None)
            return value
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
        raise ValueError(f"Column '{column}' expects a datetime, got {type(value).__name__}")

    def serialize(self, value):
        return None if value is None else value.isoformat()

    def deserialize(self, value):
        if value is None:
            return None
        return self._coerce(str(value), "")


TEXT = TextType()
INTEGER = IntegerType()
NUMERIC = NumericType
BOOLEAN = BooleanType()
DATE = DateType()
DATETIME = DateTimeType()

_BY_NAME = {
    "TEXT": TEXT,
    "INTEGER": INTEGER,
    "BOOLEAN": BOOLEAN,
    "DATE": DATE,
    "DATETIME": DATETIME,
}


def type_from_name(name: str) -> ColumnType:
    """Resolve a declared type name such as ``NUMERIC(18,4)`` to a type object."""

    normalized = name.strip().upper()
    if normalized in _BY_NAME:
        return _BY_NAME[normalized]
    if normalized.startswith("NUMERIC"):
        precision, scale = 18, 4
        if "(" in normalized and ")" in normalized:
            inner = normalized[normalized.index("(") + 1 : normalized.rindex(")")]
            parts = [part.strip() for part in inner.split(",") if part.strip()]
            if len(parts) == 2:
                precision, scale = int(parts[0]), int(parts[1])
            elif len(parts) == 1:
                precision = int(parts[0])
        return NumericType(precision, scale)
    if normalized in ("VARCHAR", "STRING"):
        return TEXT
    raise ValueError(f"Unsupported column type '{name}'")


def serialize_value(value):
    """Serialize any supported value for JSON storage."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return {"__decimal__": format(value, "f")}
    if isinstance(value, datetime):
        return {"__datetime__": value.isoformat()}
    if isinstance(value, date):
        return {"__date__": value.isoformat()}
    raise ValueError(f"Unsupported value type {type(value).__name__}")


def deserialize_value(value):
    """Rebuild a value written by :func:`serialize_value`."""

    if isinstance(value, dict) and len(value) == 1:
        if "__decimal__" in value:
            return Decimal(str(value["__decimal__"]))
        if "__datetime__" in value:
            return DateTimeType()._coerce(str(value["__datetime__"]), "")
        if "__date__" in value:
            return date.fromisoformat(str(value["__date__"]))
    return value


def dumps(payload) -> str:
    """Compact deterministic JSON used by the journal and snapshot writers."""

    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
