"""Request and response shapes for swap proposals. Validation lives here, not in the routes."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.fairness import MAX_CONDITION, MIN_CONDITION, Verdict

MAX_VALUE_EUR = 10_000

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Message = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]


class Status(StrEnum):
    proposed = "proposed"
    accepted = "accepted"
    declined = "declined"


class ListingSnapshot(BaseModel):
    """A listing as the browser saw it when the swap was proposed.

    The Swaps service never calls the Listings service; the UI sends these fields.
    """

    model_config = ConfigDict(extra="ignore")

    listing_id: int = Field(gt=0)
    title: Title
    owner_name: Name
    condition: int = Field(ge=MIN_CONDITION, le=MAX_CONDITION)
    estimated_value: float = Field(gt=0, le=MAX_VALUE_EUR)


class SwapIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposer_name: Name
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
