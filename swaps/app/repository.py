"""All SQL for swap proposals. Routes never build SQL themselves."""

from app.db import Connection
from app.fairness import Verdict
from app.models import Status, Swap, SwapIn

COLUMNS = (
    "id, proposer_name, message, "
    "offered_listing_id, offered_title, offered_owner_name, offered_condition, offered_value, offered_adjusted, "
    "requested_listing_id, requested_title, requested_owner_name, requested_condition, requested_value, "
    "requested_adjusted, fairness_score, verdict, status, created_at, updated_at"
)
INSERTED = ", ".join(f"INSERTED.{column}" for column in COLUMNS.split(", "))


def create_swap(
    conn: Connection,
    data: SwapIn,
    offered_adjusted: float,
    requested_adjusted: float,
    score: float,
    verdict: Verdict,
) -> Swap:
    with conn:
        row = conn.execute(
            "INSERT INTO swaps (proposer_name, message, "
            "offered_listing_id, offered_title, offered_owner_name, offered_condition, offered_value, "
            "offered_adjusted, requested_listing_id, requested_title, requested_owner_name, "
            "requested_condition, requested_value, requested_adjusted, fairness_score, verdict) "
            f"OUTPUT {INSERTED} "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                data.proposer_name,
                data.message,
                data.offered.listing_id,
                data.offered.title,
                data.offered.owner_name,
                data.offered.condition,
                data.offered.estimated_value,
                offered_adjusted,
                data.requested.listing_id,
                data.requested.title,
                data.requested.owner_name,
                data.requested.condition,
                data.requested.estimated_value,
                requested_adjusted,
                score,
                verdict.value,
            ),
        ).fetchone()
    return Swap.from_row(row)


def list_swaps(conn: Connection, limit: int, listing_id: int | None = None) -> list[Swap]:
    # TOP takes no bound parameter in pymssql; limit is an int validated by the route.
    sql = f"SELECT TOP {int(limit)} {COLUMNS} FROM swaps"
    params: tuple = ()
    if listing_id is not None:
        sql += " WHERE offered_listing_id = %s OR requested_listing_id = %s"
        params = (listing_id, listing_id)
    sql += " ORDER BY created_at DESC, id DESC"
    return [Swap.from_row(row) for row in conn.execute(sql, params)]


def get_swap(conn: Connection, swap_id: int) -> Swap | None:
    row = conn.execute(f"SELECT {COLUMNS} FROM swaps WHERE id = %s", (swap_id,)).fetchone()
    return Swap.from_row(row) if row else None


def decide_swap(conn: Connection, swap_id: int, status: Status) -> Swap | None:
    """Accept or decline a swap that is still proposed. Returns None if it was not proposed
    (already decided, or no such swap), so two people deciding at once cannot both win."""
    with conn:
        row = conn.execute(
            f"UPDATE swaps SET status = %s, updated_at = SYSUTCDATETIME() OUTPUT {INSERTED} "
            "WHERE id = %s AND status = 'proposed'",
            (status.value, swap_id),
        ).fetchone()
    return Swap.from_row(row) if row else None
