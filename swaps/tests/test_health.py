"""Health check and request logging."""

import logging

from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_ok():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "swaps"}


def test_every_request_logs_one_line(caplog):
    with caplog.at_level(logging.INFO, logger="swaps"):
        TestClient(app).get("/health")
    lines = [record.getMessage() for record in caplog.records if record.name == "swaps"]
    assert len(lines) == 1
    assert "path=/health status=200" in lines[0]
