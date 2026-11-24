"""All SQL for listings. Routes never build SQL themselves."""

from app.db import Connection
from app.models import Category, Listing, ListingIn, Status

COLUMNS = "id, title, description, category, condition, estimated_value, owner_name, status, created_at, updated_at"
INSERTED = ", ".join(f"INSERTED.{column}" for column in COLUMNS.split(", "))


def list_listings(conn: Connection, status: Status | None = None, category: Category | None = None) -> list[Listing]:
    where, params = [], []
    if status is not None:
        where.append("status = %s")
        params.append(status.value)
    if category is not None:
        where.append("category = %s")
        params.append(category.value)
    sql = f"SELECT {COLUMNS} FROM listings"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC, id DESC"
    return [Listing.from_row(row) for row in conn.execute(sql, params)]


def get_listing(conn: Connection, listing_id: int) -> Listing | None:
    row = conn.execute(f"SELECT {COLUMNS} FROM listings WHERE id = %s", (listing_id,)).fetchone()
    return Listing.from_row(row) if row else None


def create_listing(conn: Connection, data: ListingIn) -> Listing:
    with conn:
        row = conn.execute(
            "INSERT INTO listings (title, description, category, condition, estimated_value, owner_name) "
            f"OUTPUT {INSERTED} VALUES (%s, %s, %s, %s, %s, %s)",
            (
                data.title,
                data.description,
                data.category.value,
                data.condition,
                data.estimated_value,
                data.owner_name,
            ),
        ).fetchone()
    return Listing.from_row(row)


def update_listing(conn: Connection, listing_id: int, data: ListingIn) -> Listing | None:
    with conn:
        row = conn.execute(
            "UPDATE listings SET title = %s, description = %s, category = %s, condition = %s, "
            "estimated_value = %s, owner_name = %s, updated_at = SYSUTCDATETIME() "
            f"OUTPUT {INSERTED} WHERE id = %s",
            (
                data.title,
                data.description,
                data.category.value,
                data.condition,
                data.estimated_value,
                data.owner_name,
                listing_id,
            ),
        ).fetchone()
    return Listing.from_row(row) if row else None


def set_status(conn: Connection, listing_id: int, status: Status) -> Listing | None:
    with conn:
        row = conn.execute(
            f"UPDATE listings SET status = %s, updated_at = SYSUTCDATETIME() OUTPUT {INSERTED} WHERE id = %s",
            (status.value, listing_id),
        ).fetchone()
    return Listing.from_row(row) if row else None


def delete_listing(conn: Connection, listing_id: int) -> bool:
    with conn:
        deleted = conn.execute("DELETE FROM listings WHERE id = %s", (listing_id,)).rowcount
    return deleted == 1
