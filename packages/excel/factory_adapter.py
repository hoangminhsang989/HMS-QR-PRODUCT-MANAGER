"""Adapter for reading and importing real factory workbooks from D:\\DU-LIEU."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import glob
import os
from pathlib import Path
from typing import Any
import uuid

from openpyxl import load_workbook
import xlrd

from packages.domain.product import ProductStatus
from packages.qr.payload import QrPayload, QrPayloadService

FACTORY_EXCEL_ROOT = r"D:\DU-LIEU"


def list_factory_files(directory: str = FACTORY_EXCEL_ROOT) -> list[dict[str, Any]]:
    if not os.path.isdir(directory):
        return []
    result = []
    for path in sorted(glob.glob(os.path.join(directory, "*.*"))):
        ext = os.path.splitext(path)[1].lower()
        if ext not in {".xlsx", ".xls", ".xlsm"}:
            continue
        fname = os.path.basename(path)
        size = os.path.getsize(path)
        sheets: list[str] = []
        try:
            wb = load_workbook(path, read_only=True, data_only=True)
            sheets = list(wb.sheetnames)
            wb.close()
        except Exception:
            try:
                xwb = xlrd.open_workbook(path)
                sheets = list(xwb.sheet_names())
            except Exception:
                pass
        result.append({
            "filename": fname,
            "path": path,
            "size_bytes": size,
            "sheets_count": len(sheets),
            "sheets": sheets,
        })
    return result


def _normalize(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip().casefold().replace(" ", "").replace("_", "").replace("-", "")


def parse_factory_sheet(file_path: str, sheet_name: str | None = None) -> list[dict[str, Any]]:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Tệp không tồn tại: {file_path}")

    # Try openpyxl first
    try:
        wb = load_workbook(path, read_only=True, data_only=True)
        sname = sheet_name or wb.sheetnames[0]
        if sname not in wb.sheetnames:
            sname = wb.sheetnames[0]
        sheet = wb[sname]
        raw_rows = [list(r) for r in sheet.iter_rows(values_only=True)]
        wb.close()
        return _extract_from_rows(raw_rows, sheet_name=sname)
    except Exception:
        # Fallback to xlrd for genuine xls
        xwb = xlrd.open_workbook(str(path))
        sname = sheet_name or xwb.sheet_names()[0]
        if sname not in xwb.sheet_names():
            sname = xwb.sheet_names()[0]
        sheet = xwb.sheet_by_name(sname)
        raw_rows = [sheet.row_values(i) for i in range(sheet.nrows)]
        return _extract_from_rows(raw_rows, sheet_name=sname)


def parse_factory_tsv(tsv_text: str) -> list[dict[str, Any]]:
    """Parse clipboard text (Tab-separated values) directly copied from Excel."""
    import csv
    from io import StringIO

    lines = [line for line in (tsv_text or "").strip().splitlines() if line.strip()]
    if not lines:
        return []
    reader = csv.reader(StringIO("\n".join(lines)), delimiter="\t")
    raw_rows = list(reader)
    if not raw_rows:
        return []
    return _extract_from_rows(raw_rows, sheet_name="CLIPBOARD_PASTE")


def _extract_from_rows(rows: list[list[Any]], sheet_name: str = "") -> list[dict[str, Any]]:
    if not rows:
        return []

    # 1. Detect header row
    header_idx = -1
    col_map: dict[str, int] = {}

    for idx, row in enumerate(rows[:20]):
        norm_cells = [_normalize(c) for c in row]
        has_name = any(any(k in c for k in ("part", "tên", "ten", "description", "mã", "ma", "hànghóa", "hanghoa", "chitiet", "chitiết", "tenchitiet", "tenchi")) for c in norm_cells)
        has_qty = any(any(k in c for k in ("qty", "quantity", "sốlượng", "soluong", "sl")) for c in norm_cells)
        has_comp = any(any(k in c for k in ("company", "khách", "khach", "khachhang", "đơnvị", "donvi")) for c in norm_cells)
        if (has_name and has_qty) or (has_comp and has_name) or (has_comp and has_qty):
            header_idx = idx
            break

    if header_idx == -1:
        if sheet_name == "CLIPBOARD_PASTE":
            # For pasted text, if no header keywords found, assume row 0 is data
            header_idx = -1
        else:
            header_idx = 5 if len(rows) > 5 else 0

    if header_idx != -1:
        header = rows[header_idx]
        for c_idx, val in enumerate(header):
            n = _normalize(val)
            if not n:
                continue
            if "company" in n or "khách" in n or "khach" in n or "khachhang" in n or ("đơnvị" in n and "tính" not in n) or ("donvi" in n and "tinh" not in n):
                col_map.setdefault("company", c_idx)
            elif "partname" in n or "tênhàng" in n or "tênchi" in n or "tenchi" in n or "description" in n or "tên" in n or "ten" in n or "hànghóa" in n or "hanghoa" in n or "mặthàng" in n or "mathang" in n or "diễngiải" in n or "diengiai" in n or "chitiết" in n or "chitiet" in n or "hanghoà" in n:
                col_map.setdefault("part_name", c_idx)
            elif "quantity" in n or "qty" in n or "sốlượng" in n or "soluong" in n or n == "sl":
                col_map.setdefault("quantity", c_idx)
            elif "unit" in n or "đơnvịtính" in n or "donvitinh" in n or "đơnvị" in n or "donvi" in n or n == "dvt" or n == "đvt":
                col_map.setdefault("unit", c_idx)
            elif "price" in n or "đơngiá" in n or "dongia" in n or "giá" in n or "gia" in n:
                col_map.setdefault("price", c_idx)
            elif "material" in n or "vậtliệu" in n or "vatlieu" in n:
                col_map.setdefault("material", c_idx)
            elif "ngườiđặt" in n or "requester" in n or "nguoidat" in n:
                col_map.setdefault("requester", c_idx)
            elif "surfacetreatment" in n or "xửlý" in n or "xuly" in n or "sửlý" in n or "bềmặt" in n or "bemat" in n or "xulybemat" in n:
                col_map.setdefault("surface_treatment", c_idx)
            elif "đặtngoài" in n or "outsourced" in n or "datngoai" in n:
                col_map.setdefault("outsourced", c_idx)
            elif "size" in n or "kíchthước" in n or "kichthuoc" in n or "quycách" in n or "quycach" in n or "thôngsố" in n or "thongso" in n:
                col_map.setdefault("size", c_idx)
            elif "ghichú" in n or "ghichu" in n or "remark" in n or "notes" in n or "note" in n:
                col_map.setdefault("notes", c_idx)
            elif "lịch" in n or "lich" in n or "giaohàng" in n or "giaohang" in n or "deliveryschedule" in n or "ngàygiao" in n or "ngaygiao" in n or "hạngiao" in n or "hangiao" in n:
                col_map.setdefault("delivery_schedule", c_idx)
        start_row = header_idx + 1
    else:
        # Defaults for raw data without headers
        start_row = 0
        if len(rows[0]) >= 4:
            col_map = {
                "company": 0,
                "part_name": 2 if len(rows[0]) > 2 else 1,
                "quantity": 3 if len(rows[0]) > 3 else 2,
                "unit": 4 if len(rows[0]) > 4 else 3,
                "material": 7 if len(rows[0]) > 7 else None,
            }
        else:
            col_map = {"part_name": 0, "quantity": 1}

    # Defaults for standard List Hàng Tháng if columns weren't explicitly labelled
    col_map.setdefault("company", 0)
    col_map.setdefault("part_name", 2 if len(rows[0]) > 2 else 0)
    col_map.setdefault("quantity", 3 if len(rows[0]) > 3 else 1)
    col_map.setdefault("unit", 4 if len(rows[0]) > 4 else None)
    col_map.setdefault("price", 5 if len(rows[0]) > 5 else None)
    col_map.setdefault("material", 7 if len(rows[0]) > 7 else None)
    col_map.setdefault("requester", 8 if len(rows[0]) > 8 else None)
    col_map.setdefault("surface_treatment", 9 if len(rows[0]) > 9 else None)
    col_map.setdefault("outsourced", 11 if len(rows[0]) > 11 else None)

    items: list[dict[str, Any]] = []
    for r_idx in range(start_row, len(rows)):
        row = rows[r_idx]
        if not row:
            continue

        def get_val(key: str) -> Any:
            c = col_map.get(key)
            if c is not None and c < len(row):
                return row[c]
            return None

        comp = str(get_val("company") or "").strip()
        part = str(get_val("part_name") or "").strip()
        raw_qty = get_val("quantity")

        if not part and not comp:
            continue
        if raw_qty is None or str(raw_qty).strip() == "":
            continue

        try:
            cleaned_qty = str(raw_qty).replace(",", "").strip()
            qty = Decimal(cleaned_qty)
            if qty <= 0:
                continue
        except (InvalidOperation, ValueError, TypeError):
            continue

        unit = str(get_val("unit") or "EA").strip()
        price_raw = get_val("price")
        price = None
        if price_raw is not None:
            try:
                price = float(str(price_raw).replace(",", "").strip())
            except Exception:
                pass

        mat = str(get_val("material") or "").strip()
        req = str(get_val("requester") or "").strip()
        surf = str(get_val("surface_treatment") or "").strip()
        outsource_val = str(get_val("outsourced") or "").strip()
        is_outsourced = bool(outsource_val and outsource_val.lower() not in {"0", "false", "no", ""})

        # Monthly lists use a merged "Size" header across three columns (X/Y/Z).
        # Preserve every component, including values such as "Ø", rather than only
        # keeping the first cell under the merged header.
        size_column = col_map.get("size")
        size_parts = []
        if size_column is not None:
            size_parts = [
                str(row[column]).strip()
                for column in range(size_column, min(size_column + 3, len(row)))
                if row[column] is not None and str(row[column]).strip()
            ]
        size_str = " x ".join(size_parts)

        notes = str(get_val("notes") or "").strip()
        deliv = str(get_val("delivery_schedule") or "").strip()

        items.append({
            "row_index": r_idx + 1,
            "company": comp or "SHL",
            "part_name": part or f"Item-{r_idx+1}",
            "quantity": qty,
            "unit": unit or "EA",
            "price": price,
            "material": mat,
            "requester": req,
            "surface_treatment": surf,
            "outsourced": is_outsourced,
            "size": size_str,
            "notes": notes,
            "delivery_schedule": deliv,
            "sheet_name": sheet_name,
        })

    return items


def import_factory_items_to_db(
    items: list[dict[str, Any]],
    db_path: str,
    *,
    po_prefix: str = "PO-2609",
    actor: str = "admin",
) -> dict[str, Any]:
    """Import parsed factory items into products, orders, tracking items, and issue QR codes.

    ``db_path`` is the configured SQLite address; the engine keeps its data in the
    sibling ``<name>-engine`` directory, which is what this writes to. The whole
    import runs in one engine transaction, so a failure part-way leaves no
    half-imported sheet behind.
    """
    from packages.persistence.database import engine_path
    from packages.sqlengine import connect

    database = connect(engine_path(f"sqlite:///{Path(db_path).as_posix()}"))

    now_iso = datetime.now(timezone.utc).isoformat()
    today_iso = date.today().isoformat()
    qr_payload_svc = QrPayloadService()

    imported_products = 0
    imported_tracking = 0

    with database.transaction() as transaction:
        # Load existing customer map by code and name
        cust_rows = transaction.execute("SELECT internal_id, customer_code, name FROM customers")
        cust_map = {str(r["name"]).strip().upper(): r["internal_id"] for r in cust_rows}
        cust_code_map = {str(r["customer_code"]).strip().upper(): r["internal_id"] for r in cust_rows}

        # Load existing product codes
        prod_codes = {
            str(r["product_code"]).strip().upper()
            for r in transaction.execute("SELECT product_code FROM products")
        }

        # Next tracking item sequence
        seq_counter = int(transaction.execute("SELECT COUNT(*) FROM order_tracking_items")[0]["count"]) + 1

        for idx, item in enumerate(items, start=1):
            comp_name = item["company"].strip().upper() or "SHL"
            # 1. Resolve or create Customer
            cust_id = cust_map.get(comp_name) or cust_code_map.get(comp_name)
            if not cust_id:
                cust_id = str(uuid.uuid4())
                cust_code = f"CUS-{comp_name[:10]}"
                transaction.execute("""
                    INSERT INTO customers (
                        internal_id, customer_code, name, short_name, address, tax_code,
                        contact_name, phone, email, notes, active, created_at, updated_at, created_by, updated_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """, [cust_id, cust_code, comp_name, comp_name, "", "", "", "", "", "Khách hàng từ Excel", now_iso, now_iso, actor, actor])
                cust_map[comp_name] = cust_id

            # 2. Product code generation
            # Use part name if clean alphanumeric, else SP-2609-XXXX
            raw_code = f"SP-{item.get('sheet_name', 'DAY')[:5]}-{idx:03d}".replace(" ", "").upper()
            if raw_code in prod_codes:
                raw_code = f"SP-{uuid.uuid4().hex[:8].upper()}"
            prod_codes.add(raw_code)

            prod_id = str(uuid.uuid4())
            qty = Decimal(str(item["quantity"]))
            transaction.execute("""
                INSERT INTO products (
                    internal_id, product_code, company, part_name, quantity, unit,
                    material, requester, surface_treatment, outsourced, size, notes,
                    delivery_schedule, status, created_at, updated_at, created_by, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'IN_PROGRESS', ?, ?, ?, ?)
            """, [
                prod_id, raw_code, comp_name, item["part_name"], str(qty), item["unit"],
                item["material"], item["requester"], item["surface_treatment"], int(item["outsourced"]),
                item["size"], item["notes"], today_iso, now_iso, now_iso, actor, actor
            ])
            imported_products += 1

            # 3. Create PO & PO Line
            po_id = str(uuid.uuid4())
            po_num = f"{po_prefix}-{idx:04d}"
            ord_num = f"ORD-{po_prefix}-{idx:04d}"
            transaction.execute("""
                INSERT INTO purchase_orders (
                    internal_id, po_number, internal_order_code, customer_id, po_date,
                    requested_delivery_date, status, notes, created_at, updated_at, created_by, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, 'CONFIRMED', ?, ?, ?, ?, ?)
            """, [po_id, po_num, ord_num, cust_id, today_iso, today_iso, f"Import từ sheet {item.get('sheet_name', '')}", now_iso, now_iso, actor, actor])

            line_id = str(uuid.uuid4())
            transaction.execute("""
                INSERT INTO purchase_order_lines (
                    internal_id, po_id, product_id, line_number, ordered_quantity, unit,
                    unit_price, currency, customer_part_reference, notes
                ) VALUES (?, ?, ?, 1, ?, ?, ?, 'VND', ?, ?)
            """, [line_id, po_id, prod_id, str(qty), item["unit"], item.get("price"), item["part_name"], item["notes"]])

            # 4. Order Tracking Item & QR issuance
            tracking_id = str(uuid.uuid4())
            current_year = datetime.now().year
            tracking_code = f"ITEM-{current_year}-{seq_counter:06d}"
            seq_counter += 1
            qr_pub_id = "qr_" + uuid.uuid4().hex[:16]

            transaction.execute("""
                INSERT INTO order_tracking_items (
                    internal_id, tracking_code, purchase_order_id, purchase_order_line_id,
                    product_id, customer_id, quantity, unit, delivery_date, status,
                    qr_public_id, qr_status, created_at, updated_at, created_by, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'IN_PRODUCTION', ?, 'ACTIVE', ?, ?, ?, ?)
            """, [tracking_id, tracking_code, po_id, line_id, prod_id, cust_id, str(qty), item["unit"], today_iso, qr_pub_id, now_iso, now_iso, actor, actor])

            # 5. Tracking Audit event
            transaction.execute("""
                INSERT INTO tracking_audit_events (
                    internal_id, tracking_item_id, event_type, old_value, new_value, actor, reason, server_timestamp
                ) VALUES (?, ?, 'QR_ISSUED', NULL, ?, ?, 'Import từ Excel xưởng', ?)
            """, [str(uuid.uuid4()), tracking_id, qr_pub_id, actor, now_iso])

            imported_tracking += 1

    return {
        "success": True,
        "imported_products": imported_products,
        "imported_tracking_items": imported_tracking,
    }
