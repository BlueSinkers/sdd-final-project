"""Request and response shapes for listings. Validation lives here, not in the routes."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator

MAX_VALUE_EUR = 10_000

# SQL Server's INT, used for every id.
MAX_ID = 2_147_483_647


def fits_column(max_units: int):
    """NVARCHAR(n) counts UTF-16 units, so an emoji takes two. Check the length the
    way the database will, instead of failing later with a database error."""

    def check(value: str) -> str:
        if len(value.encode("utf-16-le")) // 2 > max_units:
            raise ValueError(f"must fit in {max_units} characters (an emoji counts as two)")
        return value

    return AfterValidator(check)


class Category(StrEnum):
    clothing = "clothing"
    books = "books"
    electronics = "electronics"
    home = "home"
    sports = "sports"
    other = "other"


class Status(StrEnum):
    open = "open"
    swapped = "swapped"


Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80), fits_column(80)]
OwnerName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40), fits_column(40)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500), fits_column(500)]


class ListingIn(BaseModel):
    """What a student sends to post or edit a listing."""

    model_config = ConfigDict(extra="forbid")

    title: Title
    description: Description = ""
    category: Category
    # 1 = heavily used, 5 = like new.
    condition: int = Field(ge=1, le=5)
    # The owner's own estimate, in euros.
    estimated_value: float = Field(gt=0, le=MAX_VALUE_EUR)
    owner_name: OwnerName

    @field_validator("estimated_value")
    @classmethod
    def whole_cents(cls, value: float) -> float:
        rounded = round(value, 2)
        if rounded <= 0:
            raise ValueError("estimated_value must be at least 0.01")
        return rounded


class StatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status


class Listing(BaseModel):
    id: int
    title: str
    description: str
    category: Category
    condition: int
    estimated_value: float
    owner_name: str
    status: Status
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: dict) -> "Listing":
        return cls(
            **{
                **row,
                "estimated_value": float(row["estimated_value"]),
                # SQL Server stores UTC without an offset; say so in the API.
                "created_at": row["created_at"].replace(tzinfo=UTC),
                "updated_at": row["updated_at"].replace(tzinfo=UTC),
            }
        )
