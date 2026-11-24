"""Accounts: sign up, log in, and password hashing. Lives in the Listings service
because an account is what owns a listing."""

import hashlib
import hmac
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, StringConstraints

from app.db import Connection, IntegrityError, get_conn
from app.models import fits_column
from app.tokens import current_user, make_token, same_person

router = APIRouter(prefix="/auth", tags=["accounts"])

# scrypt work factors: about 16 MB and a few tens of milliseconds per hash.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1

# Letters, digits and a few separators; it is shown on listings as "Posted by ...".
Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=40, pattern=r"^[^\W_][\w .'-]*$"),
    fits_column(40),
]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Username
    password: Password


# The owners of the seeded demo listings (migration 002). Nobody can sign up with these
# names, so the demo listings cannot be taken over by registering "Lucia".
DEMO_ACCOUNTS = ("Lucia", "Omar", "Chen", "Marta", "Jonas", "Aisha")


def demo_account(username: str) -> str | None:
    return next((name for name in DEMO_ACCOUNTS if same_person(name, username)), None)


class DemoLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: Username


class Session(BaseModel):
    username: str
    token: str


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return f"scrypt${salt.hex()}${digest.hex()}"


def password_matches(password: str, stored: str) -> bool:
    try:
        scheme, salt, digest = stored.split("$")
        expected = bytes.fromhex(digest)
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    except ValueError:
        return False
    return scheme == "scrypt" and hmac.compare_digest(actual, expected)


# Checked when the username does not exist, so a wrong username takes as long as a wrong password.
_NOBODY = hash_password(secrets.token_urlsafe(16))


def _session(request: Request, username: str) -> Session:
    return Session(username=username, token=make_token(request.app.state.settings.auth_secret, username))


@router.post("/signup", response_model=Session, status_code=201)
def sign_up(data: Credentials, request: Request, conn: Connection = Depends(get_conn)):
    """Create an account and sign in."""
    if demo_account(data.username):
        raise HTTPException(status_code=409, detail="That username is already taken.")
    try:
        with conn:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (data.username, hash_password(data.password)),
            )
    except IntegrityError:
        raise HTTPException(status_code=409, detail="That username is already taken.") from None
    return _session(request, data.username)


@router.post("/login", response_model=Session)
def log_in(data: Credentials, request: Request, conn: Connection = Depends(get_conn)):
    row = conn.execute("SELECT username, password_hash FROM users WHERE username = %s", (data.username,)).fetchone()
    if not password_matches(data.password, row["password_hash"] if row else _NOBODY) or row is None:
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    # The stored spelling, so "lucia" logs in as "Lucia".
    return _session(request, row["username"])


@router.get("/me")
def who_am_i(username: str = Depends(current_user)):
    return {"username": username}


@router.get("/demo")
def demo_accounts(request: Request):
    """The accounts the page may offer as one-click sign-ins; empty unless DEMO_LOGIN is on."""
    return {"accounts": list(DEMO_ACCOUNTS) if request.app.state.settings.demo_login else []}


@router.post("/demo", response_model=Session)
def demo_log_in(data: DemoLogin, request: Request):
    """Sign in as a demo account without a password. Only when DEMO_LOGIN is on."""
    name = demo_account(data.username) if request.app.state.settings.demo_login else None
    if name is None:
        raise HTTPException(status_code=403, detail="Demo sign-in is not available.")
    return _session(request, name)
