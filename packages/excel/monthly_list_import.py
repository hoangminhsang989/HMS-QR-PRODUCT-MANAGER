"""Import dated factory monthly lists and their row-anchored product images."""

from __future__ import annotations

import hashlib
import re
import sqlite3
import unicodedata
from datetime import date
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from openpyxl import load_workbook

from packages.application.product_service import ProductService
from packages.domain.product import ProductStatus
from packages.excel.factory_adapter import _extract_from_rows
from packages.persistence.database import create_database_runtime
from packages.persistence.managed_file_repository import ManagedFileRepository
from packages.persistence.sqlalchemy_product_repository import SqlAlchemyProductRepository
from packages.persistence.sqlalchemy_repository import Stage2Repository
from packages.persistence import tracking_models as _tracking_models
from packages.storage.managed_files import ManagedFileService
from packages.storage.service import FilesystemStorage


_SHEET_DATE = re.compile(r"^(\d{1,2})-(\d{1,2})$")
_MONTHLY_FILE = re.compile(r"^LIST H.+?-(\d{2})-(\d{2})\.xlsx$", re.IGNORECASE)


def _source_date(workbook_name: str, sheet_name: str) -> date:
    file_match = _MONTHLY_FILE.match(workbook_name)
    sheet_match = _SHEET_DATE.match(sheet_name.strip())
    if not file_match or not sheet_match:
        raise ValueError(f"Không nhận diện được ngày nguồn: {workbook_name} / {sheet_name}")
    month, year = map(int, file_match.groups())
    day, sheet_month = map(int, sheet_match.groups())
    if month != sheet_month:
        raise ValueError(f"Tháng của sheet không khớp workbook: {workbook_name} / {sheet_name}")
    return date(2000 + year, month, day)


def discover_monthly_list_files(root: Path) -> list[Path]:
    """Return every supported monthly list in a source folder, excluding Excel locks."""
    return sorted(
        path for path in Path(root).glob("LIST HÀNG THÁNG -??-??.xlsx")
        if not path.name.startswith("~$") and _MONTHLY_FILE.match(path.name)
    )


def _row_images(sheet) -> dict[int, list[bytes]]:
    images: dict[int, list[bytes]] = {}
    for image in sheet._images:
        anchor = getattr(image.anchor, "_from", None)
        if anchor is None or anchor.col != 1 or anchor.row < 6:
            continue
        try:
            content = image._data()
        except Exception:
            continue
        if content:
            images.setdefault(anchor.row + 1, []).append(content)
    return images


def _ensure_manifest(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS excel_monthly_import_rows (
                source_file TEXT NOT NULL,
                source_sheet TEXT NOT NULL,
                source_row INTEGER NOT NULL,
                product_id TEXT NOT NULL,
                image_sha256 TEXT,
                PRIMARY KEY (source_file, source_sheet, source_row)
            )"""
        )


def sync_product_tracking(database_path: Path, *, actor: str = "excel-import") -> dict[str, int]:
    """Give every imported product one stable order-tracking item and active QR."""
    created = 0
    runtime = create_database_runtime_for_shared_sqlite(database_path)
    Stage2Repository(runtime).create_schema()
    runtime.dispose()
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """SELECT p.internal_id, p.product_code, p.company, p.quantity, p.unit, p.delivery_schedule
               FROM products p
               LEFT JOIN order_tracking_items t ON t.product_id = p.internal_id
               WHERE t.internal_id IS NULL AND p.delivery_schedule IS NOT NULL
               ORDER BY p.delivery_schedule, p.product_code"""
        ).fetchall()
        sequence = connection.execute("SELECT COUNT(1) FROM order_tracking_items").fetchone()[0]
        for product_id, product_code, company, quantity, unit, delivery_date in rows:
            customer = connection.execute(
                "SELECT internal_id FROM customers WHERE name = ?", (company,)
            ).fetchone()
            if customer:
                customer_id = customer[0]
            else:
                customer_id = str(uuid4())
                customer_code = f"XLS-{hashlib.sha1(company.encode()).hexdigest()[:12].upper()}"
                connection.execute(
                    """INSERT INTO customers (internal_id, customer_code, name, active, created_at, updated_at, created_by, updated_by)
                       VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?)""",
                    (customer_id, customer_code, company, actor, actor),
                )
            po_id, line_id, tracking_id = str(uuid4()), str(uuid4()), str(uuid4())
            sequence += 1
            # A PO row remains as the tracking relation, but its user-facing
            # identifier is the product code rather than a separate XLS code.
            po_number = product_code
            connection.execute(
                """INSERT INTO purchase_orders (internal_id, po_number, internal_order_code, customer_id, po_date,
                   requested_delivery_date, status, notes, created_at, updated_at, created_by, updated_by)
                   VALUES (?, ?, ?, ?, ?, ?, 'CONFIRMED', 'Tự tạo từ Excel monthly list', CURRENT_TIMESTAMP,
                   CURRENT_TIMESTAMP, ?, ?)""",
                (po_id, po_number, product_code, customer_id, delivery_date, delivery_date, actor, actor),
            )
            connection.execute(
                """INSERT INTO purchase_order_lines (internal_id, po_id, product_id, line_number, ordered_quantity, unit)
                   VALUES (?, ?, ?, 1, ?, ?)""",
                (line_id, po_id, product_id, quantity, unit),
            )
            qr_public_id = f"qr_{uuid4().hex}"
            connection.execute(
                """INSERT INTO order_tracking_items (internal_id, tracking_code, purchase_order_id, purchase_order_line_id,
                   product_id, customer_id, quantity, unit, delivery_date, status, qr_public_id, qr_status, created_at,
                   updated_at, created_by, updated_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'NEW', ?, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?)""",
                (tracking_id, f"ITEM-2026-{sequence:06d}", po_id, line_id, product_id, customer_id, quantity, unit,
                 delivery_date, qr_public_id, actor, actor),
            )
            connection.execute(
                """INSERT INTO tracking_audit_events (internal_id, tracking_item_id, event_type, new_value, actor, reason,
                   server_timestamp) VALUES (?, ?, 'QR_ISSUED', ?, ?, 'Tự tạo từ Excel monthly list', CURRENT_TIMESTAMP)""",
                (str(uuid4()), tracking_id, qr_public_id, actor),
            )
            created += 1
    return {"tracking_created": created}


def import_monthly_lists(
    excel_paths: Iterable[Path], *, database_path: Path, storage_root: Path, actor: str = "excel-import"
) -> dict[str, int]:
    """Import three 2026 monthly lists idempotently, matching pictures by Excel row."""
    database_path = Path(database_path)
    storage_root = Path(storage_root)
    runtime = create_database_runtime_for_shared_sqlite(database_path)
    Stage2Repository(runtime).create_schema()
    service = ProductService(SqlAlchemyProductRepository(runtime))
    storage_root.mkdir(parents=True, exist_ok=True)
    files = ManagedFileService(
        ManagedFileRepository(runtime), FilesystemStorage(storage_root, create_root=False)
    )
    _ensure_manifest(database_path)
    totals = {"products_created": 0, "products_existing": 0, "images_imported": 0, "images_skipped": 0, "rows_skipped": 0}

    for path in excel_paths:
        workbook = load_workbook(path, data_only=True)
        try:
            for sheet in workbook.worksheets:
                try:
                    scheduled = _source_date(path.name, sheet.title)
                except ValueError:
                    totals["rows_skipped"] += 1
                    continue
                images = _row_images(sheet)
                rows = [list(row) for row in sheet.iter_rows(values_only=True)]
                for item in _extract_from_rows(rows, sheet_name=sheet.title):
                    source_row = int(item["row_index"])
                    with sqlite3.connect(database_path) as connection:
                        existing = connection.execute(
                            "SELECT product_id, image_sha256 FROM excel_monthly_import_rows "
                            "WHERE source_file = ? AND source_sheet = ? AND source_row = ?",
                            (path.name, sheet.title, source_row),
                        ).fetchone()
                    if existing:
                        product_id, prior_image_sha = existing
                        # Reconcile every source-controlled field on re-import so a
                        # corrected workbook updates both the product and its tracking.
                        with sqlite3.connect(database_path) as connection:
                            connection.execute(
                                """UPDATE products SET company = ?, part_name = ?, quantity = ?, unit = ?, material = ?, requester = ?,
                                   surface_treatment = ?, outsourced = ?, size = ?, notes = ?, delivery_schedule = ?,
                                   updated_at = CURRENT_TIMESTAMP, updated_by = ? WHERE internal_id = ?""",
                                (item["company"], item["part_name"], str(item["quantity"]), item["unit"],
                                 item["material"] or None, item["requester"] or None, item["surface_treatment"] or None,
                                 int(bool(item["outsourced"])), item["size"] or None, item["notes"] or None,
                                 scheduled.isoformat(), actor, product_id),
                            )
                            connection.execute(
                                "UPDATE order_tracking_items SET quantity = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ? WHERE product_id = ?",
                                (str(item["quantity"]), actor, product_id),
                            )
                            connection.execute(
                                "UPDATE purchase_order_lines SET ordered_quantity = ? WHERE product_id = ?",
                                (str(item["quantity"]), product_id),
                            )
                        totals["products_existing"] += 1
                    else:
                        product = service.create_product(
                            actor=actor,
                            company=item["company"],
                            part_name=item["part_name"],
                            quantity=item["quantity"],
                            unit=item["unit"],
                            material=item["material"] or None,
                            requester=item["requester"] or None,
                            surface_treatment=item["surface_treatment"] or None,
                            outsourced=bool(item["outsourced"]),
                            size=item["size"] or None,
                            notes=item["notes"] or None,
                            delivery_schedule=scheduled,
                            status=ProductStatus.NEW,
                        )
                        product_id, prior_image_sha = str(product.internal_id), None
                        with sqlite3.connect(database_path) as connection:
                            connection.execute(
                                "INSERT INTO excel_monthly_import_rows "
                                "(source_file, source_sheet, source_row, product_id) VALUES (?, ?, ?, ?)",
                                (path.name, sheet.title, source_row, product_id),
                            )
                        totals["products_created"] += 1

                    row_images = images.get(source_row, [])
                    if not row_images:
                        continue
                    content = row_images[0]
                    digest = hashlib.sha256(content).hexdigest()
                    if prior_image_sha == digest:
                        totals["images_skipped"] += 1
                        continue
                    files.upload_product_image(
                        product_id=__import__("uuid").UUID(product_id),
                        original_filename=f"{path.stem}-{sheet.title}-row-{source_row}.png",
                        declared_mime="image/png",
                        content=content,
                        actor=actor,
                        make_primary=True,
                    )
                    with sqlite3.connect(database_path) as connection:
                        connection.execute(
                            "UPDATE excel_monthly_import_rows SET image_sha256 = ? "
                            "WHERE source_file = ? AND source_sheet = ? AND source_row = ?",
                            (digest, path.name, sheet.title, source_row),
                        )
                    totals["images_imported"] += 1
        finally:
            workbook.close()
    runtime.dispose()
    tracking_totals = sync_product_tracking(database_path, actor=actor)
    return totals | tracking_totals | {"product_codes_repaired": repair_imported_product_codes(database_path)}


def repair_imported_product_codes(database_path: Path) -> int:
    """Rebuild Excel product codes from customer, product, delivery date, and source row."""
    database_path = Path(database_path)

    def initials(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value).replace("Đ", "D").replace("đ", "d")
        words = re.findall(r"[A-Z0-9]+", normalized.encode("ascii", "ignore").decode("ascii").upper())
        return "".join(word[0] for word in words) or "NO"

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """SELECT m.product_id, m.source_row, p.product_code, p.company, p.part_name, p.delivery_schedule
               FROM excel_monthly_import_rows m
               JOIN products p ON p.internal_id = m.product_id
               ORDER BY p.delivery_schedule, m.source_file, m.source_sheet, m.source_row"""
        ).fetchall()
        replacements: list[tuple[str, str, str]] = []
        for product_id, source_row, current_code, company, part_name, delivery_schedule in rows:
            delivery_date = date.fromisoformat(delivery_schedule)
            expected_code = f"{initials(company)}-{initials(part_name)}-{delivery_date:%y%m%d}-R{source_row:03d}"
            if current_code != expected_code:
                replacements.append((product_id, current_code, expected_code))
        duplicate_codes = {code for _product_id, _old_code, code in replacements
                           if sum(candidate == code for _id, _old, candidate in replacements) > 1}
        if duplicate_codes:
            raise ValueError(f"Mã sản phẩm bị trùng theo dữ liệu Excel: {', '.join(sorted(duplicate_codes))}")
        # Move through unique temporary values so existing suffixes can safely swap.
        for product_id, _current_code, _expected_code in replacements:
            connection.execute(
                "UPDATE products SET product_code = ? WHERE internal_id = ?",
                (f"TMP-PRODUCT-{product_id}", product_id),
            )
        for product_id, _old_code, expected_code in replacements:
            connection.execute(
                "UPDATE products SET product_code = ?, updated_at = CURRENT_TIMESTAMP, updated_by = 'excel-code-repair' WHERE internal_id = ?",
                (expected_code, product_id),
            )
        po_rows = connection.execute(
            """SELECT DISTINCT po.internal_id, p.product_code
               FROM excel_monthly_import_rows m
               JOIN products p ON p.internal_id = m.product_id
               JOIN purchase_order_lines line ON line.product_id = p.internal_id
               JOIN purchase_orders po ON po.internal_id = line.po_id"""
        ).fetchall()
        po_ids = {po_id for po_id, _product_code in po_rows}
        target_codes = [product_code for _po_id, product_code in po_rows]
        if len(target_codes) != len(set(target_codes)):
            raise ValueError("Không thể đồng bộ mã đơn: một mã sản phẩm có nhiều PO import.")
        for po_id, _product_code in po_rows:
            connection.execute(
                "UPDATE purchase_orders SET po_number = ? WHERE internal_id = ?",
                (f"TMP-PO-{po_id}", po_id),
            )
        for po_id, product_code in po_rows:
            connection.execute(
                "UPDATE purchase_orders SET po_number = ?, internal_order_code = ?, updated_at = CURRENT_TIMESTAMP, updated_by = 'excel-code-repair' WHERE internal_id = ?",
                (product_code, product_code, po_id),
            )
        return len(replacements)


def create_database_runtime_for_shared_sqlite(database_path: Path):
    from config.environments import AppConfig, Environment

    return create_database_runtime(
        AppConfig(Environment.DEV, f"sqlite:///{database_path.as_posix()}", "local", None)
    )


def main() -> None:
    root = Path(r"D:\DU-LIEU")
    paths = discover_monthly_list_files(root)
    database_path = Path(r"D:\HMS-QR-DATA\hms_qr_shared.sqlite")
    result = import_monthly_lists(paths, database_path=database_path, storage_root=Path(r"D:\HMS-QR-DATA\storage"))
    print(result)


if __name__ == "__main__":
    main()
