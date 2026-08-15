"""Path-free product image, attachment, and storage administration API."""

from __future__ import annotations

from dataclasses import asdict
import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime
from pathlib import Path
from typing import Annotated, Callable
from uuid import UUID, uuid4

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from config.environments import AppConfig, Environment
from packages.domain.attachments import ProductAttachment
from packages.domain.store_forward import StorageConfiguration
from packages.persistence.managed_file_repository import ManagedFileRepository
from packages.persistence.store_forward_repository import StoreForwardRepository
from packages.persistence.database import DatabaseRuntime, create_database_runtime
from packages.storage.managed_files import ManagedFileService
from packages.storage.service import FilesystemStorage, StorageUnavailable, UnconfiguredStorage
from packages.storage.store_forward import LocalCapacityError, StoreForwardService


AdminAuthorizer = Callable[[Request], bool]


class RelationPatch(BaseModel):
    sort_order: int | None = Field(default=None, ge=0)
    caption: str | None = Field(default=None, max_length=512)


class StorageConfigurationPayload(BaseModel):
    local_ingest_root: str = Field(min_length=3, max_length=2048)
    archive_target_root: str = Field(min_length=3, max_length=2048)
    grace_period_hours: int = Field(default=24, ge=0, le=168)
    retry_schedule_seconds: tuple[int, ...] = (60, 300, 900, 1800, 3600)
    warning_free_bytes: int = Field(default=10 * 1024**3, ge=0)
    critical_free_bytes: int = Field(default=5 * 1024**3, ge=0)
    upload_refusal_free_bytes: int = Field(default=2 * 1024**3, ge=0)


def build_files_api(
    managed_service: ManagedFileService | None = None,
    transfer_service: StoreForwardService | None = None,
    *,
    app_config: AppConfig,
    admin_authorizer: AdminAuthorizer | None = None,
    start_worker: bool = False,
    database_runtime: DatabaseRuntime | None = None,
) -> FastAPI:
    if managed_service is None or transfer_service is None:
        managed_service, transfer_service = _default_services(
            app_config, database_runtime=database_runtime
        )

    @asynccontextmanager
    async def lifespan(_api):
        task = asyncio.create_task(_worker_loop(transfer_service)) if start_worker else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    api = FastAPI(
        title="HMS QR Managed Files", version="6.009",
        lifespan=lifespan,
    )

    def actor(x_actor: Annotated[str | None, Header()] = None) -> str:
        value = (x_actor or "development-user").strip()
        if not value:
            raise HTTPException(400, "Actor is required")
        return value

    def storage_admin(
        request: Request,
        x_storage_admin: Annotated[str | None, Header()] = None,
    ) -> None:
        if app_config.environment is Environment.DEV:
            if (x_storage_admin or "").strip().lower() not in {"1", "true", "yes"}:
                raise HTTPException(
                    status_code=403,
                    detail={"code": "DEV_STORAGE_ADMIN_REQUIRED", "message": "Quyền quản trị lưu trữ là bắt buộc."},
                )
            return
        if admin_authorizer is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "PRODUCTION_ADMIN_AUTH_NOT_CONFIGURED",
                    "message": "Tích hợp xác thực quản trị chưa được cấu hình.",
                },
            )
        try:
            authorized = bool(admin_authorizer(request))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "ADMIN_AUTHORIZATION_UNAVAILABLE",
                    "message": "Không thể xác minh quyền quản trị.",
                },
            ) from exc
        if not authorized:
            raise HTTPException(
                status_code=403,
                detail={"code": "STORAGE_ADMIN_FORBIDDEN", "message": "Không có quyền quản trị lưu trữ."},
            )

    @api.exception_handler(LocalCapacityError)
    async def capacity_error(_, exc):
        return _json_error(507, "LOCAL_CAPACITY_UNSAFE", str(exc))

    @api.exception_handler(StorageUnavailable)
    async def storage_unavailable_error(_, _exc):
        return _json_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "STORAGE_UNAVAILABLE",
            "Tệp hiện chưa thể truy cập do vị trí lưu trữ tạm thời không khả dụng.",
        )

    @api.exception_handler(LookupError)
    async def missing_error(_, exc):
        return _json_error(404, "NOT_FOUND", str(exc))

    @api.exception_handler(ValueError)
    async def value_error(_, exc):
        return _json_error(422, "INVALID_REQUEST", str(exc))

    @api.post("/api/v1/products/{product_id}/images", status_code=status.HTTP_201_CREATED)
    def upload_image(
        product_id: UUID,
        content: bytes = Body(..., media_type="application/octet-stream"),
        filename: str = Query(..., min_length=1, max_length=512),
        declared_mime: str = Query(..., min_length=3, max_length=255),
        caption: str | None = Query(default=None, max_length=512),
        sort_order: int = Query(default=0, ge=0),
        make_primary: bool = False,
        replaces_file_id: UUID | None = None,
        current_actor: str = Depends(actor),
    ):
        item = managed_service.upload_product_image(
            product_id=product_id, original_filename=filename,
            declared_mime=declared_mime, content=content, actor=current_actor,
            caption=caption, sort_order=sort_order, make_primary=make_primary,
            replaces_file_id=replaces_file_id,
        )
        return _file_response(item, transfer_service)

    @api.get("/api/v1/products/{product_id}/images")
    def list_images(product_id: UUID):
        return {"items": [
            _file_response(item, transfer_service)
            for item in managed_service.repository.list_images(product_id)
        ]}

    @api.post("/api/v1/products/{product_id}/attachments", status_code=status.HTTP_201_CREATED)
    def upload_attachment(
        product_id: UUID,
        content: bytes = Body(..., media_type="application/octet-stream"),
        filename: str = Query(..., min_length=1, max_length=512),
        declared_mime: str = Query(..., min_length=3, max_length=255),
        category: str = Query(default="OTHER", min_length=1, max_length=64),
        caption: str | None = Query(default=None, max_length=512),
        sort_order: int = Query(default=0, ge=0),
        replaces_file_id: UUID | None = None,
        current_actor: str = Depends(actor),
    ):
        item = managed_service.upload_attachment(
            product_id=product_id, original_filename=filename,
            declared_mime=declared_mime, content=content, actor=current_actor,
            attachment_category=category, caption=caption, sort_order=sort_order,
            replaces_file_id=replaces_file_id,
        )
        return _file_response(item, transfer_service)

    @api.get("/api/v1/products/{product_id}/attachments")
    def list_attachments(product_id: UUID):
        return {"items": [
            _file_response(item, transfer_service)
            for item in managed_service.repository.list_attachments(product_id)
        ]}

    @api.get("/api/v1/files/{file_id}")
    def download_file(file_id: UUID):
        managed = managed_service.repository.get(file_id)
        content = managed_service.read(file_id)
        safe_name = managed.original_filename.replace('"', "")
        return Response(
            content=content,
            media_type=managed.media_type,
            headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
        )

    @api.get("/api/v1/files/{file_id}/status")
    def transfer_status(file_id: UUID):
        managed = managed_service.repository.get(file_id)
        return _status_response(managed, transfer_service)

    @api.post("/api/v1/products/{product_id}/images/{file_id}/primary")
    def set_primary(product_id: UUID, file_id: UUID):
        managed_service.set_primary_image(product_id=product_id, file_id=file_id)
        return {"file_id": str(file_id), "is_primary": True}

    @api.patch("/api/v1/products/{product_id}/files/{file_id}")
    def update_relation(product_id: UUID, file_id: UUID, payload: RelationPatch):
        relation = managed_service.update_relation(
            product_id=product_id, file_id=file_id,
            sort_order=payload.sort_order, caption=payload.caption,
        )
        return {
            "file_id": str(file_id), "sort_order": relation.sort_order,
            "caption": relation.caption,
        }

    @api.delete("/api/v1/files/{file_id}")
    def archive_relation(file_id: UUID, current_actor: str = Depends(actor)):
        managed = managed_service.archive(file_id=file_id, actor=current_actor)
        return {"file_id": str(file_id), "availability": managed.status.value}

    @api.post("/api/v1/admin/transfers/{file_id}/retry", dependencies=[Depends(storage_admin)])
    def retry_transfer(file_id: UUID):
        return _job_response(transfer_service.retry_now(file_id))

    @api.post("/api/v1/admin/transfers/run-once", dependencies=[Depends(storage_admin)])
    def run_once():
        job = transfer_service.transfer_one(worker_id="admin-manual")
        return {"processed": job is not None, "job": _job_response(job) if job else None}

    @api.post("/api/v1/admin/purge", dependencies=[Depends(storage_admin)])
    def purge_local():
        jobs = transfer_service.purge_ready_local_copies()
        return {"processed": len(jobs), "jobs": [_job_response(job) for job in jobs]}

    @api.get("/api/v1/admin/storage/configuration", dependencies=[Depends(storage_admin)])
    def get_configuration():
        config = transfer_service.repository.get_active_configuration()
        return _configuration_response(config)

    @api.put("/api/v1/admin/storage/configuration", dependencies=[Depends(storage_admin)])
    def set_configuration(payload: StorageConfigurationPayload, validate_write: bool = False):
        config = StorageConfiguration(
            configuration_id=uuid4(), **payload.model_dump(), active=True
        )
        return _configuration_response(
            transfer_service.configure(config, validate_write=validate_write)
        )

    @api.get("/api/v1/admin/storage/health", dependencies=[Depends(storage_admin)])
    def storage_health():
        health = transfer_service.health()
        capacity = asdict(health["capacity"])
        return {
            "local": health["local"], "archive": health["archive"],
            "capacity": capacity,
            "last_successful_transfer": _iso(health["last_successful_transfer"]),
        }

    return api


def _default_services(
    config: AppConfig,
    *,
    database_runtime: DatabaseRuntime | None = None,
) -> tuple[ManagedFileService, StoreForwardService]:
    runtime = database_runtime or create_database_runtime(config)
    repository = ManagedFileRepository(runtime)
    queue = StoreForwardRepository(runtime)
    local = (
        FilesystemStorage(config.storage_root, create_root=False)
        if config.storage_root else UnconfiguredStorage()
    )
    transfer = StoreForwardService(queue, repository, local)
    return ManagedFileService(repository, local, archive_coordinator=transfer), transfer


async def _worker_loop(transfer: StoreForwardService) -> None:
    """Bounded server worker; queue rows remain the authority across restarts."""

    while True:
        try:
            await asyncio.to_thread(transfer.reconcile)
            for _ in range(8):
                job = await asyncio.to_thread(transfer.transfer_one)
                if job is None:
                    break
            await asyncio.to_thread(transfer.purge_ready_local_copies)
        except Exception:
            # Unknown startup/runtime failures remain fail closed; the durable
            # queue is retried on the next bounded cycle without logging secrets.
            pass
        await asyncio.sleep(30)


def _file_response(item: ProductAttachment, transfer: StoreForwardService) -> dict[str, object]:
    managed = item.managed_file
    relation = item.relation
    response = {
        "file_id": str(managed.file_id),
        "original_filename": managed.original_filename,
        "category": managed.category,
        "media_type": managed.media_type,
        "size_bytes": managed.size_bytes,
        "availability": managed.status.value,
        "uploaded_at": _iso(managed.created_at),
        "uploaded_by": managed.created_by,
        "version": managed.version,
        "is_primary": relation.is_primary,
        "sort_order": relation.sort_order,
        "caption": relation.caption,
        "archive_status": transfer.status(managed.file_id).state.value,
    }
    return response


def _status_response(managed, transfer: StoreForwardService) -> dict[str, object]:
    job = transfer.status(managed.file_id)
    return {
        "file_id": str(managed.file_id),
        "availability": managed.status.value,
        "archive_status": job.state.value,
        "attempt_count": job.attempt_count,
        "next_retry_at": _iso(job.next_retry_at),
        "last_error_code": job.last_error_code,
        "last_error_summary": job.last_error_summary,
        "remote_verified_at": _iso(job.remote_verified_at),
        "grace_expires_at": _iso(job.grace_expires_at),
        "local_purged_at": _iso(job.local_purged_at),
    }


def _job_response(job) -> dict[str, object]:
    return {
        "job_id": str(job.job_id), "file_id": str(job.managed_file_id),
        "archive_status": job.state.value, "attempt_count": job.attempt_count,
        "next_retry_at": _iso(job.next_retry_at),
        "last_error_code": job.last_error_code,
    }


def _configuration_response(config: StorageConfiguration) -> dict[str, object]:
    # This response is only reachable through the storage-admin dependency.
    return {
        "configuration_id": str(config.configuration_id),
        "local_ingest_root": config.local_ingest_root,
        "archive_target_root": config.archive_target_root,
        "grace_period_hours": config.grace_period_hours,
        "retry_schedule_seconds": config.retry_schedule_seconds,
        "warning_free_bytes": config.warning_free_bytes,
        "critical_free_bytes": config.critical_free_bytes,
        "upload_refusal_free_bytes": config.upload_refusal_free_bytes,
    }


def _json_error(code: int, error_code: str, message: str):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=code,
        content={"error": {"code": error_code, "message": message}},
    )


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


__all__ = ["AdminAuthorizer", "build_files_api"]
