"""The migration runner and connection helpers, against a real SQL Server."""

import pytest

from app import db


def test_migrations_are_recorded_and_not_applied_twice(conn):
    recorded = [row["version"] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
    assert recorded == ["001_create_swaps.sql"]
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
    columns = (
        "proposer_name, offered_listing_id, offered_title, offered_owner_name, offered_condition, offered_value, "
        "offered_adjusted, requested_listing_id, requested_title, requested_owner_name, requested_condition, "
        "requested_value, requested_adjusted, fairness_score, verdict"
    )
    insert = f"INSERT INTO swaps ({columns}) VALUES ({', '.join(['%s'] * 15)})"
    good = ["Ana", 1, "Lamp", "Ana", 3, 10, 8, 2, "Book", "Ben", 3, 10, 8, 1, "Fair trade"]
    with conn:
        conn.execute(insert, good)
    for position, bad_value in [
        (7, 1),  # the same listing on both sides
        (4, 6),  # condition above 5
        (5, 0),  # value must be positive
        (13, 1.5),  # score above 1
        (14, "Great deal"),  # unknown verdict
    ]:
        row = list(good)
        row[position] = bad_value
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
