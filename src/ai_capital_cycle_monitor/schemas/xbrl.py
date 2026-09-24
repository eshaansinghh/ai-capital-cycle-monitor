"""Schemas for mapping canonical financial fields to XBRL tags, per company."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CanonicalField(StrEnum):
    REVENUE = "revenue"
    OPERATING_CASH_FLOW = "operating_cash_flow"
    CASH_CAPEX = "cash_capex"
    # Optional: mapped only where a company discloses them (see LeaseAdjustment).
    FINANCE_LEASE_PRINCIPAL = "finance_lease_principal"
    OTHER_INFRASTRUCTURE_FINANCING_PAYMENTS = "other_infrastructure_financing_payments"
    FINANCE_LEASE_ASSETS_ACQUIRED = "finance_lease_assets_acquired"


REQUIRED_FIELDS = (
    CanonicalField.REVENUE,
    CanonicalField.OPERATING_CASH_FLOW,
    CanonicalField.CASH_CAPEX,
)


class TagRef(BaseModel):
    """One candidate XBRL concept, identified by taxonomy and tag name."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    taxonomy: str = Field(min_length=1)
    tag: str = Field(min_length=1)


class FieldMapping(BaseModel):
    """How one canonical field is read from a company's XBRL facts.

    Candidates are listed in priority order. For each period the first candidate that reports it is
    used, and the tag chosen is recorded with every value. Disagreeing candidates are flagged.
    `first_fiscal_year` drops earlier periods, for example where an accounting change put the
    company's own history on two incompatible bases.
    """

    model_config = ConfigDict(extra="forbid")

    statement: str = Field(min_length=1)
    unit: str = "USD"
    expect_non_negative: bool = False
    first_fiscal_year: int | None = Field(default=None, ge=1990)
    candidates: list[TagRef] = Field(min_length=1)
    notes: str | None = None


class OtherPaymentsTreatment(StrEnum):
    """How lease-adjusted FCF treats 'other infrastructure financing payments'."""

    MAPPED = "mapped"  # a disclosed cash-flow line, mapped as its own field
    NONE_DISCLOSED = "none_disclosed"  # reviewed the filings: no such cash-flow line exists


class LeaseAdjustment(BaseModel):
    """A company's reviewed lease treatment. Required whenever finance-lease principal is mapped.

    Lease-adjusted FCF subtracts finance-lease principal and other infrastructure financing
    payments. A component that is not disclosed is never assumed to be zero: the company must say,
    with evidence, that the review found no such payment.
    """

    model_config = ConfigDict(extra="forbid")

    other_infrastructure_financing_payments: OtherPaymentsTreatment
    note: str = Field(min_length=1)
