"""The fairness rule for a proposed swap. Pure functions: no database, no HTTP.

Each side's estimated value is adjusted for its condition, then the smaller
adjusted value is divided by the larger one. The result is between 0 and 1,
where 1 means both sides are worth the same.
"""

from enum import StrEnum

MIN_CONDITION = 1
MAX_CONDITION = 5

FAIR_FROM = 0.8
LOPSIDED_FROM = 0.5


class Verdict(StrEnum):
    fair = "Fair trade"
    lopsided = "Lopsided"
    very_uneven = "Very uneven"


def adjusted_value(estimated_value: float, condition: int) -> float:
    """Scale the owner's estimate by condition: 60% at condition 1, 100% at condition 5."""
    if estimated_value < 0:
        raise ValueError("estimated_value cannot be negative")
    if isinstance(condition, bool) or not isinstance(condition, int):
        raise ValueError("condition must be a whole number")
    if not MIN_CONDITION <= condition <= MAX_CONDITION:
        raise ValueError(f"condition must be between {MIN_CONDITION} and {MAX_CONDITION}")
    return estimated_value * (0.5 + condition / 10)


def fairness_score(offered_adjusted: float, requested_adjusted: float) -> float:
    """min / max of the two adjusted values, rounded to 4 decimals.

    The order of the two sides does not matter. Two items worth nothing are an
    even trade (1.0); something for nothing is as uneven as it gets (0.0).
    """
    if offered_adjusted < 0 or requested_adjusted < 0:
        raise ValueError("adjusted values cannot be negative")
    larger = max(offered_adjusted, requested_adjusted)
    if larger == 0:
        return 1.0
    return round(min(offered_adjusted, requested_adjusted) / larger, 4)


def verdict_for(score: float) -> Verdict:
    """Fair at 0.8 or above, Lopsided from 0.5 up to 0.8, Very uneven below 0.5."""
    if not 0 <= score <= 1:
        raise ValueError("score must be between 0 and 1")
    if score >= FAIR_FROM:
        return Verdict.fair
    if score >= LOPSIDED_FROM:
        return Verdict.lopsided
    return Verdict.very_uneven
