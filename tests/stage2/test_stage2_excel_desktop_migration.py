from datetime import date
from pathlib import Path
from PySide6.QtWidgets import QApplication
from apps.desktop.stage2_window import Stage2Window
from packages.excel.stage2_export import Stage2ExcelExporter
from packages.domain.stage2 import Customer, PurchaseOrder, PurchaseOrderLine
from packages.persistence.sqlalchemy_repository import Stage2Repository


def _run_clean_engine_migrations(database: Path) -> None:
    from packages.sqlengine import connect
    from packages.sqlengine.migrations import load_migration_modules, run_migrations
    from config.paths import SOURCE_ROOT

    engine = connect(database)
    try:
        run_migrations(engine, load_migration_modules(SOURCE_ROOT / "migrations" / "engine"), now=lambda: "2026-10-18T00:00:00Z")
    finally:
        engine.close()

def test_stage2_excel_desktop_and_engine_migrations(tmp_path: Path, monkeypatch):
    customer=Customer.create(customer_code="CUS-1",name="HMS",actor="u"); po=PurchaseOrder.create(po_number="PO-1",customer_id=customer.internal_id,po_date=date(2026,8,1),actor="u"); line=PurchaseOrderLine.create(po_id=po.internal_id,product_id=customer.internal_id,line_number=1,ordered_quantity=2,unit="pcs")
    output=Stage2ExcelExporter().export(customers=[customer],purchase_orders=[po],lines=[line],path=tmp_path/'stage2.xlsx'); assert output.exists()
    app=QApplication.instance() or QApplication([]); window=Stage2Window(None); assert "Khách hàng" in window.windowTitle(); window.close(); app.processEvents()
    db=tmp_path/'migration.sqlite'; _run_clean_engine_migrations(db); assert db.exists()
