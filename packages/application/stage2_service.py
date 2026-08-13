from __future__ import annotations
from datetime import date
from datetime import date
from uuid import UUID
from packages.domain.stage2 import *
from packages.persistence.sqlalchemy_repository import Stage2Repository

class Stage2Service:
    def __init__(self, repository: Stage2Repository): self.repository=repository; self.codes=Stage2CodeService()
    def create_customer(self, *, actor: str, customer_code: str|None=None, **data):
        code=customer_code or self.codes.customer_code(self.repository.list_customers()[1]+1); return self.repository.add_customer(Customer.create(customer_code=code,actor=actor,**data))
    def list_customers(self, **kwargs): return self.repository.list_customers(**kwargs)
    def get_customer(self, identifier): return self.repository.get_customer(identifier)
    def update_customer(self, identifier, *, actor: str, **changes): return self.repository.update_customer(self.get_customer(identifier).update(actor=actor,**changes))
    def create_po(self, *, actor: str, **data): return self.repository.add_po(PurchaseOrder.create(actor=actor,**data))
    def list_pos(self, **kwargs): return self.repository.list_pos(**kwargs)
    def get_po(self, identifier): return self.repository.get_po(identifier)
    def update_po(self, identifier, *, actor: str, **changes): return self.repository.update_po(self.get_po(identifier).update(actor=actor, **changes))
    def add_line(self, *, po_id: UUID, product_id: UUID, **data): return self.repository.add_line(PurchaseOrderLine.create(po_id=po_id,product_id=product_id,**data))
    def list_lines(self, po_id): return self.repository.list_lines(po_id)
    def add_delivery(self, *, po_line_id: UUID, ordered_quantity, **data): return self.repository.add_delivery(DeliveryScheduleEntry.create(po_line_id=po_line_id,**data), quantity(ordered_quantity,"ordered_quantity"))
    def list_deliveries(self, po_line_id): return self.repository.list_deliveries(po_line_id)
    def update_delivery(self, entry: DeliveryScheduleEntry, *, ordered_quantity): return self.repository.update_delivery(entry, quantity(ordered_quantity,"ordered_quantity"))
    def create_run(self, *, actor: str, po_line_id: UUID, ordered_quantity, product_id: UUID, run_code: str|None=None, **data):
        code = run_code or self.codes.run_code(len(self.repository.list_runs())+1, date.today().year)
        return self.repository.add_run(ProductionRun.create(actor=actor,po_line_id=po_line_id,product_id=product_id,run_code=code,**data), quantity(ordered_quantity,"ordered_quantity"))
    def list_runs(self, **kwargs): return self.repository.list_runs(**kwargs)
    def update_run(self, run: ProductionRun, *, ordered_quantity): return self.repository.update_run(run, quantity(ordered_quantity,"ordered_quantity"))
