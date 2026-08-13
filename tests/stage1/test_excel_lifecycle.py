from pathlib import Path

from openpyxl import Workbook

from packages.excel.product_excel import ProductExcelImporter


def _write_workbook(path: Path, *, invalid: bool = False) -> None:
    workbook = Workbook()
    try:
        sheet = workbook.active
        sheet.append(["Product Code", "Company", "Part Name", "Quantity", "Unit"])
        sheet.append(["SP-LIFE-001", "HMS", "Plate", 0 if invalid else 1, "pcs"])
        workbook.save(path)
    finally:
        workbook.close()


def test_preview_releases_file_for_immediate_delete(tmp_path):
    source = tmp_path / "preview.xlsx"
    _write_workbook(source)
    preview = ProductExcelImporter().preview(source)
    assert preview.valid_rows == 1
    source.unlink()
    assert not source.exists()


def test_preview_error_path_releases_file_for_immediate_delete(tmp_path):
    source = tmp_path / "error.xlsx"
    _write_workbook(source, invalid=True)
    preview = ProductExcelImporter().preview(source)
    assert preview.invalid_rows == 1
    source.unlink()
    assert not source.exists()


def test_repeated_preview_has_no_accumulated_handle_leak(tmp_path):
    source = tmp_path / "repeated.xlsx"
    _write_workbook(source)
    importer = ProductExcelImporter()
    for _ in range(3):
        assert importer.preview(source).valid_rows == 1
    source.unlink()
    assert not source.exists()
