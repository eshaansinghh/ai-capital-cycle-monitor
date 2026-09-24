"""Data-quality check results shared by the pipeline steps."""

from dataclasses import dataclass
from enum import StrEnum


class CheckStatus(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class CheckResult:
    """One validation outcome. Violations get a row each; a passing check gets a summary row."""

    check: str
    field: str
    fiscal_year: int | None
    fiscal_quarter: int | None
    status: CheckStatus
    detail: str
    expected: int | float | None = None
    actual: int | float | None = None


def summarise(
    check: str, field: str, checked: int, violations: list[CheckResult], noun: str
) -> list[CheckResult]:
    """Return the violations, or one summary row saying how many items passed (or none applied)."""
    if violations:
        return violations
    if checked == 0:
        return [CheckResult(check, field, None, None, CheckStatus.SKIPPED, f"no {noun} to check")]
    return [CheckResult(check, field, None, None, CheckStatus.PASS, f"{checked} {noun} checked")]
