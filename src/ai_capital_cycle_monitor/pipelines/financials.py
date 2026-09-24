"""Assemble a company's quarterly revenue and cash-flow dataset, with provenance, from SEC facts."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from ai_capital_cycle_monitor.analysis.fcf import base_fcf
from ai_capital_cycle_monitor.clients.raw_store import Snapshot
from ai_capital_cycle_monitor.clients.sec import company_facts_url, filing_index_url
from ai_capital_cycle_monitor.pipelines.checks import CheckResult, CheckStatus
from ai_capital_cycle_monitor.pipelines.identity import IdentityReport
from ai_capital_cycle_monitor.pipelines.quarters import QuarterValue, derive_quarters
from ai_capital_cycle_monitor.pipelines.xbrl import SelectedFact, extract_facts, select_facts
from ai_capital_cycle_monitor.schemas.config import Company
from ai_capital_cycle_monitor.schemas.provenance import DataBasis, SourceRecord, SourceType
from ai_capital_cycle_monitor.schemas.xbrl import CanonicalField, FieldMapping
from ai_capital_cycle_monitor.utils.fiscal import fiscal_label, fiscal_period_for_end

PERIOD_KEY = ["fiscal_year", "fiscal_quarter"]
CHECK_COLUMNS = [
    "check",
    "field",
    "fiscal_year",
    "fiscal_quarter",
    "status",
    "detail",
    "expected",
    "actual",
]


class DatasetError(RuntimeError):
    """The facts cannot form a dataset (for example a mapped field has no observations)."""


@dataclass(frozen=True)
class CompanyDataset:
    ticker: str
    long: pd.DataFrame
    quarterly: pd.DataFrame
    checks: pd.DataFrame
    registry_records: list[SourceRecord]
    source_url: str
    retrieved_at_utc: datetime


def _from_fiscal_year(
    selected: list[SelectedFact], fye_month: int, first_fiscal_year: int | None
) -> list[SelectedFact]:
    """Drop facts from fiscal years before `first_fiscal_year`. Facts on no fiscal period stay."""
    if first_fiscal_year is None:
        return selected
    kept = []
    for item in selected:
        period = fiscal_period_for_end(item.fact.end, fye_month)
        if period is None or period[0] >= first_fiscal_year:
            kept.append(item)
    return kept


def series_id(ticker: str, field: str) -> str:
    return f"sec_xbrl.{ticker.lower()}.{field}.quarterly"


def source_name(company: Company) -> str:
    return f"U.S. Securities and Exchange Commission, EDGAR XBRL Company Facts API ({company.name})"


def _component(company: Company, item: SelectedFact) -> dict[str, Any]:
    fact = item.fact
    return {
        "taxonomy": fact.taxonomy,
        "tag": fact.tag,
        "start": fact.start.isoformat(),
        "end": fact.end.isoformat(),
        "value": fact.value,
        "unit": fact.unit,
        "accession": fact.accession,
        "form": fact.form,
        "filed": fact.filed.isoformat(),
        "filing_fiscal_year": fact.filing_fiscal_year,
        "filing_fiscal_period": fact.filing_fiscal_period,
        "filing_index_url": filing_index_url(company.cik or "", fact.accession),
    }


def _long_frame(
    company: Company,
    quarters: list[QuarterValue],
    mappings: dict[CanonicalField, FieldMapping],
    snapshot: Snapshot,
) -> pd.DataFrame:
    rows = []
    for quarter in quarters:
        filed = [item.fact.filed for item in quarter.components]
        rows.append(
            {
                "series_id": series_id(company.ticker, quarter.field),
                "ticker": company.ticker,
                "cik": company.cik,
                "field": quarter.field,
                "fiscal_year": quarter.fiscal_year,
                "fiscal_quarter": quarter.fiscal_quarter,
                "fiscal_label": fiscal_label(quarter.fiscal_year, quarter.fiscal_quarter),
                "period_start": quarter.period_start,
                "period_end": quarter.period_end,
                "unit": mappings[CanonicalField(quarter.field)].unit,
                "currency": company.currency,
                "basis": quarter.basis.value if quarter.basis else None,
                "tags": "; ".join(sorted({item.fact.tag for item in quarter.components})) or None,
                "transformation": quarter.transformation or None,
                "missing_reason": quarter.missing_reason,
                "filed_latest": max(filed) if filed else None,
                "components": json.dumps([_component(company, i) for i in quarter.components]),
                "source_name": source_name(company),
                "source_url": snapshot.url,
                "source_type": SourceType.SEC_FILING.value,
                "retrieved_at_utc": snapshot.retrieved_at_utc,
                "source_sha256": snapshot.sha256,
            }
        )
    frame = pd.DataFrame(rows)
    frame["value"] = pd.array([quarter.value for quarter in quarters], dtype="Int64")
    for column in ("period_start", "period_end", "filed_latest"):
        frame[column] = pd.to_datetime(frame[column]).astype("datetime64[us]")
    frame["basis"] = frame["basis"].astype("string")
    return frame


def _quarterly_frame(company: Company, long: pd.DataFrame, snapshot: Snapshot) -> pd.DataFrame:
    fields = [field.value for field in CanonicalField]
    indexed = long.set_index(PERIOD_KEY)
    values = pd.concat({f: indexed.loc[indexed["field"] == f, "value"] for f in fields}, axis=1)
    bases = pd.concat(
        {f"{f}_basis": indexed.loc[indexed["field"] == f, "basis"] for f in fields}, axis=1
    )
    grouped = long.groupby(PERIOD_KEY)
    quarterly = pd.concat([values, bases], axis=1)
    quarterly["period_start"] = grouped["period_start"].min()
    quarterly["period_end"] = grouped["period_end"].max()
    quarterly["filed_latest"] = grouped["filed_latest"].max()
    quarterly["base_fcf"] = base_fcf(quarterly["operating_cash_flow"], quarterly["cash_capex"])
    quarterly["base_fcf_basis"] = pd.Series(
        [DataBasis.DERIVED.value if present else None for present in quarterly["base_fcf"].notna()],
        index=quarterly.index,
        dtype="string",
    )
    quarterly = quarterly.sort_index().reset_index()
    quarterly.insert(0, "ticker", company.ticker)
    quarterly.insert(
        3,
        "fiscal_label",
        [
            fiscal_label(y, q)
            for y, q in zip(quarterly["fiscal_year"], quarterly["fiscal_quarter"], strict=True)
        ],
    )
    quarterly["source_url"] = snapshot.url
    quarterly["source_retrieved_at_utc"] = snapshot.retrieved_at_utc
    return quarterly


def _checks_frame(checks: list[CheckResult]) -> pd.DataFrame:
    rows = [{**vars(check), "status": check.status.value} for check in checks]
    frame = pd.DataFrame(rows, columns=CHECK_COLUMNS)
    for column in ("fiscal_year", "fiscal_quarter"):
        frame[column] = frame[column].astype("Int64")
    for column in ("expected", "actual"):
        frame[column] = frame[column].astype("Float64")
    return frame


def _identity_checks(report: IdentityReport) -> list[CheckResult]:
    return [
        CheckResult(
            f"identity_{check.name}",
            "company",
            None,
            None,
            CheckStatus.PASS if check.passed else CheckStatus.FAIL,
            f"expected {check.expected}, SEC reports {check.found}",
        )
        for check in report.checks
    ]


def _registry_records(
    company: Company,
    mappings: dict[CanonicalField, FieldMapping],
    long: pd.DataFrame,
    quarterly: pd.DataFrame,
    snapshot: Snapshot,
) -> list[SourceRecord]:
    common: dict[str, Any] = {
        "source_name": source_name(company),
        "source_url": company_facts_url(company.cik or ""),
        "source_type": SourceType.SEC_FILING,
        "retrieved_at_utc": snapshot.retrieved_at_utc,
        "currency": company.currency,
    }
    records = []
    for field, mapping in mappings.items():
        observed = long[(long["field"] == field.value) & long["value"].notna()]
        if observed.empty:
            raise DatasetError(f"{company.ticker} {field.value}: no observations were produced")
        derived = bool((observed["basis"] == DataBasis.DERIVED.value).any())
        tags = sorted({tag for text in observed["tags"].dropna() for tag in text.split("; ")})
        note = f"Tags used: {', '.join(tags)}. Facts are selected as first reported."
        records.append(
            SourceRecord(
                **common,
                series_id=series_id(company.ticker, field.value),
                period_start=observed["period_start"].min().date(),
                period_end=observed["period_end"].max().date(),
                filed_or_published_date=observed["filed_latest"].max().date(),
                unit=mapping.unit,
                reported_or_estimated=DataBasis.DERIVED if derived else DataBasis.REPORTED,
                transformation=(
                    "Where no three-month fact is reported (typically the fourth quarter), the "
                    "quarter is the difference of two cumulative year-to-date facts. "
                    "Per-observation basis and component facts are in the dataset."
                    if derived
                    else "Reported three-month values."
                ),
                notes=" ".join(filter(None, [note, mapping.notes])),
            )
        )
    fcf = quarterly[quarterly["base_fcf"].notna()]
    if fcf.empty:
        raise DatasetError(f"{company.ticker} base_fcf: no observations were produced")
    records.append(
        SourceRecord(
            **common,
            series_id=series_id(company.ticker, "base_fcf"),
            period_start=fcf["period_start"].min().date(),
            period_end=fcf["period_end"].max().date(),
            filed_or_published_date=fcf["filed_latest"].max().date(),
            unit="USD",
            reported_or_estimated=DataBasis.DERIVED,
            transformation="operating_cash_flow - cash_capex",
            notes=(
                "Standardised base free cash flow calculated by this project. No company-reported "
                "free-cash-flow measure is used."
            ),
        )
    )
    return records


def build_company_dataset(
    company: Company,
    mappings: dict[CanonicalField, FieldMapping],
    company_facts: dict[str, Any],
    snapshot: Snapshot,
    identity: IdentityReport | None = None,
) -> CompanyDataset:
    """Extract, select, derive and assemble every mapped field for one company."""
    if company.cik is None:
        raise DatasetError(f"{company.ticker} has no CIK, so it has no SEC filings to read")
    missing = [field.value for field in CanonicalField if field not in mappings]
    if missing:
        raise DatasetError(f"{company.ticker} has no XBRL mapping for: {', '.join(missing)}")

    quarters: list[QuarterValue] = []
    checks: list[CheckResult] = _identity_checks(identity) if identity else []
    for field in CanonicalField:
        mapping = mappings[field]
        facts = extract_facts(company_facts, mapping.candidates, unit=mapping.unit)
        field_quarters, field_checks = derive_quarters(
            field.value,
            _from_fiscal_year(
                select_facts(facts, mapping.candidates),
                company.fiscal_year_end_month,
                mapping.first_fiscal_year,
            ),
            company.fiscal_year_end_month,
            expect_non_negative=mapping.expect_non_negative,
        )
        quarters.extend(field_quarters)
        checks.extend(field_checks)
    if not quarters:
        raise DatasetError(f"{company.ticker}: no quarterly facts found for the mapped tags")

    long = _long_frame(company, quarters, mappings, snapshot)
    quarterly = _quarterly_frame(company, long, snapshot)
    return CompanyDataset(
        ticker=company.ticker,
        long=long,
        quarterly=quarterly,
        checks=_checks_frame(checks),
        registry_records=_registry_records(company, mappings, long, quarterly, snapshot),
        source_url=snapshot.url,
        retrieved_at_utc=snapshot.retrieved_at_utc,
    )
