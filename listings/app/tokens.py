"""Sign-in tokens: who the caller is, signed with a secret both services share.

The Listings service issues a token when someone signs up or logs in. Both services
check the signature themselves with the same AUTH_SECRET, so neither has to call the
other to know who is asking (see ADR-1). A token is `<payload>.<signature>`: the payload
is base64url JSON with the username and an expiry time, the signature is HMAC-SHA256.
"""

import base64
import hashlib
import hmac
import json
import time

from fastapi import HTTPException, Request

TOKEN_LIFETIME_SECONDS = 7 * 24 * 3600


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(secret: str, payload: str) -> str:
    return _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())


def make_token(secret: str, username: str, lifetime: int = TOKEN_LIFETIME_SECONDS) -> str:
    payload = _b64(json.dumps({"sub": username, "exp": int(time.time()) + lifetime}).encode())
    return f"{payload}.{_sign(secret, payload)}"


def read_token(secret: str, token: str) -> str | None:
    """The username in a valid, unexpired token; None for anything else."""
    if not secret:
        return None  # no secret configured: accept nothing
    payload, dot, signature = token.partition(".")
    if not dot or not hmac.compare_digest(signature.encode(), _sign(secret, payload).encode()):
        return None
    try:
        claims = json.loads(_unb64(payload))
        username, expires = claims["sub"], claims["exp"]
    except (ValueError, KeyError, TypeError):  # not base64, not JSON, or not our claims
        return None
    if not isinstance(username, str) or not isinstance(expires, int) or expires < time.time():
        return None
    return username


def current_user(request: Request) -> str:
    """FastAPI dependency: the signed-in username, or 401."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    username = read_token(request.app.state.settings.auth_secret, token.strip()) if scheme.lower() == "bearer" else None
    if username is None:
        raise HTTPException(
            status_code=401,
            detail="Please log in first.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username


def same_person(one: str, other: str) -> bool:
    """Usernames compare the way the database does: ignoring case."""
    return one.strip().casefold() == other.strip().casefold()
