"""Swaps service: application factory, request logging, health check."""

import logging
import sys
import time
from contextlib import asynccontextmanager, closing
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import db
from app.config import Settings, load_settings
from app.routes import router

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
log = logging.getLogger("swaps")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Bring this service's own schema up to date before serving any request.
        with closing(db.connect_with_retry(settings.database_url)) as conn:
            db.migrate(conn)
        yield
        app.state.pool.close()

    app = FastAPI(title="swaps service", version=settings.version, lifespan=lifespan)
    app.state.settings = settings
    app.state.pool = db.ConnectionPool(settings.database_url)
    app.include_router(router)

    @app.exception_handler(db.DatabaseError)
    async def database_unavailable(request: Request, error: Exception):
        # The cause goes to the log; the caller gets a clean message, never a stack trace.
        log.error("database error on %s %s: %s", request.method, request.url.path, error)
        return JSONResponse(status_code=503, content={"detail": "The swaps database is unavailable."})

    @app.exception_handler(db.IntegrityError)
    async def rejected_by_database(request: Request, error: Exception):
        # A value got past the API's validation but broke a database constraint.
        # That is a bad request, not an outage, so it must not look like one.
        log.error("constraint violation on %s %s: %s", request.method, request.url.path, error)
        return JSONResponse(status_code=422, content={"detail": "Those values were not accepted."})

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        except Exception:
            # Answered here, inside the CORS layer, so the browser can read the
            # response. The stack trace goes to the log, never to the caller.
            log.exception("unexpected error on %s %s", request.method, request.url.path)
            return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side."})
        finally:
            ms = (time.perf_counter() - start) * 1000
            # The path is percent-encoded again so a crafted URL with a line break
            # or spaces in it cannot write a fake request line into the log.
            log.info(
                "service=swaps method=%s path=%s status=%s duration_ms=%.1f",
                request.method,
                quote(request.url.path, safe="/-._~"),
                status,
                ms,
            )

    # Added last so it is the outermost layer: every response, errors included, carries
    # CORS headers. It also answers preflight (OPTIONS) requests itself.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.get("/health")
    def health():
        body = {"status": "ok", "service": "swaps", "version": settings.version}
        try:
            with closing(db.connect(settings.database_url)) as conn:
                db.ping(conn)
        except db.DatabaseError as error:
            log.error("health check failed: %s", error)
            return JSONResponse(status_code=503, content={**body, "status": "unavailable"})
        return body

    return app
