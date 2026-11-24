"""app/db.py exists twice, once per service, because each service is built and deployed
from its own folder. The two copies must stay the same apart from the service name, or a
fix made in one (a connection-pool rule, a retry change) silently misses the other.

If this fails, apply the same change to `listings/app/db.py` (or the other way round).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def masked(service: str) -> str:
    return (ROOT / service / "app" / "db.py").read_text().replace(service, "SERVICE")


def test_both_services_use_the_same_database_code():
    assert masked("listings") == masked("swaps"), "listings/app/db.py and swaps/app/db.py have drifted apart"
