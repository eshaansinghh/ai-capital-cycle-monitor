"""Assemble a company's quarterly revenue and cash-flow dataset, with provenance, from SEC facts."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

from ai_capital_cycle_monitor.analysis.fcf import (
    base_fcf,
    capex_including_finance_leases,
    lease_adjusted_fcf,
)
from ai_capital_cycle_monitor.analysis.ratios import (
    capital_intensity,
    cash_reinvestment_rate,
    fcf_margin,
    year_over_year_growth,
)
from ai_capital_cycle_monitor.clients.raw_store import Snapshot
from ai_capital_cycle_monitor.clients.sec import company_facts_url, filing_index_url
from ai_capital_cycle_monitor.pipelines.checks import CheckResult, CheckStatus
from ai_capital_cycle_monitor.pipelines.identity import IdentityReport
from ai_capital_cycle_monitor.pipelines.quarters import QuarterValue, derive_quarters
from ai_capital_cycle_monitor.pipelines.xbrl import SelectedFact, extract_facts, select_facts
from ai_capital_cycle_monitor.schemas.config import Company
from ai_capital_cycle_monitor.schemas.provenance import DataBasis, SourceRecord, SourceType
from ai_capital_cycle_monitor.schemas.xbrl import (
    REQUIRED_FIELDS,
    CanonicalField,
    FieldMapping,
    LeaseAdjustment,
    OtherPaymentsTreatment,
)
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

# column -> (formula, unit, note). Every one that has values is registered in the source registry.
DERIVED_SERIES: dict[str, tuple[str, str, str]] = {
    "base_fcf": (
        "operating_cash_flow - cash_capex",
        "USD",
        "Standardised base free cash flow calculated by this project. No company-reported "
        "free-cash-flow measure is used.",
    ),
    "lease_adjusted_fcf": (
        "base_fcf - finance_lease_principal - other_infrastructure_financing_payments",
        "USD",
        "Only where the finance-lease cash flows are disclosed. A component that is not "
        "disclosed is never assumed to be zero; see the company's lease treatment.",
    ),
    "capex_incl_finance_leases": (
        "cash_capex + finance_lease_assets_acquired",
        "USD",
        "Supplementary and not part of the FCF definitions. Finance-lease assets include every "
        "asset class the company discloses, so this is an upper-bound view of investment.",
    ),
    "capital_intensity": ("cash_capex / revenue", "ratio", "Missing when revenue is not positive."),
    "cash_reinvestment_rate": (
        "cash_capex / operating_cash_flow",
        "ratio",
        "Missing when operating cash flow is zero or negative.",
    ),
    "fcf_margin": ("base_fcf / revenue", "ratio", "Missing when revenue is not positive."),
    "revenue_yoy_growth": (
        "revenue / revenue in the same fiscal quarter one year earlier - 1",
        "ratio",
        "Fiscal quarters are compared with the same fiscal quarter, never a shifted row.",
    ),
}


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
    lease_adjustment: LeaseAdjustment | None = None


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


def _derived_basis(series: pd.Series) -> pd.Series:
    return pd.Series(
        [DataBasis.DERIVED.value if present else None for present in series.notna()],
        index=series.index,
        dtype="string",
    )


def _revenue_growth(quarterly: pd.DataFrame) -> pd.Series:
    """Growth against the same fiscal quarter one fiscal year earlier, matched by label."""
    prior = quarterly[[*PERIOD_KEY, "revenue"]].copy()
    prior["fiscal_year"] = prior["fiscal_year"] + 1
    matched = quarterly[PERIOD_KEY].merge(prior, on=PERIOD_KEY, how="left")
    growth = year_over_year_growth(quarterly["revenue"], matched["revenue"])
    growth.index = quarterly.index
    return growth


def _quarterly_frame(
    company: Company,
    long: pd.DataFrame,
    snapshot: Snapshot,
    lease: LeaseAdjustment | None,
) -> pd.DataFrame:
    fields = [field.value for field in CanonicalField]
    indexed = long.set_index(PERIOD_KEY)
    values = pd.concat({f: indexed.loc[indexed["field"] == f, "value"] for f in fields}, axis=1)
    bases = pd.concat(
        {f"{f}_basis": indexed.loc[indexed["field"] == f, "basis"] for f in fields}, axis=1
    )
    grouped = long.groupby(PERIOD_KEY)
    quarterly = pd.concat([values, bases], axis=1)
    for field in fields:
        quarterly[field] = quarterly[field].astype("Int64")
        quarterly[f"{field}_basis"] = quarterly[f"{field}_basis"].astype("string")
    quarterly["period_start"] = grouped["period_start"].min()
    quarterly["period_end"] = grouped["period_end"].max()
    quarterly["filed_latest"] = grouped["filed_latest"].max()
    quarterly = quarterly.sort_index().reset_index()

    quarterly["base_fcf"] = base_fcf(quarterly["operating_cash_flow"], quarterly["cash_capex"])
    quarterly["base_fcf_basis"] = _derived_basis(quarterly["base_fcf"])

    if lease is None:
        quarterly["lease_adjusted_fcf"] = pd.array([pd.NA] * len(quarterly), dtype="Int64")
    else:
        other = (
            quarterly["other_infrastructure_financing_payments"]
            if lease.other_infrastructure_financing_payments is OtherPaymentsTreatment.MAPPED
            else None
        )
        quarterly["lease_adjusted_fcf"] = lease_adjusted_fcf(
            quarterly["base_fcf"], quarterly["finance_lease_principal"], other
        )
    quarterly["lease_adjusted_fcf_basis"] = _derived_basis(quarterly["lease_adjusted_fcf"])

    quarterly["capex_incl_finance_leases"] = capex_including_finance_leases(
        quarterly["cash_capex"], quarterly["finance_lease_assets_acquired"]
    )
    quarterly["capex_incl_finance_leases_basis"] = _derived_basis(
        quarterly["capex_incl_finance_leases"]
    )

    quarterly["capital_intensity"] = capital_intensity(
        quarterly["cash_capex"], quarterly["revenue"]
    )
    quarterly["cash_reinvestment_rate"] = cash_reinvestment_rate(
        quarterly["cash_capex"], quarterly["operating_cash_flow"]
    )
    quarterly["fcf_margin"] = fcf_margin(quarterly["base_fcf"], quarterly["revenue"])
    quarterly["revenue_yoy_growth"] = _revenue_growth(quarterly)

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


def _lease_checks(quarterly: pd.DataFrame) -> list[CheckResult]:
    """Coverage of lease-adjusted FCF.

    Quarters before the company's first lease disclosure are "not disclosed" (reported once, not a
    defect and never assumed zero). Gaps after disclosure begins are warnings.
    """
    first = quarterly["finance_lease_principal"].first_valid_index()
    if first is None:
        return []
    position = quarterly.index.get_loc(first)
    label = f"{quarterly['fiscal_label'].iloc[position]}"
    checks: list[CheckResult] = []
    before = quarterly.iloc[:position]
    undisclosed = int(before["base_fcf"].notna().sum())
    if undisclosed:
        checks.append(
            CheckResult(
                "lease_disclosure_starts",
                "lease_adjusted_fcf",
                None,
                None,
                CheckStatus.SKIPPED,
                f"finance-lease cash flows are first disclosed for {label}; {undisclosed} earlier "
                "quarters have base FCF but no lease-adjusted FCF (not disclosed, not assumed "
                "zero)",
            )
        )
    after = quarterly.iloc[position:]
    gaps = after[after["base_fcf"].notna() & after["lease_adjusted_fcf"].isna()]
    if gaps.empty:
        checks.append(
            CheckResult(
                "lease_adjustment_coverage",
                "lease_adjusted_fcf",
                None,
                None,
                CheckStatus.PASS,
                f"{int(after['lease_adjusted_fcf'].notna().sum())} quarters from {label} have "
                "lease-adjusted FCF wherever base FCF exists",
            )
        )
        return checks
    checks.extend(
        CheckResult(
            "lease_adjustment_coverage",
            "lease_adjusted_fcf",
            int(row["fiscal_year"]),
            int(row["fiscal_quarter"]),
            CheckStatus.WARN,
            "base FCF exists but a lease component is missing, so lease-adjusted FCF is missing",
        )
        for _, row in gaps.iterrows()
    )
    return checks


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
    for column, (formula, unit, note) in DERIVED_SERIES.items():
        present = quarterly[quarterly[column].notna()]
        if present.empty:
            if column == "base_fcf":
                raise DatasetError(f"{company.ticker} base_fcf: no observations were produced")
            continue
        records.append(
            SourceRecord(
                **common,
                series_id=series_id(company.ticker, column),
                period_start=present["period_start"].min().date(),
                period_end=present["period_end"].max().date(),
                filed_or_published_date=present["filed_latest"].max().date(),
                unit=unit,
                reported_or_estimated=DataBasis.DERIVED,
                transformation=formula,
                notes=note,
            )
        )
    return records


def _validate_lease_configuration(
    company: Company,
    mappings: dict[CanonicalField, FieldMapping],
    lease: LeaseAdjustment | None,
) -> None:
    principal = CanonicalField.FINANCE_LEASE_PRINCIPAL in mappings
    other = CanonicalField.OTHER_INFRASTRUCTURE_FINANCING_PAYMENTS in mappings
    if lease is None:
        if principal:
            raise DatasetError(
                f"{company.ticker} maps finance_lease_principal but has no reviewed lease "
                "adjustment entry; state whether other infrastructure payments exist"
            )
        if other:
            raise DatasetError(
                f"{company.ticker} maps other infrastructure payments without finance-lease "
                "principal, so lease-adjusted FCF cannot be formed"
            )
        return
    if not principal:
        raise DatasetError(
            f"{company.ticker} has a lease adjustment entry but no principal mapping"
        )
    mapped = lease.other_infrastructure_financing_payments is OtherPaymentsTreatment.MAPPED
    if mapped and not other:
        raise DatasetError(f"{company.ticker} declares other payments mapped but has no mapping")
    if not mapped and other:
        raise DatasetError(
            f"{company.ticker} declares no other payments but maps other_infrastructure_payments"
        )


def build_company_dataset(
    company: Company,
    mappings: dict[CanonicalField, FieldMapping],
    company_facts: dict[str, Any],
    snapshot: Snapshot,
    identity: IdentityReport | None = None,
    lease: LeaseAdjustment | None = None,
) -> CompanyDataset:
    """Extract, select, derive and assemble every mapped field for one company."""
    if company.cik is None:
        raise DatasetError(f"{company.ticker} has no CIK, so it has no SEC filings to read")
    missing = [field.value for field in REQUIRED_FIELDS if field not in mappings]
    if missing:
        raise DatasetError(f"{company.ticker} has no XBRL mapping for: {', '.join(missing)}")
    _validate_lease_configuration(company, mappings, lease)

    quarters: list[QuarterValue] = []
    checks: list[CheckResult] = _identity_checks(identity) if identity else []
    for field in CanonicalField:
        if field not in mappings:
            continue
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
    quarterly = _quarterly_frame(company, long, snapshot, lease)
    if lease is not None:
        checks.extend(_lease_checks(quarterly))
    return CompanyDataset(
        ticker=company.ticker,
        long=long,
        quarterly=quarterly,
        checks=_checks_frame(checks),
        registry_records=_registry_records(company, mappings, long, quarterly, snapshot),
        source_url=snapshot.url,
        retrieved_at_utc=snapshot.retrieved_at_utc,
        lease_adjustment=lease,
    )
