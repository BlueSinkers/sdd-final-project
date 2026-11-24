"""The swaps endpoints end to end: HTTP in, SQL Server underneath."""

import pytest
from fastapi.testclient import TestClient

from app import db, repository
from app.config import Settings
from app.main import create_app

JACKET = {"listing_id": 1, "title": "Denim jacket", "owner_name": "Lucia", "condition": 4, "estimated_value": 35}
LAMP = {"listing_id": 3, "title": "Desk lamp", "owner_name": "Chen", "condition": 5, "estimated_value": 18}
BOOK = {"listing_id": 2, "title": "Calculus", "owner_name": "Omar", "condition": 3, "estimated_value": 40}


def propose(client, offered=JACKET, requested=LAMP, **changes):
    body = {"proposer_name": "Lucia", "offered": offered, "requested": requested, **changes}
    return client.post("/swaps", json=body)


def test_post_scores_and_stores_the_proposal(client):
    response = propose(client, message="Swap on campus on Friday?")
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["status"] == "proposed"
    assert body["proposer_name"] == "Lucia"
    assert body["message"] == "Swap on campus on Friday?"
    # 35 x 0.9 = 31.50 against 18 x 1.0 = 18.00 -> 18 / 31.5 = 0.5714
    assert body["offered"] == {**JACKET, "estimated_value": 35.0, "adjusted_value": 31.5}
    assert body["requested"] == {**LAMP, "estimated_value": 18.0, "adjusted_value": 18.0}
    assert body["fairness_score"] == 0.5714
    assert body["verdict"] == "Lopsided"
    assert client.get(f"/swaps/{body['id']}").json() == body


@pytest.mark.parametrize(
    ("offered", "requested", "verdict"),
    [
        # 40 x 0.8 = 32.00 against 35 x 0.9 = 31.50 -> 0.9844
        (BOOK, JACKET, "Fair trade"),
        # 18.00 against 32.00 -> 0.5625
        (LAMP, BOOK, "Lopsided"),
        # 5 x 0.6 = 3.00 against 31.50 -> 0.0952
        ({**LAMP, "estimated_value": 5, "condition": 1}, JACKET, "Very uneven"),
    ],
)
def test_each_verdict(client, offered, requested, verdict):
    assert propose(client, offered, requested).json()["verdict"] == verdict


def test_verdict_is_the_same_whichever_side_proposes(client):
    one = propose(client, JACKET, LAMP).json()
    other = propose(client, LAMP, JACKET).json()
    assert one["fairness_score"] == other["fairness_score"]
    assert one["verdict"] == other["verdict"]


def test_exact_boundaries_through_the_api(client):
    # Both condition 5, so adjusted value = estimated value.
    eighty = {**LAMP, "estimated_value": 80}
    fifty = {**LAMP, "estimated_value": 50}
    hundred = {**JACKET, "condition": 5, "estimated_value": 100}
    assert propose(client, eighty, hundred).json()["fairness_score"] == 0.8
    assert propose(client, eighty, hundred).json()["verdict"] == "Fair trade"
    assert propose(client, fifty, hundred).json()["fairness_score"] == 0.5
    assert propose(client, fifty, hundred).json()["verdict"] == "Lopsided"


def test_extra_listing_fields_in_a_snapshot_are_ignored(client):
    whole_listing = {**JACKET, "id": 1, "category": "clothing", "status": "open", "description": "Size M"}
    assert propose(client, offered=whole_listing).status_code == 201


@pytest.mark.parametrize(
    "body",
    [
        {"proposer_name": ""},
        {"proposer_name": "x" * 41},
        {"message": "x" * 301},
        {"offered": {**JACKET, "condition": 0}},
        {"offered": {**JACKET, "condition": 6}},
        {"requested": {**LAMP, "estimated_value": 0}},
        {"requested": {**LAMP, "estimated_value": -3}},
        {"requested": {**LAMP, "estimated_value": 10_001}},
        {"requested": {**LAMP, "title": ""}},
        {"requested": {**LAMP, "listing_id": 0}},
        {"requested": {**LAMP, "listing_id": JACKET["listing_id"]}},  # a listing cannot be swapped for itself
        {"offered": None},
        {"fairness_score": 1.0},  # the caller cannot choose the score
        {"verdict": "Fair trade"},
    ],
)
def test_post_rejects_invalid_proposals(client, body):
    response = propose(client, **body)
    assert response.status_code == 422
    assert client.get("/swaps").json() == []


def test_post_requires_both_sides(client):
    assert client.post("/swaps", json={"proposer_name": "Lucia", "offered": JACKET}).status_code == 422


def test_list_is_newest_first_and_respects_the_limit(client):
    ids = [propose(client).json()["id"] for _ in range(3)]
    assert [swap["id"] for swap in client.get("/swaps").json()] == ids[::-1]
    assert [swap["id"] for swap in client.get("/swaps", params={"limit": 2}).json()] == ids[:0:-1]
    assert client.get("/swaps", params={"limit": 0}).status_code == 422
    assert client.get("/swaps", params={"limit": 201}).status_code == 422


def test_list_filters_by_listing_on_either_side(client):
    jacket_lamp = propose(client, JACKET, LAMP).json()["id"]
    book_jacket = propose(client, BOOK, JACKET).json()["id"]
    lamp_book = propose(client, LAMP, BOOK).json()["id"]

    def ids(listing_id):
        return [swap["id"] for swap in client.get("/swaps", params={"listing_id": listing_id}).json()]

    assert ids(JACKET["listing_id"]) == [book_jacket, jacket_lamp]
    assert ids(LAMP["listing_id"]) == [lamp_book, jacket_lamp]
    assert ids(999) == []


def test_a_proposed_swap_can_be_accepted_once(client):
    swap = propose(client).json()
    accepted = client.patch(f"/swaps/{swap['id']}/status", json={"status": "accepted"})
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    again = client.patch(f"/swaps/{swap['id']}/status", json={"status": "declined"})
    assert again.status_code == 409
    assert client.get(f"/swaps/{swap['id']}").json()["status"] == "accepted"


def test_a_proposed_swap_can_be_declined(client):
    swap = propose(client).json()
    declined = client.patch(f"/swaps/{swap['id']}/status", json={"status": "declined"})
    assert declined.json()["status"] == "declined"
    # Deciding does not change the stored score.
    assert declined.json()["fairness_score"] == swap["fairness_score"]


def test_status_must_be_a_decision(client):
    swap = propose(client).json()
    assert client.patch(f"/swaps/{swap['id']}/status", json={"status": "proposed"}).status_code == 422
    assert client.patch(f"/swaps/{swap['id']}/status", json={"status": "maybe"}).status_code == 422


def test_unknown_ids_are_404(client):
    assert client.get("/swaps/999999").status_code == 404
    assert client.patch("/swaps/999999/status", json={"status": "accepted"}).status_code == 404
    assert client.get("/swaps/abc").status_code == 422


def test_database_failure_is_a_clean_503(client, monkeypatch):
    def refuse(database_url):
        raise db.DatabaseError("Login failed for user 'swaps_user' on tcp:secret-host")

    monkeypatch.setattr(db, "connect", refuse)
    response = propose(client)
    assert response.status_code == 503
    assert response.json() == {"detail": "The swaps database is unavailable."}
    assert "secret-host" not in response.text


def test_unexpected_error_is_a_500_without_a_stack_trace(database_url, conn, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("boom: internal detail")

    monkeypatch.setattr(repository, "list_swaps", explode)
    app = create_app(Settings(database_url=database_url))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/swaps")
    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong on our side."}
    assert "boom" not in response.text


def test_score_is_cut_not_rounded_through_the_api(client):
    # Both condition 5, so adjusted = estimated. 7999.60 / 10000 = 0.79996.
    almost = {**LAMP, "estimated_value": 7999.60}
    full = {**JACKET, "condition": 5, "estimated_value": 10000}
    body = propose(client, almost, full).json()
    assert body["fairness_score"] == 0.7999
    assert body["verdict"] == "Lopsided"


def test_values_are_rounded_to_cents_before_scoring(client):
    assert propose(client, requested={**LAMP, "estimated_value": 0.004}).status_code == 422
    body = propose(client, requested={**LAMP, "estimated_value": 17.999}).json()
    assert body["requested"]["estimated_value"] == 18.0
    assert body["requested"]["adjusted_value"] == 18.0


def test_ids_too_large_for_the_database_are_422_not_an_outage(client):
    too_large = 2_147_483_648
    assert propose(client, requested={**LAMP, "listing_id": too_large}).status_code == 422
    assert client.get(f"/swaps/{too_large}").status_code == 422
    assert client.get("/swaps", params={"listing_id": too_large}).status_code == 422
    assert client.patch(f"/swaps/{too_large}/status", json={"status": "accepted"}).status_code == 422


def test_text_is_measured_the_way_the_database_stores_it(client):
    assert propose(client, offered={**JACKET, "title": "🧥" * 40}).status_code == 201
    assert propose(client, offered={**JACKET, "title": "🧥" * 41}).status_code == 422
    assert propose(client, message="🙂" * 151).status_code == 422


def test_a_constraint_violation_is_422_not_an_outage(client, monkeypatch):
    def violate(*args, **kwargs):
        raise db.IntegrityError("The INSERT statement conflicted with the CHECK constraint ck_swaps_values")

    monkeypatch.setattr(repository, "create_swap", violate)
    response = propose(client)
    assert response.status_code == 422
    assert response.json() == {"detail": "Those values were not accepted."}
    assert "ck_swaps_values" not in response.text


def test_a_500_still_carries_cors_headers(database_url, conn, monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(repository, "list_swaps", explode)
    app = create_app(Settings(database_url=database_url, cors_origins=("http://localhost:8080",)))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/swaps", headers={"Origin": "http://localhost:8080"})
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:8080"
