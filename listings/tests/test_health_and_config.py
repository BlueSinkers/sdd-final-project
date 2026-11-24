"""Health check, request logging and settings."""

import logging

import pytest

from app import db
from app.config import load_settings


def test_health_reports_ok_when_the_database_answers(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "listings", "version": "dev"}


def test_health_is_503_without_details_when_the_database_is_down(client, monkeypatch):
    def refuse(database_url):
        raise db.DatabaseError("login failed for user 'listings_user'")

    monkeypatch.setattr(db, "connect", refuse)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert "login failed" not in response.text


def test_every_request_logs_one_line(client, caplog):
    with caplog.at_level(logging.INFO, logger="listings"):
        client.get("/health")
    lines = [record.getMessage() for record in caplog.records if record.name == "listings"]
    assert len(lines) == 1
    assert lines[0].startswith("service=listings method=GET path=/health status=200 duration_ms=")


def test_cors_allows_only_the_configured_origin(client):
    allowed = client.get("/health", headers={"Origin": "http://localhost:8080"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:8080"
    other = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_settings_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mssql://u:p@host:1433/listings")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8080, https://example.org/ ,")
    monkeypatch.setenv("GIT_SHA", "abc1234")
    monkeypatch.setenv("AUTH_SECRET", "s" * 32)
    settings = load_settings()
    assert settings.database_url == "mssql://u:p@host:1433/listings"
    assert settings.cors_origins == ("http://localhost:8080", "https://example.org")
    assert settings.version == "abc1234"
    assert settings.auth_secret == "s" * 32


def test_missing_database_url_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        load_settings()


@pytest.mark.parametrize("secret", [None, "", "too-short"])
def test_missing_or_short_auth_secret_is_a_clear_error(monkeypatch, secret):
    monkeypatch.setenv("DATABASE_URL", "mssql://u:p@host:1433/db")
    if secret is None:
        monkeypatch.delenv("AUTH_SECRET", raising=False)
    else:
        monkeypatch.setenv("AUTH_SECRET", secret)
    with pytest.raises(RuntimeError, match="AUTH_SECRET"):
        load_settings()
