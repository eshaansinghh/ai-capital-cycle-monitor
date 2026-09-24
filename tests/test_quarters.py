"""Tests for fiscal-quarter derivation and its checks (software fixtures only)."""

from datetime import date

import pytest

from ai_capital_cycle_monitor.pipelines.checks import CheckStatus
from ai_capital_cycle_monitor.pipelines.quarters import derive_quarters, rounding_unit
from ai_capital_cycle_monitor.pipelines.xbrl import SelectedFact
from ai_capital_cycle_monitor.schemas.provenance import DataBasis
from factories import FY_START, FYE_MONTH, cumulative, fact, selected


def _derive(items: list[SelectedFact], **kwargs: bool):
    return derive_quarters("field", items, FYE_MONTH, **kwargs)


def _statuses(checks, name: str) -> list[CheckStatus]:
    return [c.status for c in checks if c.check == name]


def test_cumulative_facts_become_standalone_quarters() -> None:
    quarters, _ = _derive(cumulative())
    assert [q.value for q in quarters] == [10, 15, 20, 25]
    assert [q.fiscal_quarter for q in quarters] == [1, 2, 3, 4]
    assert {q.fiscal_year for q in quarters} == {2025}


def test_basis_and_transformation_are_recorded() -> None:
    quarters, _ = _derive(cumulative())
    assert quarters[0].basis is DataBasis.REPORTED
    assert all(q.basis is DataBasis.DERIVED for q in quarters[1:])
    assert quarters[2].transformation == "nine-month year-to-date minus six-month year-to-date"
    assert [len(q.components) for q in quarters] == [1, 2, 2, 2]


def test_derived_quarter_dates_follow_the_component_facts() -> None:
    quarters, _ = _derive(cumulative())
    assert (quarters[1].period_start, quarters[1].period_end) == (
        date(2024, 10, 1),
        date(2024, 12, 31),
    )
    assert (quarters[3].period_start, quarters[3].period_end) == (
        date(2025, 4, 1),
        date(2025, 6, 30),
    )


def test_fiscal_period_comes_from_dates_not_from_filing_labels() -> None:
    items = [
        selected(FY_START, "2024-09-30", 10, filing_fiscal_year=1999),
        selected(FY_START, "2024-12-31", 25, filing_fiscal_year=1999),
    ]
    quarters, _ = _derive(items)
    assert [(q.fiscal_year, q.fiscal_quarter) for q in quarters] == [(2025, 1), (2025, 2)]


def test_quarters_not_yet_reported_are_not_created() -> None:
    quarters, _ = _derive(cumulative((10, 25, None, None)))
    assert [(q.fiscal_quarter, q.value) for q in quarters] == [(1, 10), (2, 15)]


def test_missing_component_leaves_quarters_missing_not_zero() -> None:
    quarters, checks = _derive(cumulative((10, 25, None, 70)))
    assert [q.value for q in quarters] == [10, 15, None, None]
    assert quarters[2].basis is None
    assert "nine-month year-to-date fact" in (quarters[2].missing_reason or "")
    assert "nine-month year-to-date fact" in (quarters[3].missing_reason or "")
    assert _statuses(checks, "missing_quarter") == [CheckStatus.WARN, CheckStatus.WARN]


def test_missing_first_quarter_is_reported_missing() -> None:
    quarters, _ = _derive(cumulative((None, 25, 45, 70)))
    assert quarters[0].value is None
    assert quarters[1].value is None  # six-month minus a missing three-month cannot be formed
    assert quarters[2].value == 20


def test_interior_gap_between_fiscal_years_appears_as_missing_quarters() -> None:
    later_year = [
        selected("2025-07-01", "2025-09-30", 5),
        selected("2025-07-01", "2025-12-31", 12),
    ]
    quarters, _ = _derive([*cumulative((10, 25, None, None)), *later_year])
    assert [(q.fiscal_year, q.fiscal_quarter, q.value) for q in quarters] == [
        (2025, 1, 10),
        (2025, 2, 15),
        (2025, 3, None),
        (2025, 4, None),
        (2026, 1, 5),
        (2026, 2, 7),
    ]


def test_standalone_quarter_fact_is_used_and_agreement_is_checked() -> None:
    items = [*cumulative(), selected("2024-10-01", "2024-12-31", 15)]
    quarters, checks = _derive(items)
    assert quarters[1].basis is DataBasis.REPORTED
    assert quarters[1].value == 15
    assert _statuses(checks, "standalone_vs_cumulative") == [CheckStatus.PASS]


def test_disagreeing_standalone_fact_warns_and_sum_check_fails() -> None:
    items = [*cumulative(), selected("2024-10-01", "2024-12-31", 20)]
    quarters, checks = _derive(items)
    assert quarters[1].value == 20
    (warning,) = [c for c in checks if c.check == "standalone_vs_cumulative"]
    assert (warning.status, warning.expected, warning.actual) == (CheckStatus.WARN, 15, 20)
    (failure,) = [c for c in checks if c.check == "quarters_sum_to_year"]
    assert (failure.status, failure.expected, failure.actual) == (CheckStatus.FAIL, 70, 75)


def test_consistent_quarters_pass_the_sum_check() -> None:
    _, checks = _derive(cumulative())
    assert _statuses(checks, "quarters_sum_to_year") == [CheckStatus.PASS]


def test_negative_value_fails_sign_check_only_when_a_sign_is_expected() -> None:
    items = cumulative((10, 5, 45, 70))  # second quarter derives to -5
    _, unconstrained = _derive(items)
    assert _statuses(unconstrained, "sign") == [CheckStatus.SKIPPED]
    _, constrained = _derive(items, expect_non_negative=True)
    (failure,) = [c for c in constrained if c.check == "sign"]
    assert (failure.status, failure.fiscal_quarter, failure.actual) == (CheckStatus.FAIL, 2, -5)


def test_later_revisions_and_tag_conflicts_surface_as_warnings() -> None:
    revised = fact("2024-07-01", "2024-09-30", 11, accession="0000000000-00-000009")
    conflicting = fact("2024-07-01", "2024-09-30", 12, tag="Other")
    first = selected("2024-07-01", "2024-09-30", 10)
    flagged = SelectedFact(first.fact, later_revisions=(revised,), tag_conflicts=(conflicting,))
    _, checks = _derive([flagged])
    assert _statuses(checks, "later_revision") == [CheckStatus.WARN]
    assert _statuses(checks, "tag_conflict") == [CheckStatus.WARN]


def test_clean_facts_pass_revision_and_conflict_checks() -> None:
    _, checks = _derive(cumulative())
    assert _statuses(checks, "later_revision") == [CheckStatus.PASS]
    assert _statuses(checks, "tag_conflict") == [CheckStatus.PASS]


def test_irrelevant_durations_are_ignored() -> None:
    one_month = selected("2024-07-01", "2024-07-31", 3)
    quarters, _ = _derive([*cumulative(), one_month])
    assert [q.value for q in quarters] == [10, 15, 20, 25]


def test_ambiguous_duplicate_periods_are_rejected() -> None:
    clash = selected("2024-07-02", "2024-09-30", 99)  # also a Q1 fact, within date tolerance
    with pytest.raises(ValueError, match="ambiguous"):
        _derive([*cumulative(), clash])


def test_no_facts_yield_no_quarters() -> None:
    assert _derive([]) == ([], [])


MILLION = 1_000_000


def _in_millions(values: tuple[int | None, ...]) -> list[SelectedFact]:
    return cumulative(tuple(None if v is None else v * MILLION for v in values))


def test_rounding_unit_is_inferred_from_the_values() -> None:
    assert rounding_unit(_in_millions((10, 25, 45, 70))) == 1_000_000
    assert rounding_unit(cumulative((10_000, 25_000, 45_000, 70_000))) == 1_000
    assert rounding_unit(cumulative((10, 25, 45, 71))) == 1
    assert rounding_unit([]) == 1


def test_a_one_million_disagreement_in_millions_is_rounding_not_an_error() -> None:
    """Reported in millions, five rounded figures can differ by a million with no filing error."""
    items = [*_in_millions((10, 25, 45, 70)), selected("2024-10-01", "2024-12-31", 16 * MILLION)]
    quarters, checks = _derive(items)
    assert quarters[1].value == 16 * MILLION  # the reported standalone value is used as reported
    standalone = [c for c in checks if c.check == "standalone_vs_cumulative"]
    total = [c for c in checks if c.check == "quarters_sum_to_year"]
    assert [c.status for c in standalone] == [CheckStatus.PASS]
    assert [c.status for c in total] == [CheckStatus.PASS]
    assert "differ by rounding only" in standalone[0].detail
    assert "FY25 Q2 1" in standalone[0].detail
    assert "FY25 1" in total[0].detail


def test_a_disagreement_beyond_rounding_still_warns_and_fails_when_in_millions() -> None:
    items = [*_in_millions((10, 25, 45, 70)), selected("2024-10-01", "2024-12-31", 20 * MILLION)]
    _, checks = _derive(items)
    assert _statuses(checks, "standalone_vs_cumulative") == [CheckStatus.WARN]
    assert _statuses(checks, "quarters_sum_to_year") == [CheckStatus.FAIL]


def test_exactly_matching_values_carry_no_rounding_note() -> None:
    _, checks = _derive(_in_millions((10, 25, 45, 70)))
    total = next(c for c in checks if c.check == "quarters_sum_to_year")
    assert total.status is CheckStatus.PASS
    assert "rounding" not in total.detail
