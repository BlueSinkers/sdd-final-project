"""Shared fixtures: a real SQL Server test database, emptied before every test.

TEST_DATABASE_URL points at a database the tests may drop and recreate, e.g.
mssql://sa:<password>@localhost:1433/listings_test. Tests never touch Azure SQL.
"""

import os
from contextlib import closing
from urllib.parse import unquote, urlparse

import pymssql
import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import Settings
from app.main import create_app


def recreate_database(database_url: str) -> None:
    """Drop and create the test database, so every run starts from migration 001."""
    url = urlparse(database_url)
    name = url.path.lstrip("/")
    assert name.endswith("_test"), "refusing to drop a database whose name does not end in _test"
    with closing(
        pymssql.connect(
            server=url.hostname,
            port=url.port or 1433,
            user=unquote(url.username),
            password=unquote(url.password),
            database="master",
            autocommit=True,  # CREATE/DROP DATABASE cannot run inside a transaction
        )
    ) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"IF DB_ID('{name}') IS NOT NULL BEGIN "
            f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; "
            f"DROP DATABASE [{name}]; END"
        )
        cursor.execute(f"CREATE DATABASE [{name}]")


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.exit("TEST_DATABASE_URL is not set; see 'Tests' in the README", 2)
    recreate_database(url)
    with closing(db.connect_with_retry(url, attempts=10)) as conn:
        db.migrate(conn)
    return url


@pytest.fixture
def conn(database_url):
    """A connection to a database with the schema applied and no listings."""
    conn = db.connect(database_url)
    with conn:
        conn.execute("DELETE FROM listings")
    yield conn
    conn.close()


@pytest.fixture
def client(database_url, conn):
    app = create_app(Settings(database_url=database_url, cors_origins=("http://localhost:8080",)))
    with TestClient(app) as client:
        yield client
