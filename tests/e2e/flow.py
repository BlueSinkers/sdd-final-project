"""End-to-end checks against the running compose stack, using only the standard library.

    python tests/e2e/flow.py flow            both services up: post, propose, accept
    python tests/e2e/flow.py swaps-down      Swaps stopped: Listings must still work
    python tests/e2e/flow.py listings-down   Listings stopped: Swaps must still work

The services never call each other, so each one has to keep working alone.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

LISTINGS = os.environ.get("LISTINGS_URL", "http://localhost:8001")
SWAPS = os.environ.get("SWAPS_URL", "http://localhost:8002")
TIMEOUT_S = 10


def call(method: str, url: str, body: dict | None = None) -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"} if body is not None else {}
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
            "owner_name": owner,
        },
    )
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
        {"proposer_name": offered["owner_name"], "offered": snapshot(offered), "requested": snapshot(requested)},
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

    status, accepted = call("PATCH", f"{SWAPS}/swaps/{swap['id']}/status", {"status": "accepted"})
    expect(status == 200 and accepted["status"] == "accepted", "the swap can be accepted")
    status, _ = call("PATCH", f"{SWAPS}/swaps/{swap['id']}/status", {"status": "declined"})
    expect(status == 409, "an accepted swap cannot be decided again")

    for listing in (jacket, lamp):
        status, updated = call("PATCH", f"{LISTINGS}/listings/{listing['id']}/status", {"status": "swapped"})
        expect(status == 200 and updated["status"] == "swapped", f"'{listing['title']}' is marked swapped")
    status, still_open = call("GET", f"{LISTINGS}/listings?status=open")
    open_ids = {listing["id"] for listing in still_open}
    expect(status == 200 and not open_ids & {jacket["id"], lamp["id"]}, "swapped listings leave the open board")

    for listing in (jacket, lamp):
        status, _ = call("DELETE", f"{LISTINGS}/listings/{listing['id']}")
        expect(status == 204, f"'{listing['title']}' is deleted again")


def swaps_down() -> None:
    expect(is_down(f"{SWAPS}/health"), "Swaps is not reachable")
    wait_until_up(LISTINGS)
    status, body = call("GET", f"{LISTINGS}/health")
    expect(status == 200 and body["status"] == "ok", "Listings /health is still ok")
    status, _ = call("GET", f"{LISTINGS}/listings")
    expect(status == 200, "browsing listings still works")
    listing = post_listing("e2e posted while swaps is down", 3, 10, "Omar")
    status, _ = call("DELETE", f"{LISTINGS}/listings/{listing['id']}")
    expect(status == 204, "deleting a listing still works")


def listings_down() -> None:
    expect(is_down(f"{LISTINGS}/health"), "Listings is not reachable")
    wait_until_up(SWAPS)
    status, body = call("GET", f"{SWAPS}/health")
    expect(status == 200 and body["status"] == "ok", "Swaps /health is still ok")
    book = {"id": 9001, "title": "e2e book", "owner_name": "Omar", "condition": 3, "estimated_value": 40}
    mat = {"id": 9002, "title": "e2e mat", "owner_name": "Jonas", "condition": 5, "estimated_value": 30}
    swap = propose(book, mat)  # 32.00 against 30.00 -> 0.9375
    expect(swap["verdict"] == "Fair trade", "Swaps scores a proposal from snapshots alone")
    status, _ = call("GET", f"{SWAPS}/swaps")
    expect(status == 200, "listing proposals still works")


if __name__ == "__main__":
    scenarios = {"flow": flow, "swaps-down": swaps_down, "listings-down": listings_down}
    if len(sys.argv) != 2 or sys.argv[1] not in scenarios:
        sys.exit(f"usage: python tests/e2e/flow.py [{' | '.join(scenarios)}]")
    scenarios[sys.argv[1]]()
    print(f"{sys.argv[1]}: all checks passed")
