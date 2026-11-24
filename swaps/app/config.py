"""Runtime settings, read only from environment variables."""

import os
from dataclasses import dataclass

MIN_SECRET_LENGTH = 32


@dataclass(frozen=True)
class Settings:
    # mssql://user:password@host:1433/database
    database_url: str
    # Browser origins allowed to call this API (the UI's address), comma-separated in CORS_ORIGINS.
    cors_origins: tuple[str, ...] = ()
    # Signs and checks sign-in tokens. Both services get the same value (AUTH_SECRET).
    auth_secret: str = ""
    # The commit the image was built from, baked in by the Dockerfile.
    version: str = "dev"


def load_settings() -> Settings:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set, e.g. mssql://user:password@host:1433/swaps")
    auth_secret = os.environ.get("AUTH_SECRET", "")
    if len(auth_secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(f"AUTH_SECRET is not set or shorter than {MIN_SECRET_LENGTH} characters")
    origins = os.environ.get("CORS_ORIGINS", "")
    return Settings(
        database_url=database_url,
        auth_secret=auth_secret,
        cors_origins=tuple(origin.strip().rstrip("/") for origin in origins.split(",") if origin.strip()),
        version=os.environ.get("GIT_SHA", "dev"),
    )
