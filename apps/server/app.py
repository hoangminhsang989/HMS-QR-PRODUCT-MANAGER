"""Versioned FastAPI boundary for Product Master."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status

from config.environments import load_config
from packages.application.product_service import ProductService
from packages.contracts.api import ProductPageResponse, ProductPatch, ProductPayload, ProductResponse, to_response
from packages.domain.product import ProductStatus, ProductValidationError
from packages.domain.repository import DuplicateProductCode, ProductNotFound
from packages.persistence.sqlite_product_repository import SQLiteProductRepository

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


def _error(code: int, error_code: str, message: str, details: dict[str, str] | None = None):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=code, content={"error": {"code": error_code, "message": message, "details": details or {}}})


app = build_api()

__all__ = ["APP_NAME", "app", "build_api", "create_app"]
