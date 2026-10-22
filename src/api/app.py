import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from amazon_audit.cli import prepare_store
from amazon_audit.ingestion.csv_import import InvalidDataset
from amazon_audit.service import execute_audit
from platform_core.orchestration.runner import WorkflowError


class BodyLimitMiddleware:
    """Bound the entire request stream before multipart parsing can consume unlimited disk."""

    def __init__(self, app, max_bytes: int):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        try:
            declared = int(headers.get(b"content-length", b"0"))
            if declared < 0:
                raise ValueError
        except ValueError:
            return await JSONResponse({"detail": "Invalid content length"}, status_code=400)(
                scope, receive, send
            )
        if declared > self.max_bytes:
            return await JSONResponse({"detail": "Request too large"}, status_code=413)(scope, receive, send)
        consumed = 0

        async def limited_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get("body", b""))
            if consumed > self.max_bytes:
                raise StarletteHTTPException(413, "Request too large")
            return message

        await self.app(scope, limited_receive, send)


def create_app(database_url: str | None = None, max_upload_bytes: int | None = None) -> FastAPI:
    max_bytes = (
        max_upload_bytes
        if max_upload_bytes is not None
        else int(os.getenv("ENTREPRENEUR_MAX_UPLOAD_BYTES", "2097152"))
    )
    if max_bytes <= 0 or max_bytes > 20_971_520:
        raise ValueError("Upload limit must be between 1 and 20971520 bytes")

    @asynccontextmanager
    async def lifespan(app):
        app.state.store = prepare_store(database_url)
        yield
        app.state.store.engine.dispose()

    application = FastAPI(
        title="Autonomous Entrepreneur — Sprint 1",
        version="0.1.0",
        lifespan=lifespan,
        description="Synthetic-only local proof of concept. No customer authentication; bind to loopback.",
    )
    application.add_middleware(BodyLimitMiddleware, max_bytes=max_bytes + 65_536)

    @application.get("/health")
    def health(request: Request):
        from sqlalchemy import text

        with request.app.state.store.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "mode": "synthetic-local"}

    @application.post("/audits", status_code=201)
    async def audit(
        request: Request,
        file: Annotated[UploadFile, File(description="Normalized synthetic seller CSV")],
        business_id: Annotated[
            str, Query(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
        ] = "synthetic-demo",
        resume: UUID | None = None,
    ):
        try:
            if not file.filename or not file.filename.lower().endswith(".csv"):
                raise HTTPException(415, "Only .csv uploads are accepted")
            if file.content_type not in {
                "text/csv",
                "application/csv",
                "application/vnd.ms-excel",
                "application/octet-stream",
            }:
                raise HTTPException(415, "Unsupported CSV content type")
            chunks, size = [], 0
            while chunk := await file.read(65_536):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, "CSV exceeds upload limit")
                chunks.append(chunk)
            store = request.app.state.store
            try:
                run_id = await run_in_threadpool(
                    execute_audit,
                    store,
                    b"".join(chunks),
                    business_id,
                    str(resume) if resume else None,
                    max_bytes,
                )
            except WorkflowError as exc:
                if isinstance(exc.__cause__, InvalidDataset):
                    raise HTTPException(422, {"message": str(exc.__cause__), "run_id": exc.run_id}) from None
                raise HTTPException(
                    500, {"message": "Audit execution failed", "run_id": exc.run_id}
                ) from None
            except ValueError:
                raise HTTPException(
                    409, "Resume requires an inactive run with matching business and input"
                ) from None
            return {
                "run_id": run_id,
                "status": "completed",
                "result_path": f"/audits/{run_id}",
                "report_path": f"/audits/{run_id}/report",
            }
        finally:
            await file.close()

    @application.get("/audits/{run_id}")
    def result(run_id: UUID, request: Request):
        data = request.app.state.store.run(str(run_id))
        if data is None:
            raise HTTPException(404, "Execution not found")
        return data

    @application.get("/audits/{run_id}/report", response_class=HTMLResponse)
    def report(run_id: UUID, request: Request):
        html = request.app.state.store.report(str(run_id))
        if html is None:
            raise HTTPException(404, "Completed report not found")
        return HTMLResponse(
            html,
            headers={
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
            },
        )

    return application


logging.basicConfig(level=logging.INFO, format="%(message)s")
app = create_app()
