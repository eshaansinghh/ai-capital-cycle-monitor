"""Derive standalone fiscal quarters from SEC facts, which mix quarterly and year-to-date periods.

A 10-Q income statement reports three-month values, but its cash-flow statement is cumulative from
the start of the fiscal year, and no filing reports the fourth quarter on its own. A quarter is
therefore either a reported three-month fact or the difference of two cumulative facts. A quarter
whose components are missing stays missing. Nothing is estimated.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from ai_capital_cycle_monitor.pipelines.checks import CheckResult, CheckStatus, summarise
from ai_capital_cycle_monitor.pipelines.xbrl import SelectedFact
from ai_capital_cycle_monitor.schemas.provenance import DataBasis
from ai_capital_cycle_monitor.utils.fiscal import (
    duration_months,
    fiscal_period_for_end,
    fiscal_quarter_end,
    fiscal_quarter_start,
    fiscal_year_start,
    is_near,
)

type Period = tuple[int, int]

_CUMULATIVE_NAME = {1: "three-month", 2: "six-month", 3: "nine-month", 4: "twelve-month"}


@dataclass(frozen=True)
class QuarterValue:
    """One fiscal quarter of one field: a value with its basis, or missing with a reason."""

    field: str
    fiscal_year: int
    fiscal_quarter: int
    period_start: date
    period_end: date
    value: int | float | None
    basis: DataBasis | None
    transformation: str
    components: tuple[SelectedFact, ...]
    missing_reason: str | None = None


def _next(period: Period) -> Period:
    fiscal_year, quarter = period
    return (fiscal_year, quarter + 1) if quarter < 4 else (fiscal_year + 1, 1)


def _index_facts(
    selected: list[SelectedFact], fye_month: int
) -> tuple[dict[Period, SelectedFact], dict[Period, SelectedFact]]:
    """Split facts into cumulative-from-year-start and standalone-quarter, keyed by fiscal period.

    Classification uses dates only. Facts fitting neither shape (for example one-month periods)
    are ignored.
    """
    cumulative: dict[Period, SelectedFact] = {}
    standalone: dict[Period, SelectedFact] = {}
    for item in selected:
        fact = item.fact
        months = duration_months(fact.start, fact.end)
        period = fiscal_period_for_end(fact.end, fye_month)
        if months is None or period is None:
            continue
        fiscal_year, quarter = period
        if months == 3 * quarter and is_near(fact.start, fiscal_year_start(fiscal_year, fye_month)):
            target = cumulative
        elif (
            months == 3
            and quarter > 1
            and is_near(fact.start, fiscal_quarter_start(fiscal_year, quarter, fye_month))
        ):
            target = standalone
        else:
            continue
        if period in target:
            raise ValueError(
                f"ambiguous facts for fiscal period {period}: {fact.start}..{fact.end}"
            )
        target[period] = item
    return cumulative, standalone


def _build_quarter(
    field: str,
    period: Period,
    cumulative: dict[Period, SelectedFact],
    standalone: dict[Period, SelectedFact],
    fye_month: int,
) -> QuarterValue:
    fiscal_year, quarter = period
    direct = cumulative.get(period) if quarter == 1 else standalone.get(period)
    if direct is not None:
        return QuarterValue(
            field,
            fiscal_year,
            quarter,
            direct.fact.start,
            direct.fact.end,
            direct.fact.value,
            DataBasis.REPORTED,
            "reported three-month value",
            (direct,),
        )

    if quarter == 1:
        reason = "no three-month fact starting at the fiscal year start"
    else:
        upper, lower = cumulative.get(period), cumulative.get((fiscal_year, quarter - 1))
        if upper is not None and lower is not None:
            transformation = (
                f"{_CUMULATIVE_NAME[quarter]} year-to-date minus "
                f"{_CUMULATIVE_NAME[quarter - 1]} year-to-date"
            )
            return QuarterValue(
                field,
                fiscal_year,
                quarter,
                lower.fact.end + timedelta(days=1),
                upper.fact.end,
                upper.fact.value - lower.fact.value,
                DataBasis.DERIVED,
                transformation,
                (upper, lower),
            )
        absent = [
            f"{_CUMULATIVE_NAME[q]} year-to-date fact"
            for q, item in ((quarter, upper), (quarter - 1, lower))
            if item is None
        ]
        reason = "no standalone quarter fact and missing " + " and ".join(absent)
    return QuarterValue(
        field,
        fiscal_year,
        quarter,
        fiscal_quarter_start(fiscal_year, quarter, fye_month),
        fiscal_quarter_end(fiscal_year, quarter, fye_month),
        None,
        None,
        "",
        (),
        reason,
    )


def derive_quarters(
    field: str,
    selected: list[SelectedFact],
    fye_month: int,
    *,
    expect_non_negative: bool = False,
) -> tuple[list[QuarterValue], list[CheckResult]]:
    """Build quarters from Q1 of the first fiscal year with a fact through the last fact.

    Gaps, including a missing first quarter, appear as missing quarters. Quarters after the last
    available fact are not created, because they have not been reported.
    """
    cumulative, standalone = _index_facts(selected, fye_month)
    periods = sorted(set(cumulative) | set(standalone))
    if not periods:
        return [], []
    quarters: list[QuarterValue] = []
    period = (periods[0][0], 1)
    while period <= periods[-1]:
        quarters.append(_build_quarter(field, period, cumulative, standalone, fye_month))
        period = _next(period)
    unit = rounding_unit(selected)
    checks = [
        *_standalone_vs_cumulative(field, cumulative, standalone, unit),
        *_quarters_sum_to_year(field, quarters, cumulative, unit),
        *_signs(field, quarters, expect_non_negative),
        *_revisions_and_conflicts(field, quarters),
        *_missing_quarters(field, quarters),
    ]
    return quarters, checks


def rounding_unit(selected: list[SelectedFact]) -> int:
    """The reporting scale implied by the values.

    1,000,000 if every value is a whole number of millions, else 1,000 if thousands, else 1.
    Reported figures are rounded to this unit.
    """
    values = [item.fact.value for item in selected]
    if not values or any(float(value) != int(value) for value in values):
        return 1
    for unit in (1_000_000, 1_000):
        if all(int(value) % unit == 0 for value in values):
            return unit
    return 1


def _rounding_note(differences: list[tuple[str, float]], unit: int) -> str:
    if not differences:
        return ""
    shown = ", ".join(f"{label} {amount / unit:,.0f}" for label, amount in differences[:6])
    return f"; {len(differences)} differ by rounding only (in reporting units: {shown})"


def _with_detail(check: CheckResult, suffix: str) -> CheckResult:
    return CheckResult(**{**vars(check), "detail": check.detail + suffix})


def _standalone_vs_cumulative(
    field: str,
    cumulative: dict[Period, SelectedFact],
    standalone: dict[Period, SelectedFact],
    unit: int,
) -> list[CheckResult]:
    """A reported three-month value should equal the year-to-date difference, to within rounding.

    Each of the three reported figures is rounded to `unit`, so they can disagree by up to 1.5
    units without any error in the filing.
    """
    tolerance = 1.5 * unit
    checked, violations, rounding = 0, [], []
    for (fiscal_year, quarter), item in sorted(standalone.items()):
        upper, lower = (
            cumulative.get((fiscal_year, quarter)),
            cumulative.get((fiscal_year, quarter - 1)),
        )
        if upper is None or lower is None:
            continue
        checked += 1
        expected = upper.fact.value - lower.fact.value
        difference = abs(item.fact.value - expected)
        if difference > tolerance:
            violations.append(
                CheckResult(
                    "standalone_vs_cumulative",
                    field,
                    fiscal_year,
                    quarter,
                    CheckStatus.WARN,
                    "standalone quarter fact differs from the year-to-date difference by more "
                    "than rounding",
                    expected,
                    item.fact.value,
                )
            )
        elif difference:
            rounding.append((f"FY{fiscal_year % 100:02d} Q{quarter}", difference))
    result = summarise("standalone_vs_cumulative", field, checked, violations, "quarters")
    if not violations and checked:
        result[0] = _with_detail(result[0], _rounding_note(rounding, unit))
    return result


def _quarters_sum_to_year(
    field: str,
    quarters: list[QuarterValue],
    cumulative: dict[Period, SelectedFact],
    unit: int,
) -> list[CheckResult]:
    """The four quarters should sum to the reported year, to within rounding.

    Five rounded figures are involved (four quarters and the year), so they can disagree by up to
    2.5 units without any error in the filing.
    """
    tolerance = 2.5 * unit
    by_period = {(q.fiscal_year, q.fiscal_quarter): q for q in quarters}
    checked, violations, rounding = 0, [], []
    for fiscal_year in sorted({q.fiscal_year for q in quarters}):
        year_fact = cumulative.get((fiscal_year, 4))
        parts = [by_period.get((fiscal_year, quarter)) for quarter in (1, 2, 3, 4)]
        if year_fact is None or any(part is None or part.value is None for part in parts):
            continue
        checked += 1
        total = sum(part.value for part in parts if part is not None and part.value is not None)
        difference = abs(total - year_fact.fact.value)
        if difference > tolerance:
            violations.append(
                CheckResult(
                    "quarters_sum_to_year",
                    field,
                    fiscal_year,
                    None,
                    CheckStatus.FAIL,
                    "the four quarters do not sum to the reported fiscal-year value by more "
                    "than rounding",
                    year_fact.fact.value,
                    total,
                )
            )
        elif difference:
            rounding.append((f"FY{fiscal_year % 100:02d}", difference))
    result = summarise("quarters_sum_to_year", field, checked, violations, "fiscal years")
    if not violations and checked:
        result[0] = _with_detail(result[0], _rounding_note(rounding, unit))
    return result


def _signs(
    field: str, quarters: list[QuarterValue], expect_non_negative: bool
) -> list[CheckResult]:
    if not expect_non_negative:
        return [CheckResult("sign", field, None, None, CheckStatus.SKIPPED, "no sign expectation")]
    present = [q for q in quarters if q.value is not None]
    violations = [
        CheckResult(
            "sign",
            field,
            q.fiscal_year,
            q.fiscal_quarter,
            CheckStatus.FAIL,
            "negative value where a non-negative amount is expected",
            None,
            q.value,
        )
        for q in present
        if q.value is not None and q.value < 0
    ]
    return summarise("sign", field, len(present), violations, "quarters")


def _revisions_and_conflicts(field: str, quarters: list[QuarterValue]) -> list[CheckResult]:
    checked = 0
    revisions: list[CheckResult] = []
    conflicts: list[CheckResult] = []
    for quarter in quarters:
        for item in quarter.components:
            checked += 1
            if item.later_revisions:
                revisions.append(
                    CheckResult(
                        "later_revision",
                        field,
                        quarter.fiscal_year,
                        quarter.fiscal_quarter,
                        CheckStatus.WARN,
                        "a later filing reports a different value for a component period: "
                        + ", ".join(f"{f.accession}={f.value}" for f in item.later_revisions),
                        item.fact.value,
                        item.later_revisions[-1].value,
                    )
                )
            if item.tag_conflicts:
                conflicts.append(
                    CheckResult(
                        "tag_conflict",
                        field,
                        quarter.fiscal_year,
                        quarter.fiscal_quarter,
                        CheckStatus.WARN,
                        "another candidate tag reports a different value: "
                        + ", ".join(f"{f.tag}={f.value}" for f in item.tag_conflicts),
                        item.fact.value,
                        item.tag_conflicts[0].value,
                    )
                )
    return [
        *summarise("later_revision", field, checked, revisions, "component facts"),
        *summarise("tag_conflict", field, checked, conflicts, "component facts"),
    ]


def _missing_quarters(field: str, quarters: list[QuarterValue]) -> list[CheckResult]:
    violations = [
        CheckResult(
            "missing_quarter",
            field,
            q.fiscal_year,
            q.fiscal_quarter,
            CheckStatus.WARN,
            q.missing_reason or "missing",
        )
        for q in quarters
        if q.value is None
    ]
    return summarise("missing_quarter", field, len(quarters), violations, "quarters")
