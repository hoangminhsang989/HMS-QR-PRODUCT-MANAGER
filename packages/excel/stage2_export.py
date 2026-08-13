from __future__ import annotations
from pathlib import Path
from typing import Iterable
from openpyxl import Workbook
from packages.domain.stage2 import Customer, PurchaseOrder, PurchaseOrderLine, ProductionRun, DeliveryScheduleEntry

class Stage2ExcelExporter:
    def export(self, *, customers: Iterable[Customer]=(), purchase_orders: Iterable[PurchaseOrder]=(), lines: Iterable[PurchaseOrderLine]=(), deliveries: Iterable[DeliveryScheduleEntry]=(), runs: Iterable[ProductionRun]=(), path: str|Path) -> Path:
        target=Path(path); target.parent.mkdir(parents=True,exist_ok=True); wb=Workbook()
        try:
            ws=wb.active; ws.title="Orders"; ws.append(["Customer","PO Number","Product ID","Ordered Quantity","Unit","Delivery Schedule","Production Run Status"])
            po_by_id={x.internal_id:x for x in purchase_orders}; customer_by_id={x.internal_id:x for x in customers}; deliveries_by_line={}
            for d in deliveries: deliveries_by_line.setdefault(d.po_line_id,[]).append(f"{d.planned_date.isoformat()}: {d.planned_quantity} ({d.status.value})")
            runs_by_line={}
            for r in runs: runs_by_line.setdefault(r.po_line_id,[]).append(r.status.value)
            for line in lines:
                po=po_by_id.get(line.po_id); customer=customer_by_id.get(po.customer_id) if po else None
                ws.append([customer.name if customer else "",po.po_number if po else "",str(line.product_id),float(line.ordered_quantity),line.unit,"\n".join(deliveries_by_line.get(line.internal_id,[])),"\n".join(runs_by_line.get(line.internal_id,[]))])
            ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
            for i,w in enumerate([24,20,38,18,12,34,24],1): ws.column_dimensions[chr(64+i)].width=w
            wb.save(target)
        finally: wb.close()
        return target
