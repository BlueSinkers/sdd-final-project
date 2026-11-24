"""The migration runner and connection helpers, against a real SQL Server."""

import pytest

from app import db


def test_migrations_are_recorded_and_not_applied_twice(conn):
    recorded = [row["version"] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
    assert recorded == ["001_create_listings.sql", "002_seed_demo_listings.sql"]
    assert db.migrate(conn) == []


def test_new_migration_file_is_applied_once(conn, tmp_path):
    (tmp_path / "900_create_scratch.sql").write_text(
        "CREATE TABLE scratch (id INT NOT NULL);\nGO\nINSERT INTO scratch (id) VALUES (1);"
    )
    try:
        assert db.migrate(conn, tmp_path) == ["900_create_scratch.sql"]
        assert db.migrate(conn, tmp_path) == []
        assert conn.execute("SELECT COUNT(*) AS n FROM scratch").fetchone()["n"] == 1
    finally:
        with conn:
            conn.execute("DROP TABLE IF EXISTS scratch")
            conn.execute("DELETE FROM schema_migrations WHERE version = '900_create_scratch.sql'")


def test_failing_migration_is_rolled_back_and_not_recorded(conn, tmp_path):
    (tmp_path / "901_broken.sql").write_text(
        "CREATE TABLE half_done (id INT NOT NULL);\nGO\nINSERT INTO no_such_table (id) VALUES (1);"
    )
    with pytest.raises(db.DatabaseError):
        db.migrate(conn, tmp_path)
    assert conn.execute("SELECT OBJECT_ID('half_done', 'U') AS id").fetchone()["id"] is None
    recorded = conn.execute("SELECT COUNT(*) AS n FROM schema_migrations WHERE version = '901_broken.sql'")
    assert recorded.fetchone()["n"] == 0


def test_badly_named_migration_is_refused(conn, tmp_path):
    (tmp_path / "add_column.sql").write_text("SELECT 1;")
    with pytest.raises(ValueError, match="001_name.sql"):
        db.migrate(conn, tmp_path)


def test_schema_rejects_values_the_api_should_never_send(conn):
    insert = (
        "INSERT INTO listings (title, category, condition, estimated_value, owner_name) VALUES (%s, %s, %s, %s, %s)"
    )
    for row in [
        ("Lamp", "furniture", 3, 10, "Ana"),  # unknown category
        ("Lamp", "home", 6, 10, "Ana"),  # condition above 5
        ("Lamp", "home", 3, 0, "Ana"),  # value must be positive
    ]:
        with pytest.raises(db.DatabaseError):
            conn.execute(insert, row)
        conn.rollback()


def test_connect_with_retry_gives_up_after_the_last_attempt(monkeypatch):
    calls = []

    def refuse(database_url):
        calls.append(database_url)
        raise db.DatabaseError("login refused")

    monkeypatch.setattr(db, "connect", refuse)
    monkeypatch.setattr(db.time, "sleep", lambda seconds: None)
    with pytest.raises(db.DatabaseError):
        db.connect_with_retry("mssql://u:p@nowhere/db", attempts=3)
    assert len(calls) == 3
