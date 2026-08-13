from datetime import date
from pathlib import Path
from PySide6.QtWidgets import QApplication
from apps.desktop.stage2_window import Stage2Window
from packages.excel.stage2_export import Stage2ExcelExporter
from packages.domain.stage2 import Customer, PurchaseOrder, PurchaseOrderLine
from packages.persistence.sqlalchemy_repository import Stage2Repository
from alembic.config import Config
from alembic import command

def test_stage2_excel_desktop_and_alembic(tmp_path: Path, monkeypatch):
    customer=Customer.create(customer_code="CUS-1",name="HMS",actor="u"); po=PurchaseOrder.create(po_number="PO-1",customer_id=customer.internal_id,po_date=date(2026,8,1),actor="u"); line=PurchaseOrderLine.create(po_id=po.internal_id,product_id=customer.internal_id,line_number=1,ordered_quantity=2,unit="pcs")
    output=Stage2ExcelExporter().export(customers=[customer],purchase_orders=[po],lines=[line],path=tmp_path/'stage2.xlsx'); assert output.exists()
    app=QApplication.instance() or QApplication([]); window=Stage2Window(None); assert "Khách hàng" in window.windowTitle(); window.close(); app.processEvents()
    db=tmp_path/'migration.sqlite'; cfg=Config('alembic.ini'); cfg.set_main_option('sqlalchemy.url', f'sqlite:///{db.as_posix()}'); command.upgrade(cfg,'head'); assert db.exists()
