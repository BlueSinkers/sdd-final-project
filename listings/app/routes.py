"""HTTP endpoints for listings."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response

from app import repository
from app.db import Connection, get_conn
from app.models import MAX_ID, Category, Listing, ListingIn, Status, StatusIn

router = APIRouter(prefix="/listings", tags=["listings"])

# An id outside the range of the database column is a 422, not a database error.
ListingId = Annotated[int, Path(ge=1, le=MAX_ID)]


def found(listing: Listing | None) -> Listing:
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found.")
    return listing


@router.get("", response_model=list[Listing])
def list_listings(
    status: Status | None = None,
    category: Category | None = None,
    conn: Connection = Depends(get_conn),
):
    """All listings, newest first. Filter with ?status=open and ?category=books."""
    return repository.list_listings(conn, status, category)


@router.post("", response_model=Listing, status_code=201)
def create_listing(data: ListingIn, conn: Connection = Depends(get_conn)):
    return repository.create_listing(conn, data)


@router.get("/{listing_id}", response_model=Listing)
def get_listing(listing_id: ListingId, conn: Connection = Depends(get_conn)):
    return found(repository.get_listing(conn, listing_id))


@router.put("/{listing_id}", response_model=Listing)
def update_listing(listing_id: ListingId, data: ListingIn, conn: Connection = Depends(get_conn)):
    return found(repository.update_listing(conn, listing_id, data))


@router.patch("/{listing_id}/status", response_model=Listing)
def set_status(listing_id: ListingId, data: StatusIn, conn: Connection = Depends(get_conn)):
    """Mark a listing swapped once the trade happened, or open it again."""
    return found(repository.set_status(conn, listing_id, data.status))


@router.delete("/{listing_id}", status_code=204)
def delete_listing(listing_id: ListingId, conn: Connection = Depends(get_conn)):
    if not repository.delete_listing(conn, listing_id):
        raise HTTPException(status_code=404, detail="Listing not found.")
    return Response(status_code=204)
