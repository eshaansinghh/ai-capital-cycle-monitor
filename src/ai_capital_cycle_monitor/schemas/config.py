"""Pydantic models for the YAML configuration files in config/."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai_capital_cycle_monitor.schemas.provenance import SourceType


class CompanyRole(StrEnum):
    HYPERSCALER = "hyperscaler"
    INFRASTRUCTURE = "infrastructure"
    NEOCLOUD = "neocloud"
    EUROPEAN_BANK = "european_bank"


class FilerType(StrEnum):
    """Determines which SEC forms and XBRL taxonomy a company's filings use."""

    DOMESTIC_10K = "domestic_10k"
    FOREIGN_PRIVATE_ISSUER_20F = "foreign_private_issuer_20f"
    NON_SEC = "non_sec"


class Company(BaseModel):
    """One member of the investable universe. Identifiers and calendars only, no financials."""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1)
    name: str = Field(min_length=1)
    role: CompanyRole
    exchange: str = Field(min_length=1)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    filer_type: FilerType
    cik: str | None = Field(default=None, pattern=r"^\d{10}$")
    cik_verified: bool = False
    fiscal_year_end_month: int = Field(ge=1, le=12)
    fiscal_calendar_note: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _cik_required_for_sec_filers(self) -> "Company":
        if self.filer_type is not FilerType.NON_SEC and self.cik is None:
            raise ValueError("cik is required for SEC filers")
        return self


class MetricDefinition(BaseModel):
    """A standardised financial metric: formula, inputs and behaviour when undefined."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(min_length=1)
    formula: str = Field(min_length=1)
    inputs: list[str] = Field(min_length=1)
    unit: str = Field(min_length=1)
    notes: str | None = None


class Confounder(BaseModel):
    """Other news inside an event window that could explain abnormal returns."""

    model_config = ConfigDict(extra="forbid")

    date: date
    description: str = Field(min_length=1)
    source_url: str = Field(min_length=1)


class EventStatus(StrEnum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    REJECTED = "rejected"


class EventDefinition(BaseModel):
    """A dated disclosure for the event-study module, with its confounder log."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    title: str = Field(min_length=1)
    first_public_timestamp_utc: datetime
    source_url: str = Field(min_length=1)
    source_type: SourceType
    exposed_tickers: list[str] = Field(min_length=1)
    benchmark_tickers: list[str] = Field(min_length=1)
    confounders: list[Confounder] = Field(default_factory=list)
    anticipated: bool | None = None
    status: EventStatus = EventStatus.CANDIDATE
    notes: str | None = None

    @field_validator("first_public_timestamp_utc")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("first_public_timestamp_utc must be timezone-aware (UTC)")
        return value
