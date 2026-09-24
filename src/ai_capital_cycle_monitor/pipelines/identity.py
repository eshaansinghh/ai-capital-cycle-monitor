"""Verify configured company identifiers against the SEC's own records."""

from dataclasses import dataclass
from typing import Any

from ai_capital_cycle_monitor.clients.sec import normalise_cik
from ai_capital_cycle_monitor.schemas.config import Company


@dataclass(frozen=True)
class IdentityCheck:
    name: str
    expected: str
    found: str

    @property
    def passed(self) -> bool:
        return self.expected == self.found


@dataclass(frozen=True)
class IdentityReport:
    ticker: str
    sec_name: str
    checks: tuple[IdentityCheck, ...]
    informational: dict[str, str]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


def _ticker_map_cik(ticker_map: dict[str, Any], ticker: str) -> str:
    """CIK the SEC's ticker map assigns to `ticker`, or 'not found'."""
    for entry in ticker_map.values():
        if str(entry.get("ticker", "")).upper() == ticker.upper():
            return normalise_cik(entry["cik_str"])
    return "not found"


def _submissions_cik(submissions: dict[str, Any]) -> str:
    raw = submissions.get("cik")
    return normalise_cik(raw) if raw else "not found"


def _fiscal_year_end_month(submissions: dict[str, Any]) -> str:
    text = str(submissions.get("fiscalYearEnd") or "")
    return str(int(text[:2])) if len(text) == 4 and text[:2].isdigit() else "not reported"


def verify_company_identity(
    company: Company, ticker_map: dict[str, Any], submissions: dict[str, Any]
) -> IdentityReport:
    """Compare the configuration with the SEC ticker map and submissions record."""
    if company.cik is None:
        raise ValueError(f"{company.ticker} has no CIK configured")
    listed = {str(t).upper() for t in submissions.get("tickers", [])}
    exchanges = {str(e).lower() for e in submissions.get("exchanges", [])}
    checks = (
        IdentityCheck(
            "cik_in_sec_ticker_map", company.cik, _ticker_map_cik(ticker_map, company.ticker)
        ),
        IdentityCheck("cik_in_submissions", company.cik, _submissions_cik(submissions)),
        IdentityCheck(
            "ticker_listed_for_cik",
            company.ticker.upper(),
            company.ticker.upper() if company.ticker.upper() in listed else "not listed",
        ),
        IdentityCheck(
            "exchange",
            company.exchange.lower(),
            company.exchange.lower() if company.exchange.lower() in exchanges else "not listed",
        ),
        IdentityCheck(
            "fiscal_year_end_month",
            str(company.fiscal_year_end_month),
            _fiscal_year_end_month(submissions),
        ),
    )
    informational = {
        key: str(submissions.get(key) or "")
        for key in ("entityType", "sic", "sicDescription", "stateOfIncorporation", "fiscalYearEnd")
    }
    return IdentityReport(
        ticker=company.ticker,
        sec_name=str(submissions.get("name", "")),
        checks=checks,
        informational=informational,
    )
