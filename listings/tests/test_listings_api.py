"""The listings endpoints end to end: HTTP in, SQL Server underneath."""

import logging

import pytest
from fastapi.testclient import TestClient

from app import db, repository
from app.config import Settings
from app.main import create_app

JACKET = {
    "title": "Denim jacket",
    "description": "Size M, worn one season.",
    "category": "clothing",
    "condition": 4,
    "estimated_value": 35,
    "owner_name": "Lucia",
}


def post(client, **changes):
    return client.post("/listings", json={**JACKET, **changes})


def test_post_creates_an_open_listing(client):
    response = post(client)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["status"] == "open"
    assert body["estimated_value"] == 35.0
    assert body["created_at"].endswith("Z") or body["created_at"].endswith("+00:00")
    assert {key: body[key] for key in JACKET} == {**JACKET, "estimated_value": 35.0}


def test_post_trims_text_and_rounds_to_cents(client):
    body = post(client, title="  Lamp  ", estimated_value=12.349).json()
    assert body["title"] == "Lamp"
    assert body["owner_name"] == "Lucia"
    assert body["estimated_value"] == 12.35


def test_description_is_optional(client):
    listing = {key: value for key, value in JACKET.items() if key != "description"}
    response = client.post("/listings", json=listing)
    assert response.status_code == 201
    assert response.json()["description"] == ""


def test_text_with_accents_and_quotes_survives(client):
    title = "Señor O'Brien's «Algèbre» 📚"
    created = post(client, title=title).json()
    assert client.get(f"/listings/{created['id']}").json()["title"] == title


@pytest.mark.parametrize(
    "changes",
    [
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 81},
        {"description": "x" * 501},
        {"category": "furniture"},
        {"condition": 0},
        {"condition": 6},
        {"condition": 2.5},
        {"estimated_value": 0},
        {"estimated_value": -5},
        {"estimated_value": 0.001},
        {"estimated_value": 10_001},
        {"estimated_value": "a lot"},
        {"owner_name": ""},
        {"status": "swapped"},  # unknown fields are refused, status has its own endpoint
    ],
)
def test_post_rejects_invalid_listings(client, changes):
    response = post(client, **changes)
    assert response.status_code == 422
    assert client.get("/listings").json() == []


def test_post_rejects_a_missing_field(client):
    listing = {key: value for key, value in JACKET.items() if key != "category"}
    assert client.post("/listings", json=listing).status_code == 422


def test_list_is_newest_first(client):
    first = post(client, title="First").json()
    second = post(client, title="Second").json()
    assert [listing["id"] for listing in client.get("/listings").json()] == [second["id"], first["id"]]


def test_list_filters_by_status_and_category(client):
    jacket = post(client).json()
    book = post(client, title="Calculus", category="books").json()
    client.patch(f"/listings/{book['id']}/status", json={"status": "swapped"})

    assert [x["id"] for x in client.get("/listings", params={"status": "open"}).json()] == [jacket["id"]]
    assert [x["id"] for x in client.get("/listings", params={"category": "books"}).json()] == [book["id"]]
    assert client.get("/listings", params={"status": "open", "category": "books"}).json() == []
    assert client.get("/listings", params={"status": "gone"}).status_code == 422


def test_get_one_listing(client):
    created = post(client).json()
    assert client.get(f"/listings/{created['id']}").json() == created


def test_put_replaces_the_listing_and_keeps_its_status(client):
    created = post(client).json()
    client.patch(f"/listings/{created['id']}/status", json={"status": "swapped"})
    response = client.put(f"/listings/{created['id']}", json={**JACKET, "title": "Jacket", "condition": 2})
    assert response.status_code == 200
    body = response.json()
    assert (body["title"], body["condition"], body["status"]) == ("Jacket", 2, "swapped")
    assert body["created_at"] == created["created_at"]
    assert body["updated_at"] >= created["updated_at"]


def test_put_validates_like_post(client):
    created = post(client).json()
    assert client.put(f"/listings/{created['id']}", json={**JACKET, "condition": 9}).status_code == 422
    assert client.get(f"/listings/{created['id']}").json()["condition"] == 4


def test_status_goes_from_open_to_swapped_and_back(client):
    created = post(client).json()
    swapped = client.patch(f"/listings/{created['id']}/status", json={"status": "swapped"})
    assert swapped.status_code == 200
    assert swapped.json()["status"] == "swapped"
    reopened = client.patch(f"/listings/{created['id']}/status", json={"status": "open"})
    assert reopened.json()["status"] == "open"
    assert client.patch(f"/listings/{created['id']}/status", json={"status": "lost"}).status_code == 422


def test_delete_removes_the_listing(client):
    created = post(client).json()
    assert client.delete(f"/listings/{created['id']}").status_code == 204
    assert client.get(f"/listings/{created['id']}").status_code == 404
    assert client.delete(f"/listings/{created['id']}").status_code == 404


def test_unknown_ids_are_404(client):
    assert client.get("/listings/999999").status_code == 404
    assert client.put("/listings/999999", json=JACKET).status_code == 404
    assert client.patch("/listings/999999/status", json={"status": "swapped"}).status_code == 404
    assert client.delete("/listings/999999").status_code == 404
    assert client.get("/listings/abc").status_code == 422


def test_database_failure_is_a_clean_503(client, monkeypatch):
    def refuse(database_url):
        raise db.DatabaseError("Login failed for user 'listings_user' on tcp:secret-host")

    monkeypatch.setattr(db, "connect", refuse)
    response = client.get("/listings")
    assert response.status_code == 503
    assert response.json() == {"detail": "The listings database is unavailable."}
    assert "secret-host" not in response.text


def test_unexpected_error_is_a_500_without_a_stack_trace(database_url, conn, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("boom: internal detail")

    monkeypatch.setattr(repository, "list_listings", explode)
    app = create_app(Settings(database_url=database_url))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/listings")
    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong on our side."}
    assert "boom" not in response.text


def test_an_id_too_large_for_the_database_is_422_not_an_outage(client):
    too_large = 2_147_483_648
    assert client.get(f"/listings/{too_large}").status_code == 422
    assert client.delete(f"/listings/{too_large}").status_code == 422
    assert client.get("/listings/0").status_code == 422


def test_text_is_measured_the_way_the_database_stores_it(client):
    # An emoji is one character to Python but two units in NVARCHAR.
    assert post(client, title="📚" * 40).status_code == 201
    assert post(client, title="📚" * 41).status_code == 422
    assert post(client, owner_name="🙂" * 21).status_code == 422


def test_a_constraint_violation_is_422_not_an_outage(client, monkeypatch):
    def violate(*args, **kwargs):
        raise db.IntegrityError("The INSERT statement conflicted with the CHECK constraint ck_listings_value")

    monkeypatch.setattr(repository, "create_listing", violate)
    response = post(client)
    assert response.status_code == 422
    assert response.json() == {"detail": "Those values were not accepted."}
    assert "ck_listings_value" not in response.text


def test_a_500_still_carries_cors_headers(database_url, conn, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(repository, "list_listings", explode)
    app = create_app(Settings(database_url=database_url, cors_origins=("http://localhost:8080",)))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/listings", headers={"Origin": "http://localhost:8080"})
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:8080"


def test_a_crafted_path_cannot_forge_a_log_line(client, caplog):
    forged = "/listings/x%0Aservice=listings method=POST path=/listings status=500 duration_ms=9999"
    with caplog.at_level(logging.INFO, logger="listings"):
        client.get(forged)
    lines = [record.getMessage() for record in caplog.records if record.name == "listings"]
    assert len(lines) == 1
    assert "\n" not in lines[0]
    assert lines[0].count("service=listings ") == 1
    assert " status=500 " not in lines[0]


def test_list_is_paged_newest_first(client):
    ids = [post(client, title=f"Item {n}").json()["id"] for n in range(5)]
    newest_first = list(reversed(ids))
    page = lambda **q: [item["id"] for item in client.get("/listings", params=q).json()]  # noqa: E731
    assert page() == newest_first  # no paging asked for: everything, as before
    assert page(limit=2) == newest_first[:2]
    assert page(limit=2, offset=2) == newest_first[2:4]
    assert page(limit=2, offset=4) == newest_first[4:]
    assert page(offset=50) == []


def test_paging_works_together_with_the_filters(client):
    for n in range(3):
        post(client, title=f"Book {n}", category="books")
    post(client, title="Lamp", category="home")
    books = client.get("/listings", params={"category": "books", "limit": 2}).json()
    assert [item["title"] for item in books] == ["Book 2", "Book 1"]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 501}, {"limit": "x"}, {"offset": -1}, {"offset": 2**31}])
def test_paging_limits_are_422_not_an_outage(client, params):
    assert client.get("/listings", params=params).status_code == 422
