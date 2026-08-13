from __future__ import annotations
from dataclasses import asdict
from datetime import date
from pathlib import Path
from uuid import UUID
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from packages.domain.stage2 import *
from .sqlalchemy_models import Base, CustomerORM, PurchaseOrderORM, PurchaseOrderLineORM, DeliveryScheduleORM, ProductionRunORM

class Stage2Repository:
    """SQLAlchemy repository; SQLite is test/dev only, PostgreSQL is target."""
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, future=True)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)
    def create_schema(self): Base.metadata.create_all(self.engine)
    def add_customer(self, obj: Customer):
        try:
            with self.Session.begin() as s: s.add(CustomerORM(**{k: (str(v) if isinstance(v, UUID) else v) for k,v in asdict(obj).items()}))
        except IntegrityError as e: raise ValueError("customer_code đã tồn tại.") from e
        return obj
    def list_customers(self, search=None, active=None, page=1, page_size=50):
        with self.Session() as s:
            q=select(CustomerORM)
            if search: q=q.where((CustomerORM.name.contains(search)) | (CustomerORM.customer_code.contains(search)))
            if active is not None: q=q.where(CustomerORM.active == active)
            total=s.scalar(select(func.count()).select_from(q.subquery())) or 0; rows=s.scalars(q.order_by(CustomerORM.name).offset((page-1)*page_size).limit(page_size)).all()
            return tuple(self._customer(x) for x in rows), total
    def get_customer(self, identifier):
        with self.Session() as s:
            q=select(CustomerORM).where(CustomerORM.customer_code == str(identifier))
            try: x=s.scalars(q).one()
            except Exception:
                x=s.get(CustomerORM,str(identifier))
            if not x: raise LookupError("customer not found")
            return self._customer(x)
    def update_customer(self,obj):
        with self.Session.begin() as s: s.merge(CustomerORM(**{k: (str(v) if isinstance(v, UUID) else v) for k,v in asdict(obj).items()}))
        return obj
    def add_po(self,obj:PurchaseOrder):
        try:
            with self.Session.begin() as s:
                if not s.get(CustomerORM,str(obj.customer_id)): raise LookupError("customer not found")
                s.add(PurchaseOrderORM(**{k: (str(v) if isinstance(v, UUID) else v) for k,v in asdict(obj).items()}))
        except IntegrityError as e: raise ValueError("po_number đã tồn tại.") from e
        return obj
    def list_pos(self, customer_id=None, status=None):
        with self.Session() as s:
            q=select(PurchaseOrderORM)
            if customer_id:q=q.where(PurchaseOrderORM.customer_id==str(customer_id))
            if status:q=q.where(PurchaseOrderORM.status==str(status))
            return tuple(self._po(x) for x in s.scalars(q.order_by(PurchaseOrderORM.po_date.desc())).all())
    def update_po(self, obj):
        with self.Session.begin() as s:
            s.merge(PurchaseOrderORM(**{k: (str(v) if isinstance(v, UUID) else v) for k,v in asdict(obj).items()}))
        return obj
    def get_po(self, identifier):
        with self.Session() as s:
            x=s.get(PurchaseOrderORM,str(identifier)) or s.scalar(select(PurchaseOrderORM).where(PurchaseOrderORM.po_number==str(identifier)))
            if not x: raise LookupError("purchase order not found")
            return self._po(x)
    def add_line(self,obj:PurchaseOrderLine):
        with self.Session.begin() as s:
            if not s.get(PurchaseOrderORM,str(obj.po_id)): raise LookupError("purchase order not found")
            if not s.get(__import__('packages.persistence.sqlalchemy_models',fromlist=['ProductORM']).ProductORM,str(obj.product_id)): raise LookupError("product not found")
            try:s.add(PurchaseOrderLineORM(**{k: (str(v) if isinstance(v, UUID) else v) for k,v in asdict(obj).items()}))
            except IntegrityError as e: raise ValueError("line_number đã tồn tại trong PO.") from e
        return obj
    def list_lines(self, po_id):
        with self.Session() as s:return tuple(self._line(x) for x in s.scalars(select(PurchaseOrderLineORM).where(PurchaseOrderLineORM.po_id==str(po_id)).order_by(PurchaseOrderLineORM.line_number)).all())
    def add_delivery(self,obj:DeliveryScheduleEntry, ordered:Decimal):
        with self.Session() as s:
            existing = s.scalars(select(DeliveryScheduleORM).where(DeliveryScheduleORM.po_line_id == str(obj.po_line_id), DeliveryScheduleORM.status != DeliveryStatus.CANCELLED.value)).all()
            total = sum((x.planned_quantity for x in existing), Decimal(0)) + obj.planned_quantity
            if total>ordered: raise Stage2ValidationError("planned_quantity","Tổng lịch giao vượt ordered quantity.")
            s.add(DeliveryScheduleORM(**{k: (str(v) if isinstance(v, UUID) else v) for k,v in asdict(obj).items()})); s.commit()
        return obj
    def update_delivery(self, obj: DeliveryScheduleEntry, ordered: Decimal):
        with self.Session() as s:
            existing = s.scalars(select(DeliveryScheduleORM).where(DeliveryScheduleORM.po_line_id == str(obj.po_line_id), DeliveryScheduleORM.internal_id != str(obj.internal_id), DeliveryScheduleORM.status != DeliveryStatus.CANCELLED.value)).all()
            total = sum((x.planned_quantity for x in existing), Decimal(0)) + obj.planned_quantity
            if total > ordered: raise Stage2ValidationError("planned_quantity", "Tổng lịch giao vượt ordered quantity.")
            if not s.get(DeliveryScheduleORM, str(obj.internal_id)): raise LookupError("delivery schedule not found")
            s.merge(DeliveryScheduleORM(**{k: (str(v) if isinstance(v, UUID) else v) for k,v in asdict(obj).items()})); s.commit()
        return obj
    def list_deliveries(self,line_id):
            with self.Session() as s:return tuple(self._delivery(x) for x in s.scalars(select(DeliveryScheduleORM).where(DeliveryScheduleORM.po_line_id==str(line_id)).order_by(DeliveryScheduleORM.planned_date)).all())
    def add_run(self,obj:ProductionRun, ordered:Decimal):
        with self.Session.begin() as s:
            existing = s.scalars(select(ProductionRunORM).where(ProductionRunORM.po_line_id == str(obj.po_line_id), ProductionRunORM.status != RunStatus.CANCELLED.value)).all()
            planned = sum((x.planned_quantity for x in existing), Decimal(0)) + obj.planned_quantity
            if planned>ordered: raise Stage2ValidationError("planned_quantity","Tổng run vượt ordered quantity.")
            line = s.get(PurchaseOrderLineORM, str(obj.po_line_id))
            if not line: raise LookupError("purchase order line not found")
            if str(line.product_id) != str(obj.product_id): raise Stage2ValidationError("product_id", "Product không khớp PO Line.")
            s.add(ProductionRunORM(**{k: (str(v) if isinstance(v, UUID) else v) for k,v in asdict(obj).items()}))
        return obj
    def update_run(self, obj: ProductionRun, ordered: Decimal):
        with self.Session.begin() as s:
            existing = s.scalars(select(ProductionRunORM).where(ProductionRunORM.po_line_id == str(obj.po_line_id), ProductionRunORM.internal_id != str(obj.internal_id), ProductionRunORM.status != RunStatus.CANCELLED.value)).all()
            planned = sum((x.planned_quantity for x in existing), Decimal(0)) + obj.planned_quantity
            if planned > ordered: raise Stage2ValidationError("planned_quantity", "Tổng run vượt ordered quantity.")
            if not s.get(ProductionRunORM, str(obj.internal_id)): raise LookupError("production run not found")
            s.merge(ProductionRunORM(**{k: (str(v) if isinstance(v, UUID) else v) for k,v in asdict(obj).items()}))
        return obj
    def list_runs(self, po_line_id=None, status=None):
        with self.Session() as s:
            q=select(ProductionRunORM)
            if po_line_id:q=q.where(ProductionRunORM.po_line_id==str(po_line_id))
            if status:q=q.where(ProductionRunORM.status==str(status))
            return tuple(self._run(x) for x in s.scalars(q.order_by(ProductionRunORM.priority,ProductionRunORM.planned_start)).all())
    @staticmethod
    def _customer(x): return Customer(UUID(x.internal_id),x.customer_code,x.name,x.short_name,x.address,x.tax_code,x.contact_name,x.phone,x.email,x.notes,x.active,x.created_at,x.updated_at,x.created_by,x.updated_by)
    @staticmethod
    def _po(x): return PurchaseOrder(UUID(x.internal_id),x.po_number,UUID(x.customer_id),x.po_date,x.requested_delivery_date,POStatus(x.status),x.notes,x.created_at,x.updated_at,x.created_by,x.updated_by)
    @staticmethod
    def _line(x): return PurchaseOrderLine(UUID(x.internal_id),UUID(x.po_id),UUID(x.product_id),x.line_number,x.ordered_quantity,x.unit,x.unit_price,x.currency,x.customer_part_reference,x.notes)
    @staticmethod
    def _delivery(x): return DeliveryScheduleEntry(UUID(x.internal_id),UUID(x.po_line_id),x.planned_date,x.planned_quantity,DeliveryStatus(x.status),x.notes,x.created_at,x.updated_at)
    @staticmethod
    def _run(x): return ProductionRun(UUID(x.internal_id),x.run_code,UUID(x.po_line_id),UUID(x.product_id),x.planned_quantity,x.completed_quantity,RunStatus(x.status),x.priority,x.planned_start,x.planned_finish,x.actual_start,x.actual_finish,x.notes,x.created_at,x.updated_at,x.created_by,x.updated_by)
