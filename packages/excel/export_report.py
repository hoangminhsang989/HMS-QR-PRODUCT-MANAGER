"""Production progress and activity report exporter to styled Excel."""

from __future__ import annotations
from datetime import datetime
from io import BytesIO
from pathlib import Path
import sqlite3

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def generate_production_excel_report(db_path: str) -> BytesIO:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    wb = Workbook()
    ws_summary = wb.active
    ws_summary.title = "TỔNG QUAN TIẾN ĐỘ"

    # Fetch stats
    total_prods = cur.execute("SELECT count(*) FROM products").fetchone()[0]
    total_tracking = cur.execute("SELECT count(*) FROM order_tracking_items").fetchone()[0]
    status_counts = dict(cur.execute("SELECT status, count(*) FROM order_tracking_items GROUP BY status").fetchall())
    total_reports = cur.execute("SELECT count(*) FROM process_report_events").fetchone()[0]
    total_workflows = cur.execute("SELECT count(*) FROM tracking_workflow_events").fetchone()[0]

    # Styles
    title_font = Font(name="Segoe UI", size=16, bold=True, color="1B365D")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    sub_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
    bold_font = Font(name="Segoe UI", size=11, bold=True)
    normal_font = Font(name="Segoe UI", size=11)
    thin_border = Border(
        left=Side(style="thin", color="D1D5DB"),
        right=Side(style="thin", color="D1D5DB"),
        top=Side(style="thin", color="D1D5DB"),
        bottom=Side(style="thin", color="D1D5DB"),
    )

    # --- SHEET 1: SUMMARY ---
    ws_summary["A1"] = "BÁO CÁO TIẾN ĐỘ SẢN XUẤT & TRUY VẾT QR — HMS FACTORY"
    ws_summary["A1"].font = title_font
    ws_summary["A2"] = f"Thời gian xuất báo cáo: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    ws_summary["A2"].font = Font(name="Segoe UI", size=10, italic=True, color="6B7280")

    ws_summary["A4"] = "CHỈ SỐ TỔNG HỢP"
    ws_summary["A4"].font = Font(name="Segoe UI", size=12, bold=True, color="1E3A8A")

    kpis = [
        ("Tổng số sản phẩm quản lý", total_prods, "Chi tiết"),
        ("Tổng số mã QR theo dõi (Tracking)", total_tracking, "Mã QR"),
        ("Đang tiến hành gia công (IN_PRODUCTION)", status_counts.get("IN_PRODUCTION", 0), "Chi tiết"),
        ("Đã kiểm tra chất lượng (QC_CHECKED)", status_counts.get("QC_CHECKED", 0), "Chi tiết"),
        ("Đã hoàn tất đóng gói (PACKED)", status_counts.get("PACKED", 0), "Chi tiết"),
        ("Đã xuất xưởng giao hàng (DELIVERED)", status_counts.get("DELIVERED", 0), "Chi tiết"),
        ("Tổng lượt báo cáo công đoạn gia công", total_reports, "Lượt"),
        ("Tổng lượt sự kiện quy trình QC & xuất hàng", total_workflows, "Lượt"),
    ]

    ws_summary.append([])
    ws_summary.append(["Chỉ số hoạt động", "Số lượng", "Đơn vị tính"])
    for cell in ws_summary[6]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for idx, (label, val, unit) in enumerate(kpis, start=7):
        ws_summary.append([label, val, unit])
        row_cells = ws_summary[idx]
        row_cells[0].font = normal_font
        row_cells[1].font = bold_font
        row_cells[1].alignment = Alignment(horizontal="right")
        row_cells[2].font = normal_font
        row_cells[2].alignment = Alignment(horizontal="center")
        for c in row_cells:
            c.border = thin_border

    # --- SHEET 2: TRACKING ITEMS ---
    ws_items = wb.create_sheet(title="DANH SÁCH CHI TIẾT")
    headers_items = [
        "STT", "Mã Tracking", "Mã Sản Phẩm", "Tên Chi Tiết", "Khách Hàng",
        "Số Lượng", "ĐVT", "Mác Vật Liệu", "Quy Cách / Kích Thước",
        "Xử Lý Bề Mặt", "Hạn Giao", "Trạng Thái", "Mã QR Public"
    ]
    ws_items.append(headers_items)
    for cell in ws_items[1]:
        cell.font = header_font
        cell.fill = sub_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    items_rows = cur.execute("""
        SELECT t.tracking_code, p.product_code, p.part_name, p.company,
               t.quantity, t.unit, p.material, p.size, p.surface_treatment,
               t.delivery_date, t.status, t.qr_public_id
        FROM order_tracking_items t
        JOIN products p ON t.product_id = p.internal_id
        ORDER BY t.rowid DESC
    """).fetchall()

    for idx, r in enumerate(items_rows, start=1):
        raw_q = r["quantity"]
        try:
            fq = float(raw_q)
            q = int(fq) if fq.is_integer() else fq
        except Exception:
            q = raw_q
        row_data = [
            idx, r["tracking_code"], r["product_code"], r["part_name"], r["company"],
            q, r["unit"], r["material"] or "", r["size"] or "",
            r["surface_treatment"] or "", str(r["delivery_date"] or ""),
            r["status"], r["qr_public_id"] or ""
        ]
        ws_items.append(row_data)
        for c in ws_items[idx + 1]:
            c.font = normal_font
            c.border = thin_border

    # --- SHEET 3: ACTIVITY LOG ---
    ws_log = wb.create_sheet(title="NHẬT KÝ SẢN XUẤT")
    headers_log = [
        "Thời Gian", "Nhân Sự", "Chi Tiết Sản Phẩm", "Mã Tracking",
        "Công Đoạn / Thao Tác", "Phân Loại", "Số Lượng", "Nội Dung Báo Cáo"
    ]
    ws_log.append(headers_log)
    for cell in ws_log[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    reports = cur.execute("""
        SELECT r.server_timestamp, r.actor_display_name_snapshot as actor,
               p.part_name, t.tracking_code,
               coalesce(m.display_name, 'Gia công') || case when r.attempt_number is not null then ' (Lần ' || r.attempt_number || ')' else ' (Đã xong)' end as action,
               'GIA CÔNG' as category, r.quantity, r.notes
        FROM process_report_events r
        LEFT JOIN machining_types m ON r.machining_type_id = m.internal_id
        LEFT JOIN order_tracking_items t ON r.tracking_item_id = t.internal_id
        LEFT JOIN products p ON t.product_id = p.internal_id
    """).fetchall()

    workflows = cur.execute("""
        SELECT w.server_timestamp, w.actor_display_name_snapshot as actor,
               p.part_name, t.tracking_code,
               w.event_type as action, 'QUY TRÌNH QC/GIAO' as category,
               w.quantity, w.notes
        FROM tracking_workflow_events w
        LEFT JOIN order_tracking_items t ON w.tracking_item_id = t.internal_id
        LEFT JOIN products p ON t.product_id = p.internal_id
    """).fetchall()

    all_logs = sorted(list(reports) + list(workflows), key=lambda x: str(x["server_timestamp"]), reverse=True)

    for idx, l in enumerate(all_logs, start=1):
        ts = str(l["server_timestamp"])[:19].replace("T", " ")
        raw_q = l["quantity"]
        q = ""
        if raw_q is not None and str(raw_q).strip():
            try:
                fq = float(raw_q)
                q = int(fq) if fq.is_integer() else fq
            except Exception:
                q = raw_q

        ws_log.append([
            ts, l["actor"], l["part_name"] or "", l["tracking_code"] or "",
            l["action"], l["category"], q, l["notes"] or ""
        ])
        for c in ws_log[idx + 1]:
            c.font = normal_font
            c.border = thin_border

    # Auto-adjust column widths for all sheets
    for ws in [ws_summary, ws_items, ws_log]:
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 11), 45)

    conn.close()

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
