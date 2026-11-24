"""HTTP endpoints for swap proposals."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app import repository
from app.db import Connection, get_conn
from app.fairness import adjusted_value, fairness_score, verdict_for
from app.models import MAX_ID, DecisionIn, Status, Swap, SwapIn
from app.tokens import current_user, same_person

router = APIRouter(prefix="/swaps", tags=["swaps"])

# An id outside the range of the database column is a 422, not a database error.
SwapId = Annotated[int, Path(ge=1, le=MAX_ID)]


@router.post("", response_model=Swap, status_code=201)
def propose_swap(data: SwapIn, conn: Connection = Depends(get_conn), username: str = Depends(current_user)):
    """Score a proposed swap from the two listing snapshots, store it and return the verdict.

    You offer one of your own items for someone else's."""
    if not same_person(data.offered.owner_name, username):
        raise HTTPException(status_code=403, detail="You can only offer one of your own listings.")
    if same_person(data.requested.owner_name, username):
        raise HTTPException(status_code=403, detail="You cannot propose a swap for your own listing.")
    data = data.model_copy(update={"proposer_name": username})
    offered = adjusted_value(data.offered.estimated_value, data.offered.condition)
    requested = adjusted_value(data.requested.estimated_value, data.requested.condition)
    score = fairness_score(offered, requested)
    return repository.create_swap(conn, data, offered, requested, score, verdict_for(score))


@router.get("", response_model=list[Swap])
def list_swaps(
    limit: int = Query(default=50, ge=1, le=200),
    listing_id: int | None = Query(default=None, gt=0, le=MAX_ID),
    conn: Connection = Depends(get_conn),
):
    """Recent proposals, newest first. ?listing_id=7 keeps those that involve listing 7."""
    return repository.list_swaps(conn, limit, listing_id)


@router.get("/{swap_id}", response_model=Swap)
def get_swap(swap_id: SwapId, conn: Connection = Depends(get_conn)):
    swap = repository.get_swap(conn, swap_id)
    if swap is None:
        raise HTTPException(status_code=404, detail="Swap not found.")
    return swap


@router.patch("/{swap_id}/status", response_model=Swap)
def decide_swap(
    swap_id: SwapId,
    data: DecisionIn,
    conn: Connection = Depends(get_conn),
    username: str = Depends(current_user),
):
    """Accept or decline a proposed swap. A swap can be decided only once.

    The owner of the requested item decides. The proposer may also decline, which
    withdraws the proposal."""
    existing = repository.get_swap(conn, swap_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Swap not found.")
    is_owner = same_person(existing.requested.owner_name, username)
    is_withdrawal = data.status is Status.declined and same_person(existing.proposer_name, username)
    if not (is_owner or is_withdrawal):
        raise HTTPException(status_code=403, detail="Only the owner of the requested item can answer this swap.")
    decided = repository.decide_swap(conn, swap_id, data.status)
    if decided is not None:
        return decided
    swap = repository.get_swap(conn, swap_id)
    if swap is None:
        raise HTTPException(status_code=404, detail="Swap not found.")
    if swap.status != Status.proposed:
        raise HTTPException(status_code=409, detail="This swap was already accepted or declined.")
    # Still proposed, yet it could not be accepted: an item in it is already in another
    # accepted swap. It can still be declined.
    raise HTTPException(status_code=409, detail="One of these items is already part of another accepted swap.")
