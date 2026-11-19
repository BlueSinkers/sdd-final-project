import logging
import time

from fastapi import FastAPI, Request

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("swaps")

app = FastAPI(title="swaps service")


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
        log.info("method=%s path=%s status=%s duration_ms=%.1f", request.method, request.url.path, status, ms)


@app.get("/health")
def health():
    return {"status": "ok", "service": "swaps"}
