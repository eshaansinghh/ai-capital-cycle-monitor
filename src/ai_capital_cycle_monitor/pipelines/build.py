"""Orchestrate a company build: verify identity, fetch, assemble, write and record lineage."""

from pathlib import Path

from ai_capital_cycle_monitor.clients.sec import SecClient
from ai_capital_cycle_monitor.pipelines.datasets import write_dataset
from ai_capital_cycle_monitor.pipelines.financials import CompanyDataset, build_company_dataset
from ai_capital_cycle_monitor.pipelines.identity import IdentityReport, verify_company_identity
from ai_capital_cycle_monitor.schemas.config import Company
from ai_capital_cycle_monitor.schemas.xbrl import CanonicalField, FieldMapping
from ai_capital_cycle_monitor.utils.config import load_companies, load_xbrl_mappings
from ai_capital_cycle_monitor.utils.registry import upsert_source_records


class BuildError(RuntimeError):
    """The build cannot proceed, for example an unknown ticker or unverified identifiers."""


def find_company(ticker: str, companies: list[Company] | None = None) -> Company:
    for company in companies if companies is not None else load_companies():
        if company.ticker.upper() == ticker.upper():
            return company
    raise BuildError(f"{ticker} is not in config/companies.yml")


def find_mappings(
    company: Company, mappings: dict[str, dict[CanonicalField, FieldMapping]] | None = None
) -> dict[CanonicalField, FieldMapping]:
    available = mappings if mappings is not None else load_xbrl_mappings()
    if company.ticker not in available:
        raise BuildError(
            f"no XBRL mapping is configured for {company.ticker}; add one to "
            "config/xbrl_mappings.yml after auditing its tags"
        )
    return available[company.ticker]


def verify_identity(
    company: Company, client: SecClient, *, refresh: bool = False
) -> IdentityReport:
    """Compare the configured identifiers with the SEC ticker map and submissions record."""
    if company.cik is None:
        raise BuildError(f"{company.ticker} has no CIK configured")
    ticker_map = client.company_tickers(refresh=refresh).read_json()
    submissions = client.submissions(company.cik, refresh=refresh).read_json()
    return verify_company_identity(company, ticker_map, submissions)


def build_company(
    ticker: str,
    client: SecClient,
    data_dir: Path,
    *,
    refresh: bool = False,
    companies: list[Company] | None = None,
    mappings: dict[str, dict[CanonicalField, FieldMapping]] | None = None,
) -> CompanyDataset:
    company = find_company(ticker, companies)
    cik = company.cik
    if cik is None:
        raise BuildError(f"{company.ticker} has no CIK configured")
    field_mappings = find_mappings(company, mappings)
    if not company.cik_verified:
        raise BuildError(
            f"{company.ticker}'s CIK is not marked cik_verified in config/companies.yml. "
            f"Run `verify-identity {company.ticker}` and record the result first."
        )
    report = verify_identity(company, client, refresh=refresh)
    if not report.passed:
        failed = ", ".join(check.name for check in report.checks if not check.passed)
        raise BuildError(f"{company.ticker} identifiers disagree with the SEC record: {failed}")

    snapshot = client.company_facts(cik, refresh=refresh)
    dataset = build_company_dataset(
        company, field_mappings, snapshot.read_json(), snapshot, identity=report
    )
    write_dataset(dataset, data_dir)
    upsert_source_records(dataset.registry_records, data_dir / "source_registry.csv")
    return dataset
