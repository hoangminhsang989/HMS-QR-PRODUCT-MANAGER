"""Versioned FastAPI boundary for Product Master."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import os
from pathlib import Path
import re
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from config.environments import AppConfig, Environment, load_config
from packages.application.product_service import ProductService
from packages.contracts.api import ProductPageResponse, ProductPatch, ProductPayload, ProductResponse, to_response
from packages.domain.product import ProductStatus, ProductValidationError
from packages.domain.stage2 import DeliveryScheduleEntry, POStatus, RunStatus, Stage2ValidationError, now_utc
from packages.domain.repository import DuplicateProductCode, ProductConflict, ProductNotFound
from packages.persistence.sqlalchemy_product_repository import SqlAlchemyProductRepository
from packages.persistence.database import (
    DatabaseRuntime,
    create_database_runtime,
    database_schema_readiness,
    require_database_ready,
    require_database_schema_current,
    sqlite_path,
)
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
from apps.server.files import build_files_api, require_production_storage_ready
from apps.server.admin import admin_page, build_admin_api
from packages.application.server_discovery import DiscoveryResponder
from packages.application.server_auth import AuthenticationError, ServerAuthService, UserRole

APP_NAME = "hms-qr-server"


from fastapi import WebSocket, WebSocketDisconnect

class WebSocketHub:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, payload: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(ws)

ws_hub = WebSocketHub()


def create_app() -> dict[str, str]:
    """Preserve the Stage 0 import descriptor contract."""
    return {"name": APP_NAME, "status": "foundation"}


def require_sqlite_legacy_endpoint(config: AppConfig) -> None:
    """Keep incomplete SQLite-only portal features out of PostgreSQL deployments."""
    if config.environment is not Environment.DEV:
        raise HTTPException(
            status_code=501,
            detail={
                "code": "SQLITE_LEGACY_ENDPOINT_UNSUPPORTED",
                "message": "Chức năng portal này chưa hỗ trợ PostgreSQL server.",
            },
        )


def cors_origins_from_environment() -> tuple[str, ...]:
    """Read the cross-origin allowlist from ``HMS_QR_CORS_ORIGINS``.

    Empty by default: a LAN-only deployment stays same-origin, exactly as before.
    Set the variable to the Vercel deployment origin (comma-separated for several)
    to let that frontend call this server through the tunnel.

    Separators are commas *and* newlines, because the launcher reads the list out
    of a text file where one origin per line is the natural way to write it.
    Splitting on commas alone would turn a two-line file into a single origin
    containing an embedded newline, which matches nothing and silently locks the
    first frontend out.
    """

    raw = os.environ.get("HMS_QR_CORS_ORIGINS", "")
    return tuple(
        origin.strip()
        for origin in re.split(r"[,\r\n]", raw)
        if origin.strip()
    )


def apply_cors(api: FastAPI) -> None:
    """Allow only explicitly configured origins; never a wildcard."""

    origins = cors_origins_from_environment()
    if not origins:
        return
    api.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Actor"],
        max_age=600,
    )


def build_api(
    service: ProductService | None = None,
    *,
    app_config: AppConfig | None = None,
    database_runtime: DatabaseRuntime | None = None,
) -> FastAPI:
    api = FastAPI(title="HMS QR Product Manager", version="1.0")
    apply_cors(api)
    if service is None:
        config = app_config or load_config()
        runtime = database_runtime or create_database_runtime(config)
        repository = SqlAlchemyProductRepository(runtime)
        service = ProductService(repository)
    else:
        runtime = database_runtime

    if runtime is not None:
        @api.get("/health/readiness/database")
        def database_readiness():
            result = runtime.readiness()
            if result["state"] != "READY":
                raise HTTPException(
                    status_code=503,
                    detail={"code": "DATABASE_UNAVAILABLE", "message": "Database is unavailable."},
                )
            schema = database_schema_readiness(runtime)
            if schema["state"] not in {"READY", "NOT_REQUIRED"}:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "code": "DATABASE_SCHEMA_UNAVAILABLE",
                        "message": "Database schema is unavailable or not at the deployed migration revision.",
                    },
                )
            result["schema"] = schema["state"]
            return result

    auth = ServerAuthService(runtime) if runtime is not None else None

    def current_principal(authorization: Annotated[str | None, Header()] = None) -> dict[str, str] | None:
        if auth is None:
            return None
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail={"code": "AUTHENTICATION_REQUIRED", "message": "Cần đăng nhập."})
        try:
            return auth.authenticate(authorization.removeprefix("Bearer ").strip())
        except AuthenticationError as exc:
            raise HTTPException(status_code=401, detail={"code": "AUTHENTICATION_INVALID", "message": str(exc)}) from None

    def current_actor(principal: dict[str, str] | None = Depends(current_principal),
                      x_actor: Annotated[str | None, Header()] = None) -> str:
        if principal is not None:
            if principal["role"] not in {UserRole.ADMIN.value, UserRole.EDITOR.value}:
                raise HTTPException(status_code=403, detail={"code": "PRODUCT_WRITE_FORBIDDEN", "message": "Tài khoản chỉ có quyền xem dữ liệu."})
            return principal["username"]
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

    @api.exception_handler(ProductConflict)
    async def conflict_error(_, exc: ProductConflict):
        return _error(409, "PRODUCT_CONFLICT", str(exc))

    @api.exception_handler(ProductNotFound)
    async def not_found_error(_, exc: ProductNotFound):
        return _error(404, "PRODUCT_NOT_FOUND", f"Không tìm thấy sản phẩm: {exc}")

    @api.post("/api/v1/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
    def create_product(payload: ProductPayload, actor: str = Depends(current_actor)):
        data = payload.model_dump()
        return to_response(service.create_product(actor=actor, **data))

    @api.get("/api/v1/products", response_model=ProductPageResponse)
    def list_products(_principal: dict[str, str] | None = Depends(current_principal),
                      page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
                       search: str | None = None, status_filter: ProductStatus | None = Query(None, alias="status"),
                       sort_by: str = "updated_at", descending: bool = True,
                       delivery_start: date | None = None, delivery_end: date | None = None):
        result = service.list_products(page=page, page_size=page_size, search=search,
                                       status=status_filter, sort_by=sort_by, descending=descending,
                                       delivery_start=delivery_start, delivery_end=delivery_end)
        return ProductPageResponse(items=[to_response(p) for p in result.items], total=result.total,
                                    page=result.page, page_size=result.page_size)

    @api.get("/api/v1/products/{identifier}", response_model=ProductResponse)
    def get_product(identifier: str):
        return to_response(service.get_product(identifier))

    @api.patch("/api/v1/products/{identifier}", response_model=ProductResponse)
    def update_product(identifier: str, payload: ProductPatch, actor: str = Depends(current_actor)):
        changes = payload.model_dump(exclude_unset=True)
        if runtime is not None and "expected_updated_at" not in changes:
            raise HTTPException(422, detail={"code": "PRODUCT_VERSION_REQUIRED", "message": "Cần phiên bản sản phẩm trước khi cập nhật."})
        return to_response(service.update_product(identifier, actor=actor, **changes))

    return api


def build_stage2_api(
    service: Stage2Service | None = None,
    *,
    app_config: AppConfig | None = None,
    database_runtime: DatabaseRuntime | None = None,
) -> FastAPI:
    api = FastAPI(title="HMS QR Product Manager Stage 2", version="2.0")
    runtime = database_runtime
    if service is None:
        cfg = app_config or load_config()
        runtime = database_runtime or create_database_runtime(cfg)
        service = Stage2Service(Stage2Repository(runtime))
    auth = ServerAuthService(runtime) if runtime is not None else None

    def principal(authorization: Annotated[str | None, Header()] = None) -> dict[str, str] | None:
        if auth is None:
            return None
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, detail={"code": "AUTHENTICATION_REQUIRED", "message": "Cần đăng nhập."})
        try:
            return auth.authenticate(authorization.removeprefix("Bearer ").strip())
        except AuthenticationError as exc:
            raise HTTPException(401, detail={"code": "AUTHENTICATION_INVALID", "message": str(exc)}) from None

    def actor(current: dict[str, str] | None = Depends(principal),
              x_actor: Annotated[str | None, Header()] = None) -> str:
        if current is not None:
            if current["role"] not in {UserRole.ADMIN.value, UserRole.EDITOR.value}:
                raise HTTPException(403, detail={"code": "STAGE2_WRITE_FORBIDDEN", "message": "Tài khoản chỉ có quyền xem dữ liệu."})
            return current["username"]
        return (x_actor or "development-user").strip()

    if auth is not None:
        api.router.dependencies.append(Depends(principal))
    @api.exception_handler(Stage2ValidationError)
    async def stage2_validation(_, exc): return _error(422, "VALIDATION_ERROR", exc.message, {"field": exc.field})
    @api.exception_handler(ValueError)
    async def stage2_value(_, exc): return _error(409, "BUSINESS_CONFLICT", str(exc))
    @api.exception_handler(LookupError)
    async def stage2_missing(_, exc): return _error(404, "NOT_FOUND", str(exc))
    @api.post("/api/v1/customers")
    def create_customer(payload: CustomerPayload, current_actor: str = Depends(actor)):
        return dump(service.create_customer(actor=current_actor, **payload.model_dump()))
    @api.get("/api/v1/customers")
    def list_customers(search: str|None=None, active: bool|None=None, page: int=Query(1,ge=1), page_size: int=Query(50,ge=1,le=200)):
        items,total=service.list_customers(search=search,active=active,page=page,page_size=page_size); return {"items":[dump(x) for x in items],"total":total,"page":page,"page_size":page_size}
    @api.get("/api/v1/customers/{identifier}")
    def get_customer(identifier: str): return dump(service.get_customer(identifier))
    @api.patch("/api/v1/customers/{identifier}")
    def update_customer(identifier: str,payload: CustomerPatch,current_actor: str=Depends(actor)): return dump(service.update_customer(identifier,actor=current_actor,**payload.model_dump(exclude_unset=True)))
    @api.post("/api/v1/purchase-orders")
    def create_po(payload: POData,current_actor: str=Depends(actor)): return dump(service.create_po(actor=current_actor,**payload.model_dump()))
    @api.get("/api/v1/purchase-orders")
    def list_pos(customer_id: UUID|None=None,status_filter: POStatus|None=Query(None,alias="status")): return {"items":[dump(x) for x in service.list_pos(customer_id=customer_id,status=status_filter)]}
    @api.get("/api/v1/purchase-orders/{identifier}")
    def get_po(identifier: str): return dump(service.get_po(identifier))
    @api.patch("/api/v1/purchase-orders/{identifier}")
    def update_po(identifier: str, payload: POData, current_actor: str=Depends(actor)):
        data=payload.model_dump(exclude_unset=True); data.pop("po_number",None); data.pop("customer_id",None); data.pop("po_date",None); return dump(service.update_po(identifier,actor=current_actor,**data))
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
        updated = DeliveryScheduleEntry(entry_id, po_line_id, payload.planned_date, payload.planned_quantity, payload.status, payload.notes, current.created_at, now_utc())
        return dump(service.update_delivery(updated, ordered_quantity=ordered_quantity))
    @api.post("/api/v1/production-runs")
    def create_run(payload: RunData,current_actor: str=Depends(actor)):
        data=payload.model_dump(); ordered=data.pop("ordered_quantity"); return dump(service.create_run(actor=current_actor,ordered_quantity=ordered,**data))
    @api.get("/api/v1/production-runs")
    def list_runs(po_line_id: UUID|None=None,status_filter: RunStatus|None=Query(None,alias="status")): return {"items":[dump(x) for x in service.list_runs(po_line_id=po_line_id,status=status_filter)]}
    @api.patch("/api/v1/production-runs/{run_id}")
    def update_run(run_id: UUID, payload: RunData, ordered_quantity: Decimal=Query(...,gt=0)):
        current = next((x for x in service.list_runs() if x.internal_id == run_id), None)
        if not current: raise HTTPException(404, "production run not found")
        updated = current.update(actor="api-user", **payload.model_dump(exclude={"po_line_id","product_id","ordered_quantity","run_code"}, exclude_unset=True))
        return dump(service.update_run(updated, ordered_quantity=ordered_quantity))
    return api

def build_tracking_api(service:TrackingService|None=None,*,app_config:AppConfig|None=None,database_runtime:DatabaseRuntime|None=None)->FastAPI:
    runtime = database_runtime
    api=FastAPI(title="HMS QR Tracking",version="3.0")
    if service is None:
        cfg=app_config or load_config();runtime=database_runtime or create_database_runtime(cfg);repo=Stage2Repository(runtime)
        if cfg.environment is Environment.DEV:repo.create_schema()
        service=TrackingService(TrackingRepository(runtime))
    auth = ServerAuthService(runtime) if runtime is not None else None

    async def require_tracking_access(request: Request, authorization: Annotated[str | None, Header()] = None) -> None:
        if auth is None:
            return
        # The page itself must stay reachable: it carries the login form, so
        # gating it behind authentication would leave no way to sign in.
        if request.url.path.rstrip("/").endswith("/mobile"):
            return
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, detail={"code": "AUTHENTICATION_REQUIRED", "message": "Cần đăng nhập."})
        try:
            principal = auth.authenticate(authorization.removeprefix("Bearer ").strip())
        except AuthenticationError as exc:
            raise HTTPException(401, detail={"code": "AUTHENTICATION_INVALID", "message": str(exc)}) from None
        if request.method not in {"GET", "HEAD", "OPTIONS"} and principal["role"] not in {UserRole.ADMIN.value, UserRole.EDITOR.value}:
            raise HTTPException(403, detail={"code": "TRACKING_WRITE_FORBIDDEN", "message": "Tài khoản chỉ có quyền xem theo dõi."})

    workflow_repo=WorkflowRepository(service.repo.database);qc_service=QcService(workflow_repo);packing_service=PackingService(workflow_repo);delivery_service=DeliveryService(workflow_repo);general_service=GeneralReportService(workflow_repo);history_service=TrackingHistoryService(workflow_repo,service.repo)
    if auth is not None:
        api.router.dependencies.append(Depends(require_tracking_access))
    _existing_types={mt.code for mt in service.repo.list_machining_types()}
    for order,(code,name) in enumerate((("BLANK","TẠO PHÔI"),("TURN","TIỆN"),("MILL","PHAY"),("WIRE","CẮT DÂY"),("GRIND","MÀI"),("HEAT","NHIỆT LUYỆN"),("OTHER","KHÁC")),1):
        if code not in _existing_types:service.repo.add_machining_type(MachiningType(uuid4(),code,name,True,order))
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
    async def report(payload:ReportSubmit):
        res = dump(service.submit_report(**payload.model_dump()))
        try: await ws_hub.broadcast({"type": "PROCESS_REPORT", "payload": res})
        except Exception: pass
        return res
    @api.get("/api/v1/tracking-items/{item_id}/process-reports")
    def history(item_id:UUID):return {"items":[dump(x) for x in service.repo.history(item_id)]}
    @api.post("/api/v1/process-reports/{event_id}/revisions")
    def revise(event_id:UUID,payload:ReportRevision):
        event=service.repo.get_report(event_id)
        return dump(service.revise_report(event,**payload.model_dump()))
    async def submit_workflow(item_id:UUID,payload:WorkflowEventSubmit,target):
        data=payload.model_dump();data["tracking_item_id"]=item_id;res=dump(target.submit(**data))
        try: await ws_hub.broadcast({"type": "WORKFLOW_EVENT", "payload": res})
        except Exception: pass
        return res
    @api.post("/api/v1/tracking-items/{item_id}/qc-events")
    async def qc_event(item_id:UUID,payload:WorkflowEventSubmit):return await submit_workflow(item_id,payload,qc_service)
    @api.post("/api/v1/tracking-items/{item_id}/packing-events")
    async def packing_event(item_id:UUID,payload:WorkflowEventSubmit):return await submit_workflow(item_id,payload,packing_service)
    @api.post("/api/v1/tracking-items/{item_id}/delivery-events")
    async def delivery_event(item_id:UUID,payload:WorkflowEventSubmit):return await submit_workflow(item_id,payload,delivery_service)
    @api.post("/api/v1/tracking-items/{item_id}/reports")
    async def general_report(item_id:UUID,payload:WorkflowEventSubmit):return await submit_workflow(item_id,payload,general_service)
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


SERVER_APP_CONFIG = load_config()
SERVER_DATABASE_RUNTIME = create_database_runtime(SERVER_APP_CONFIG)
if SERVER_APP_CONFIG.environment is not Environment.DEV:
    require_database_ready(SERVER_DATABASE_RUNTIME)
    require_database_schema_current(SERVER_DATABASE_RUNTIME)
    server_auth = ServerAuthService(SERVER_DATABASE_RUNTIME)
    server_auth.require_production_configuration()
    server_auth.bootstrap_admin()
    require_production_storage_ready(SERVER_APP_CONFIG)
app = build_api(app_config=SERVER_APP_CONFIG, database_runtime=SERVER_DATABASE_RUNTIME)
discovery_responder = DiscoveryResponder()


@app.on_event("startup")
def start_lan_discovery() -> None:
    discovery_responder.start()


@app.on_event("shutdown")
def stop_lan_discovery() -> None:
    discovery_responder.stop()
tracking_api = build_tracking_api(app_config=SERVER_APP_CONFIG, database_runtime=SERVER_DATABASE_RUNTIME)
app.mount("/tracking", tracking_api)
files_api = build_files_api(
    app_config=SERVER_APP_CONFIG,
    start_worker=True,
    database_runtime=SERVER_DATABASE_RUNTIME,
    auth_service=ServerAuthService(SERVER_DATABASE_RUNTIME),
)
app.mount("/files", files_api)
admin_api = build_admin_api(SERVER_APP_CONFIG, SERVER_DATABASE_RUNTIME)
app.mount("/admin-api", admin_api)
stage2_api = build_stage2_api(app_config=SERVER_APP_CONFIG, database_runtime=SERVER_DATABASE_RUNTIME)
app.mount("/stage2", stage2_api)

from apps.server.portal import get_live_events, get_public_tunnel_url, get_local_ip, portal_page
from apps.server.tls import lan_url_scheme
from fastapi.responses import RedirectResponse

@app.get("/", response_class=HTMLResponse)
def index_portal():
    return portal_page()


@app.get("/admin", response_class=HTMLResponse)
def server_admin():
    return admin_page()

@app.get("/mobile")
def redirect_mobile():
    return RedirectResponse(url="/tracking/mobile", status_code=302)

@app.get("/api/v1/live-feed")
def live_feed():
    return {"events": get_live_events()}

@app.get("/api/v1/tunnel-status")
def tunnel_status():
    url = get_public_tunnel_url()
    local_ip = get_local_ip()
    mobile_url = f"{url}/tracking/mobile" if url else None
    lan_url = f"{lan_url_scheme()}://{local_ip}:8000/tracking/mobile"
    return {
        "tunnel_url": url,
        "mobile_url": mobile_url,
        "lan_url": lan_url,
        "active": url is not None,
    }

from packages.excel.factory_adapter import (
    FACTORY_EXCEL_ROOT,
    list_factory_files,
    parse_factory_sheet,
    parse_factory_tsv,
    import_factory_items_to_db,
)
from pydantic import BaseModel

class ExcelSheetRequest(BaseModel):
    filename: str
    sheet: str | None = None

class ExcelPasteRequest(BaseModel):
    tsv: str
    po_prefix: str | None = "PO-DAN"


def factory_excel_path(filename: str) -> Path:
    root = Path(FACTORY_EXCEL_ROOT).resolve()
    candidate = (root / filename).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Tên tệp Excel không hợp lệ.") from exc
    return candidate

@app.get("/api/v1/excel/files")
def excel_files():
    return {"files": list_factory_files()}

@app.post("/api/v1/excel/preview")
def excel_preview(req: ExcelSheetRequest):
    file_path = factory_excel_path(req.filename)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Tệp {req.filename} không tồn tại.")
    items = parse_factory_sheet(str(file_path), req.sheet)
    companies = sorted(list({x["company"] for x in items if x.get("company")}))
    materials = sorted(list({x["material"] for x in items if x.get("material")}))
    total_qty = sum(x.get("quantity", 0) for x in items)
    return {
        "filename": req.filename,
        "sheet": req.sheet,
        "total_items": len(items),
        "total_quantity": total_qty,
        "companies": companies,
        "materials": materials,
        "items": items[:60],
    }

@app.post("/api/v1/excel/import")
async def excel_import(req: ExcelSheetRequest):
    require_sqlite_legacy_endpoint(SERVER_APP_CONFIG)
    file_path = factory_excel_path(req.filename)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Tệp {req.filename} không tồn tại.")
    items = parse_factory_sheet(str(file_path), req.sheet)
    if not items:
        raise HTTPException(status_code=400, detail="Không tìm thấy chi tiết hợp lệ để nhập.")
    db = sqlite_path(SERVER_APP_CONFIG.database_url)
    po_prefix = f"PO-{req.sheet.replace('-', '')}" if req.sheet else "PO-EXCEL"
    result = import_factory_items_to_db(items, str(db), po_prefix=po_prefix)
    try:
        await ws_hub.broadcast({"type": "EXCEL_IMPORT", "payload": result})
    except Exception:
        pass
    return result

@app.post("/api/v1/excel/paste-preview")
def excel_paste_preview(req: ExcelPasteRequest):
    items = parse_factory_tsv(req.tsv)
    if not items:
        raise HTTPException(status_code=400, detail="Không tìm thấy dòng dữ liệu hợp lệ trong nội dung dán.")
    companies = sorted(list({x["company"] for x in items if x.get("company")}))
    materials = sorted(list({x["material"] for x in items if x.get("material")}))
    total_qty = sum(x.get("quantity", 0) for x in items)
    return {
        "total_items": len(items),
        "total_quantity": total_qty,
        "companies": companies,
        "materials": materials,
        "items": items[:100],
    }

@app.post("/api/v1/excel/paste-import")
async def excel_paste_import(req: ExcelPasteRequest):
    require_sqlite_legacy_endpoint(SERVER_APP_CONFIG)
    items = parse_factory_tsv(req.tsv)
    if not items:
        raise HTTPException(status_code=400, detail="Không tìm thấy dòng dữ liệu hợp lệ để nhập.")
    db = sqlite_path(SERVER_APP_CONFIG.database_url)
    po_prefix = req.po_prefix or "PO-DAN"
    result = import_factory_items_to_db(items, str(db), po_prefix=po_prefix)
    try:
        await ws_hub.broadcast({"type": "EXCEL_IMPORT", "payload": result})
    except Exception:
        pass
    return result

@app.get("/api/v1/qr-catalog")
def qr_catalog(search: str | None = None, limit: int = 150):
    require_sqlite_legacy_endpoint(SERVER_APP_CONFIG)
    from packages.qr.payload import QrPayload
    from packages.qr.service import QRService

    # The engine's join merges rows by column name, and both tables carry
    # ``internal_id``, so the joined table's value would overwrite the tracking
    # item's. The lookup is therefore resolved in Python, as in the portal.
    database = SERVER_DATABASE_RUNTIME.database
    items = database.query(
        "SELECT internal_id, tracking_code, quantity, unit, status, delivery_date,"
        " product_id, customer_id FROM order_tracking_items"
    )
    products = {
        row["internal_id"]: row
        for row in database.query(
            "SELECT internal_id, part_name, product_code, company, material, size,"
            " surface_treatment FROM products"
        )
    }
    # The QR contract's customer_name is the customer record's name - the same
    # source TrackingService.qr_payload reads, so a payload rendered here decodes
    # and matches what scan() verifies. Reading products.company instead made the
    # catalog disagree with the issued QR, and because company is optional on a
    # product, an empty one raised inside encode() and took the whole endpoint
    # down with a 500 rather than skipping the one item.
    customers = {
        row["internal_id"]: row
        for row in database.query("SELECT internal_id, name FROM customers")
    }
    if search:
        term = f"%{search.strip()}%"
        lowered = term.lower()
        items = [
            item
            for item in items
            if lowered in str(item["tracking_code"] or "").lower()
            or lowered in str(products.get(item["product_id"], {}).get("part_name") or "").lower()
            or lowered in str(products.get(item["product_id"], {}).get("product_code") or "").lower()
            or lowered in str(products.get(item["product_id"], {}).get("company") or "").lower()
        ]
    # ``ORDER BY rowid`` is a no-op on the engine, so newest-first is restored here.
    items = list(reversed(items))[:limit]

    qr_svc = QRService()
    catalog = []
    for item in items:
        product = products.get(item["product_id"])
        customer = customers.get(item["customer_id"])
        if product is None or customer is None:
            continue
        try:
            p = QrPayload(product["part_name"], customer["name"], product["product_code"], item["tracking_code"])
            uri, enc = qr_svc.data_uri(p)
        except TrackingError:
            # An item whose identity is incomplete cannot produce a scannable QR,
            # so it does not belong in a picker whose whole job is handing out
            # scannable codes. Skipping it keeps one bad row from failing the
            # entire catalog.
            continue
        raw_qty = item["quantity"]
        try:
            fq = float(raw_qty)
            clean_qty = str(int(fq)) if fq.is_integer() else f"{fq:g}"
        except Exception:
            clean_qty = str(raw_qty)
        catalog.append({
            "internal_id": item["internal_id"],
            "tracking_code": item["tracking_code"],
            "product_code": product["product_code"],
            "part_name": product["part_name"],
            "company": product["company"],
            "quantity": clean_qty,
            "unit": item["unit"],
            "material": product["material"] or "",
            "size": product["size"] or "",
            "surface_treatment": product["surface_treatment"] or "",
            "delivery_date": str(item["delivery_date"] or ""),
            "status": item["status"],
            "qr_data_uri": uri,
            "qr_payload": enc,
        })
    return {"total": len(catalog), "items": catalog}

@app.get("/api/v1/export/excel")
def export_excel():
    require_sqlite_legacy_endpoint(SERVER_APP_CONFIG)
    from fastapi.responses import Response
    from packages.excel.export_report import generate_production_excel_report
    db = sqlite_path(SERVER_APP_CONFIG.database_url)
    bio = generate_production_excel_report(str(db))
    filename = f"HMS_BAO_CAO_SAN_XUAT_{date.today().strftime('%Y%m%d')}.xlsx"
    return Response(
        content=bio.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import UploadFile, File, WebSocket, WebSocketDisconnect
from packages.qr.cv_scanner import decode_qr_image

static_dir = Path(__file__).resolve().parents[1] / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/manifest.json")
def pwa_manifest():
    p = static_dir / "manifest.json"
    return FileResponse(str(p), media_type="application/manifest+json")

@app.get("/sw.js")
def pwa_sw():
    p = static_dir / "sw.js"
    return FileResponse(str(p), media_type="application/javascript")

@app.post("/api/v1/scan-image")
async def scan_image(file: UploadFile = File(...)):
    data = await file.read()
    res = decode_qr_image(data)
    if not res.get("success"):
        raise HTTPException(status_code=422, detail=res.get("error", "Không thể nhận diện mã QR"))
    return res

@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await ws_hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except (WebSocketDisconnect, Exception):
        ws_hub.disconnect(ws)

__all__ = ["APP_NAME", "SERVER_APP_CONFIG", "SERVER_DATABASE_RUNTIME", "app", "build_api", "build_tracking_api", "create_app", "tracking_api", "files_api", "admin_api", "index_portal", "server_admin", "redirect_mobile", "live_feed", "excel_files", "excel_preview", "excel_import", "excel_paste_preview", "excel_import", "excel_paste_import", "qr_catalog", "export_excel", "pwa_manifest", "pwa_sw", "scan_image", "ws_live", "ws_hub"]
