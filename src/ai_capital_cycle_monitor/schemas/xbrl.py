"""Schemas for mapping canonical financial fields to XBRL tags, per company."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CanonicalField(StrEnum):
    REVENUE = "revenue"
    OPERATING_CASH_FLOW = "operating_cash_flow"
    CASH_CAPEX = "cash_capex"


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
