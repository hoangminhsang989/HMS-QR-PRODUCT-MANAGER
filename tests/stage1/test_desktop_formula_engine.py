import pytest

from packages.excel.desktop_formula_engine import FormulaEngine, FormulaError


def test_desktop_formula_engine_calculates_production_sheet_functions():
    cells = {(0, 0): "10", (1, 0): "20", (0, 1): "A", (1, 1): "B"}
    engine = FormulaEngine(lambda row, column: cells.get((row, column), ""), 10, 10)

    assert engine.evaluate("=SUM(A1:A2)") == 30
    assert engine.evaluate("=AVERAGE(A1:A2)") == 15
    assert engine.evaluate("=COUNTIF(A1:A2,\">15\")") == 1
    assert engine.evaluate("=SUMIF(A1:A2,\">15\")") == 20
    assert engine.evaluate("=IF(A1>5,\"OK\",\"NO\")") == "OK"
    assert engine.evaluate("=A1*A2+5") == 205
    assert engine.evaluate("=CONCATENATE(B1,\"-\",B2)") == "A-B"


def test_desktop_formula_engine_calculates_lookup_and_multi_criteria_functions():
    cells = {
        (0, 0): "P-01", (0, 1): "Gia cong", (0, 2): "10",
        (1, 0): "P-02", (1, 1): "Gia cong", (1, 2): "20",
        (2, 0): "P-03", (2, 1): "Lap rap", (2, 2): "30",
        (0, 4): "P-01", (0, 5): "P-02", (0, 6): "P-03",
        (1, 4): "10", (1, 5): "20", (1, 6): "30",
    }
    engine = FormulaEngine(lambda row, column: cells.get((row, column), ""), 10, 10)

    assert engine.evaluate("=VLOOKUP(\"P-02\",A1:C3,3,0)") == "20"
    assert engine.evaluate("=HLOOKUP(\"P-02\",E1:G2,2,0)") == "20"
    assert engine.evaluate("=INDEX(A1:C3,2,2)") == "Gia cong"
    assert engine.evaluate("=MATCH(\"P-03\",A1:A3,0)") == 3
    assert engine.evaluate("=COUNTIFS(B1:B3,\"Gia cong\",C1:C3,\">10\")") == 1
    assert engine.evaluate("=SUMIFS(C1:C3,B1:B3,\"Gia cong\",C1:C3,\">10\")") == 20
    assert engine.evaluate("=IFERROR(VLOOKUP(\"MISSING\",A1:C3,2,0),\"Không có\")") == "Không có"
    assert engine.evaluate("=XLOOKUP(\"P-03\",A1:A3,C1:C3,\"Không có\")") == "30"
    assert engine.evaluate("=XLOOKUP(\"MISSING\",A1:A3,C1:C3,\"Không có\")") == "Không có"


def test_desktop_formula_engine_calculates_modern_logic_text_and_date_functions():
    engine = FormulaEngine(lambda _row, _column: "", 10, 10)

    assert engine.evaluate("=IFS(1>2,\"Sai\",2>1,\"Đúng\")") == "Đúng"
    assert engine.evaluate("=SWITCH(\"QC\",\"SX\",\"Sản xuất\",\"QC\",\"Kiểm tra\",\"Khác\")") == "Kiểm tra"
    assert engine.evaluate("=TEXTJOIN(\"-\",TRUE,\"HMS\",\"\",\"QR\")") == "HMS-QR"
    assert engine.evaluate("=DAYS(\"2026-01-15\",\"2026-01-10\")") == 5


@pytest.mark.parametrize(("formula", "code"), [
    ("=1/0", "#DIV/0!"),
    ("=SUM(\"text\", 1)", "#VALUE!"),
    ("=UNKNOWN(A1)", "#NAME?"),
    ("=Z99", "#REF!"),
    ("=MATCH(\"missing\", A1:A1, 0)", "#N/A"),
])
def test_desktop_formula_engine_returns_excel_error_codes(formula, code):
    engine = FormulaEngine(lambda _row, _column: "present", 2, 2)

    with pytest.raises(FormulaError) as error:
        engine.evaluate(formula)

    assert error.value.code == code
