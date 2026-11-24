"""The fairness rule for a proposed swap. Pure functions: no database, no HTTP.

Each side's estimated value is adjusted for its condition, then the smaller
adjusted value is divided by the larger one. The result is between 0 and 1,
where 1 means both sides are worth the same.

All arithmetic is done in whole cents with integers, so a result never depends
on floating-point rounding: 79.996% is below the 80% line and stays below it.
"""

from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

MIN_CONDITION = 1
MAX_CONDITION = 5

FAIR_FROM = 0.8
LOPSIDED_FROM = 0.5

# The score keeps four decimals: 0.5714 is 57.14%.
SCORE_STEPS = 10_000


class Verdict(StrEnum):
    fair = "Fair trade"
    lopsided = "Lopsided"
    very_uneven = "Very uneven"


def to_cents(euros: float) -> int:
    """Euros to whole cents, half a cent rounding up (0.005 -> 1 cent)."""
    return int((Decimal(str(euros)) * 100).to_integral_value(rounding=ROUND_HALF_UP))


def adjusted_value(estimated_value: float, condition: int) -> float:
    """Scale the owner's estimate by condition: 60% at condition 1, 100% at condition 5.

    The result is in euros, rounded to the cent (half a cent rounds up).
    """
    if estimated_value < 0:
        raise ValueError("estimated_value cannot be negative")
    if isinstance(condition, bool) or not isinstance(condition, int):
        raise ValueError("condition must be a whole number")
    if not MIN_CONDITION <= condition <= MAX_CONDITION:
        raise ValueError(f"condition must be between {MIN_CONDITION} and {MAX_CONDITION}")
    # value x (0.5 + condition / 10) is value x (5 + condition) / 10; adding 5 before the
    # whole-number division rounds half a cent up.
    cents = (to_cents(estimated_value) * (5 + condition) + 5) // 10
    return cents / 100


def fairness_score(offered_adjusted: float, requested_adjusted: float) -> float:
    """min / max of the two adjusted values, cut (not rounded) to 4 decimals.

    Cutting matters at the boundaries: 0.79996 must not become 0.8 and turn a
    lopsided swap into a fair one. The order of the two sides does not matter.
    Two items worth nothing are an even trade (1.0); something for nothing is as
    uneven as it gets (0.0).
    """
    if offered_adjusted < 0 or requested_adjusted < 0:
        raise ValueError("adjusted values cannot be negative")
    smaller, larger = sorted((to_cents(offered_adjusted), to_cents(requested_adjusted)))
    if larger == 0:
        return 1.0
    return (smaller * SCORE_STEPS // larger) / SCORE_STEPS


def verdict_for(score: float) -> Verdict:
    """Fair at 0.8 or above, Lopsided from 0.5 up to 0.8, Very uneven below 0.5."""
    if not 0 <= score <= 1:
        raise ValueError("score must be between 0 and 1")
    if score >= FAIR_FROM:
        return Verdict.fair
    if score >= LOPSIDED_FROM:
        return Verdict.lopsided
    return Verdict.very_uneven
