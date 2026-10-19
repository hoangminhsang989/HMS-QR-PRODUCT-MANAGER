"""HMS SQL parser.

A small recursive-descent parser for the statement subset the product needs:

- ``CREATE TABLE`` / ``DROP TABLE`` / ``ALTER TABLE ... ADD COLUMN``
- ``INSERT INTO ... VALUES ...``
- ``UPDATE ... SET ... WHERE ...``
- ``DELETE FROM ... WHERE ...``
- ``SELECT ... FROM ... WHERE ... ORDER BY ... LIMIT ... OFFSET ...``
- ``SELECT COUNT(*) FROM ...``

Expressions cover comparisons, ``LIKE``, ``IN``, ``IS NULL``, ``AND``/``OR``,
parentheses, and literals.  Parameters are positional ``?`` placeholders.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from .errors import SyntaxError_
from .schema import Column, ForeignKey, Table
from .types import type_from_name


KEYWORDS = {
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "UPDATE", "SET",
    "DELETE", "CREATE", "TABLE", "DROP", "ALTER", "ADD", "COLUMN", "AND", "OR",
    "NOT", "NULL", "IS", "IN", "LIKE", "ORDER", "BY", "ASC", "DESC", "LIMIT",
    "OFFSET", "COUNT", "PRIMARY", "KEY", "UNIQUE", "FOREIGN", "REFERENCES",
    "DEFAULT", "TRUE", "FALSE", "AS", "DISTINCT", "CONSTRAINT", "JOIN", "ON",
}


@dataclass
class Token:
    kind: str  # keyword | identifier | number | string | punct | eof
    value: str
    position: int


def tokenize(sql: str) -> list[Token]:
    tokens: list[Token] = []
    index = 0
    length = len(sql)
    while index < length:
        char = sql[index]
        if char.isspace():
            index += 1
            continue
        if char == "-" and index + 1 < length and sql[index + 1] == "-":
            while index < length and sql[index] != "\n":
                index += 1
            continue
        if char == "'":
            index += 1
            buffer = []
            while index < length:
                if sql[index] == "'":
                    if index + 1 < length and sql[index + 1] == "'":
                        buffer.append("'")
                        index += 2
                        continue
                    index += 1
                    break
                buffer.append(sql[index])
                index += 1
            else:
                raise SyntaxError_("Unterminated string literal")
            tokens.append(Token("string", "".join(buffer), index))
            continue
        if char == '"':
            index += 1
            start = index
            while index < length and sql[index] != '"':
                index += 1
            if index >= length:
                raise SyntaxError_("Unterminated quoted identifier")
            tokens.append(Token("identifier", sql[start:index], index))
            index += 1
            continue
        if char.isdigit() or (char == "." and index + 1 < length and sql[index + 1].isdigit()):
            start = index
            while index < length and (sql[index].isdigit() or sql[index] in ".eE+-"):
                if sql[index] in "+-" and sql[index - 1] not in "eE":
                    break
                index += 1
            tokens.append(Token("number", sql[start:index], index))
            continue
        if char.isalpha() or char == "_":
            start = index
            while index < length and (sql[index].isalnum() or sql[index] in "_."):
                index += 1
            word = sql[start:index]
            kind = "keyword" if word.upper() in KEYWORDS else "identifier"
            tokens.append(Token(kind, word, index))
            continue
        if char in "(),*;":
            tokens.append(Token("punct", char, index))
            index += 1
            continue
        if char in "=<>":
            start = index
            index += 1
            if index < length and sql[index] in "=>" and char in "<>":
                index += 1
            tokens.append(Token("punct", sql[start:index], index))
            continue
        if char == "!":
            if index + 1 < length and sql[index + 1] == "=":
                tokens.append(Token("punct", "!=", index))
                index += 2
                continue
            raise SyntaxError_(f"Unexpected character '!' at {index}")
        if char == "?":
            tokens.append(Token("param", "?", index))
            index += 1
            continue
        raise SyntaxError_(f"Unexpected character {char!r} at {index}")
    tokens.append(Token("eof", "", length))
    return tokens


# -- expression tree ------------------------------------------------------


@dataclass
class Literal:
    value: Any


@dataclass
class Parameter:
    index: int


@dataclass
class ColumnRef:
    name: str


@dataclass
class Comparison:
    left: Any
    operator: str
    right: Any


@dataclass
class IsNull:
    operand: Any
    negated: bool


@dataclass
class InList:
    operand: Any
    items: list
    negated: bool


@dataclass
class LikeExpression:
    operand: Any
    pattern: str
    negated: bool


@dataclass
class BooleanExpression:
    operator: str  # AND | OR
    operands: list


@dataclass
class NotExpression:
    operand: Any


# -- statement tree -------------------------------------------------------


@dataclass
class JoinClause:
    table: str
    on_left: str
    on_right: str


@dataclass
class SelectStatement:
    table: str
    columns: list[str] = field(default_factory=list)
    count_only: bool = False
    distinct: bool = False
    where: Any = None
    order_by: list[tuple[str, str]] = field(default_factory=list)
    limit: Any = None
    offset: Any = None
    literal: Any = None
    joins: list[JoinClause] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


@dataclass
class InsertStatement:
    table: str
    columns: list[str]
    values: list[Any]


@dataclass
class UpdateStatement:
    table: str
    assignments: list[tuple[str, Any]]
    where: Any = None


@dataclass
class DeleteStatement:
    table: str
    where: Any = None


@dataclass
class CreateTableStatement:
    table: Table


@dataclass
class DropTableStatement:
    table: str


@dataclass
class AddColumnStatement:
    table: str
    column: Column


@dataclass
class AddUniqueConstraintStatement:
    table: str
    columns: tuple[str, ...]
    name: str = ""


class Parser:
    def __init__(self, sql: str) -> None:
        self.tokens = tokenize(sql)
        self.position = 0
        self.parameters = 0

    # -- token helpers ---------------------------------------------------

    @property
    def current(self) -> Token:
        return self.tokens[self.position]

    def advance(self) -> Token:
        token = self.tokens[self.position]
        self.position += 1
        return token

    def accept_keyword(self, *words: str) -> bool:
        token = self.current
        if token.kind == "keyword" and token.value.upper() in words:
            self.advance()
            return True
        return False

    def expect_keyword(self, *words: str) -> Token:
        token = self.current
        if token.kind != "keyword" or token.value.upper() not in words:
            raise SyntaxError_(f"Expected {'/'.join(words)}, got {token.value!r}")
        return self.advance()

    def expect_punct(self, value: str) -> Token:
        token = self.current
        if token.kind != "punct" or token.value != value:
            raise SyntaxError_(f"Expected {value!r}, got {token.value!r}")
        return self.advance()

    def accept_punct(self, value: str) -> bool:
        if self.current.kind == "punct" and self.current.value == value:
            self.advance()
            return True
        return False

    def expect_identifier(self) -> str:
        token = self.current
        if token.kind not in ("identifier", "keyword"):
            raise SyntaxError_(f"Expected an identifier, got {token.value!r}")
        self.advance()
        return token.value

    def expect_string(self) -> str:
        token = self.current
        if token.kind != "string":
            raise SyntaxError_(f"Expected a string literal, got {token.value!r}")
        self.advance()
        return token.value

    # -- statements ------------------------------------------------------

    def parse_statement(self):
        if self.accept_keyword("SELECT"):
            return self.parse_select()
        if self.accept_keyword("INSERT"):
            return self.parse_insert()
        if self.accept_keyword("UPDATE"):
            return self.parse_update()
        if self.accept_keyword("DELETE"):
            return self.parse_delete()
        if self.accept_keyword("CREATE"):
            return self.parse_create_table()
        if self.accept_keyword("DROP"):
            return self.parse_drop_table()
        if self.accept_keyword("ALTER"):
            return self.parse_alter_table()
        raise SyntaxError_(f"Unsupported statement starting with {self.current.value!r}")

    def parse_select(self) -> SelectStatement:
        statement = SelectStatement(table="")
        if self.accept_keyword("DISTINCT"):
            statement.distinct = True
        if self.accept_keyword("COUNT"):
            self.expect_punct("(")
            self.expect_punct("*")
            self.expect_punct(")")
            statement.count_only = True
        elif self.current.kind == "punct" and self.current.value == "*":
            self.advance()
            statement.columns = ["*"]
        elif self.current.kind == "number" and self.tokens[self.position + 1].kind in (
            "eof",
            "punct",
        ):
            statement.columns = ["*"]
            statement.table = ""
            statement.literal = Literal(_number(self.advance().value))
            self.accept_punct(";")
            return statement
        else:
            while True:
                source = self.expect_identifier()
                alias = source.rsplit(".", 1)[1] if "." in source else source
                if self.accept_keyword("AS"):
                    alias = self.expect_identifier()
                statement.columns.append(alias)
                statement.sources.append(source)
                if not self.accept_punct(","):
                    break
        self.expect_keyword("FROM")
        statement.table = self.expect_identifier()
        if self.current.kind == "identifier":
            self.advance()
        while self.accept_keyword("JOIN"):
            joined = self.expect_identifier()
            if self.current.kind == "identifier":
                self.advance()
            self.expect_keyword("ON")
            left = self.expect_identifier()
            self.expect_punct("=")
            right = self.expect_identifier()
            statement.joins.append(JoinClause(joined, left, right))
        if self.accept_keyword("WHERE"):
            statement.where = self.parse_expression()
        if self.accept_keyword("ORDER"):
            self.expect_keyword("BY")
            while True:
                column = self.expect_identifier()
                direction = "ASC"
                if self.accept_keyword("DESC"):
                    direction = "DESC"
                else:
                    self.accept_keyword("ASC")
                statement.order_by.append((column, direction))
                if not self.accept_punct(","):
                    break
        if self.accept_keyword("LIMIT"):
            statement.limit = self.parse_literal_or_param()
        if self.accept_keyword("OFFSET"):
            statement.offset = self.parse_literal_or_param()
        self.accept_punct(";")
        return statement

    def parse_insert(self) -> InsertStatement:
        self.expect_keyword("INTO")
        table = self.expect_identifier()
        columns: list[str] = []
        if self.accept_punct("("):
            while True:
                columns.append(self.expect_identifier())
                if not self.accept_punct(","):
                    break
            self.expect_punct(")")
        self.expect_keyword("VALUES")
        self.expect_punct("(")
        values = [self.parse_literal_or_param()]
        while self.accept_punct(","):
            values.append(self.parse_literal_or_param())
        self.expect_punct(")")
        self.accept_punct(";")
        return InsertStatement(table=table, columns=columns, values=values)

    def parse_update(self) -> UpdateStatement:
        table = self.expect_identifier()
        self.expect_keyword("SET")
        assignments: list[tuple[str, Any]] = []
        while True:
            column = self.expect_identifier()
            if self.current.kind == "punct" and self.current.value == "=":
                self.advance()
            else:
                raise SyntaxError_("Expected '=' in UPDATE assignment")
            assignments.append((column, self.parse_literal_or_param()))
            if not self.accept_punct(","):
                break
        where = None
        if self.accept_keyword("WHERE"):
            where = self.parse_expression()
        self.accept_punct(";")
        return UpdateStatement(table=table, assignments=assignments, where=where)

    def parse_delete(self) -> DeleteStatement:
        self.expect_keyword("FROM")
        table = self.expect_identifier()
        where = None
        if self.accept_keyword("WHERE"):
            where = self.parse_expression()
        self.accept_punct(";")
        return DeleteStatement(table=table, where=where)

    def parse_create_table(self) -> CreateTableStatement:
        self.expect_keyword("TABLE")
        name = self.expect_identifier()
        self.expect_punct("(")
        columns: list[Column] = []
        primary_key: list[str] = []
        unique_constraints: list[tuple[str, ...]] = []
        foreign_keys: list[ForeignKey] = []
        while True:
            if self.accept_keyword("PRIMARY"):
                self.expect_keyword("KEY")
                self.expect_punct("(")
                keys = [self.expect_identifier()]
                while self.accept_punct(","):
                    keys.append(self.expect_identifier())
                self.expect_punct(")")
                primary_key.extend(keys)
            elif self.accept_keyword("UNIQUE"):
                self.expect_punct("(")
                keys = [self.expect_identifier()]
                while self.accept_punct(","):
                    keys.append(self.expect_identifier())
                self.expect_punct(")")
                unique_constraints.append(tuple(keys))
            elif self.accept_keyword("FOREIGN"):
                self.expect_keyword("KEY")
                self.expect_punct("(")
                column = self.expect_identifier()
                self.expect_punct(")")
                self.expect_keyword("REFERENCES")
                target_table = self.expect_identifier()
                self.expect_punct("(")
                target_column = self.expect_identifier()
                self.expect_punct(")")
                foreign_keys.append(ForeignKey(column, target_table, target_column))
            else:
                columns.append(self.parse_column_definition(primary_key))
            if not self.accept_punct(","):
                break
        self.expect_punct(")")
        self.accept_punct(";")
        for column in columns:
            if column.primary_key and column.name not in primary_key:
                primary_key.append(column.name)
        columns = [
            replace(column, nullable=False) if column.name in primary_key else column
            for column in columns
        ]
        table = Table(
            name=name,
            columns=columns,
            primary_key=primary_key,
            unique_constraints=unique_constraints,
            foreign_keys=foreign_keys,
        )
        return CreateTableStatement(table=table)

    def parse_column_definition(self, primary_key: list[str]) -> Column:
        name = self.expect_identifier()
        type_name = self.parse_type_name()
        column_type = type_from_name(type_name)
        nullable = True
        is_primary = False
        unique = False
        default = None
        has_default = False
        while True:
            if self.accept_keyword("PRIMARY"):
                self.expect_keyword("KEY")
                is_primary = True
                nullable = False
                continue
            if self.accept_keyword("UNIQUE"):
                unique = True
                continue
            if self.accept_keyword("NOT"):
                self.expect_keyword("NULL")
                nullable = False
                continue
            if self.accept_keyword("NULL"):
                nullable = True
                continue
            if self.accept_keyword("DEFAULT"):
                default = self.parse_default_value(column_type)
                has_default = True
                continue
            break
        return Column(
            name=name,
            type=column_type,
            nullable=nullable,
            primary_key=is_primary,
            unique=unique,
            default=default,
            has_default=has_default,
        )

    def parse_type_name(self) -> str:
        token = self.current
        if token.kind not in ("identifier", "keyword"):
            raise SyntaxError_(f"Expected a type name, got {token.value!r}")
        name = token.value.upper()
        self.advance()
        if self.accept_punct("("):
            parts = []
            while True:
                parts.append(self.advance().value)
                if not self.accept_punct(","):
                    break
            self.expect_punct(")")
            name = f"{name}({','.join(parts)})"
        return name

    def parse_default_value(self, column_type):
        if self.accept_keyword("NULL"):
            return None
        if self.accept_keyword("TRUE"):
            return True
        if self.accept_keyword("FALSE"):
            return False
        token = self.current
        if token.kind == "string":
            self.advance()
            return column_type.coerce(token.value, column="default")
        if token.kind == "number":
            self.advance()
            return column_type.coerce(token.value, column="default")
        raise SyntaxError_(f"Unsupported DEFAULT value {token.value!r}")

    def parse_drop_table(self) -> DropTableStatement:
        self.expect_keyword("TABLE")
        name = self.expect_identifier()
        self.accept_punct(";")
        return DropTableStatement(table=name)

    def parse_alter_table(self):
        self.expect_keyword("TABLE")
        table = self.expect_identifier()
        self.expect_keyword("ADD")
        if self.accept_keyword("CONSTRAINT"):
            name = self.expect_identifier()
            self.expect_keyword("UNIQUE")
            self.expect_punct("(")
            columns = [self.expect_identifier()]
            while self.accept_punct(","):
                columns.append(self.expect_identifier())
            self.expect_punct(")")
            self.accept_punct(";")
            return AddUniqueConstraintStatement(
                table=table, columns=tuple(columns), name=name
            )
        self.accept_keyword("COLUMN")
        column = self.parse_column_definition([])
        self.accept_punct(";")
        return AddColumnStatement(table=table, column=column)

    # -- expressions -----------------------------------------------------

    def parse_literal_or_param(self):
        if self.current.kind == "param":
            self.advance()
            index = self.parameters
            self.parameters += 1
            return Parameter(index)
        return self.parse_literal()

    def parse_literal(self):
        token = self.current
        if self.accept_keyword("NULL"):
            return Literal(None)
        if self.accept_keyword("TRUE"):
            return Literal(True)
        if self.accept_keyword("FALSE"):
            return Literal(False)
        if token.kind == "string":
            self.advance()
            return Literal(token.value)
        if token.kind == "number":
            self.advance()
            return Literal(_number(token.value))
        raise SyntaxError_(f"Expected a literal, got {token.value!r}")

    def parse_expression(self):
        return self.parse_or()

    def parse_or(self):
        operands = [self.parse_and()]
        while self.accept_keyword("OR"):
            operands.append(self.parse_and())
        if len(operands) == 1:
            return operands[0]
        return BooleanExpression("OR", operands)

    def parse_and(self):
        operands = [self.parse_not()]
        while self.accept_keyword("AND"):
            operands.append(self.parse_not())
        if len(operands) == 1:
            return operands[0]
        return BooleanExpression("AND", operands)

    def parse_not(self):
        if self.accept_keyword("NOT"):
            return NotExpression(self.parse_not())
        return self.parse_predicate()

    def parse_predicate(self):
        if self.accept_punct("("):
            expression = self.parse_expression()
            self.expect_punct(")")
            return expression
        left = self.parse_operand()
        if self.accept_keyword("IS"):
            negated = self.accept_keyword("NOT")
            self.expect_keyword("NULL")
            return IsNull(left, negated)
        negated = False
        if self.accept_keyword("NOT"):
            negated = True
        if self.accept_keyword("IN"):
            self.expect_punct("(")
            items = [self.parse_literal_or_param()]
            while self.accept_punct(","):
                items.append(self.parse_literal_or_param())
            self.expect_punct(")")
            return InList(left, items, negated)
        if self.accept_keyword("LIKE"):
            pattern = self.parse_literal_or_param()
            return LikeExpression(left, pattern, negated)
        if negated:
            raise SyntaxError_("Expected IN or LIKE after NOT")
        token = self.current
        if token.kind == "punct" and token.value in ("=", "!=", "<>", "<", "<=", ">", ">="):
            self.advance()
            right = self.parse_literal_or_param()
            return Comparison(left, "!=" if token.value == "<>" else token.value, right)
        raise SyntaxError_(f"Expected a comparison operator, got {token.value!r}")

    def parse_operand(self):
        token = self.current
        if token.kind == "identifier":
            self.advance()
            if self.accept_punct("."):
                return ColumnRef(self.expect_identifier())
            return ColumnRef(token.value)
        return self.parse_literal()


def _number(text: str):
    if any(char in text for char in ".eE"):
        return Decimal(text)
    return int(text)


def parse(sql: str):
    """Parse one statement and return the statement tree."""

    return Parser(sql).parse_statement()
