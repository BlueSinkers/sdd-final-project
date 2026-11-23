"""HTTP endpoints for swap proposals."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app import repository
from app.db import Connection, get_conn
from app.fairness import adjusted_value, fairness_score, verdict_for
from app.models import DecisionIn, Swap, SwapIn

router = APIRouter(prefix="/swaps", tags=["swaps"])


@router.post("", response_model=Swap, status_code=201)
def propose_swap(data: SwapIn, conn: Connection = Depends(get_conn)):
    """Score a proposed swap from the two listing snapshots, store it and return the verdict."""
    offered = round(adjusted_value(data.offered.estimated_value, data.offered.condition), 2)
    requested = round(adjusted_value(data.requested.estimated_value, data.requested.condition), 2)
    score = fairness_score(offered, requested)
    return repository.create_swap(conn, data, offered, requested, score, verdict_for(score))


@router.get("", response_model=list[Swap])
def list_swaps(
    limit: int = Query(default=50, ge=1, le=200),
    listing_id: int | None = Query(default=None, gt=0),
    conn: Connection = Depends(get_conn),
):
    """Recent proposals, newest first. ?listing_id=7 keeps those that involve listing 7."""
    return repository.list_swaps(conn, limit, listing_id)


@router.get("/{swap_id}", response_model=Swap)
def get_swap(swap_id: int, conn: Connection = Depends(get_conn)):
    swap = repository.get_swap(conn, swap_id)
    if swap is None:
        raise HTTPException(status_code=404, detail="Swap not found.")
    return swap


@router.patch("/{swap_id}/status", response_model=Swap)
def decide_swap(swap_id: int, data: DecisionIn, conn: Connection = Depends(get_conn)):
    """Accept or decline a proposed swap. A swap can be decided only once."""
    decided = repository.decide_swap(conn, swap_id, data.status)
    if decided is not None:
        return decided
    if repository.get_swap(conn, swap_id) is None:
        raise HTTPException(status_code=404, detail="Swap not found.")
    raise HTTPException(status_code=409, detail="This swap was already accepted or declined.")
