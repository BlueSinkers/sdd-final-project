"""End-to-end checks against the running compose stack, using only the standard library.

    python tests/e2e/flow.py flow            both services up: post, propose, accept
    python tests/e2e/flow.py swaps-down      Swaps stopped: Listings must still work
    python tests/e2e/flow.py listings-down   Listings stopped: Swaps must still work
    python tests/e2e/flow.py deployed        after a deploy: read-only checks, nothing is stored

The services never call each other, so each one has to keep working alone.
"""

import base64
import hashlib
import hmac
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

LISTINGS = os.environ.get("LISTINGS_URL", "http://localhost:8001")
SWAPS = os.environ.get("SWAPS_URL", "http://localhost:8002")
TIMEOUT_S = 10


def auth_secret() -> str:
    """AUTH_SECRET from the environment, or from the .env file the compose stack uses."""
    secret = os.environ.get("AUTH_SECRET", "")
    env_file = pathlib.Path(__file__).resolve().parents[2] / ".env"
    if not secret and env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("AUTH_SECRET="):
                secret = line.split("=", 1)[1].strip()
    if not secret:
        sys.exit("FAIL AUTH_SECRET is not set and not in .env; the checks cannot sign in")
    return secret


def token_for(username: str) -> str:
    """A sign-in token like the Listings service issues (see app/tokens.py). The checks
    make their own so that Swaps can be tested while Listings is stopped."""

    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    payload = b64(json.dumps({"sub": username, "exp": int(time.time()) + 600}).encode())
    signature = b64(hmac.new(auth_secret().encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def call(method: str, url: str, body: dict | None = None, user: str | None = None) -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if body is not None else {}
    if user:
        headers["Authorization"] = f"Bearer {token_for(user)}"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            text = response.read().decode()
            return response.status, json.loads(text) if text else None
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode() or "null")


def is_down(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=3)
    except urllib.error.HTTPError:
        return False
    except OSError:
        return True
    return False


def wait_until_up(base_url: str, seconds: int = 90) -> None:
    """A service that was just started needs a moment to apply its migrations."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=3) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(1)
    sys.exit(f"FAIL {base_url}/health did not answer 200 within {seconds} s")


def expect(condition: bool, what: str) -> None:
    print(("ok   " if condition else "FAIL ") + what)
    if not condition:
        sys.exit(1)


def post_listing(title: str, condition: int, value: float, owner: str) -> dict:
    status, listing = call(
        "POST",
        f"{LISTINGS}/listings",
        {
            "title": title,
            "category": "other",
            "condition": condition,
            "estimated_value": value,
        },
        user=owner,
    )
    expect(status != 201 or listing["owner_name"] == owner, f"'{title}' belongs to {owner}")
    expect(status == 201, f"POST /listings creates '{title}'")
    return listing


def snapshot(listing: dict) -> dict:
    return {
        "listing_id": listing["id"],
        "title": listing["title"],
        "owner_name": listing["owner_name"],
        "condition": listing["condition"],
        "estimated_value": listing["estimated_value"],
    }


def propose(offered: dict, requested: dict) -> dict:
    status, swap = call(
        "POST",
        f"{SWAPS}/swaps",
        {"offered": snapshot(offered), "requested": snapshot(requested)},
        user=offered["owner_name"],
    )
    expect(status == 201, "POST /swaps stores the proposal")
    return swap


def flow() -> None:
    wait_until_up(LISTINGS)
    wait_until_up(SWAPS)
    jacket = post_listing("e2e jacket", 4, 35, "Lucia")  # 35 x 0.9 = 31.50
    lamp = post_listing("e2e lamp", 5, 18, "Chen")  # 18 x 1.0 = 18.00
    swap = propose(jacket, lamp)
    expect(swap["fairness_score"] == 0.5714, "fairness score is 18.00 / 31.50 = 0.5714")
    expect(swap["verdict"] == "Lopsided", "verdict is Lopsided")

    decision = f"{SWAPS}/swaps/{swap['id']}/status"
    status, _ = call("PATCH", decision, {"status": "accepted"})
    expect(status == 401, "accepting needs a login")
    status, _ = call("PATCH", decision, {"status": "accepted"}, user="Lucia")
    expect(status == 403, "the proposer cannot accept her own proposal")
    status, accepted = call("PATCH", decision, {"status": "accepted"}, user="Chen")
    expect(status == 200 and accepted["status"] == "accepted", "the owner of the requested item accepts")
    status, _ = call("PATCH", decision, {"status": "declined"}, user="Chen")
    expect(status == 409, "an accepted swap cannot be decided again")

    for listing in (jacket, lamp):
        status, updated = call(
            "PATCH", f"{LISTINGS}/listings/{listing['id']}/status", {"status": "swapped"}, user="Chen"
        )
        expect(status == 200 and updated["status"] == "swapped", f"'{listing['title']}' is marked swapped")
    status, still_open = call("GET", f"{LISTINGS}/listings?status=open")
    open_ids = {listing["id"] for listing in still_open}
    expect(status == 200 and not open_ids & {jacket["id"], lamp["id"]}, "swapped listings leave the open board")

    status, _ = call("DELETE", f"{LISTINGS}/listings/{jacket['id']}", user="Chen")
    expect(status == 403, "nobody can delete someone else's listing")
    for listing in (jacket, lamp):
        status, _ = call("DELETE", f"{LISTINGS}/listings/{listing['id']}", user=listing["owner_name"])
        expect(status == 204, f"'{listing['title']}' is deleted again")


def swaps_down() -> None:
    expect(is_down(f"{SWAPS}/health"), "Swaps is not reachable")
    wait_until_up(LISTINGS)
    status, body = call("GET", f"{LISTINGS}/health")
    expect(status == 200 and body["status"] == "ok", "Listings /health is still ok")
    status, _ = call("GET", f"{LISTINGS}/listings")
    expect(status == 200, "browsing listings still works")
    listing = post_listing("e2e posted while swaps is down", 3, 10, "Omar")
    status, _ = call("DELETE", f"{LISTINGS}/listings/{listing['id']}", user="Omar")
    expect(status == 204, "deleting a listing still works")


def listings_down() -> None:
    expect(is_down(f"{LISTINGS}/health"), "Listings is not reachable")
    wait_until_up(SWAPS)
    status, body = call("GET", f"{SWAPS}/health")
    expect(status == 200 and body["status"] == "ok", "Swaps /health is still ok")
    # Signed in with a token made here: Swaps checks it alone, without asking Listings.
    book = {"id": 9001, "title": "e2e book", "owner_name": "Omar", "condition": 3, "estimated_value": 40}
    mat = {"id": 9002, "title": "e2e mat", "owner_name": "Jonas", "condition": 5, "estimated_value": 30}
    swap = propose(book, mat)  # 32.00 against 30.00 -> 0.9375
    expect(swap["verdict"] == "Fair trade", "Swaps scores a proposal from snapshots alone")
    status, _ = call("GET", f"{SWAPS}/swaps")
    expect(status == 200, "listing proposals still works")


def deployed() -> None:
    """Smoke test for the live system. It must not leave test data behind, so it only
    reads, and checks the write paths with requests that validation refuses."""
    wait_until_up(LISTINGS, seconds=240)  # scale to zero and a paused database: allow a cold start
    wait_until_up(SWAPS, seconds=240)
    status, listings = call("GET", f"{LISTINGS}/listings")
    expect(status == 200 and isinstance(listings, list), "GET /listings returns a list")
    status, _ = call("POST", f"{LISTINGS}/listings", {"title": ""})
    expect(status in (401, 422), "POST /listings refuses a request without a login")
    status, _ = call("POST", f"{LISTINGS}/auth/login", {"username": "smoke-test", "password": "not-the-password"})
    expect(status == 401, "POST /auth/login refuses a wrong password with 401")
    status, _ = call("GET", f"{LISTINGS}/listings/2147483647")
    expect(status == 404, "an unknown listing is 404")
    status, swaps = call("GET", f"{SWAPS}/swaps?limit=1")
    expect(status == 200 and isinstance(swaps, list), "GET /swaps returns a list")
    item = {"listing_id": 1, "title": "smoke", "owner_name": "smoke", "condition": 3, "estimated_value": 10}
    status, _ = call("POST", f"{SWAPS}/swaps", {"offered": item, "requested": item})
    expect(status in (401, 422), "POST /swaps refuses a request without a login")

    ui = os.environ.get("UI_URL")
    if ui:
        with urllib.request.urlopen(f"{ui}/", timeout=TIMEOUT_S) as response:
            expect(response.status == 200 and b"Thrift-Swap Board" in response.read(), "the UI page loads")
        with urllib.request.urlopen(f"{ui}/config.js", timeout=TIMEOUT_S) as response:
            config = response.read().decode()
        expect(LISTINGS in config and SWAPS in config, "the UI is configured with both deployed service URLs")


if __name__ == "__main__":
    scenarios = {"flow": flow, "swaps-down": swaps_down, "listings-down": listings_down, "deployed": deployed}
    if len(sys.argv) != 2 or sys.argv[1] not in scenarios:
        sys.exit(f"usage: python tests/e2e/flow.py [{' | '.join(scenarios)}]")
    scenarios[sys.argv[1]]()
    print(f"{sys.argv[1]}: all checks passed")
