"""The fairness rule: adjustment by condition, the score, and the verdict boundaries."""

import pytest

from app.fairness import Verdict, adjusted_value, fairness_score, to_cents, verdict_for


@pytest.mark.parametrize(
    ("condition", "expected"),
    [(1, 60.0), (2, 70.0), (3, 80.0), (4, 90.0), (5, 100.0)],
)
def test_adjusted_value_scales_with_condition(condition, expected):
    assert adjusted_value(100, condition) == pytest.approx(expected)


def test_adjusted_value_of_a_worthless_item_is_zero():
    assert adjusted_value(0, 3) == 0


@pytest.mark.parametrize("condition", [0, 6, -1, 2.5, "3", None, True])
def test_adjusted_value_rejects_a_condition_outside_1_to_5(condition):
    with pytest.raises(ValueError):
        adjusted_value(10, condition)


def test_adjusted_value_rejects_a_negative_value():
    with pytest.raises(ValueError):
        adjusted_value(-0.01, 3)


def test_adjusted_value_rounds_half_a_cent_up():
    # 1.05 x 0.7 = 0.735 exactly; binary floating point would call it 0.73.
    assert adjusted_value(1.05, 2) == 0.74
    assert adjusted_value(0.01, 1) == 0.01  # 0.6 of a cent is still one cent


@pytest.mark.parametrize(
    ("euros", "cents"), [(0, 0), (0.01, 1), (0.005, 1), (0.004, 0), (19.99, 1999), (10_000, 1_000_000)]
)
def test_to_cents(euros, cents):
    assert to_cents(euros) == cents


def test_equal_values_score_one():
    assert fairness_score(42.5, 42.5) == 1.0


def test_score_is_the_smaller_value_over_the_larger():
    assert fairness_score(30, 40) == 0.75
    assert fairness_score(1, 3) == 0.3333


def test_score_does_not_depend_on_which_side_is_offered():
    assert fairness_score(18, 31.5) == fairness_score(31.5, 18)


@pytest.mark.parametrize(
    ("smaller", "larger", "score", "verdict"),
    [
        (8000.00, 10000.00, 0.8, Verdict.fair),
        (7999.99, 10000.00, 0.7999, Verdict.lopsided),
        (7999.60, 10000.00, 0.7999, Verdict.lopsided),  # 0.79996 must not round up to fair
        (5000.00, 10000.00, 0.5, Verdict.lopsided),
        (4999.60, 10000.00, 0.4999, Verdict.very_uneven),  # 0.49996 must not round up
        (18.00, 22.50, 0.8, Verdict.fair),
    ],
)
def test_score_is_cut_not_rounded_at_the_boundaries(smaller, larger, score, verdict):
    assert fairness_score(smaller, larger) == score
    assert verdict_for(fairness_score(larger, smaller)) is verdict


def test_two_worthless_items_are_an_even_trade():
    assert fairness_score(0, 0) == 1.0


def test_something_for_nothing_scores_zero():
    assert fairness_score(0, 25) == 0.0
    assert fairness_score(25, 0) == 0.0


def test_score_rejects_negative_values():
    with pytest.raises(ValueError):
        fairness_score(-1, 10)
    with pytest.raises(ValueError):
        fairness_score(10, -1)


@pytest.mark.parametrize(
    ("score", "verdict"),
    [
        (1.0, Verdict.fair),
        (0.8, Verdict.fair),  # boundary: exactly 0.8 is fair
        (0.7999, Verdict.lopsided),
        (0.5, Verdict.lopsided),  # boundary: exactly 0.5 is lopsided
        (0.4999, Verdict.very_uneven),
        (0.0, Verdict.very_uneven),
    ],
)
def test_verdict_boundaries(score, verdict):
    assert verdict_for(score) is verdict


@pytest.mark.parametrize("score", [-0.01, 1.01])
def test_verdict_rejects_a_score_outside_0_to_1(score):
    with pytest.raises(ValueError):
        verdict_for(score)


def test_verdict_texts_are_what_the_ui_shows():
    assert [verdict.value for verdict in Verdict] == ["Fair trade", "Lopsided", "Very uneven"]


def test_worked_example_from_the_backlog():
    # Jacket: 35 euros, condition 4 -> 31.50. Lamp: 18 euros, condition 5 -> 18.00.
    jacket = adjusted_value(35, 4)
    lamp = adjusted_value(18, 5)
    assert jacket == pytest.approx(31.5)
    assert lamp == pytest.approx(18.0)
    score = fairness_score(jacket, lamp)
    assert score == 0.5714
    assert verdict_for(score) is Verdict.lopsided
