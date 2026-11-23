"""Listings service: application factory, request logging, health check."""

import logging
import time
from contextlib import asynccontextmanager, closing

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import db
from app.config import Settings, load_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("listings")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Bring this service's own schema up to date before serving any request.
        with closing(db.connect_with_retry(settings.database_url)) as conn:
            db.migrate(conn)
        yield

    app = FastAPI(title="listings service", version=settings.version, lifespan=lifespan)
    app.state.settings = settings

    @app.exception_handler(db.DatabaseError)
    async def database_unavailable(request: Request, error: Exception):
        # The cause goes to the log; the caller gets a clean message, never a stack trace.
        log.error("database error on %s %s: %s", request.method, request.url.path, error)
        return JSONResponse(status_code=503, content={"detail": "The listings database is unavailable."})

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            ms = (time.perf_counter() - start) * 1000
            log.info(
                "service=listings method=%s path=%s status=%s duration_ms=%.1f",
                request.method,
                request.url.path,
                status,
                ms,
            )

    # Added last so it is the outermost layer: error responses carry CORS headers too.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health():
        body = {"status": "ok", "service": "listings", "version": settings.version}
        try:
            with closing(db.connect(settings.database_url)) as conn:
                db.ping(conn)
        except db.DatabaseError as error:
            log.error("health check failed: %s", error)
            return JSONResponse(status_code=503, content={**body, "status": "unavailable"})
        return body

    return app
