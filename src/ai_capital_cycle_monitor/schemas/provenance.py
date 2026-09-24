"""Provenance schema: one row of the source registry, mirroring the blueprint's required fields."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SourceType(StrEnum):
    """Source category, ordered roughly by the project's source-priority hierarchy."""

    SEC_FILING = "sec_filing"
    COMPANY_IR = "company_ir"
    OFFICIAL_STATISTICS = "official_statistics"
    REGULATOR = "regulator"
    PEER_REVIEWED = "peer_reviewed"
    NEWSWIRE = "newswire"
    INSTITUTIONAL_RESEARCH = "institutional_research"
    SPECIALIST_DATASET = "specialist_dataset"
    PRICE_AGGREGATOR = "price_aggregator"


class DataBasis(StrEnum):
    """How a value came to exist. Observed, guided, estimated, derived and modelled never mix."""

    REPORTED = "reported"
    COMPANY_GUIDED = "company_guided"
    CONSENSUS_ESTIMATED = "consensus_estimated"
    DERIVED = "derived"
    SCENARIO_MODELLED = "scenario_modelled"


class SourceRecord(BaseModel):
    """A series-to-source lineage entry. Field order is the CSV column order."""

    model_config = ConfigDict(extra="forbid")

    series_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    source_type: SourceType
    retrieved_at_utc: datetime | None = None
    observation_date: date | None = None
    period_start: date | None = None
    period_end: date | None = None
    filed_or_published_date: date | None = None
    fiscal_year: int | None = None
    fiscal_quarter: int | None = Field(default=None, ge=1, le=4)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    unit: str | None = None
    reported_or_estimated: DataBasis
    transformation: str | None = None
    notes: str | None = None

    @field_validator("retrieved_at_utc")
    @classmethod
    def _require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("retrieved_at_utc must be timezone-aware (UTC)")
        return value

    @model_validator(mode="after")
    def _period_is_ordered(self) -> "SourceRecord":
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start")
        return self
