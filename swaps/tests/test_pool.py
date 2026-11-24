"""The connection pool: reuse, and the cases where reuse would be unsafe. Real SQL Server."""

import pytest

from app import db, repository


@pytest.fixture
def logins(monkeypatch):
    """Counts how many real logins the pool makes."""
    made = []
    real = db.connect

    def counting(database_url):
        made.append(database_url)
        return real(database_url)

    monkeypatch.setattr(db, "connect", counting)
    return made


@pytest.fixture
def pool(database_url, logins):
    pool = db.ConnectionPool(database_url)
    yield pool
    pool.close()


def test_a_released_connection_is_reused_without_a_new_login(pool, logins):
    first = pool.acquire()
    pool.release(first)
    second = pool.acquire()
    assert second is first
    assert len(logins) == 1
    assert second.execute("SELECT 1 AS ok").fetchone()["ok"] == 1
    pool.release(second)


def test_an_uncommitted_change_never_reaches_the_next_user(pool, database_url):
    dirty = pool.acquire()
    dirty.execute("INSERT INTO schema_migrations (version) VALUES ('999_never_committed.sql')")
    pool.release(dirty)  # rolls back
    reused = pool.acquire()
    count = reused.execute("SELECT COUNT(*) AS n FROM schema_migrations WHERE version = '999_never_committed.sql'")
    assert count.fetchone()["n"] == 0
    pool.release(reused)


def test_a_connection_the_database_closed_is_replaced(pool, logins):
    stale = pool.acquire()
    pool.release(stale)
    stale._raw.close()  # as if the server or the network dropped it while it sat idle
    pool._ping_after = 0  # check it on the way out, as happens after a few idle seconds
    fresh = pool.acquire()
    assert fresh is not stale
    assert fresh.execute("SELECT 1 AS ok").fetchone()["ok"] == 1
    assert len(logins) == 2
    pool.release(fresh)


def test_a_connection_idle_for_too_long_is_dropped(database_url, logins):
    pool = db.ConnectionPool(database_url, max_age=0)
    first = pool.acquire()
    pool.release(first)
    second = pool.acquire()
    assert second is not first
    assert len(logins) == 2
    pool.release(second)
    pool.close()


def test_the_pool_keeps_at_most_max_idle_connections(database_url):
    pool = db.ConnectionPool(database_url, max_idle=1)
    a, b = pool.acquire(), pool.acquire()
    pool.release(a)
    pool.release(b)  # over the limit: closed instead of kept
    assert pool._idle.qsize() == 1
    pool.close()
    assert pool._idle.qsize() == 0


def test_a_connection_marked_not_reusable_is_closed(pool):
    conn = pool.acquire()
    pool.release(conn, reusable=False)
    assert pool._idle.qsize() == 0


def test_requests_share_one_connection(client):
    pool = client.app.state.pool
    for _ in range(3):
        assert client.get("/swaps").status_code == 200
    assert pool._idle.qsize() == 1


def test_a_database_error_throws_the_connection_away(client, monkeypatch):
    pool = client.app.state.pool

    def broken(*args, **kwargs):
        raise db.DatabaseError("connection is dead")

    monkeypatch.setattr(repository, "list_swaps", broken)
    assert client.get("/swaps").status_code == 503
    assert pool._idle.qsize() == 0


def test_a_404_does_not_cost_the_connection(client):
    pool = client.app.state.pool
    assert client.get("/swaps/999999").status_code == 404
    assert pool._idle.qsize() == 1
