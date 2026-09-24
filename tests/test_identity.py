"""Tests for identifier verification logic.

The dictionaries mimic the shape of SEC responses with synthetic values. They exercise the
comparison logic only. Checks against real SEC responses use retrieved data separately.
"""

import copy
from typing import Any

import pytest

from ai_capital_cycle_monitor.pipelines.identity import verify_company_identity
from ai_capital_cycle_monitor.schemas.config import Company

COMPANY = Company.model_validate(
    {
        "ticker": "TEST",
        "name": "Test Co",
        "role": "hyperscaler",
        "exchange": "TESTX",
        "currency": "USD",
        "filer_type": "domestic_10k",
        "cik": "0000000001",
        "fiscal_year_end_month": 6,
    }
)
TICKER_MAP: dict[str, Any] = {
    "0": {"cik_str": 999, "ticker": "OTHER", "title": "OTHER CO"},
    "1": {"cik_str": 1, "ticker": "TEST", "title": "TEST CO"},
}
SUBMISSIONS: dict[str, Any] = {
    "cik": "0000000001",
    "name": "TEST CO",
    "tickers": ["TEST"],
    "exchanges": ["TestX"],
    "fiscalYearEnd": "0630",
    "sic": "1234",
    "sicDescription": "Test industry",
    "entityType": "operating",
    "stateOfIncorporation": "XX",
}


def _report(ticker_map: dict[str, Any] = TICKER_MAP, submissions: dict[str, Any] = SUBMISSIONS):
    return verify_company_identity(COMPANY, ticker_map, submissions)


def test_matching_records_pass_every_check() -> None:
    report = _report()
    assert report.passed
    assert {check.name for check in report.checks} == {
        "cik_in_sec_ticker_map",
        "cik_in_submissions",
        "ticker_listed_for_cik",
        "exchange",
        "fiscal_year_end_month",
    }
    assert report.sec_name == "TEST CO"
    assert report.informational["sicDescription"] == "Test industry"


@pytest.mark.parametrize(
    ("mutate", "failing"),
    [
        (lambda tm, sub: tm["1"].update(cik_str=2), "cik_in_sec_ticker_map"),
        (lambda tm, sub: tm.pop("1"), "cik_in_sec_ticker_map"),
        (lambda tm, sub: sub.update(cik="0000000002"), "cik_in_submissions"),
        (lambda tm, sub: sub.update(tickers=["ELSE"]), "ticker_listed_for_cik"),
        (lambda tm, sub: sub.update(exchanges=["Elsewhere"]), "exchange"),
        (lambda tm, sub: sub.update(fiscalYearEnd="1231"), "fiscal_year_end_month"),
        (lambda tm, sub: sub.pop("fiscalYearEnd"), "fiscal_year_end_month"),
    ],
)
def test_each_mismatch_is_detected(mutate, failing: str) -> None:
    ticker_map, submissions = copy.deepcopy(TICKER_MAP), copy.deepcopy(SUBMISSIONS)
    mutate(ticker_map, submissions)
    report = _report(ticker_map, submissions)
    assert not report.passed
    assert [c.name for c in report.checks if not c.passed] == [failing]


def test_company_without_a_cik_cannot_be_verified() -> None:
    no_cik = COMPANY.model_copy(update={"cik": None})
    with pytest.raises(ValueError, match="no CIK"):
        verify_company_identity(no_cik, TICKER_MAP, SUBMISSIONS)
