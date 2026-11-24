"""Accounts and ownership: sign up, log in, and who may change which listing."""

import pytest
from fastapi.testclient import TestClient
from tests.conftest import TEST_SECRET, as_user

from app import accounts
from app.config import Settings
from app.main import create_app
from app.tokens import make_token, read_token

NOBODY = {"Authorization": ""}
JACKET = {"title": "Denim jacket", "category": "clothing", "condition": 4, "estimated_value": 35}
NADIA = {"username": "Nadia", "password": "correct horse"}


def test_sign_up_then_use_the_token(client):
    response = client.post("/auth/signup", json=NADIA, headers=NOBODY)
    assert response.status_code == 201
    session = response.json()
    assert session["username"] == "Nadia"
    headers = {"Authorization": f"Bearer {session['token']}"}
    assert client.get("/auth/me", headers=headers).json() == {"username": "Nadia"}
    posted = client.post("/listings", json=JACKET, headers=headers)
    assert posted.status_code == 201
    assert posted.json()["owner_name"] == "Nadia"


def test_the_password_is_stored_only_as_a_salted_hash(client, conn):
    client.post("/auth/signup", json=NADIA)
    client.post("/auth/signup", json={**NADIA, "username": "Pablo"})
    hashes = [row["password_hash"] for row in conn.execute("SELECT password_hash FROM users ORDER BY id")]
    assert len(hashes) == 2
    assert all(stored.startswith("scrypt$") and "correct horse" not in stored for stored in hashes)
    assert hashes[0] != hashes[1]  # same password, different salt


def test_log_in_with_the_right_password_only(client):
    client.post("/auth/signup", json=NADIA)
    good = client.post("/auth/login", json={"username": "nadia", "password": "correct horse"})
    assert good.status_code == 200
    assert good.json()["username"] == "Nadia"  # the spelling she signed up with
    for wrong in ({**NADIA, "password": "wrong horse"}, {"username": "Nobody", "password": "correct horse"}):
        response = client.post("/auth/login", json=wrong)
        assert response.status_code == 401
        assert response.json()["detail"] == "Wrong username or password."


def test_a_username_can_be_taken_only_once(client):
    assert client.post("/auth/signup", json=NADIA).status_code == 201
    assert client.post("/auth/signup", json={**NADIA, "username": "NADIA"}).status_code == 409


def test_demo_names_cannot_be_registered(client):
    assert client.post("/auth/signup", json={**NADIA, "username": "lucia"}).status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"username": "N", "password": "correct horse"},
        {"username": "x" * 41, "password": "correct horse"},
        {"username": "_sneaky", "password": "correct horse"},
        {"username": "line\nbreak", "password": "correct horse"},
        {"username": "Nadia", "password": "short"},
        {"username": "Nadia", "password": "x" * 129},
        {"username": "Nadia"},
        {**NADIA, "admin": True},
    ],
)
def test_sign_up_rejects_bad_input(client, body):
    assert client.post("/auth/signup", json=body).status_code == 422


def test_password_hash_helpers():
    stored = accounts.hash_password("correct horse")
    assert accounts.password_matches("correct horse", stored)
    assert not accounts.password_matches("wrong horse", stored)
    assert not accounts.password_matches("correct horse", "not-a-hash")
    assert not accounts.password_matches("correct horse", "md5$00$00")


def test_tokens_expire_and_cannot_be_forged():
    assert read_token(TEST_SECRET, make_token(TEST_SECRET, "Nadia")) == "Nadia"
    assert read_token(TEST_SECRET, make_token(TEST_SECRET, "Nadia", lifetime=-1)) is None
    assert read_token(TEST_SECRET, make_token("x" * 40, "Nadia")) is None
    assert read_token("", make_token("", "Nadia")) is None  # no secret configured: accept nothing
    payload, _, signature = make_token(TEST_SECRET, "Nadia").partition(".")
    assert read_token(TEST_SECRET, f"{payload}x.{signature}") is None
    for junk in ("", "abc", "a.b", "..", "é.é"):
        assert read_token(TEST_SECRET, junk) is None


# --- who may change a listing -----------------------------------------------------------


def test_reading_needs_no_login_but_posting_does(client):
    assert client.get("/listings", headers=NOBODY).status_code == 200
    for headers in (NOBODY, {"Authorization": "Bearer nope"}, {"Authorization": "Basic abc"}):
        response = client.post("/listings", json=JACKET, headers=headers)
        assert response.status_code == 401
        assert response.json()["detail"] == "Please log in first."
    assert client.get("/listings").json() == []


def test_the_owner_is_the_signed_in_account_whatever_the_body_says(client):
    posted = client.post("/listings", json={**JACKET, "owner_name": "Somebody else"}).json()
    assert posted["owner_name"] == "Lucia"
    edited = client.put(f"/listings/{posted['id']}", json={**JACKET, "title": "Jacket", "owner_name": "Omar"}).json()
    assert edited["owner_name"] == "Lucia"
    assert edited["title"] == "Jacket"


def test_only_the_owner_can_edit_or_delete(client):
    listing = client.post("/listings", json=JACKET).json()  # Lucia's
    url = f"/listings/{listing['id']}"
    for headers in (as_user("Omar"), NOBODY):
        expected = 403 if headers is not NOBODY else 401
        assert client.put(url, json={**JACKET, "title": "Mine now"}, headers=headers).status_code == expected
        assert client.delete(url, headers=headers).status_code == expected
    assert client.get(url).json()["title"] == "Denim jacket"
    assert client.delete(url, headers=as_user("lucia")).status_code == 204  # case does not matter


def test_a_missing_listing_is_404_not_403(client):
    assert client.put("/listings/999999", json=JACKET).status_code == 404
    assert client.delete("/listings/999999").status_code == 404


def test_marking_swapped_needs_a_login_but_not_ownership(client):
    listing = client.post("/listings", json=JACKET).json()
    url = f"/listings/{listing['id']}/status"
    assert client.patch(url, json={"status": "swapped"}, headers=NOBODY).status_code == 401
    # The other person in an accepted swap marks it, so any signed-in account may.
    assert client.patch(url, json={"status": "swapped"}, headers=as_user("Omar")).status_code == 200


# --- one-click demo accounts ------------------------------------------------------------


def test_demo_sign_in_is_off_unless_switched_on(client):
    assert client.get("/auth/demo").json() == {"accounts": []}
    assert client.post("/auth/demo", json={"username": "Lucia"}).status_code == 403


def test_demo_sign_in_when_switched_on(database_url, conn):
    settings = Settings(database_url=database_url, auth_secret=TEST_SECRET, demo_login=True)
    with TestClient(create_app(settings)) as client:
        assert "Lucia" in client.get("/auth/demo").json()["accounts"]
        session = client.post("/auth/demo", json={"username": "lucia"}).json()
        assert session["username"] == "Lucia"
        assert read_token(TEST_SECRET, session["token"]) == "Lucia"
        # Only the seeded demo names, never a real account.
        assert client.post("/auth/demo", json={"username": "Nadia"}).status_code == 403
