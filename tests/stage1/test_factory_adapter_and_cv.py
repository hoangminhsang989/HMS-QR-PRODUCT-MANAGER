"""Tests for factory_adapter TSV parsing and decode_qr_image fallback."""
from __future__ import annotations
import io

import pytest

from packages.excel.factory_adapter import parse_factory_tsv


# ---------------------------------------------------------------------------
# parse_factory_tsv tests
# ---------------------------------------------------------------------------

SIMPLE_TSV = (
    "Company\tPart Name\tQuantity\tUnit\tMaterial\tSurface treatment\tSize\tPrice\n"
    "CIT\tTRỤC DẪN HƯỚNG D30\t15\tEA\tS45C\tMạ Crom\tD30x450mm\t320000\n"
    "QCM\tBẠC TRƯỢT\t40\tPCS\tĐồng Thau\t—\tID20xOD32\t140000\n"
)

VIETNAMESE_HEADER_TSV = (
    "Khách hàng\tTên chi tiết\tSố lượng\tĐVT\tVật liệu\n"
    "SHL\tĐẾ GÁ BƠM\t5\tEA\tA6061\n"
    "CIT\tNẮP HỘP GEAR\t12\tEA\tGray Iron\n"
)

MINIMAL_TSV = "CIT\tTEST ITEM\t10\tEA\n"


def test_parse_tsv_simple_english_headers():
    items = parse_factory_tsv(SIMPLE_TSV)
    assert len(items) == 2
    assert items[0]["company"] == "CIT"
    assert items[0]["part_name"] == "TRỤC DẪN HƯỚNG D30"
    assert items[0]["quantity"] == 15.0
    assert items[0]["unit"] == "EA"
    assert items[0]["material"] == "S45C"
    assert items[0]["price"] == 320000.0
    assert items[1]["company"] == "QCM"
    assert items[1]["quantity"] == 40.0


def test_parse_tsv_vietnamese_headers():
    items = parse_factory_tsv(VIETNAMESE_HEADER_TSV)
    assert len(items) == 2
    assert items[0]["company"] == "SHL"
    assert items[0]["part_name"] == "ĐẾ GÁ BƠM"
    assert items[0]["quantity"] == 5.0
    assert items[0]["unit"] == "EA"
    assert items[0]["material"] == "A6061"


def test_parse_tsv_returns_empty_for_empty_input():
    assert parse_factory_tsv("") == []
    assert parse_factory_tsv("   \n  ") == []


def test_parse_tsv_skips_zero_quantity_rows():
    tsv = "Company\tPart Name\tQuantity\tUnit\nCIT\tPHÔI THÉP\t0\tEA\n"
    assert parse_factory_tsv(tsv) == []


def test_parse_tsv_skips_negative_quantity_rows():
    tsv = "Company\tPart Name\tQuantity\tUnit\nCIT\tPHÔI THÉP\t-5\tEA\n"
    assert parse_factory_tsv(tsv) == []


def test_parse_tsv_handles_comma_thousands_in_quantity():
    tsv = "Company\tPart Name\tQuantity\tUnit\nCIT\tITEM A\t1,000\tPCS\n"
    items = parse_factory_tsv(tsv)
    assert len(items) == 1
    assert items[0]["quantity"] == 1000.0


def test_parse_tsv_sheet_name_is_clipboard_paste():
    items = parse_factory_tsv(SIMPLE_TSV)
    assert all(it["sheet_name"] == "CLIPBOARD_PASTE" for it in items)


def test_parse_tsv_row_index_is_positive():
    items = parse_factory_tsv(SIMPLE_TSV)
    assert all(it["row_index"] > 0 for it in items)


def test_parse_tsv_multiple_rows_distinct_row_indices():
    items = parse_factory_tsv(SIMPLE_TSV)
    indices = [it["row_index"] for it in items]
    assert len(set(indices)) == len(indices)


# ---------------------------------------------------------------------------
# decode_qr_image tests (with OpenCV available)
# ---------------------------------------------------------------------------

def test_decode_qr_image_empty_bytes_returns_failure():
    from packages.qr.cv_scanner import decode_qr_image
    result = decode_qr_image(b"")
    assert result["success"] is False
    assert "error" in result


def test_decode_qr_image_invalid_bytes_returns_failure():
    from packages.qr.cv_scanner import decode_qr_image
    result = decode_qr_image(b"not an image at all 12345")
    assert result["success"] is False
    assert "error" in result


def test_decode_qr_image_real_qr_succeeds():
    """Generate a real QR PNG and decode it back."""
    import qrcode
    from packages.qr.cv_scanner import decode_qr_image, _OPENCV_AVAILABLE
    if not _OPENCV_AVAILABLE:
        pytest.skip("OpenCV not installed")
    payload = "HMS-QR-TEST-ITEM-2026-000001"
    buf = io.BytesIO()
    qrcode.make(payload).save(buf, format="PNG")
    result = decode_qr_image(buf.getvalue())
    assert result["success"] is True
    assert result["payload"] == payload
    assert "method" in result


def test_decode_qr_image_no_opencv_returns_graceful_error(monkeypatch):
    """If cv2 is unavailable, the function should return success=False with a clear message."""
    import packages.qr.cv_scanner as mod
    monkeypatch.setattr(mod, "_OPENCV_AVAILABLE", False)
    result = mod.decode_qr_image(b"anything")
    assert result["success"] is False
    assert "OpenCV" in result["error"] or "opencv" in result["error"].lower()
