"""Request and response shapes for swap proposals. Validation lives here, not in the routes."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.fairness import MAX_CONDITION, MIN_CONDITION, Verdict

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


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40), fits_column(40)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80), fits_column(80)]
Message = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300), fits_column(300)]


class Status(StrEnum):
    proposed = "proposed"
    accepted = "accepted"
    declined = "declined"


class ListingSnapshot(BaseModel):
    """A listing as the browser saw it when the swap was proposed.

    The Swaps service never calls the Listings service; the UI sends these fields.
    """

    model_config = ConfigDict(extra="ignore")

    listing_id: int = Field(gt=0, le=MAX_ID)
    title: Title
    owner_name: Name
    condition: int = Field(ge=MIN_CONDITION, le=MAX_CONDITION)
    estimated_value: float = Field(gt=0, le=MAX_VALUE_EUR)

    @field_validator("estimated_value")
    @classmethod
    def whole_cents(cls, value: float) -> float:
        # Same rule as the Listings service: money is stored in cents.
        rounded = round(value, 2)
        if rounded <= 0:
            raise ValueError("estimated_value must be at least 0.01")
        return rounded


class SwapIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Set by the service from the signed-in account; anything sent here is replaced.
    proposer_name: Name | None = None
    message: Message = ""
    offered: ListingSnapshot
    requested: ListingSnapshot

    @model_validator(mode="after")
    def two_different_listings(self) -> Self:
        if self.offered.listing_id == self.requested.listing_id:
            raise ValueError("offered and requested must be two different listings")
        return self


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Status

    @model_validator(mode="after")
    def is_a_decision(self) -> Self:
        if self.status is Status.proposed:
            raise ValueError("status must be accepted or declined")
        return self


class SwapSide(BaseModel):
    listing_id: int
    title: str
    owner_name: str
    condition: int
    estimated_value: float
    # The estimate after the condition adjustment; this is what the score compares.
    adjusted_value: float


class Swap(BaseModel):
    id: int
    proposer_name: str
    message: str
    offered: SwapSide
    requested: SwapSide
    fairness_score: float
    verdict: Verdict
    status: Status
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: dict) -> "Swap":
        def side(prefix: str) -> SwapSide:
            return SwapSide(
                listing_id=row[f"{prefix}_listing_id"],
                title=row[f"{prefix}_title"],
                owner_name=row[f"{prefix}_owner_name"],
                condition=row[f"{prefix}_condition"],
                estimated_value=float(row[f"{prefix}_value"]),
                adjusted_value=float(row[f"{prefix}_adjusted"]),
            )

        return cls(
            id=row["id"],
            proposer_name=row["proposer_name"],
            message=row["message"],
            offered=side("offered"),
            requested=side("requested"),
            fairness_score=float(row["fairness_score"]),
            verdict=row["verdict"],
            status=row["status"],
            # SQL Server stores UTC without an offset; say so in the API.
            created_at=row["created_at"].replace(tzinfo=UTC),
            updated_at=row["updated_at"].replace(tzinfo=UTC),
        )
