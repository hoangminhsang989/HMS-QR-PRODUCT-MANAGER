"""Safe, compact Excel-style formula evaluator for the desktop entry worksheet.

It deliberately supports the calculation features used by production entry sheets,
not macros, external workbooks, PivotTables, or arbitrary Python execution.
"""

from __future__ import annotations

import ast
import math
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Callable


CELL_REF = re.compile(r"(?<![A-Z0-9_])\$?([A-Z]{1,3})\$?(\d+)(?![A-Z0-9_])", re.IGNORECASE)
RANGE_REF = re.compile(r"(?<![A-Z0-9_])\$?([A-Z]{1,3})\$?(\d+):\$?([A-Z]{1,3})\$?(\d+)(?![A-Z0-9_])", re.IGNORECASE)


class FormulaError(ValueError):
    """A user-visible spreadsheet calculation error."""

    def __init__(self, message: str, code: str = "#VALUE!") -> None:
        super().__init__(message)
        self.code = code


def column_index(name: str) -> int:
    value = 0
    for char in name:
        value = value * 26 + ord(char) - ord("A") + 1
    return value - 1


def flatten(values):
    for value in values:
        if isinstance(value, (list, tuple)):
            yield from flatten(value)
        else:
            yield value


def number(value: object) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, bool):
        return float(value)
    try:
        return float(Decimal(str(value).replace(",", "")))
    except (InvalidOperation, ValueError):
        raise FormulaError(f"Giá trị '{value}' không phải là số") from None


def criterion(value: object, expression: object) -> bool:
    text = str(expression)
    match = re.match(r"^(<=|>=|<>|=|<|>)(.*)$", text)
    operator, expected = match.groups() if match else ("=", text)
    actual_text = str(value)
    try:
        actual, expected_value = number(value), number(expected)
    except FormulaError:
        actual, expected_value = actual_text.casefold(), expected.casefold()
    return {
        "=": actual == expected_value,
        "<>": actual != expected_value,
        "<": actual < expected_value,
        ">": actual > expected_value,
        "<=": actual <= expected_value,
        ">=": actual >= expected_value,
    }[operator]


class FormulaEngine:
    """Evaluate one formula against a callback returning raw/calculated cell values."""

    def __init__(self, cell_value: Callable[[int, int], object], rows: int, columns: int) -> None:
        self.cell_value = cell_value
        self.rows = rows
        self.columns = columns

    def evaluate(self, formula: str) -> object:
        if not formula.startswith("="):
            return formula
        expression = formula[1:].strip()
        if not expression:
            return ""
        expression = RANGE_REF.sub(
            lambda m: f"__range({column_index(m.group(1))},{int(m.group(2)) - 1},{column_index(m.group(3))},{int(m.group(4)) - 1})",
            expression,
        )
        expression = CELL_REF.sub(lambda m: f"__cell({column_index(m.group(1))},{int(m.group(2)) - 1})", expression)
        expression = expression.replace("<>", "!=").replace("^", "**").replace("&", "+")
        expression = re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?=\()", lambda m: m.group(1).upper(), expression)
        expression = re.sub(r"(?<![<>=!])=(?!=)", "==", expression)
        expression = re.sub(r"\bTRUE\b", "True", expression)
        expression = re.sub(r"\bFALSE\b", "False", expression)
        expression = expression.replace(";", ",")
        try:
            tree = ast.parse(expression, mode="eval")
            return _SafeFormula(self._functions()).visit(tree.body)
        except FormulaError:
            raise
        except Exception as exc:
            raise FormulaError("Công thức không hợp lệ") from exc

    def _functions(self) -> dict[str, Callable]:
        def cell(column: int, row: int):
            if row < 0 or column < 0 or row >= self.rows or column >= self.columns:
                raise FormulaError("Tham chiếu nằm ngoài bảng", "#REF!")
            return self.cell_value(row, column)

        def range_(start_col: int, start_row: int, end_col: int, end_row: int):
            return [[cell(col, row) for col in range(start_col, end_col + 1)] for row in range(start_row, end_row + 1)]

        def values(*items): return list(flatten(items))
        def sum_(*items): return sum(number(value) for value in values(*items))
        def average(*items):
            nums = [number(value) for value in values(*items) if value not in (None, "")]
            return sum(nums) / len(nums) if nums else 0
        def count(*items): return sum(1 for value in values(*items) if _is_number(value))
        def counta(*items): return sum(1 for value in values(*items) if value not in (None, ""))
        def countif(items, condition): return sum(criterion(value, condition) for value in flatten([items]))
        def sumif(items, condition, sum_items=None):
            criteria_values = list(flatten([items])); sums = list(flatten([sum_items if sum_items is not None else items]))
            return sum(number(sums[index]) for index, value in enumerate(criteria_values) if criterion(value, condition))
        def countifs(*items):
            if len(items) < 2 or len(items) % 2:
                raise FormulaError("COUNTIFS cần các cặp vùng và điều kiện")
            ranges = [list(flatten([items[index]])) for index in range(0, len(items), 2)]
            conditions = items[1::2]
            if len({len(item) for item in ranges}) != 1:
                raise FormulaError("Các vùng COUNTIFS phải cùng kích thước")
            return sum(all(criterion(ranges[group][row], conditions[group]) for group in range(len(ranges))) for row in range(len(ranges[0])))
        def sumifs(sum_range, *items):
            if len(items) < 2 or len(items) % 2:
                raise FormulaError("SUMIFS cần các cặp vùng và điều kiện")
            sums = list(flatten([sum_range])); ranges = [list(flatten([items[index]])) for index in range(0, len(items), 2)]
            conditions = items[1::2]
            if any(len(item) != len(sums) for item in ranges):
                raise FormulaError("Các vùng SUMIFS phải cùng kích thước")
            return sum(number(sums[row]) for row in range(len(sums)) if all(criterion(ranges[group][row], conditions[group]) for group in range(len(ranges))))
        def match(lookup_value, lookup_array, match_type=0):
            candidates = list(flatten([lookup_array]))
            if int(number(match_type)) != 0:
                raise FormulaError("MATCH hiện hỗ trợ khớp chính xác (0)")
            for index, value in enumerate(candidates):
                if criterion(value, lookup_value):
                    return index + 1
            raise FormulaError("Không tìm thấy giá trị", "#N/A")
        def index(array, row, column=1):
            row_index, column_index_ = int(number(row)) - 1, int(number(column)) - 1
            matrix = array if isinstance(array, list) and array and isinstance(array[0], list) else [list(flatten([array]))]
            try:
                return matrix[row_index][column_index_]
            except IndexError:
                raise FormulaError("INDEX nằm ngoài vùng") from None
        def vlookup(lookup_value, table, column, exact=True):
            column_index_ = int(number(column)) - 1
            if not isinstance(table, list) or not table or not isinstance(table[0], list):
                raise FormulaError("VLOOKUP cần vùng bảng")
            for row in table:
                if criterion(row[0], lookup_value):
                    try:
                        return row[column_index_]
                    except IndexError:
                        raise FormulaError("Cột VLOOKUP nằm ngoài vùng") from None
            raise FormulaError("Không tìm thấy giá trị", "#N/A")
        def hlookup(lookup_value, table, row, exact=True):
            if not isinstance(table, list) or not table or not isinstance(table[0], list):
                raise FormulaError("HLOOKUP cần vùng bảng")
            row_index = int(number(row)) - 1
            for column, value in enumerate(table[0]):
                if criterion(value, lookup_value):
                    try:
                        return table[row_index][column]
                    except IndexError:
                        raise FormulaError("Hàng HLOOKUP nằm ngoài vùng") from None
            raise FormulaError("Không tìm thấy giá trị", "#N/A")
        def xlookup(lookup_value, lookup_array, return_array, if_not_found=None):
            lookup_values, return_values = list(flatten([lookup_array])), list(flatten([return_array]))
            if len(lookup_values) != len(return_values):
                raise FormulaError("Vùng XLOOKUP phải cùng kích thước")
            for index, value in enumerate(lookup_values):
                if criterion(value, lookup_value):
                    return return_values[index]
            if if_not_found is not None:
                return if_not_found
            raise FormulaError("Không tìm thấy giá trị")
        def choose(index, *items):
            try:
                return items[int(number(index)) - 1]
            except IndexError:
                raise FormulaError("CHOOSE nằm ngoài danh sách") from None
        def textjoin(delimiter, ignore_empty, *items):
            values_ = values(*items)
            if ignore_empty:
                values_ = [value for value in values_ if value not in (None, "")]
            return str(delimiter).join(str(value) for value in values_)
        def switch(value, *items):
            pairs, fallback = items, None
            if len(items) % 2:
                pairs, fallback = items[:-1], items[-1]
            for index in range(0, len(pairs), 2):
                if criterion(value, pairs[index]):
                    return pairs[index + 1]
            if fallback is not None:
                return fallback
            raise FormulaError("SWITCH không có giá trị phù hợp")
        def ifs(*items):
            if len(items) % 2:
                raise FormulaError("IFS cần các cặp điều kiện và kết quả")
            for index in range(0, len(items), 2):
                if items[index]:
                    return items[index + 1]
            raise FormulaError("IFS không có điều kiện đúng")
        def date_value(value):
            try:
                return datetime.fromisoformat(str(value)).date()
            except ValueError:
                raise FormulaError("Ngày không hợp lệ; dùng YYYY-MM-DD") from None
        def days(end_date, start_date): return (date_value(end_date) - date_value(start_date)).days
        def if_(condition, yes, no=False): return yes if condition else no
        def left(value, count=1): return str(value)[:int(number(count))]
        def right(value, count=1): return str(value)[-int(number(count)):]
        def mid(value, start, count): return str(value)[int(number(start)) - 1:int(number(start)) - 1 + int(number(count))]
        def find(needle, haystack, start=1): return str(haystack).find(str(needle), int(number(start)) - 1) + 1
        def today(): return date.today().isoformat()
        return {
            "__CELL": cell, "__RANGE": range_, "SUM": sum_, "AVERAGE": average,
            "MIN": lambda *x: min(number(v) for v in values(*x)), "MAX": lambda *x: max(number(v) for v in values(*x)),
            "COUNT": count, "COUNTA": counta, "COUNTIF": countif, "SUMIF": sumif, "COUNTIFS": countifs, "SUMIFS": sumifs,
            "VLOOKUP": vlookup, "HLOOKUP": hlookup, "INDEX": index, "MATCH": match,
            "XLOOKUP": xlookup, "CHOOSE": choose, "IF": if_, "IFS": ifs, "SWITCH": switch,
            "AND": lambda *x: all(values(*x)), "OR": lambda *x: any(values(*x)), "NOT": lambda x: not x,
            "ROUND": lambda x, digits=0: round(number(x), int(number(digits))), "ROUNDUP": lambda x, digits=0: math.ceil(number(x) * 10 ** int(number(digits))) / 10 ** int(number(digits)),
            "ROUNDDOWN": lambda x, digits=0: math.floor(number(x) * 10 ** int(number(digits))) / 10 ** int(number(digits)),
            "ABS": lambda x: abs(number(x)), "INT": lambda x: math.floor(number(x)), "MOD": lambda x, y: number(x) % number(y), "POWER": lambda x, y: number(x) ** number(y), "SQRT": lambda x: math.sqrt(number(x)),
            "LEN": lambda x: len(str(x)), "LOWER": lambda x: str(x).lower(), "UPPER": lambda x: str(x).upper(), "TRIM": lambda x: " ".join(str(x).split()),
            "CONCATENATE": lambda *x: "".join(str(v) for v in values(*x)), "LEFT": left, "RIGHT": right, "MID": mid,
            "TEXTJOIN": textjoin, "SUBSTITUTE": lambda x, old, new: str(x).replace(str(old), str(new)), "FIND": find,
            "EXACT": lambda x, y: str(x) == str(y), "ISBLANK": lambda x: x in (None, ""), "ISNUMBER": _is_number, "ISTEXT": lambda x: isinstance(x, str) and not _is_number(x),
            "TODAY": today, "YEAR": lambda x: int(str(x)[:4]), "MONTH": lambda x: int(str(x)[5:7]), "DAY": lambda x: int(str(x)[8:10]),
            "DATE": lambda year, month, day: date(int(number(year)), int(number(month)), int(number(day))).isoformat(), "DAYS": days,
        }


def _is_number(value: object) -> bool:
    try:
        number(value)
        return value not in (None, "")
    except FormulaError:
        return False


class _SafeFormula(ast.NodeVisitor):
    def __init__(self, functions: dict[str, Callable]) -> None:
        self.functions = functions

    def visit_Constant(self, node): return node.value
    def visit_List(self, node): return [self.visit(item) for item in node.elts]
    def visit_UnaryOp(self, node):
        value = self.visit(node.operand)
        return -number(value) if isinstance(node.op, ast.USub) else number(value)
    def visit_BinOp(self, node):
        left, right = self.visit(node.left), self.visit(node.right)
        if isinstance(node.op, ast.Add): return left + right if isinstance(left, str) or isinstance(right, str) else number(left) + number(right)
        if isinstance(node.op, ast.Sub): return number(left) - number(right)
        if isinstance(node.op, ast.Mult): return number(left) * number(right)
        if isinstance(node.op, ast.Div):
            divisor = number(right)
            if divisor == 0:
                raise FormulaError("Không thể chia cho 0", "#DIV/0!")
            return number(left) / divisor
        if isinstance(node.op, ast.Pow): return number(left) ** number(right)
        raise FormulaError("Toán tử không được hỗ trợ")
    def visit_Compare(self, node):
        left, right = self.visit(node.left), self.visit(node.comparators[0])
        try:
            left, right = number(left), number(right)
        except FormulaError:
            pass
        return {ast.Eq: left == right, ast.NotEq: left != right, ast.Lt: left < right, ast.Gt: left > right, ast.LtE: left <= right, ast.GtE: left >= right}[type(node.ops[0])]
    def visit_BoolOp(self, node): return all(self.visit(v) for v in node.values) if isinstance(node.op, ast.And) else any(self.visit(v) for v in node.values)
    def visit_Call(self, node):
        if not isinstance(node.func, ast.Name):
                raise FormulaError("Hàm không được hỗ trợ", "#NAME?")
        if node.func.id == "IFERROR":
            if len(node.args) != 2:
                raise FormulaError("IFERROR cần giá trị và giá trị thay thế")
            try:
                return self.visit(node.args[0])
            except FormulaError:
                return self.visit(node.args[1])
        if node.func.id not in self.functions:
            raise FormulaError("Hàm không được hỗ trợ", "#NAME?")
        return self.functions[node.func.id](*(self.visit(arg) for arg in node.args))
    def generic_visit(self, node): raise FormulaError("Biểu thức không được hỗ trợ")
