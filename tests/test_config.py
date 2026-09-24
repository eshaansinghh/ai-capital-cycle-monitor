"""Tests for the YAML configuration schemas and loaders.

Inline fixtures are obviously synthetic software inputs used only inside pytest temp directories.
"""

import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_capital_cycle_monitor.schemas.config import Company, EventDefinition
from ai_capital_cycle_monitor.schemas.xbrl import CanonicalField
from ai_capital_cycle_monitor.utils.config import (
    load_companies,
    load_events,
    load_metrics,
    load_xbrl_mappings,
)

INITIAL_UNIVERSE = {"MSFT", "GOOGL", "AMZN", "META", "ORCL", "NVDA", "CRWV"}
EXPECTED_METRICS = {
    "base_fcf",
    "lease_adjusted_fcf",
    "capital_intensity",
    "cash_reinvestment_rate",
    "fcf_margin",
    "incremental_cash_conversion",
    "fcf_yield",
    "net_debt",
}


def _company(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "ticker": "TEST",
        "name": "Test Co",
        "role": "hyperscaler",
        "exchange": "TESTX",
        "currency": "USD",
        "filer_type": "domestic_10k",
        "cik": "0000000001",
        "fiscal_year_end_month": 12,
    }
    return base | overrides


def test_committed_companies_cover_initial_universe() -> None:
    tickers = {company.ticker for company in load_companies()}
    assert tickers >= INITIAL_UNIVERSE


def test_committed_companies_carry_no_financial_fields() -> None:
    forbidden = {"revenue", "capex", "market_cap", "price"}
    assert forbidden.isdisjoint(Company.model_fields)


def test_domestic_filer_requires_cik() -> None:
    with pytest.raises(ValidationError, match="cik is required"):
        Company.model_validate(_company(cik=None))


def test_non_sec_company_may_omit_cik() -> None:
    company = Company.model_validate(_company(filer_type="non_sec", cik=None))
    assert company.cik is None


def test_malformed_cik_is_rejected() -> None:
    with pytest.raises(ValidationError, match="cik"):
        Company.model_validate(_company(cik="789019"))


def test_duplicate_tickers_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "companies.yml"
    entry = (
        "  - {ticker: DUP, name: Dup, role: hyperscaler, exchange: X, currency: USD,"
        " filer_type: domestic_10k, cik: '0000000001', fiscal_year_end_month: 12}\n"
    )
    path.write_text("companies:\n" + entry * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate tickers"):
        load_companies(path)


def test_missing_top_level_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "companies.yml"
    path.write_text("something_else: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="top-level list under 'companies'"):
        load_companies(path)


def test_committed_metrics_cover_blueprint_definitions() -> None:
    assert {metric.id for metric in load_metrics()} == EXPECTED_METRICS


def test_metric_formula_identifiers_are_declared_inputs() -> None:
    for metric in load_metrics():
        identifiers = set(re.findall(r"[a-z_]+", metric.formula))
        assert identifiers == set(metric.inputs), metric.id


def test_committed_events_catalogue_is_empty_until_verified() -> None:
    assert load_events() == []


def test_event_requires_timezone_and_exposed_tickers() -> None:
    event = {
        "event_id": "unit_test_event",
        "title": "Unit-test event",
        "first_public_timestamp_utc": "2026-01-01T00:00:00Z",
        "source_url": "https://example.com/unit-test",
        "source_type": "regulator",
        "exposed_tickers": ["TEST"],
        "benchmark_tickers": ["BENCH"],
    }
    assert EventDefinition.model_validate(event).status.value == "candidate"
    with pytest.raises(ValidationError, match="timezone-aware"):
        naive = event | {"first_public_timestamp_utc": "2026-01-01T00:00:00"}
        EventDefinition.model_validate(naive)
    with pytest.raises(ValidationError, match="exposed_tickers"):
        EventDefinition.model_validate(event | {"exposed_tickers": []})


def _mapping_file(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "xbrl_mappings.yml"
    path.write_text(body, encoding="utf-8")
    return path


def test_xbrl_mappings_load_by_ticker_and_canonical_field(tmp_path: Path) -> None:
    path = _mapping_file(
        tmp_path,
        "mappings:\n"
        "  TEST:\n"
        "    revenue:\n"
        "      statement: income_statement\n"
        "      expect_non_negative: true\n"
        "      candidates:\n"
        "        - {taxonomy: test, tag: FirstChoice}\n"
        "        - {taxonomy: test, tag: SecondChoice}\n",
    )
    mapping = load_xbrl_mappings(path)["TEST"][CanonicalField.REVENUE]
    assert [candidate.tag for candidate in mapping.candidates] == ["FirstChoice", "SecondChoice"]
    assert mapping.unit == "USD"
    assert mapping.expect_non_negative is True


@pytest.mark.parametrize(
    "field_body",
    [
        "    not_a_field:\n      statement: s\n      candidates: [{taxonomy: t, tag: T}]\n",
        "    revenue:\n      statement: s\n      candidates: []\n",
        "    revenue:\n      statement: s\n      typo: 1\n"
        "      candidates: [{taxonomy: t, tag: T}]\n",
    ],
)
def test_invalid_xbrl_mappings_are_rejected(tmp_path: Path, field_body: str) -> None:
    path = _mapping_file(tmp_path, "mappings:\n  TEST:\n" + field_body)
    with pytest.raises(ValueError):
        load_xbrl_mappings(path)


def test_xbrl_mappings_file_needs_a_top_level_mapping(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="under 'mappings'"):
        load_xbrl_mappings(_mapping_file(tmp_path, "other: {}\n"))


def test_committed_microsoft_mapping_covers_every_canonical_field() -> None:
    mapping = load_xbrl_mappings()["MSFT"]
    assert set(mapping) == set(CanonicalField)
    assert all(field.first_fiscal_year == 2018 for field in mapping.values())
    revenue_tags = [c.tag for c in mapping[CanonicalField.REVENUE].candidates]
    assert revenue_tags[0] == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert "SalesRevenueGoodsNet" not in revenue_tags  # a component, not total revenue
    assert mapping[CanonicalField.CASH_CAPEX].expect_non_negative is True
