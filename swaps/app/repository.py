"""All SQL for swap proposals. Routes never build SQL themselves."""

from app.db import Connection, DatabaseError
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


# Another accepted swap that took one of this swap's two items after this proposal was
# made. It is "after" on purpose: a listing that was swapped and later reopened can be
# proposed again, and that new proposal is not blocked by the old accepted swap.
_ITEM_ALREADY_TAKEN = (
    " AND NOT EXISTS ("
    "SELECT 1 FROM swaps AS other WHERE other.status = 'accepted' AND other.id <> swaps.id "
    "AND other.updated_at >= swaps.created_at "
    "AND (other.offered_listing_id IN (swaps.offered_listing_id, swaps.requested_listing_id) "
    "OR other.requested_listing_id IN (swaps.offered_listing_id, swaps.requested_listing_id)))"
)


def decide_swap(conn: Connection, swap_id: int, status: Status) -> Swap | None:
    """Accept or decline a swap that is still proposed. Returns None if nothing changed:
    no such swap, it was already decided, or (for accept) one of its items is already part
    of another accepted swap. Two people deciding at once cannot both win."""
    accepting = status is Status.accepted
    with conn:
        if accepting:
            # Accepts take turns. Without this, two swaps that share an item could both
            # pass the check below at the same moment and both be accepted. The lock is
            # released when this transaction ends.
            lock = conn.execute(
                "DECLARE @result INT; "
                "EXEC @result = sp_getapplock @Resource = 'accept_swap', @LockMode = 'Exclusive', "
                "@LockOwner = 'Transaction', @LockTimeout = 10000; "
                "SELECT @result AS code"
            ).fetchone()
            if lock["code"] < 0:
                raise DatabaseError("could not take the accept lock")
        row = conn.execute(
            f"UPDATE swaps SET status = %s, updated_at = SYSUTCDATETIME() OUTPUT {INSERTED} "
            "WHERE id = %s AND status = 'proposed'" + (_ITEM_ALREADY_TAKEN if accepting else ""),
            (status.value, swap_id),
        ).fetchone()
    return Swap.from_row(row) if row else None
