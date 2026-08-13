"""Versioned FastAPI boundary for Product Master."""

from __future__ import annotations

from pathlib import Path
from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import HTMLResponse

from config.environments import load_config
from packages.application.product_service import ProductService
from packages.contracts.api import ProductPageResponse, ProductPatch, ProductPayload, ProductResponse, to_response
from packages.domain.product import ProductStatus, ProductValidationError
from packages.domain.stage2 import DeliveryScheduleEntry, POStatus, RunStatus, Stage2ValidationError, now_utc
from packages.domain.repository import DuplicateProductCode, ProductNotFound
from packages.persistence.sqlite_product_repository import SQLiteProductRepository
from packages.application.stage2_service import Stage2Service
from packages.contracts.stage2 import CustomerPatch, CustomerPayload, DeliveryData, POData, POLineData, RunData, dump
from packages.persistence.sqlalchemy_repository import Stage2Repository
from packages.application.tracking_service import TrackingService
from packages.contracts.tracking import AttemptExpand,DateChange,NewOrder,OperatorCreate,PreferenceSet,ReportRevision,ReportSubmit,TrackingCreate,WorkflowEventRevision,WorkflowEventSubmit
from packages.domain.tracking import MachiningType,Operator,TrackingError
from packages.domain.workflow import WorkflowEventType
from packages.persistence.tracking_repository import TrackingRepository
from packages.persistence.workflow_repository import WorkflowRepository
from packages.application.workflow_services import DeliveryService,GeneralReportService,PackingService,QcService,TrackingHistoryService
from apps.mobile.web import mobile_page

APP_NAME = "hms-qr-server"


def create_app() -> dict[str, str]:
    """Preserve the Stage 0 import descriptor contract."""
    return {"name": APP_NAME, "status": "foundation"}


def build_api(service: ProductService | None = None) -> FastAPI:
    api = FastAPI(title="HMS QR Product Manager", version="1.0")
    if service is None:
        config = load_config()
        db_path = Path(config.database_url.removeprefix("sqlite:///"))
        service = ProductService(SQLiteProductRepository(db_path))

    def current_actor(x_actor: Annotated[str | None, Header()] = None) -> str:
        actor = (x_actor or "development-user").strip()
        if not actor or actor.lower() in {"admin", "123456"}:
            raise HTTPException(status_code=400, detail={"code": "INVALID_ACTOR", "message": "Actor không hợp lệ."})
        return actor

    @api.exception_handler(ProductValidationError)
    async def validation_error(_, exc: ProductValidationError):
        return _error(422, "VALIDATION_ERROR", exc.message, {"field": exc.field})

    @api.exception_handler(DuplicateProductCode)
    async def duplicate_error(_, exc: DuplicateProductCode):
        return _error(409, "DUPLICATE_PRODUCT_CODE", f"Mã sản phẩm đã tồn tại: {exc}")

    @api.exception_handler(ProductNotFound)
    async def not_found_error(_, exc: ProductNotFound):
        return _error(404, "PRODUCT_NOT_FOUND", f"Không tìm thấy sản phẩm: {exc}")

    @api.post("/api/v1/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
    def create_product(payload: ProductPayload, actor: str = Depends(current_actor)):
        data = payload.model_dump()
        return to_response(service.create_product(actor=actor, **data))

    @api.get("/api/v1/products", response_model=ProductPageResponse)
    def list_products(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                      search: str | None = None, status_filter: ProductStatus | None = Query(None, alias="status"),
                      sort_by: str = "updated_at", descending: bool = True):
        result = service.list_products(page=page, page_size=page_size, search=search,
                                       status=status_filter, sort_by=sort_by, descending=descending)
        return ProductPageResponse(items=[to_response(p) for p in result.items], total=result.total,
                                    page=result.page, page_size=result.page_size)

    @api.get("/api/v1/products/{identifier}", response_model=ProductResponse)
    def get_product(identifier: str):
        return to_response(service.get_product(identifier))

    @api.patch("/api/v1/products/{identifier}", response_model=ProductResponse)
    def update_product(identifier: str, payload: ProductPatch, actor: str = Depends(current_actor)):
        return to_response(service.update_product(identifier, actor=actor, **payload.model_dump(exclude_unset=True)))

    return api


def build_stage2_api(service: Stage2Service | None = None) -> FastAPI:
    api = FastAPI(title="HMS QR Product Manager Stage 2", version="2.0")
    if service is None:
        cfg = load_config(); service = Stage2Service(Stage2Repository(cfg.database_url))
    def actor(x_actor: Annotated[str | None, Header()] = None) -> str:
        return (x_actor or "development-user").strip()
    @api.exception_handler(Stage2ValidationError)
    async def stage2_validation(_, exc): return _error(422, "VALIDATION_ERROR", exc.message, {"field": exc.field})
    @api.exception_handler(ValueError)
    async def stage2_value(_, exc): return _error(409, "BUSINESS_CONFLICT", str(exc))
    @api.exception_handler(LookupError)
    async def stage2_missing(_, exc): return _error(404, "NOT_FOUND", str(exc))
    @api.post("/api/v1/customers")
    def create_customer(payload: CustomerPayload, x_actor: str = Depends(actor)):
        return dump(service.create_customer(actor=x_actor, **payload.model_dump()))
    @api.get("/api/v1/customers")
    def list_customers(search: str|None=None, active: bool|None=None, page: int=Query(1,ge=1), page_size: int=Query(50,ge=1,le=200)):
        items,total=service.list_customers(search=search,active=active,page=page,page_size=page_size); return {"items":[dump(x) for x in items],"total":total,"page":page,"page_size":page_size}
    @api.get("/api/v1/customers/{identifier}")
    def get_customer(identifier: str): return dump(service.get_customer(identifier))
    @api.patch("/api/v1/customers/{identifier}")
    def update_customer(identifier: str,payload: CustomerPatch,x_actor: str=Depends(actor)): return dump(service.update_customer(identifier,actor=x_actor,**payload.model_dump(exclude_unset=True)))
    @api.post("/api/v1/purchase-orders")
    def create_po(payload: POData,x_actor: str=Depends(actor)): return dump(service.create_po(actor=x_actor,**payload.model_dump()))
    @api.get("/api/v1/purchase-orders")
    def list_pos(customer_id: UUID|None=None,status_filter: POStatus|None=Query(None,alias="status")): return {"items":[dump(x) for x in service.list_pos(customer_id=customer_id,status=status_filter)]}
    @api.get("/api/v1/purchase-orders/{identifier}")
    def get_po(identifier: str): return dump(service.get_po(identifier))
    @api.patch("/api/v1/purchase-orders/{identifier}")
    def update_po(identifier: str, payload: POData, x_actor: str=Depends(actor)):
        data=payload.model_dump(exclude_unset=True); data.pop("po_number",None); data.pop("customer_id",None); data.pop("po_date",None); return dump(service.update_po(identifier,actor=x_actor,**data))
    @api.post("/api/v1/purchase-orders/{po_id}/lines")
    def add_line(po_id: UUID,payload: POLineData): return dump(service.add_line(po_id=po_id,**payload.model_dump()))
    @api.get("/api/v1/purchase-orders/{po_id}/lines")
    def list_lines(po_id: UUID): return {"items":[dump(x) for x in service.list_lines(po_id)]}
    @api.post("/api/v1/purchase-order-lines/{line_id}/delivery-schedules")
    def add_delivery(line_id: UUID, payload: DeliveryData, ordered_quantity: Decimal=Query(...,gt=0)): return dump(service.add_delivery(po_line_id=line_id,ordered_quantity=ordered_quantity,**payload.model_dump()))
    @api.get("/api/v1/purchase-order-lines/{line_id}/delivery-schedules")
    def list_deliveries(line_id: UUID): return {"items":[dump(x) for x in service.list_deliveries(line_id)]}
    @api.patch("/api/v1/delivery-schedule-entries/{entry_id}")
    def update_delivery(entry_id: UUID, payload: DeliveryData, po_line_id: UUID=Query(...), ordered_quantity: Decimal=Query(...,gt=0)):
        current = next((x for x in service.list_deliveries(po_line_id) if x.internal_id == entry_id), None)
        if not current: raise HTTPException(404, "delivery schedule not found")
        updated = DeliveryScheduleEntry(entry_id, po_line_id, payload.planned_date, payload.planned_quantity, payload.status, payload.notes, current.created_at, now_utc(), current.created_at.isoformat(), current.created_at.isoformat())
        return dump(service.update_delivery(updated, ordered_quantity=ordered_quantity))
    @api.post("/api/v1/production-runs")
    def create_run(payload: RunData,x_actor: str=Depends(actor)):
        data=payload.model_dump(); ordered=data.pop("ordered_quantity"); return dump(service.create_run(actor=x_actor,ordered_quantity=ordered,**data))
    @api.get("/api/v1/production-runs")
    def list_runs(po_line_id: UUID|None=None,status_filter: RunStatus|None=Query(None,alias="status")): return {"items":[dump(x) for x in service.list_runs(po_line_id=po_line_id,status=status_filter)]}
    @api.patch("/api/v1/production-runs/{run_id}")
    def update_run(run_id: UUID, payload: RunData, ordered_quantity: Decimal=Query(...,gt=0)):
        current = next((x for x in service.list_runs() if x.internal_id == run_id), None)
        if not current: raise HTTPException(404, "production run not found")
        updated = current.update(actor="api-user", **payload.model_dump(exclude={"po_line_id","product_id","ordered_quantity","run_code"}, exclude_unset=True))
        return dump(service.update_run(updated, ordered_quantity=ordered_quantity))
    return api

def build_tracking_api(service:TrackingService|None=None)->FastAPI:
    api=FastAPI(title="HMS QR Tracking",version="3.0")
    if service is None:
        cfg=load_config();repo=Stage2Repository(cfg.database_url);repo.create_schema();service=TrackingService(TrackingRepository(repo.engine))
    workflow_repo=WorkflowRepository(service.repo.engine);qc_service=QcService(workflow_repo);packing_service=PackingService(workflow_repo);delivery_service=DeliveryService(workflow_repo);general_service=GeneralReportService(workflow_repo);history_service=TrackingHistoryService(workflow_repo,service.repo)
    for order,(code,name) in enumerate((("BLANK","TẠO PHÔI"),("TURN","TIỆN"),("MILL","PHAY"),("WIRE","CẮT DÂY"),("GRIND","MÀI"),("HEAT","NHIỆT LUYỆN"),("OTHER","KHÁC")),1):service.repo.add_machining_type(MachiningType(uuid4(),code,name,True,order))
    @api.exception_handler(TrackingError)
    async def tracking_validation(_,exc):return _error(422,"TRACKING_VALIDATION_ERROR",str(exc))
    @api.exception_handler(LookupError)
    async def tracking_missing(_,exc):return _error(404,"TRACKING_NOT_FOUND",str(exc))
    @api.get("/mobile",response_class=HTMLResponse)
    def mobile():return mobile_page()
    @api.post("/api/v1/tracking-items")
    def create_tracking(payload:TrackingCreate,x_actor:Annotated[str|None,Header()]=None):return dump(service.create_item(actor=x_actor or "development-user",**payload.model_dump()))
    @api.get("/api/v1/tracking-items")
    def list_tracking(search:str|None=None,status_filter:str|None=Query(None,alias="status")):
        items=[]
        for item in service.repo.list_items(search):
            summary=history_service.summary(item.internal_id)
            if not status_filter or summary["current_status"]==status_filter:items.append({**dump(item),**summary})
        return {"items":items}
    @api.get("/api/v1/tracking-items/{identifier}")
    def get_tracking(identifier:str):return dump(service.repo.get_item(identifier))
    @api.post("/api/v1/tracking-items/{identifier}/qr")
    def issue_qr(identifier:str,x_actor:Annotated[str|None,Header()]=None):
        item=service.issue_qr(identifier,x_actor or "development-user");return {**dump(item),"payload":service.qr_payload(item.internal_id)}
    @api.get("/api/v1/tracking-items/{identifier}/qr")
    def get_qr(identifier:str):
        item=service.repo.get_item(identifier);return {"qr_public_id":item.qr_public_id,"qr_status":item.qr_status,"payload":service.qr_payload(item.internal_id) if item.qr_public_id else None}
    @api.post("/api/v1/tracking-items/{identifier}/qr/reissue")
    def reissue_qr(identifier:str,x_actor:Annotated[str|None,Header()]=None):
        item=service.reissue_qr(identifier,x_actor or "development-user");return {**dump(item),"payload":service.qr_payload(item.internal_id)}
    @api.patch("/api/v1/tracking-items/{identifier}/delivery-date")
    def change_date(identifier:str,payload:DateChange,x_actor:Annotated[str|None,Header()]=None):return dump(service.change_date(identifier,payload.delivery_date,x_actor or "development-user",payload.reason))
    @api.post("/api/v1/tracking-items/{identifier}/new-order")
    def new_order(identifier:str,payload:NewOrder,x_actor:Annotated[str|None,Header()]=None):return dump(service.create_new_order_from_item(identifier,new_po_number=payload.po_number,delivery_date=payload.delivery_date,actor=x_actor or "development-user"))
    @api.get("/api/v1/scan")
    def scan(payload:str=Query(...)):return service.scan(payload)
    @api.post("/api/v1/operators")
    def operator(payload:OperatorCreate):return dump(service.repo.add_operator(Operator.create(payload.display_name)))
    @api.get("/api/v1/operators")
    def operators():return {"items":[{"internal_id":x.internal_id,"display_name":x.display_name} for x in service.repo.list_operators()]}
    @api.post("/api/v1/machining-types")
    def machining_type(code:str=Query(...),display_name:str=Query(...),display_order:int=Query(0)):
        return dump(service.repo.add_machining_type(MachiningType(uuid4(),code.upper(),display_name,True,display_order)))
    @api.get("/api/v1/machining-types")
    def machining_types():return {"items":[{"internal_id":x.internal_id,"code":x.code,"display_name":x.display_name} for x in service.repo.list_machining_types()]}
    @api.get("/api/v1/operators/{user_id}/preference")
    def get_pref(user_id:UUID):return {"machining_type_id":service.repo.get_preference(user_id)}
    @api.put("/api/v1/operators/{user_id}/preference")
    def set_pref(user_id:UUID,payload:PreferenceSet):service.repo.set_preference(user_id,payload.machining_type_id);return {"machining_type_id":payload.machining_type_id}
    @api.get("/api/v1/tracking-items/{item_id}/attempt-display")
    def attempt_display(item_id:UUID,machining_type_id:UUID=Query(...)):return {"max_visible_attempt":service.repo.get_attempt_max(item_id,machining_type_id)}
    @api.post("/api/v1/tracking-items/{item_id}/attempt-display/expand")
    def expand(item_id:UUID,payload:AttemptExpand):return {"max_visible_attempt":service.repo.expand_attempt(item_id,payload.machining_type_id,payload.new_max,payload.user_id)}
    @api.post("/api/v1/process-reports")
    def report(payload:ReportSubmit):return dump(service.submit_report(**payload.model_dump()))
    @api.get("/api/v1/tracking-items/{item_id}/process-reports")
    def history(item_id:UUID):return {"items":[dump(x) for x in service.repo.history(item_id)]}
    @api.post("/api/v1/process-reports/{event_id}/revisions")
    def revise(event_id:UUID,payload:ReportRevision):
        event=service.repo.get_report(event_id)
        return dump(service.revise_report(event,**payload.model_dump()))
    def submit_workflow(item_id:UUID,payload:WorkflowEventSubmit,target):
        data=payload.model_dump();data["tracking_item_id"]=item_id;return dump(target.submit(**data))
    @api.post("/api/v1/tracking-items/{item_id}/qc-events")
    def qc_event(item_id:UUID,payload:WorkflowEventSubmit):return submit_workflow(item_id,payload,qc_service)
    @api.post("/api/v1/tracking-items/{item_id}/packing-events")
    def packing_event(item_id:UUID,payload:WorkflowEventSubmit):return submit_workflow(item_id,payload,packing_service)
    @api.post("/api/v1/tracking-items/{item_id}/delivery-events")
    def delivery_event(item_id:UUID,payload:WorkflowEventSubmit):return submit_workflow(item_id,payload,delivery_service)
    @api.post("/api/v1/tracking-items/{item_id}/reports")
    def general_report(item_id:UUID,payload:WorkflowEventSubmit):return submit_workflow(item_id,payload,general_service)
    @api.get("/api/v1/tracking-items/{item_id}/workflow-summary")
    def workflow_summary(item_id:UUID):return history_service.summary(item_id)
    @api.get("/api/v1/tracking-items/{item_id}/history")
    def combined_history(item_id:UUID):return {"items":list(history_service.history(item_id))}
    @api.post("/api/v1/workflow-events/{event_id}/revisions")
    def revise_workflow(event_id:UUID,payload:WorkflowEventRevision):
        original=workflow_repo.get(event_id);target={WorkflowEventType.PACKED:packing_service,WorkflowEventType.DELIVERED:delivery_service,WorkflowEventType.GENERAL_REPORT:general_service}.get(original.event_type,qc_service)
        return dump(target.revise(event_id,**payload.model_dump()))
    return api


def _error(code: int, error_code: str, message: str, details: dict[str, str] | None = None):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=code, content={"error": {"code": error_code, "message": message, "details": details or {}}})


app = build_api()
tracking_api = build_tracking_api()
app.mount("/tracking", tracking_api)

__all__ = ["APP_NAME", "app", "build_api", "build_tracking_api", "create_app", "tracking_api"]
