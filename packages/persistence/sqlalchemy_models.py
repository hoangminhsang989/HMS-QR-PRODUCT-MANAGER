from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase): pass

class ProductORM(Base):
    __tablename__ = "products"
    internal_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    part_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    material: Mapped[str|None] = mapped_column(String(255)); requester: Mapped[str|None] = mapped_column(String(255)); surface_treatment: Mapped[str|None] = mapped_column(String(255)); outsourced: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False); size: Mapped[str|None] = mapped_column(String(255)); notes: Mapped[str|None] = mapped_column(Text); delivery_schedule: Mapped[date|None] = mapped_column(Date); status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW"); created_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True)); updated_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True)); created_by: Mapped[str|None] = mapped_column(String(128)); updated_by: Mapped[str|None] = mapped_column(String(128))

class CustomerORM(Base):
    __tablename__ = "customers"
    internal_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str|None] = mapped_column(String(255)); address: Mapped[str|None] = mapped_column(Text)
    tax_code: Mapped[str|None] = mapped_column(String(64)); contact_name: Mapped[str|None] = mapped_column(String(255)); phone: Mapped[str|None] = mapped_column(String(64)); email: Mapped[str|None] = mapped_column(String(255)); notes: Mapped[str|None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False); updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False); created_by: Mapped[str] = mapped_column(String(128), nullable=False); updated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    purchase_orders: Mapped[list["PurchaseOrderORM"]] = relationship(back_populates="customer")

class PurchaseOrderORM(Base):
    __tablename__ = "purchase_orders"
    internal_id: Mapped[str] = mapped_column(String(36), primary_key=True); po_number: Mapped[str] = mapped_column(String(128), unique=True, nullable=False); internal_order_code: Mapped[str|None] = mapped_column(String(64), unique=True); customer_id: Mapped[str] = mapped_column(ForeignKey("customers.internal_id"), nullable=False); po_date: Mapped[date] = mapped_column(Date, nullable=False); requested_delivery_date: Mapped[date|None] = mapped_column(Date); status: Mapped[str] = mapped_column(String(32), nullable=False); notes: Mapped[str|None] = mapped_column(Text); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False); updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False); created_by: Mapped[str] = mapped_column(String(128), nullable=False); updated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    customer: Mapped[CustomerORM] = relationship(back_populates="purchase_orders"); lines: Mapped[list["PurchaseOrderLineORM"]] = relationship(back_populates="purchase_order", cascade="save-update, merge")

class PurchaseOrderLineORM(Base):
    __tablename__ = "purchase_order_lines"
    internal_id: Mapped[str] = mapped_column(String(36), primary_key=True); po_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.internal_id"), nullable=False); product_id: Mapped[str] = mapped_column(ForeignKey("products.internal_id"), nullable=False); line_number: Mapped[int] = mapped_column(Integer, nullable=False); ordered_quantity: Mapped[Decimal] = mapped_column(Numeric(18,4), nullable=False); unit: Mapped[str] = mapped_column(String(32), nullable=False); unit_price: Mapped[Decimal|None] = mapped_column(Numeric(18,4)); currency: Mapped[str|None] = mapped_column(String(8)); customer_part_reference: Mapped[str|None] = mapped_column(String(255)); notes: Mapped[str|None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("po_id", "line_number", name="uq_po_line_number"),)
    purchase_order: Mapped[PurchaseOrderORM] = relationship(back_populates="lines"); deliveries: Mapped[list["DeliveryScheduleORM"]] = relationship(back_populates="line", cascade="save-update, merge"); runs: Mapped[list["ProductionRunORM"]] = relationship(back_populates="line", cascade="save-update, merge")

class DeliveryScheduleORM(Base):
    __tablename__ = "delivery_schedule_entries"
    internal_id: Mapped[str] = mapped_column(String(36), primary_key=True); po_line_id: Mapped[str] = mapped_column(ForeignKey("purchase_order_lines.internal_id"), nullable=False); planned_date: Mapped[date] = mapped_column(Date, nullable=False); planned_quantity: Mapped[Decimal] = mapped_column(Numeric(18,4), nullable=False); status: Mapped[str] = mapped_column(String(32), nullable=False); notes: Mapped[str|None] = mapped_column(Text); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False); updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    line: Mapped[PurchaseOrderLineORM] = relationship(back_populates="deliveries")

class ProductionRunORM(Base):
    __tablename__ = "production_runs"
    internal_id: Mapped[str] = mapped_column(String(36), primary_key=True); run_code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False); po_line_id: Mapped[str] = mapped_column(ForeignKey("purchase_order_lines.internal_id"), nullable=False); product_id: Mapped[str] = mapped_column(ForeignKey("products.internal_id"), nullable=False); planned_quantity: Mapped[Decimal] = mapped_column(Numeric(18,4), nullable=False); completed_quantity: Mapped[Decimal] = mapped_column(Numeric(18,4), nullable=False); status: Mapped[str] = mapped_column(String(32), nullable=False); priority: Mapped[int] = mapped_column(Integer, nullable=False); planned_start: Mapped[date|None] = mapped_column(Date); planned_finish: Mapped[date|None] = mapped_column(Date); actual_start: Mapped[date|None] = mapped_column(Date); actual_finish: Mapped[date|None] = mapped_column(Date); notes: Mapped[str|None] = mapped_column(Text); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False); updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False); created_by: Mapped[str] = mapped_column(String(128), nullable=False); updated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    line: Mapped[PurchaseOrderLineORM] = relationship(back_populates="runs")
